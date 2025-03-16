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
pygame.mixer.init()
WIDTH, HEIGHT = 1280, 720
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Whiffle Playfield")
clock = pygame.time.Clock()

# Constants
COOLDOWN_FRAMES = 30
CONFIRMATION_FRAMES = 10
SOUND_COOLDOWN = 1.0  # Seconds to wait before playing score sound again

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)

# Load sound effect
try:
    score_sound = pygame.mixer.Sound("score.wav")
except FileNotFoundError:
    print("Score sound file 'score.wav' not found. Sound effects disabled.")
    score_sound = None

# Game State
class GameState:
    def __init__(self):
        self.score = 0
        self.balls = 7
        self.power_up = None
        self.time = "N/A"
        self.hole_positions = []
        self.running = True
        self.show_leaderboard = False
        self.scored_balls = set()
        self.detection_cooldown = {}
        self.detected_positions = []
        self.confirming_balls = {}
        self.just_reset = False
        self.last_sound_time = 0

    def reset(self):
        self.score = 0
        self.balls = 7
        self.power_up = None
        self.time = "N/A"
        self.scored_balls.clear()
        self.detection_cooldown.clear()
        self.detected_positions.clear()
        self.confirming_balls.clear()
        self.just_reset = True
        print("Game reset: Score = 0, Balls = 7")

    def get_nearest_hole(self, pos):
        min_dist = float('inf')
        nearest_hole = None
        for (x, y, radius, points) in self.hole_positions:
            dist = np.hypot(pos[0] - x, pos[1] - y)
            if dist < min_dist and dist <= radius:
                min_dist = dist
                nearest_hole = (x, y, points)
        return nearest_hole

game = GameState()

# Calibration File
CALIBRATION_FILE = "calibration.json"

# Video Capture Reinitialization
def reinitialize_camera():
    global cap
    if 'cap' in globals() and cap.isOpened():
        cap.release()
    time.sleep(1)
    backends = [cv2.CAP_MSMF, cv2.CAP_VFW, cv2.CAP_DSHOW, cv2.CAP_FFMPEG, cv2.CAP_ANY]
    indices = [0, 1]
    for backend in backends:
        for index in indices:
            print(f"Trying backend {backend} and index {index}...")
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
                time.sleep(0.2)
                ret, frame = cap.read()
                if ret and frame is not None and frame.size != 0 and frame.shape == (HEIGHT, WIDTH, 3):
                    print(f"Success with backend {backend} and index {index}. Shape: {frame.shape}")
                    return True
                cap.release()
    print("Error: Could not open video capture.")
    return False

# Initial Camera Setup
if not reinitialize_camera():
    sys.exit()

# Calibration Functions
def load_calibrated_holes():
    if os.path.exists(CALIBRATION_FILE):
        with open(CALIBRATION_FILE, 'r') as f:
            try:
                data = json.load(f)
                print("Loaded calibration data.")
                return data["holes"]
            except Exception as e:
                print(f"Error loading calibration: {e}")
    print("No calibration file. Entering calibration mode.")
    return calibrate_holes()

def save_calibrated_holes(holes):
    with open(CALIBRATION_FILE, 'w') as f:
        json.dump({"holes": holes}, f)
        print("Calibration saved.")

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
            print(f"Selected hole at ({x}, {y}). Enter points.")

    cv2.setMouseCallback('Calibrate Holes', mouse_callback)

    while calibrating:
        ret, frame = cap.read()
        if not ret:
            print(f"Failed to capture frame in calibration. Retry {retry_count + 1}/{max_retries}")
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
            if key == 13:  # Enter
                points = int(current_input) if current_input.isdigit() else 10
                calibrated_holes.append((current_pos[0], current_pos[1], 20, points))
                print(f"Added hole at {current_pos} with {points} points")
                input_active = False
                current_input = ""
                current_pos = None
            elif key == 8:  # Backspace
                current_input = current_input[:-1]
            elif key in range(48, 58):  # 0-9
                current_input += chr(key)

    if calibrated_holes:
        save_calibrated_holes(calibrated_holes)

    cv2.destroyAllWindows()
    print("Reinitializing camera after calibration...")
    if not reinitialize_camera():
        print("Failed to reinitialize camera. Exiting...")
        sys.exit()
    return calibrated_holes

game.hole_positions = load_calibrated_holes()

# Force Camera Reinitialization
print("Forcing camera reinitialization before game loop...")
if not reinitialize_camera():
    print("Failed to reinitialize camera. Exiting...")
    sys.exit()

# Ball Detection
def detect_ball_in_hole(image, hole_coords, game_state, frame_count):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Tightened HSV range for white balls
    lower_white = np.array([0, 0, 200])  # Increased value threshold
    upper_white = np.array([180, 30, 255])  # Reduced saturation threshold
    mask = cv2.inRange(hsv, lower_white, upper_white)

    # Apply morphological operations to reduce noise
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.erode(mask, kernel, iterations=1)
    mask = cv2.dilate(mask, kernel, iterations=1)

    ball_positions = []
    points_list = []
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detected_balls = set()
    for contour in contours:
        area = cv2.contourArea(contour)
        if 0.1 * np.pi * 20 * 20 < area < np.pi * 20 * 20:  # Adjusted lower bound
            # Check circularity
            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue
            circularity = 4 * np.pi * area / (perimeter * perimeter)
            if circularity < 0.7:  # Ensure contour is roughly circular
                continue

            approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
            if len(approx) > 4:
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    ball_x = int(M["m10"] / M["m00"])
                    ball_y = int(M["m01"] / M["m00"])
                    ball_pos = (ball_x, ball_y)
                    rounded_x = round(ball_x / 10) * 10
                    rounded_y = round(ball_y / 10) * 10
                    ball_id = f"{rounded_x},{rounded_y}"

                    nearest_hole = game_state.get_nearest_hole(ball_pos)
                    if nearest_hole:
                        hole_x, hole_y, points = nearest_hole
                        hole_pos = (hole_x, hole_y)

                        # Check cooldown and scored status
                        if hole_pos in game_state.detection_cooldown:
                            if frame_count - game_state.detection_cooldown[hole_pos] < COOLDOWN_FRAMES:
                                continue
                        if hole_pos in game_state.scored_balls:
                            continue

                        if ball_id in game_state.confirming_balls:
                            current_data = game_state.confirming_balls[ball_id]
                            current_pos = current_data["position"]
                            frames = current_data["frames"]
                            dist = np.hypot(ball_x - current_pos[0], ball_y - current_pos[1])
                            if dist < 10:  # Tightened distance threshold
                                game_state.confirming_balls[ball_id]["frames"] += 1
                                game_state.confirming_balls[ball_id]["position"] = (ball_x, ball_y)
                                game_state.confirming_balls[ball_id]["hole_pos"] = hole_pos
                                if frames + 1 >= CONFIRMATION_FRAMES:
                                    ball_positions.append(hole_pos)
                                    points_list.append(points)
                                    game_state.scored_balls.add(hole_pos)
                                    game_state.detection_cooldown[hole_pos] = frame_count
                                    print(f"Confirmed ball at {hole_pos}, Points: {points}")
                                    del game_state.confirming_balls[ball_id]
                            else:
                                game_state.confirming_balls[ball_id] = {
                                    "position": (ball_x, ball_y), "frames": 1, "hole_pos": hole_pos
                                }
                        else:
                            game_state.confirming_balls[ball_id] = {
                                "position": (ball_x, ball_y), "frames": 1, "hole_pos": hole_pos
                            }

                        if hole_pos not in game_state.detected_positions:
                            game_state.detected_positions.append(hole_pos)
                        detected_balls.add(ball_id)
                    else:
                        if ball_id in game_state.confirming_balls:
                            hole_pos = game_state.confirming_balls[ball_id]["hole_pos"]
                            del game_state.confirming_balls[ball_id]
                            if hole_pos in game_state.detected_positions:
                                game_state.detected_positions.remove(hole_pos)
                else:
                    continue

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
    pygame.draw.rect(screen, BLUE, (10, 10, 100, 50))

# Main Game Loop (Stops around line 700)
running = True
frame_count = 0
retry_count = 0
max_retries = 10
while running and game.running:
    try:
        if not cap.isOpened():
            print("Camera not open. Reinitializing...")
            if not reinitialize_camera():
                print("Failed to reinitialize camera. Exiting...")
                break
            retry_count = 0

        print("Attempting to read frame...")
        ret, frame = cap.read()
        if not ret:
            print(f"Failed to capture frame. Retry {retry_count + 1}/{max_retries}")
            retry_count += 1
            if retry_count >= max_retries:
                print("Max retries reached. Reinitializing camera...")
                if not reinitialize_camera():
                    print("Failed to reinitialize camera. Exiting...")
                    break
                retry_count = 0
            time.sleep(0.1)
            continue

        retry_count = 0
        print("Validating frame...")
        if frame is None or frame.size == 0 or frame.shape != (HEIGHT, WIDTH, 3) or frame.mean() < 1:
            print(f"Invalid frame: Shape: {frame.shape if frame is not None else 'None'}, Mean: {frame.mean() if frame is not None else 'N/A'}")
            frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        else:
            if frame_count % 30 == 0:
                print(f"Frame captured: Shape: {frame.shape}, Mean: {frame.mean()}")

        print("Processing frame...")
        roi = frame
        for (x, y, radius, points) in game.hole_positions:
            cv2.circle(roi, (x, y), radius, (0, 255, 0), 2)
            cv2.putText(roi, str(points), (x - 20, y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        print("Detecting balls...")
        if game.just_reset:
            game.just_reset = False  # Skip detection immediately after reset
            game.detected_positions.clear()
            game.confirming_balls.clear()
        else:
            ball_positions, points_list = detect_ball_in_hole(roi, game.hole_positions, game, frame_count)
            for pos, points in zip(ball_positions, points_list):
                game.score += points
                game.balls -= 1
                print(f"Ball scored at {pos}, Points: {points}, Score: {game.score}, Balls: {game.balls}")
                # Debounce sound playback
                current_time = time.time()
                if score_sound and (current_time - game.last_sound_time) >= SOUND_COOLDOWN:
                    score_sound.play()
                    game.last_sound_time = current_time

        print("Preparing frame for display...")
        frame_to_display = roi if roi is not None else np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        if frame_to_display.size == 0 or frame_to_display.shape != (HEIGHT, WIDTH, 3):
            print("Frame invalid, using fallback...")
            frame_to_display = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        frame_rgb = cv2.cvtColor(frame_to_display, cv2.COLOR_BGR2RGB)
        pygame_surface = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
        scaled_surface = pygame.transform.scale(pygame_surface, (WIDTH, HEIGHT))

        print("Rendering to screen...")
        screen.fill(BLACK)
        screen.blit(scaled_surface, (0, 0))

        for pos in game.detected_positions:
            if any(pos == game.confirming_balls[ball_id]["hole_pos"] for ball_id in game.confirming_balls
                   if game.confirming_balls[ball_id]["frames"] < CONFIRMATION_FRAMES):
                pygame.draw.circle(screen, YELLOW, pos, 20, 2)
            else:
                pygame.draw.circle(screen, RED, pos, 20, 2)

        draw_ui()
        pygame.display.flip()
        clock.tick(30)

        frame_count += 1
        if frame_count % 30 == 0:
            game.time = time.strftime("%H:%M:%S")

        for event in pygame.event.get():
            if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                running = False
            elif event.type == KEYDOWN:
                if event.key == K_l:
                    game.show_leaderboard = not game.show_leaderboard
                elif event.key == K_r:
                    game.reset()
                elif event.key == K_c:
                    game.hole_positions = calibrate_holes()

        if game.balls <= 0:
            print("Posting score to leaderboard...")
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

    except Exception as e:
        print(f"Crash occurred: {e}")
        import traceback
        traceback.print_exc()
        break

# Supabase Configuration
SUPABASE_URL = "https://jtkbujumrobglftzokcs.supabase.co"
SUPABASE_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp0a2J1anVtcm9iZ2xmdHpva2NzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDIwMTM8NzcsImV4cCI6MjA1NzU4OTg3N30.OibLuqr3X922SUSBL8yGxDw8uwuTjivH97-2wNhJDqs"
LEADERBOARD_ENDPOINT = f"{SUPABASE_URL}/rest/v1/leaderboard"

headers = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# Cleanup
cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()