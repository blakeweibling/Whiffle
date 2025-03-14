import cv2
import numpy as np
import json
import os
import tkinter as tk
from tkinter import simpledialog, messagebox

# Initialize webcam
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit()

# Set webcam resolution to 1920x1080 (1080p)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

# Verify the resolution
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"Webcam resolution set to: {width}x{height}")

# File to store hole positions, points, and high score
HOLES_FILE = "whiffle_holes.json"
HIGH_SCORE_FILE = "high_score.txt"

# Global flag to control program execution
running = True

def calibrate_holes(frame):
    global running
    holes = []
    root = tk.Tk()
    root.withdraw()

    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            points = simpledialog.askinteger("Hole Points", "Enter points for hole at ({}, {}):".format(x, y),
                                            minvalue=1, maxvalue=1000)
            if points is None:
                return
            is_special = messagebox.askyesno("Special Hole", "Is this the special hole?")
            holes.append({"x": x, "y": y, "radius": 10, "points": points, "is_special": is_special})
            color = (255, 0, 255) if is_special else (0, 0, 255)
            cv2.circle(frame, (x, y), 10, color, 2)
            cv2.imshow("Calibrate Whiffle Holes", frame)

    cv2.namedWindow("Calibrate Whiffle Holes")
    cv2.setMouseCallback("Calibrate Whiffle Holes", mouse_callback)
    messagebox.showinfo("Calibration", "Click the center of each hole on the Whiffle playfield. Press 'c' to finish.")

    while running:
        cv2.imshow("Calibrate Whiffle Holes", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('c'):
            break
        if cv2.getWindowProperty("Calibrate Whiffle Holes", cv2.WND_PROP_VISIBLE) < 1:
            running = False
            break

    if cv2.getWindowProperty("Calibrate Whiffle Holes", cv2.WND_PROP_VISIBLE) >= 1:
        cv2.destroyWindow("Calibrate Whiffle Holes")

    root.destroy()

    if running:
        special_count = sum(1 for h in holes if h["is_special"])
        if special_count > 1:
            messagebox.showwarning("Calibration Warning", "Multiple special holes detected. Only the first will be used.")
        elif special_count == 0 and holes:
            messagebox.showwarning("Calibration Warning", "No special hole selected. Score doubling won’t apply.")

    return holes

def save_holes(holes):
    with open(HOLES_FILE, "w") as f:
        json.dump(holes, f)

def load_holes():
    if os.path.exists(HOLES_FILE):
        with open(HOLES_FILE, "r") as f:
            return json.load(f)
    return None

def load_high_score():
    if os.path.exists(HIGH_SCORE_FILE):
        with open(HIGH_SCORE_FILE, "r") as f:
            return int(f.read().strip())
    return 0

def save_high_score(score):
    with open(HIGH_SCORE_FILE, "w") as f:
        f.write(str(score))

def create_high_score_window(high_score):
    high_score_img = np.zeros((100, 300, 3), dtype=np.uint8)
    cv2.putText(high_score_img, f"High Score: {high_score}", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
    return high_score_img

def preprocess_frame(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    return blurred, frame

def detect_balls(frame, blurred, tracked_balls):
    circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=30,
                               param1=50, param2=20, minRadius=5, maxRadius=30)
    balls = []
    if circles is not None:
        circles = np.round(circles[0, :]).astype("int")
        height, width = frame.shape[:2]
        with open("detection_log.txt", "a") as f:
            f.write("--- New Frame ---\n")
            f.write(f"Total circles detected: {len(circles)}\n")
        for (x, y, r) in circles:
            # Create a unique identifier for the ball (position and radius)
            ball_id = f"{x}_{y}_{r}"
            # Skip if this ball has already been tracked
            if ball_id in tracked_balls:
                with open("detection_log.txt", "a") as f:
                    f.write(f"Skipped ball (already tracked): {ball_id}\n")
                continue
            with open("detection_log.txt", "a") as f:
                f.write(f"Circle at ({x}, {y}), radius {r}\n")
            if r < height * 0.003 or r > height * 0.015:
                with open("detection_log.txt", "a") as f:
                    f.write(f"Filtered by radius: {r} (expected {height * 0.003}-{height * 0.015})\n")
                continue
            y_min = max(y - r, 0)
            y_max = min(y + r, height)
            x_min = max(x - r, 0)
            x_max = min(x + r, width)
            if y_max <= y_min or x_max <= x_min:
                continue
            roi = frame[y_min:y_max, x_min:x_max]
            hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            avg_color = np.mean(hsv_roi, axis=(0, 1))[:3]
            is_red = (0 <= avg_color[0] <= 10 or 160 <= avg_color[0] <= 180) and avg_color[1] > 40 and avg_color[2] > 80
            is_white = avg_color[1] < 50 and avg_color[2] > 150
            with open("detection_log.txt", "a") as f:
                f.write(f"HSV color: {avg_color}, is_red: {is_red}, is_white: {is_white}\n")
            if is_red or is_white:
                balls.append({"x": x, "y": y, "radius": r, "is_red": is_red, "id": ball_id})
                with open("detection_log.txt", "a") as f:
                    f.write(f"Confirmed ball: {'red' if is_red else 'white'}\n")
    else:
        with open("detection_log.txt", "a") as f:
            f.write("No circles detected by HoughCircles\n")
    return balls

def calculate_score(balls, holes, tracked_balls):
    frame_score = 0
    special_hole_hit = False
    special_hole = next((h for h in holes if h["is_special"]), None)
    
    for ball in balls:
        # Skip if already tracked (shouldn't happen due to detect_balls filter, but added for safety)
        if ball["id"] in tracked_balls:
            continue
        for hole in holes:
            distance = np.sqrt((ball["x"] - hole["x"])**2 + (ball["y"] - hole["y"])**2)
            if distance < hole["radius"]:
                points = hole["points"] * 2 if ball["is_red"] else hole["points"]
                frame_score += points
                # Add to tracked_balls immediately to prevent re-scoring
                tracked_balls.add(ball["id"])
                with open("scoring_log.txt", "a") as f:
                    f.write(f"Scored ball {ball['id']}: {points} points\n")
                if hole == special_hole:
                    special_hole_hit = True
                break
    
    final_score = frame_score * 2 if special_hole_hit else frame_score
    return final_score, tracked_balls

def draw_elements(frame, balls, holes):
    for hole in holes:
        color = (255, 0, 255) if hole["is_special"] else (0, 0, 255)
        cv2.circle(frame, (hole["x"], hole["y"]), 10, color, 2)
        cv2.putText(frame, str(hole["points"]), (hole["x"]-10, hole["y"]-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    for ball in balls:
        color = (0, 0, 255) if ball["is_red"] else (0, 255, 0)
        cv2.circle(frame, (ball["x"], ball["y"]), ball["radius"], color, 2)
        cv2.circle(frame, (ball["x"], ball["y"]), 2, (255, 0, 0), 3)

# Load or calibrate holes
scoring_holes = load_holes()
if scoring_holes is None and running:
    ret, frame = cap.read()
    if ret:
        scoring_holes = calibrate_holes(frame)
        if running:
            save_holes(scoring_holes)

# Check if calibration was canceled or window closed
if not running:
    cap.release()
    cv2.destroyAllWindows()
    exit()

# Load or initialize high score
high_score = load_high_score()
high_score_img = create_high_score_window(high_score)
game_over = False

# Initialize scoring variables
total_score = 0
tracked_balls = set()

# Main loop
cv2.namedWindow("Whiffle 1931 Playfield")
cv2.namedWindow("High Score")
cv2.moveWindow("High Score", 0, 0)
while running:
    ret, frame = cap.read()
    if not ret:
        print("Error: Could not read frame.")
        break

    blurred, display_frame = preprocess_frame(frame)
    # Pass tracked_balls to detect_balls to filter before scoring
    balls = detect_balls(display_frame, blurred, tracked_balls)
    frame_score, tracked_balls = calculate_score(balls, scoring_holes, tracked_balls)
    total_score += frame_score

    draw_elements(display_frame, balls, scoring_holes)
    cv2.putText(display_frame, f"Score: {total_score}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    if any(h["is_special"] for h in scoring_holes) and frame_score > 0:
        special_hole = next(h for h in scoring_holes if h["is_special"])
        cv2.putText(display_frame, "Double Score!", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)

    balls_in_holes = len(tracked_balls)
    if balls_in_holes == 10 and not game_over:
        game_over = True
        if total_score > high_score:
            high_score = total_score
            save_high_score(high_score)
            high_score_img = create_high_score_window(high_score)
        cv2.putText(display_frame, "Game Over!", (display_frame.shape[1]//2 - 100, display_frame.shape[0]//2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

    cv2.imshow("Whiffle 1931 Playfield", display_frame)
    cv2.imshow("High Score", high_score_img)

    key = cv2.waitKey(10) & 0xFF
    if key == ord('q'):
        running = False
    elif key == ord('r') and game_over:
        game_over = False
        total_score = 0
        tracked_balls.clear()
    if cv2.getWindowProperty("Whiffle 1931 Playfield", cv2.WND_PROP_VISIBLE) < 1 or \
       cv2.getWindowProperty("High Score", cv2.WND_PROP_VISIBLE) < 1:
        running = False

cap.release()
cv2.destroyAllWindows()