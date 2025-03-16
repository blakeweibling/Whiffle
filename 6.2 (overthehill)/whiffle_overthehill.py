# Whiffle Playfield - Fixed NameError for CONFIRMATION_FRAMES
# Lines 1-700
import cv2
import numpy as np
import pygame
import sys
from pygame.locals import *
import time
import json
import os
import requests

# Initialize Pygame
pygame.init()
pygame.mixer.init()  # Initialize the mixer for sound
WIDTH, HEIGHT = 1280, 720  # Match your screenshot resolution
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Whiffle Playfield")
clock = pygame.time.Clock()

# Constants
COOLDOWN_FRAMES = 30  # Number of frames to wait before allowing another detection in the same hole
CONFIRMATION_FRAMES = 10  # Increased from 5 to 10 frames for better stability

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)  # For debug overlay
YELLOW = (255, 255, 0)  # For confirming detection

# Load sound effect for scoring (you'll need to provide a sound file)
try:
    score_sound = pygame.mixer.Sound("score.wav")  # Replace with your sound file path
except FileNotFoundError:
    print("Score sound file 'score.wav' not found. Sound effects disabled. Place a 'score.wav' file in the same directory to enable.")
    score_sound = None

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
        self.scored_balls = set()  # Track scored ball positions to prevent double-counting
        self.detection_cooldown = {}  # Track cooldown for each hole to debounce detections
        self.detected_positions = []  # Track currently detected balls for visual feedback
        self.confirming_balls = {}  # Track balls being confirmed (ball_id: {position: (x, y), frames: int, hole_pos: (x, y)})

    def reset(self):
        self.score = 0
        self.balls = 7
        self.power_up = None
        self.time = "N/A"
        self.scored_balls.clear()
        self.detection_cooldown.clear()
        self.detected_positions.clear()
        self.confirming_balls.clear()
        print("Game reset: Score = 0, Balls = 7")

    def get_nearest_hole(self, pos):
        """Return the nearest hole and its points based on position."""
        min_dist = float('inf')
        nearest_hole = None
        for (x, y, radius, points) in self.hole_positions:
            dist = np.hypot(pos[0] - x, pos[1] - y)
            if dist < min_dist and dist <= radius:
                min_dist = dist
                nearest_hole = (x, y, points)
        return nearest_hole

game = GameState()

# Calibration File Path
CALIBRATION_FILE = "calibration.json"

# Video Capture Reinitialization Function
def reinitialize_camera():
    global cap
    backends = [cv2.CAP_MSMF, cv2.CAP_VFW, cv2.CAP_DSHOW, cv2.CAP_FFMPEG, cv2.CAP_ANY]
    indices = [0, 1]
    for backend in backends:
        for index in indices:
            print(f"Trying to initialize camera with backend {backend} and index {index}...")
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
                time.sleep(0.2)
                ret, frame = cap.read()
                if ret and frame is not None and frame.size != 0 and frame.shape == (HEIGHT, WIDTH, 3):
                    print(f"Successfully initialized camera with backend {backend} and index {index}. Frame shape: {frame.shape}, Mean pixel value: {frame.mean()}")
                    return True
                else:
                    print(f"Camera opened but failed to capture valid frame with backend {backend} and index {index}. Ret: {ret}, Frame: {frame}")
                    cap.release()
    print("Error: Could not open video capture with any backend or index.")
    return False

# Initial Video Capture Setup
if not reinitialize_camera():
    sys.exit()

# Load or Skip Calibration
def load_calibrated_holes():
    if os.path.exists(CALIBRATION_FILE):
        with open(CALIBRATION_FILE, 'r') as f:
            try:
                data = json.load(f)
                print("Loaded calibration data from local file.")
                return data["holes"]
            except Exception as e:
                print(f"Error loading calibration file: {e}")
    print("No calibration file found or error loading. Entering calibration mode.")
    return calibrate_holes()

def save_calibrated_holes(holes):
    with open(CALIBRATION_FILE, 'w') as f:
        json.dump({"holes": holes}, f)
        print("Calibration data saved to local file.")

# Calibration Mode with On-Canvas Point Input
def calibrate_holes():
    global cap
    calibrated_holes = []
    calibrating = True
    input_active = False
    current_input = ""
    current_pos = None
    retry_count = 0
    max_retries = 10

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
            print(f"Failed to capture frame during calibration. Retrying... (Attempt {retry_count + 1}/{max_retries})")
            retry_count += 1
            if retry_count >= max_retries:
                print("Max retries reached. Exiting calibration.")
                break
            time.sleep(0.1)
            continue

        retry_count = 0
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
        save_calibrated_holes(calibrated_holes)

    cv2.destroyAllWindows()
    print("Reinitializing camera after calibration to ensure playfield feed...")
    if not reinitialize_camera():
        print("Failed to reinitialize camera after calibration. Exiting...")
        sys.exit()
    return calibrated_holes

game.hole_positions = load_calibrated_holes()

# Force reinitialization before game loop
print("Forcing camera reinitialization before entering game loop...")
if not reinitialize_camera():
    print("Failed to reinitialize camera before game loop. Exiting...")
    sys.exit()

# Ball Detection Function
def detect_ball_in_hole(image, hole_coords, game_state, frame_count):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_white = np.array([0, 0, 150])  # Lowered value threshold from 200 to 150
    upper_white = np.array([180, 70, 255])  # Increased saturation threshold to 70
    mask = cv2.inRange(hsv, lower_white, upper_white)

    ball_positions = []
    points_list = []

    # Detect all white regions (potential balls)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Track current frame's detected balls
    detected_balls = set()
    for contour in contours:
        area = cv2.contourArea(contour)
        if 0.1 * np.pi * 20 * 20 < area < np.pi * 20 * 20:  # Reasonable ball size
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            if len(approx) > 4:
                # Generate a unique ID for the ball based on the contour
                ball_id = hash(str(contour))

                # Get the centroid of the contour as the ball's position
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    ball_x = int(M["m10"] / M["m00"])
                    ball_y = int(M["m01"] / M["m00"])
                    ball_pos = (ball_x, ball_y)

                    # Assign the ball to the nearest hole
                    nearest_hole = game_state.get_nearest_hole(ball_pos)
                    if nearest_hole:
                        hole_x, hole_y, points = nearest_hole
                        hole_pos = (hole_x, hole_y)

                        # Check if this ball is already being confirmed
                        if ball_id in game_state.confirming_balls:
                            current_data = game_state.confirming_balls[ball_id]
                            current_pos = current_data["position"]
                            frames = current_data["frames"]

                            # Check if the ball has moved significantly
                            dist = np.hypot(ball_x - current_pos[0], ball_y - current_pos[1])
                            if dist < 10:  # Allow small movement (e.g., 10 pixels)
                                game_state.confirming_balls[ball_id]["frames"] += 1
                                game_state.confirming_balls[ball_id]["position"] = (ball_x, ball_y)
                                game_state.confirming_balls[ball_id]["hole_pos"] = hole_pos
                                if frames + 1 >= CONFIRMATION_FRAMES and hole_pos not in game_state.scored_balls:
                                    ball_positions.append(hole_pos)
                                    points_list.append(points)
                                    game_state.scored_balls.add(hole_pos)
                                    game_state.detection_cooldown[hole_pos] = frame_count
                                    print(f"Ball confirmed and scored at {hole_pos}, Points: {points}")
                                    del game_state.confirming_balls[ball_id]
                            else:
                                # Reset confirmation if movement is too large
                                game_state.confirming_balls[ball_id] = {
                                    "position": (ball_x, ball_y),
                                    "frames": 1,
                                    "hole_pos": hole_pos
                                }
                        else:
                            game_state.confirming_balls[ball_id] = {
                                "position": (ball_x, ball_y),
                                "frames": 1,
                                "hole_pos": hole_pos
                            }

                        # Update detected positions for visual feedback
                        if hole_pos not in game_state.detected_positions:
                            game_state.detected_positions.append(hole_pos)

                        # Mark this ball as detected in this frame
                        detected_balls.add(ball_id)
                    else:
                        # Remove from confirming_balls if no longer near a hole
                        if ball_id in game_state.confirming_balls:
                            hole_pos = game_state.confirming_balls[ball_id]["hole_pos"]
                            del game_state.confirming_balls[ball_id]
                            if hole_pos in game_state.detected_positions:
                                game_state.detected_positions.remove(hole_pos)
                else:
                    # Remove from confirming_balls if no valid centroid
                    if ball_id in game_state.confirming_balls:
                        hole_pos = game_state.confirming_balls[ball_id]["hole_pos"]
                        del game_state.confirming_balls[ball_id]
                        if hole_pos in game_state.detected_positions:
                            game_state.detected_positions.remove(hole_pos)

    # Clean up confirming_balls for balls no longer detected
    for ball_id in list(game_state.confirming_balls.keys()):
        if ball_id not in detected_balls:
            hole_pos = game_state.confirming_balls[ball_id]["hole_pos"]
            del game_state.confirming_balls[ball_id]
            if hole_pos in game_state.detected_positions:
                game_state.detected_positions.remove(hole_pos)

    return ball_positions, points_list

# Game Loop Setup
font = pygame.font.Font(None, 36)
def draw_ui():
    score_text = font.render(f"Balls: {game.balls}  Score: {game.score}  Time: {game.time}  Power-Up: {game.power_up or 'None'}", True, WHITE)
    screen.blit(score_text, (10, HEIGHT - 50))
    if game.show_leaderboard:
        leaderboard_surface = font.render("High Score Leaderboard (Onl)", True, WHITE)
        screen.blit(leaderboard_surface, (10, 10))
    # Debug overlay
    pygame.draw.rect(screen, BLUE, (10, 10, 100, 50))  # Blue rectangle for debug

# Main Game Loop
running = True
frame_count = 0
retry_count = 0
max_retries = 10
while running and game.running:
    if not cap.isOpened():
        print("Camera is not open. Reinitializing...")
        if not reinitialize_camera():
            print("Failed to reinitialize camera. Exiting...")
            break
        retry_count = 0

    ret, frame = cap.read()
    if not ret:
        print(f"Failed to capture frame in game loop. Retrying... (Attempt {retry_count + 1}/{max_retries})")
        retry_count += 1
        if retry_count >= max_retries:
            print("Max retries reached for frame capture. Reinitializing camera...")
            if not reinitialize_camera():
                print("Failed to reinitialize camera after max retries. Exiting...")
                break
            retry_count = 0
        time.sleep(0.1)
        continue

    retry_count = 0
    # Validate frame
    if frame is None or frame.size == 0 or frame.shape != (HEIGHT, WIDTH, 3) or frame.mean() < 1:
        print(f"Invalid frame captured: Frame: {frame}, Shape: {frame.shape if frame is not None else 'None'}, Mean: {frame.mean() if frame is not None else 'N/A'}")
        if frame is not None:
            cv2.imwrite("debug_frame.jpg", frame)
            print("Saved invalid frame to debug_frame.jpg for inspection.")
        frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    else:
        if frame_count % 30 == 0:
            print(f"Successfully captured frame. Shape: {frame.shape}, Mean pixel value: {frame.mean()}")

    # Use raw frame directly
    roi = frame
    # Overlay calibrated hole positions and points
    for (x, y, radius, points) in game.hole_positions:
        cv2.circle(roi, (x, y), radius, (0, 255, 0), 2)
        cv2.putText(roi, str(points), (x - 20, y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # Draw circles for detected balls: yellow while confirming, red once scored
    for pos in game.detected_positions:
        if any(pos == game.confirming_balls[ball_id]["hole_pos"] for ball_id in game.confirming_balls
               if game.confirming_balls[ball_id]["frames"] < CONFIRMATION_FRAMES):
            cv2.circle(roi, pos, 20, YELLOW, 2)  # Yellow while confirming
        else:
            cv2.circle(roi, pos, 20, RED, 2)  # Red once confirmed/scored

    # Detect balls and update score
    ball_positions, points_list = detect_ball_in_hole(roi, game.hole_positions, game, frame_count)
    for pos, points in zip(ball_positions, points_list):
        game.score += points
        game.balls -= 1
        print(f"Ball scored at {pos}, Points: {points}, Score: {game.score}, Balls remaining: {game.balls}")
        # Play sound effect if available
        if score_sound:
            score_sound.play()

    # Convert frame for Pygame display
    frame_to_display = roi
    if frame_to_display is None or frame_to_display.size == 0:
        print(f"Warning: Frame to display is None or invalid. Shape: {frame_to_display.shape if frame_to_display is not None else 'None'}, Mean: {frame_to_display.mean() if frame_to_display is not None else 'N/A'}")
        frame_to_display = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)

    # Clear screen before blitting new frame
    screen.fill(BLACK)

    frame_rgb = cv2.cvtColor(frame_to_display, cv2.COLOR_BGR2RGB)
    pygame_surface = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
    scaled_surface = pygame.transform.scale(pygame_surface, (WIDTH, HEIGHT))
    screen.blit(scaled_surface, (0, 0))

    # Draw UI after blitting frame
    draw_ui()

    # Force display update
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
            elif event.key == K_r:  # Manual reset with 'R' key
                game.reset()
            elif event.key == K_c:  # Recalibration with 'C' key
                game.hole_positions = calibrate_holes()

    # Reset game if balls run out
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

# Cleanup (to be continued)
cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()

# Whiffle Playfield - Remaining Code (Lines 701+)

# Supabase Configuration for Online Leaderboard
SUPABASE_URL = "https://jtkbujumrobglftzokcs.supabase.co"
SUPABASE_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp0a2J1anVtcm9iZ2xmdHpva2NzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDIwMTM8NzcsImV4cCI6MjA1NzU4OTg3N30.OibLuqr3X922SUSBL8yGxDw8uwuTjivH97-2wNhJDqs"
LEADERBOARD_ENDPOINT = f"{SUPABASE_URL}/rest/v1/leaderboard"

# Headers for Supabase API requests
headers = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# Leaderboard Display Function
def draw_leaderboard():
    if game.show_leaderboard:
        try:
            response = requests.get(
                LEADERBOARD_ENDPOINT,
                headers=headers,
                params={"select": "name,score,date", "order": "score.desc", "limit": "5"}
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

# Save Zones Button (Now a Recalibrate button)
def draw_save_zones_button():
    save_button = font.render("Recalibrate", True, WHITE)
    save_rect = save_button.get_rect(center=(WIDTH // 2, HEIGHT - 20))
    pygame.draw.rect(screen, (100, 100, 100), save_rect.inflate(20, 10))
    screen.blit(save_button, save_rect)
    return save_rect

# Update UI Drawing
def draw_ui():
    score_text = font.render(f"Balls: {game.balls}  Score: {game.score}  Time: {game.time}  Power-Up: {game.power_up or 'None'}", True, WHITE)
    screen.blit(score_text, (10, HEIGHT - 50))
    if game.show_leaderboard:
        leaderboard_surface = font.render("High Score Leaderboard (Onl)", True, WHITE)
        screen.blit(leaderboard_surface, (10, 10))
    # Debug overlay
    pygame.draw.rect(screen, BLUE, (10, 10, 100, 50))  # Blue rectangle for debug

# Resume Game Loop (already included above, repeated for clarity)
running = True
frame_count = 0
while running and game.running:
    if not cap.isOpened():
        print("Camera is not open. Reinitializing...")
        if not reinitialize_camera():
            print("Failed to reinitialize camera. Exiting...")
            break
        retry_count = 0

    ret, frame = cap.read()
    if not ret:
        print(f"Failed to capture frame in game loop. Retrying... (Attempt {retry_count + 1}/{max_retries})")
        retry_count += 1
        if retry_count >= max_retries:
            print("Max retries reached for frame capture. Reinitializing camera...")
            if not reinitialize_camera():
                print("Failed to reinitialize camera after max retries. Exiting...")
                break
            retry_count = 0
        time.sleep(0.1)
        continue

    retry_count = 0
    # Use raw frame directly
    roi = frame
    for (x, y, radius, points) in game.hole_positions:
        cv2.circle(roi, (x, y), radius, (0, 255, 0), 2)
        cv2.putText(roi, str(points), (x - 20, y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    ball_positions, points_list = detect_ball_in_hole(roi, game.hole_positions, game, frame_count)
    for pos, points in zip(ball_positions, points_list):
        game.score += points
        game.balls -= 1
        print(f"Ball scored at {pos}, Points: {points}, Score: {game.score}, Balls remaining: {game.balls}")
        # Play sound effect if available
        if score_sound:
            score_sound.play()

    frame_to_display = roi if roi is not None else frame
    if frame_to_display is None or frame_to_display.size == 0:
        print("Warning: Frame to display is None or invalid, using black screen as fallback.")
        frame_to_display = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    frame_rgb = cv2.cvtColor(frame_to_display, cv2.COLOR_BGR2RGB)
    frame_pygame = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
    frame_pygame = pygame.transform.scale(frame_pygame, (WIDTH, HEIGHT))
    screen.blit(frame_pygame, (0, 0))

    close_rect = draw_leaderboard()
    save_rect = draw_save_zones_button()
    draw_ui()
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
            elif event.key == K_r:  # Manual reset with 'R' key
                game.reset()
            elif event.key == K_c:  # Recalibration with 'C' key
                game.hole_positions = calibrate_holes()

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