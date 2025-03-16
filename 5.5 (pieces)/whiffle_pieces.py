# Whiffle Playfield - Updated with Video Capture Reinitialization
# Lines 1-700
import cv2
import numpy as np
import pygame
import sys
from pygame.locals import *
import time
import requests

# Initialize Pygame
pygame.init()
WIDTH, HEIGHT = 1280, 720  # Match your screenshot resolution
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Whiffle Playfield")
clock = pygame.time.Clock()

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)

# Game State
class GameState:
    def __init__(self):
        self.score = 0
        self.balls = 7
        self.power_up = None
        self.time = "N/A"
        self.hole_positions = []  # Will store (x, y, radius, points)
        self.running = True
        self.show_leaderboard = False

    def reset(self):
        self.score = 0
        self.balls = 7
        self.power_up = None
        self.time = "N/A"

game = GameState()

# Supabase Configuration for Online Leaderboard
SUPABASE_URL = "https://jtkbujumrobglftzokcs.supabase.co"
SUPABASE_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp0a2J1anVtcm9iZ2xmdHpva2NzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDIwMTM8NzcsImV4cCI6MjA1NzU4OTg3N30.OibLuqr3X922SUSBL8yGxDw8uwuTjivH97-2wNhJDqs"
LEADERBOARD_ENDPOINT = f"{SUPABASE_URL}/rest/v1/leaderboard"
CALIBRATION_ENDPOINT = f"{SUPABASE_URL}/rest/v1/calibration"

# Headers for Supabase API requests
headers = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# Video Capture Setup (Global initialization)
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Could not open video capture initially.")
    sys.exit()

# Calibration Mode with On-Canvas Point Input
def calibrate_holes():
    print("Entering calibration mode. Click on each hole center, type points, press Enter to confirm, then press 'c' to finish.")
    global cap
    calibrated_holes = []
    calibrating = True
    input_active = False
    current_input = ""
    current_pos = None

    cv2.namedWindow('Calibrate Holes', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Calibrate Holes', 1280, 720)

    def mouse_callback(event, x, y, flags, param):
        nonlocal input_active, current_pos
        if event == cv2.EVENT_LBUTTONDOWN and not input_active:
            input_active = True
            current_pos = (x, y)
            print(f"Selected hole at ({x}, {y}). Type point value and press Enter.")

    cv2.setMouseCallback('Calibrate Holes', mouse_callback)

    while calibrating:
        ret, frame = cap.read()
        if not ret:
            print("Failed to capture frame during calibration. Retrying...")
            continue

        for (x, y, radius, points) in calibrated_holes:
            cv2.circle(frame, (x, y), radius, (0, 255, 0), 2)
            cv2.putText(frame, str(points), (x - 20, y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        if input_active and current_pos:
            x, y = current_pos
            cv2.rectangle(frame, (x, y + 10), (x + 100, y + 40), (255, 255, 255), -1)
            cv2.putText(frame, current_input, (x + 5, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
            cv2.circle(frame, (x, y), 20, (0, 255, 0), 2)

        cv2.imshow('Calibrate Holes', frame)
        key = cv2.waitKey(1) & 0xFF

        if cv2.getWindowProperty('Calibrate Holes', cv2.WND_PROP_VISIBLE) < 1:
            calibrating = False
            break

        if key == ord('c') and not input_active:
            calibrating = False

        if input_active:
            if key == 13:  # Enter key
                try:
                    points = int(current_input) if current_input else 10
                except ValueError:
                    print("Invalid input, defaulting to 10 points.")
                    points = 10
                calibrated_holes.append((current_pos[0], current_pos[1], 20, points))
                print(f"Added hole at {current_pos} with {points} points")
                input_active = False
                current_input = ""
                current_pos = None
            elif key == 8:  # Backspace
                current_input = current_input[:-1]
            elif key in range(48, 58):  # Numbers 0-9
                current_input += chr(key)

    if calibrated_holes:
        try:
            requests.patch(
                CALIBRATION_ENDPOINT,
                headers=headers,
                json={"id": 1, "holes": calibrated_holes},
                params={"id": "eq.1"}
            )
            print("Calibration data saved to Supabase.")
        except Exception as e:
            print(f"Error saving calibration: {e}")

    cv2.destroyAllWindows()  # Close the calibration window but don't release cap
    # Reinitialize video capture if it fails after calibration
    if not cap.isOpened():
        print("Reinitializing video capture after calibration...")
        cap.release()  # Ensure any stale state is cleared
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not reinitialize video capture.")
            sys.exit()
    return calibrated_holes

def load_calibrated_holes():
    try:
        response = requests.get(CALIBRATION_ENDPOINT, headers=headers, params={"id": "eq.1"})
        if response.status_code == 200 and response.json():
            return response.json()[0]["holes"]
    except Exception as e:
        print(f"Error loading calibration: {e}")
    return calibrate_holes()

game.hole_positions = load_calibrated_holes()

# ROI and Ball Detection Functions
def get_table_roi(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        table_contour = max(contours, key=cv2.contourArea)
        mask = np.zeros_like(gray)
        cv2.drawContours(mask, [table_contour], -1, 255, thickness=cv2.FILLED)
        roi = cv2.bitwise_and(image, image, mask=mask)
        return roi, mask
    return image, None

def detect_ball_in_hole(image, hole_coords):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_white = np.array([0, 0, 200])
    upper_white = np.array([180, 30, 255])
    mask = cv2.inRange(hsv, lower_white, upper_white)
    for (x, y, radius, points) in hole_coords:
        roi = mask[y-radius:y+radius, x-radius:x+radius]
        white_pixels = cv2.countNonZero(roi)
        if white_pixels > 0.5 * (np.pi * radius * radius):
            return (x, y), points
    return None, None

# Game Loop Setup
font = pygame.font.Font(None, 36)
def draw_ui():
    screen.fill(BLACK)
    score_text = font.render(f"Balls: {game.balls}  Score: {game.score}  Time: {game.time}  Power-Up: {game.power_up or 'None'}", True, WHITE)
    screen.blit(score_text, (10, HEIGHT - 50))
    if game.show_leaderboard:
        leaderboard_surface = font.render("High Score Leaderboard (Onl)", True, WHITE)
        screen.blit(leaderboard_surface, (10, 10))

# Main Game Loop
running = True
frame_count = 0
while running and game.running:
    ret, frame = cap.read()
    if not ret:
        print("Failed to capture frame in game loop. Reinitializing...")
        cap.release()
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not reinitialize video capture.")
            break
        continue

    # Apply ROI
    roi, mask = get_table_roi(frame)
    if roi is not None:
        # Overlay calibrated hole positions and points
        for (x, y, radius, points) in game.hole_positions:
            cv2.circle(roi, (x, y), radius, (0, 255, 0), 2)
            cv2.putText(roi, str(points), (x - 20, y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Detect ball and update score
        ball_position, points = detect_ball_in_hole(roi, game.hole_positions)
        if ball_position and points:
            game.score += points
            game.balls -= 1
            print(f"Ball scored at {ball_position}, Points: {points}, Score: {game.score}")
            cv2.circle(roi, ball_position, 20, (0, 0, 255), 2)  # Red circle for detected ball

    # Convert frame for Pygame display
    frame_to_display = roi if roi is not None else frame
    frame_rgb = cv2.cvtColor(frame_to_display, cv2.COLOR_BGR2RGB)
    frame_pygame = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
    frame_pygame = pygame.transform.scale(frame_pygame, (WIDTH, HEIGHT))
    screen.blit(frame_pygame, (0, 0))

    # Draw UI
    draw_ui()

    # Update Display
    pygame.display.flip()
    clock.tick(30)

    frame_count += 1
    if frame_count % 30 == 0:
        game.time = time.strftime("%H:%M:%S")

    for event in pygame.event.get():
        if event.type == QUIT:
            running = False
        elif event.type == KEYDOWN:
            if event.key == K_ESCAPE:
                running = False
            elif event.key == K_l:
                game.show_leaderboard = not game.show_leaderboard

# Cleanup (to be continued)
cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()

# Whiffle Playfield - Remaining Code (Lines 701+)

# Leaderboard Display Function
def draw_leaderboard():
    if game.show_leaderboard:
        try:
            response = requests.get(
                LEADERBOARD_ENDPOINT,
                headers=headers,
                params={"select": "name,score,date", "order": "score.desc", "limit": 5}
            )
            leaderboard_data = response.json() if response.status_code == 200 else []
        except Exception as e:
            print(f"Error fetching leaderboard: {e}")
            leaderboard_data = []

        leaderboard_surface = pygame.Surface((300, 400))
        leaderboard_surface.fill((50, 50, 50))
        leaderboard_surface.set_alpha(200)

        title_text = font.render("High Score Leaderboard (Onl)", True, WHITE)
        leaderboard_surface.blit(title_text, (10, 10))

        for i, entry in enumerate(leaderboard_data):
            name = entry['name']
            score = entry['score']
            date = entry['date'].split('T')[0]
            entry_text = font.render(f"{i+1}. {name}: {score} ({date})", True, WHITE)
            leaderboard_surface.blit(entry_text, (10, 50 + i * 30))

        close_button = font.render("Close", True, WHITE)
        close_rect = close_button.get_rect(topleft=(10, 50 + 5 * 30))
        pygame.draw.rect(leaderboard_surface, (100, 100, 100), close_rect.inflate(20, 10))
        leaderboard_surface.blit(close_button, close_rect)

        screen.blit(leaderboard_surface, (10, 10))
        return close_rect
    return None

# Save Zones Button
def draw_save_zones_button():
    save_button = font.render("Save Zones", True, WHITE)
    save_rect = save_button.get_rect(center=(WIDTH // 2, HEIGHT - 20))
    pygame.draw.rect(screen, (100, 100, 100), save_rect.inflate(20, 10))
    screen.blit(save_button, save_rect)
    return save_rect

# Update UI Drawing
def draw_ui():
    screen.fill(BLACK)
    score_text = font.render(f"Balls: {game.balls}  Score: {game.score}  Time: {game.time}  Power-Up: {game.power_up or 'None'}", True, WHITE)
    screen.blit(score_text, (10, HEIGHT - 50))
    
    close_rect = draw_leaderboard()
    save_rect = draw_save_zones_button()
    return close_rect, save_rect

# Resume Game Loop
running = True
frame_count = 0
while running and game.running:
    ret, frame = cap.read()
    if not ret:
        print("Failed to capture frame in game loop. Reinitializing...")
        cap.release()
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not reinitialize video capture.")
            break
        continue

    roi, mask = get_table_roi(frame)
    if roi is not None:
        for (x, y, radius, points) in game.hole_positions:
            cv2.circle(roi, (x, y), radius, (0, 255, 0), 2)
            cv2.putText(roi, str(points), (x - 20, y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        ball_position, points = detect_ball_in_hole(roi, game.hole_positions)
        if ball_position and points:
            game.score += points
            game.balls -= 1
            print(f"Ball scored at {ball_position}, Points: {points}, Score: {game.score}")
            cv2.circle(roi, ball_position, 20, (0, 0, 255), 2)

    frame_to_display = roi if roi is not None else frame
    frame_rgb = cv2.cvtColor(frame_to_display, cv2.COLOR_BGR2RGB)
    frame_pygame = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
    frame_pygame = pygame.transform.scale(frame_pygame, (WIDTH, HEIGHT))
    screen.blit(frame_pygame, (0, 0))

    close_rect, save_rect = draw_ui()
    pygame.display.flip()
    clock.tick(30)

    frame_count += 1
    if frame_count % 30 == 0:
        game.time = time.strftime("%H:%M:%S")

    for event in pygame.event.get():
        if event.type == QUIT:
            running = False
        elif event.type == KEYDOWN:
            if event.key == K_ESCAPE:
                running = False
            elif event.key == K_l:
                game.show_leaderboard = not game.show_leaderboard
        elif event.type == MOUSEBUTTONDOWN:
            mouse_pos = event.pos
            close_rect, save_rect = draw_ui()
            if close_rect and close_rect.collidepoint(mouse_pos):
                game.show_leaderboard = False
            if save_rect and save_rect.collidepoint(mouse_pos):
                try:
                    requests.patch(
                        CALIBRATION_ENDPOINT,
                        headers=headers,
                        json={"id": 1, "holes": game.hole_positions},
                        params={"id": "eq.1"}
                    )
                    print("Calibration data saved to Supabase.")
                except Exception as e:
                    print(f"Error saving calibration: {e}")

    if game.balls <= 0:
        try:
            requests.post(
                LEADERBOARD_ENDPOINT,
                headers=headers,
                json={
                    "name": "BMW",
                    "score": game.score,
                    "date": time.strftime("%Y-%m-%dT%H:%M:%S")
                }
            )
        except Exception as e:
            print(f"Error saving score: {e}")
        game.reset()

# Cleanup
cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()