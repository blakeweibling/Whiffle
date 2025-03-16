# Whiffle Playfield - Fixed Ball Detection Crash and Improved Scoring
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
WIDTH, HEIGHT = 1280, 720  # Match your screenshot resolution
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Whiffle Playfield")
clock = pygame.time.Clock()

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)  # For debug overlay

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
        self.last_detected = []  # To track previously detected balls and avoid double-counting

    def reset(self):
        self.score = 0
        self.balls = 7
        self.power_up = None
        self.time = "N/A"
        self.last_detected = []

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

# ROI and Ball Detection Functions
def get_table_roi(image, frame_count=0):
    # Preprocess: Convert to HSV and use saturation channel to enhance table edges
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    gray = hsv[:, :, 1]  # Use saturation channel
    # Enhance contrast
    gray = cv2.equalizeHist(gray)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    # Lower Canny thresholds further to detect more edges
    edges = cv2.Canny(blurred, 20, 80)  # Adjusted from (30, 100) to (20, 80)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Debug: Save edge image and log contours
    if frame_count % 30 == 0:
        cv2.imwrite("debug_edges.jpg", edges)
        print(f"Saved edge-detected image to debug_edges.jpg. Number of contours found: {len(contours)}")
        if contours:
            contour_areas = [cv2.contourArea(c) for c in contours]
            print(f"Contour areas: {contour_areas}")

    if contours:
        # Filter contours: Select contours with reasonable area and rectangular shape
        filtered_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 5000 or area > (WIDTH * HEIGHT * 0.9):  # Ignore very small or very large contours
                continue
            # Approximate the contour to a polygon
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            # Check if the contour is roughly rectangular (4 sides)
            if len(approx) == 4:
                # Check aspect ratio (table should be roughly 2:1 or similar)
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / float(h)
                if 1.5 < aspect_ratio < 3.0:  # Adjust based on table proportions
                    filtered_contours.append((contour, area))

        if filtered_contours:
            # Select the largest filtered contour
            filtered_contours.sort(key=lambda x: x[1], reverse=True)
            table_contour = filtered_contours[0][0]
            mask = np.zeros_like(gray)
            cv2.drawContours(mask, [table_contour], -1, 255, thickness=cv2.FILLED)
            roi = cv2.bitwise_and(image, image, mask=mask)

            # Debug: Save mask
            if frame_count % 30 == 0:
                cv2.imwrite("debug_mask.jpg", mask)
                print(f"Saved mask to debug_mask.jpg. Mask mean: {mask.mean()}")

            # Check if ROI is mostly black
            if roi.mean() < 1:
                print(f"ROI is mostly black (mean: {roi.mean()}), falling back to raw frame.")
                return image, None
            return roi, mask
        else:
            print("No suitable contours found for table, falling back to raw frame.")
            return image, None
    print("No contours found in get_table_roi, returning original image.")
    return image, None

def detect_ball_in_hole(image, hole_coords):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Adjusted HSV range for white balls under varying lighting
    lower_white = np.array([0, 0, 200])  # Lower bound
    upper_white = np.array([180, 50, 255])  # Expanded upper bound for brightness
    mask = cv2.inRange(hsv, lower_white, upper_white)

    ball_positions = []
    points_list = []
    for (x, y, radius, points) in hole_coords:
        # Define ROI around the hole
        roi = mask[y-radius:y+radius, x-radius:x+radius]
        white_pixels = cv2.countNonZero(roi)
        total_pixels = np.pi * radius * radius
        if white_pixels > 0.3 * total_pixels:  # Lowered threshold to 0.3 for sensitivity
            # Validate ball shape using contour detection in the ROI
            gray_roi = cv2.cvtColor(image[y-radius:y+radius, x-radius:x+radius], cv2.COLOR_BGR2GRAY)
            _, binary_roi = cv2.threshold(gray_roi, 200, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(binary_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 0.1 * total_pixels and area < total_pixels:  # Reasonable ball size
                    # Approximate the contour to check circularity
                    peri = cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
                    if len(approx) > 4:  # Loose check for circularity
                        ball_positions.append((x, y))
                        points_list.append(points)
                        break
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
frame_capture_count = 0
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
        frame_capture_count += 1
        if frame_capture_count % 30 == 0:
            print(f"Successfully captured frame. Shape: {frame.shape}, Mean pixel value: {frame.mean()}")

    # Apply ROI
    roi, mask = get_table_roi(frame, frame_count)
    if roi is not None:
        if frame_capture_count % 30 == 0:
            cv2.imwrite("debug_roi_frame.jpg", roi)
            print(f"Saved ROI frame to debug_roi_frame.jpg. Shape: {roi.shape}, Mean: {roi.mean()}")
        # Overlay calibrated hole positions and points
        for (x, y, radius, points) in game.hole_positions:
            cv2.circle(roi, (x, y), radius, (0, 255, 0), 2)
            cv2.putText(roi, str(points), (x - 20, y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Detect balls and update score
        ball_positions, points_list = detect_ball_in_hole(roi, game.hole_positions)
        current_detections = list(zip(ball_positions, points_list))
        new_detections = [d for d in current_detections if d not in game.last_detected]
        game.last_detected = current_detections  # Update last detected balls

        for pos, points in new_detections:
            game.score += points
            game.balls -= 1
            print(f"Ball scored at {pos}, Points: {points}, Score: {game.score}, Balls remaining: {game.balls}")
            cv2.circle(roi, pos, 20, RED, 2)  # Visual feedback
    else:
        roi = frame  # Fall back to raw frame if ROI fails

    # Convert frame for Pygame display
    frame_to_display = roi
    if frame_to_display is None or frame_to_display.size == 0:
        print(f"Warning: Frame to display is None or invalid after ROI. Shape: {frame_to_display.shape if frame_to_display is not None else 'None'}, Mean: {frame_to_display.mean() if frame_to_display is not None else 'N/A'}")
        frame_to_display = frame  # Fall back to raw frame
        if frame_to_display is None or frame_to_display.size == 0:
            print("Warning: Raw frame is also invalid, using black screen as fallback.")
            frame_to_display = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)

    if frame_capture_count % 30 == 0:
        cv2.imwrite("debug_frame_before_blit.jpg", frame_to_display)
        print(f"Saved frame before blitting to debug_frame_before_blit.jpg. Shape: {frame_to_display.shape}, Mean: {frame_to_display.mean()}")

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
            elif event.key == K_r:  # Add 'r' key to force recalibration
                game.hole_positions = calibrate_holes()

# Cleanup (to be continued)
cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()

# Whiffle Playfield - Remaining Code (Lines 701+)

# Supabase Configuration for Online Leaderboard (still used for scores)
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

# Resume Game Loop
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
    roi, mask = get_table_roi(frame, frame_count)
    if roi is not None:
        for (x, y, radius, points) in game.hole_positions:
            cv2.circle(roi, (x, y), radius, (0, 255, 0), 2)
            cv2.putText(roi, str(points), (x - 20, y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        ball_positions, points_list = detect_ball_in_hole(roi, game.hole_positions)
        if ball_positions and points_list:
            for (pos, points) in zip(ball_positions, points_list):
                if pos not in [(bp[0], bp[1]) for bp in game.hole_positions]:  # Avoid double-counting
                    game.score += points
                    game.balls -= 1
                    print(f"Ball scored at {pos}, Points: {points}, Score: {game.score}")
                    cv2.circle(roi, pos, 20, RED, 2)  # Visual feedback
    else:
        roi = frame  # Fall back to raw frame if ROI fails

    frame_to_display = roi if roi is not None else frame
    if frame_to_display is None or frame_to_display.size == 0:
        print("Warning: Frame to display is None or invalid, using black screen as fallback.")
        frame_to_display = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
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