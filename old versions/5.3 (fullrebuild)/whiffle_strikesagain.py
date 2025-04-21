# Whiffle Playfield - Updated with New Supabase Configuration (Corrected)
# Lines 1-700
import cv2
import numpy as np
import pygame
import sys
from pygame.locals import *
import time
import requests  # For HTTP requests to Supabase REST API

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
        self.hole_positions = []  # Will be populated during calibration
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
SUPABASE_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp0a2J1anVtcm9iZ2xmdHpva2NzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDIwMTM4NzcsImV4cCI6MjA1NzU4OTg3N30.OibLuqr3X922SUSBL8yGxDw8uwuTjivH97-2wNhJDqs"
LEADERBOARD_ENDPOINT = f"{SUPABASE_URL}/rest/v1/leaderboard"
CALIBRATION_ENDPOINT = f"{SUPABASE_URL}/rest/v1/calibration"

# Headers for Supabase API requests
headers = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# Calibration Mode
def calibrate_holes():
    print("Entering calibration mode. Click on each hole center, then press 'c' to confirm.")
    cap = cv2.VideoCapture(0)  # Use your camera
    calibrated_holes = []
    calibrating = True

    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            calibrated_holes.append((x, y, 20))  # Radius 20 as default
            print(f"Added hole at ({x}, {y})")

    cv2.namedWindow('Calibrate Holes')
    cv2.setMouseCallback('Calibrate Holes', mouse_callback)

    while calibrating:
        ret, frame = cap.read()
        if not ret:
            print("Failed to capture frame")
            break

        # Draw circles for already selected holes
        for (x, y, radius) in calibrated_holes:
            cv2.circle(frame, (x, y), radius, (0, 255, 0), 2)

        cv2.imshow('Calibrate Holes', frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('c'):
            calibrating = False

    cap.release()
    cv2.destroyAllWindows()
    return calibrated_holes

# Load calibrated holes from Supabase (if available)
def load_calibrated_holes():
    try:
        response = requests.get(CALIBRATION_ENDPOINT, headers=headers, params={"id": "eq.1"})
        if response.status_code == 200 and response.json():
            return response.json()[0]["holes"]
    except Exception as e:
        print(f"Error loading calibration: {e}")
    return calibrate_holes()  # Fallback to manual calibration

game.hole_positions = load_calibrated_holes()

# ROI and Ball Detection Functions
def get_table_roi(image):
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Canny edge detection
    edges = cv2.Canny(blurred, 50, 150)
    
    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Assume the largest contour is the table
    if contours:
        table_contour = max(contours, key=cv2.contourArea)
        # Create mask
        mask = np.zeros_like(gray)
        cv2.drawContours(mask, [table_contour], -1, 255, thickness=cv2.FILLED)
        
        # Apply mask to original image
        roi = cv2.bitwise_and(image, image, mask=mask)
        return roi, mask
    return image, None

def detect_ball_in_hole(image, hole_coords):
    # Convert to HSV for better white detection
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_white = np.array([0, 0, 200])  # Adjust thresholds for white
    upper_white = np.array([180, 30, 255])
    mask = cv2.inRange(hsv, lower_white, upper_white)

    # Check each hole
    for (x, y, radius) in hole_coords:
        # Extract region around hole
        roi = mask[y-radius:y+radius, x-radius:x+radius]
        white_pixels = cv2.countNonZero(roi)
        if white_pixels > 0.5 * (np.pi * radius * radius):  # Threshold for ball presence
            return (x, y)  # Return center of detected hole
    return None

# Video Capture Setup
cap = cv2.VideoCapture(0)  # Use your camera index
if not cap.isOpened():
    print("Error: Could not open video capture.")
    sys.exit()

# Game Loop Setup
font = pygame.font.Font(None, 36)
def draw_ui():
    screen.fill(BLACK)
    score_text = font.render(f"Balls: {game.balls}  Score: {game.score}  Time: {game.time}  Power-Up: {game.power_up or 'None'}", True, WHITE)
    screen.blit(score_text, (10, HEIGHT - 50))
    
    if game.show_leaderboard:
        leaderboard_surface = font.render("High Score Leaderboard (Onl)", True, WHITE)
        screen.blit(leaderboard_surface, (10, 10))
        # Placeholder for leaderboard data (to be updated later)

# Main Game Loop
running = True
frame_count = 0
while running and game.running:
    # Event Handling
    for event in pygame.event.get():
        if event.type == QUIT:
            running = False
        elif event.type == KEYDOWN:
            if event.key == K_ESCAPE:
                running = False
            elif event.key == K_l:
                game.show_leaderboard = not game.show_leaderboard

    # Capture Frame
    ret, frame = cap.read()
    if not ret:
        print("Failed to capture frame")
        break

    # Apply ROI and Detect Ball
    roi, mask = get_table_roi(frame)
    if roi is not None:
        ball_position = detect_ball_in_hole(roi, game.hole_positions)
        if ball_position:
            game.score += 10  # Example scoring (adjust based on hole value)
            print(f"Ball scored at {ball_position}")
            cv2.circle(roi, ball_position, 20, (0, 255, 0), 2)  # Visualize

    # Convert frame for Pygame display
    frame_rgb = cv2.cvtColor(roi if roi is not None else frame, cv2.COLOR_BGR2RGB)
    frame_pygame = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))  # Fixed line
    frame_pygame = pygame.transform.scale(frame_pygame, (WIDTH, HEIGHT))
    screen.blit(frame_pygame, (0, 0))

    # Draw UI
    draw_ui()

    # Update Display
    pygame.display.flip()
    clock.tick(30)  # 30 FPS

    frame_count += 1
    if frame_count % 30 == 0:  # Update time every second
        game.time = time.strftime("%H:%M:%S")

# Cleanup (to be continued in the next part)
cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()

# Whiffle Playfield - Remaining Code (Lines 701+)

# Leaderboard Display Function
def draw_leaderboard():
    if game.show_leaderboard:
        # Fetch leaderboard data from Supabase REST API
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
        leaderboard_surface.fill((50, 50, 50))  # Dark gray background
        leaderboard_surface.set_alpha(200)  # Semi-transparent

        # Title
        title_text = font.render("High Score Leaderboard (Onl)", True, WHITE)
        leaderboard_surface.blit(title_text, (10, 10))

        # Display entries with date
        for i, entry in enumerate(leaderboard_data):
            name = entry['name']
            score = entry['score']
            date = entry['date'].split('T')[0]  # Format date (e.g., YYYY-MM-DD)
            entry_text = font.render(f"{i+1}. {name}: {score} ({date})", True, WHITE)
            leaderboard_surface.blit(entry_text, (10, 50 + i * 30))

        # Close button
        close_button = font.render("Close", True, WHITE)
        close_rect = close_button.get_rect(topleft=(10, 50 + 5 * 30))
        pygame.draw.rect(leaderboard_surface, (100, 100, 100), close_rect.inflate(20, 10))
        leaderboard_surface.blit(close_button, close_rect)

        screen.blit(leaderboard_surface, (10, 10))
        return close_rect
    return None

# Save Zones Button (Saves calibration data to Supabase)
def draw_save_zones_button():
    save_button = font.render("Save Zones", True, WHITE)
    save_rect = save_button.get_rect(center=(WIDTH // 2, HEIGHT - 20))
    pygame.draw.rect(screen, (100, 100, 100), save_rect.inflate(20, 10))
    screen.blit(save_button, save_rect)
    return save_rect

# Update UI Drawing to Include Leaderboard
def draw_ui():
    screen.fill(BLACK)
    score_text = font.render(f"Balls: {game.balls}  Score: {game.score}  Time: {game.time}  Power-Up: {game.power_up or 'None'}", True, WHITE)
    screen.blit(score_text, (10, HEIGHT - 50))
    
    close_rect = draw_leaderboard()
    save_rect = draw_save_zones_button()

    return close_rect, save_rect

# Resume Game Loop from First 700 Lines
running = True
frame_count = 0
# Map hole positions to scores based on your playfield (adjust as needed)
hole_scores = {
    game.hole_positions[i][:2]: score for i, score in enumerate([300, 100, 50, 30, 20, 10, 60])  # Example mapping
}

while running and game.running:
    # Event Handling
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
            close_rect, save_rect = draw_ui()  # Get rects for clicking
            if close_rect and close_rect.collidepoint(mouse_pos):
                game.show_leaderboard = False
            if save_rect and save_rect.collidepoint(mouse_pos):
                # Save hole positions to Supabase
                print("Saving zones to Supabase...")
                try:
                    requests.patch(
                        CALIBRATION_ENDPOINT,
                        headers=headers,
                        json={"id": 1, "holes": game.hole_positions},
                        params={"id": "eq.1"}
                    )
                except Exception as e:
                    print(f"Error saving calibration: {e}")

    # Capture Frame
    ret, frame = cap.read()
    if not ret:
        print("Failed to capture frame")
        break

    # Apply ROI and Detect Ball
    roi, mask = get_table_roi(frame)
    if roi is not None:
        ball_position = detect_ball_in_hole(roi, game.hole_positions)
        if ball_position:
            # Score based on hole position
            if ball_position in hole_scores:
                game.score += hole_scores[ball_position]
                game.balls -= 1
                print(f"Ball scored at {ball_position}, Score: {game.score}")
                cv2.circle(roi, ball_position, 20, (0, 255, 0), 2)  # Visualize

    # Convert frame for Pygame display
    frame_rgb = cv2.cvtColor(roi if roi is not None else frame, cv2.COLOR_BGR2RGB)
    frame_pygame = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))  # Fixed line
    frame_pygame = pygame.transform.scale(frame_pygame, (WIDTH, HEIGHT))
    screen.blit(frame_pygame, (0, 0))

    # Draw UI
    close_rect, save_rect = draw_ui()

    # Update Display
    pygame.display.flip()
    clock.tick(30)  # 30 FPS

    frame_count += 1
    if frame_count % 30 == 0:  # Update time every second
        game.time = time.strftime("%H:%M:%S")

    # Game Over Check
    if game.balls <= 0:
        # Save score to Supabase via REST API
        try:
            requests.post(
                LEADERBOARD_ENDPOINT,
                headers=headers,
                json={
                    "name": "BMW",  # Replace with player name input
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

# End of Whiffle Code