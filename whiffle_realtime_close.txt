import cv2
import numpy as np
import json
import os
import tkinter as tk
from tkinter import simpledialog, messagebox
import logging

# Set up logging
logging.basicConfig(filename="debug_log.txt", level=logging.DEBUG,
                    format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize webcam
try:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logging.error("Could not open webcam.")
        print("Error: Could not open webcam.")
        exit()
except Exception as e:
    logging.error(f"Webcam initialization failed: {e}")
    print(f"Error: Webcam initialization failed: {e}")
    exit()

# Set webcam resolution to 1920x1080
try:
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logging.info(f"Webcam resolution set to: {width}x{height}")
    print(f"Webcam resolution: {width}x{height}")
except Exception as e:
    logging.error(f"Failed to set webcam resolution: {e}")
    print(f"Error setting webcam resolution: {e}")
    cap.release()
    exit()

# File paths
HOLES_FILE = "whiffle_holes.json"
HIGH_SCORE_FILE = "high_score.txt"

# Program control
running = True

def calibrate_holes(frame):
    """Calibrate hole positions and points on the Whiffle playfield."""
    holes = []
    root = tk.Tk()
    root.withdraw()
    logging.info("Starting hole calibration.")

    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            logging.info(f"Mouse click at ({x}, {y})")
            points = simpledialog.askinteger("Hole Points", f"Enter points for hole at ({x}, {y}):",
                                            minvalue=1, maxvalue=1000)
            if points is None:
                logging.warning("User canceled points input.")
                return
            is_special = messagebox.askyesno("Special Hole", "Is this the special hole?")
            holes.append({"x": x, "y": y, "radius": 15, "points": points, "is_special": is_special})
            color = (255, 0, 255) if is_special else (0, 0, 255)
            cv2.circle(frame, (x, y), 15, color, 2)
            cv2.imshow("Calibrate Whiffle Holes", frame)

    try:
        cv2.namedWindow("Calibrate Whiffle Holes")
        cv2.setMouseCallback("Calibrate Whiffle Holes", mouse_callback)
        messagebox.showinfo("Calibration", "Click the center of each hole. Press 'c' to finish.")
    except Exception as e:
        logging.error(f"Error setting up calibration window: {e}")
        root.destroy()
        return []

    while running:
        try:
            cv2.imshow("Calibrate Whiffle Holes", frame)
            if (cv2.waitKey(1) & 0xFF) == ord('c'):
                logging.info("Calibration completed by user.")
                break
            if cv2.getWindowProperty("Calibrate Whiffle Holes", cv2.WND_PROP_VISIBLE) < 1:
                logging.warning("Calibration window closed.")
                running = False
                break
        except Exception as e:
            logging.error(f"Error during calibration loop: {e}")
            break

    if cv2.getWindowProperty("Calibrate Whiffle Holes", cv2.WND_PROP_VISIBLE) >= 1:
        cv2.destroyWindow("Calibrate Whiffle Holes")
    root.destroy()

    if running and holes:
        special_count = sum(1 for h in holes if h["is_special"])
        if special_count > 1:
            messagebox.showwarning("Calibration Warning", "Multiple special holes detected. Using the first.")
        elif special_count == 0:
            messagebox.showwarning("Calibration Warning", "No special hole selected. Score won’t double.")
    logging.info(f"Calibration finished. Holes: {len(holes)}")
    return holes

def save_holes(holes):
    """Save hole configurations to a JSON file."""
    try:
        with open(HOLES_FILE, "w") as f:
            json.dump(holes, f)
        logging.info("Holes saved successfully.")
    except Exception as e:
        logging.error(f"Error saving holes: {e}")
        print(f"Error saving holes: {e}")

def load_holes():
    """Load hole configurations from a JSON file."""
    if os.path.exists(HOLES_FILE):
        try:
            with open(HOLES_FILE, "r") as f:
                holes = json.load(f)
            logging.info(f"Loaded {len(holes)} holes from file.")
            return holes
        except Exception as e:
            logging.error(f"Error loading holes: {e}")
            print(f"Error loading holes: {e}")
    logging.info("No holes file found. Calibration required.")
    return None

def load_high_score():
    """Load the high score and initials from a file."""
    if os.path.exists(HIGH_SCORE_FILE):
        try:
            with open(HIGH_SCORE_FILE, "r") as f:
                data = f.read().strip()
                if data:
                    try:
                        high_score_data = json.loads(data)
                        logging.info(f"Loaded high score: {high_score_data}")
                        return high_score_data
                    except json.JSONDecodeError:
                        logging.warning("High score file contains old format. Converting to dictionary.")
                        score = int(data) if data.isdigit() else 0
                        return {"score": score, "initials": "???"}
                logging.info("High score file empty. Using default.")
                return {"score": 0, "initials": "???"}
        except Exception as e:
            logging.error(f"Error loading high score: {e}")
            print(f"Error loading high score: {e}")
    logging.info("No high score file found. Using default.")
    return {"score": 0, "initials": "???"}

def save_high_score(score, initials):
    """Save the high score and initials to a file."""
    try:
        with open(HIGH_SCORE_FILE, "w") as f:
            json.dump({"score": score, "initials": initials}, f)
        logging.info(f"Saved high score: {score}, initials: {initials}")
    except Exception as e:
        logging.error(f"Error saving high score: {e}")
        print(f"Error saving high score: {e}")

def create_high_score_window(high_score_data):
    """Create a window displaying the high score and initials."""
    try:
        img = np.zeros((120, 300, 3), dtype=np.uint8)
        cv2.putText(img, f"High Score: {high_score_data['score']}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(img, f"By: {high_score_data['initials']}", (10, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        logging.info("High score window created.")
        return img
    except Exception as e:
        logging.error(f"Error creating high score window: {e}")
        return np.zeros((120, 300, 3), dtype=np.uint8)

def preprocess_frame(frame):
    """Preprocess the frame for ball detection."""
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        return blurred, frame
    except Exception as e:
        logging.error(f"Error preprocessing frame: {e}")
        return None, frame

def detect_balls(frame, blurred):
    """Detect red and white balls using HoughCircles."""
    try:
        circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=30,
                                   param1=50, param2=20, minRadius=5, maxRadius=30)
        balls = []
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            height, width = frame.shape[:2]
            with open("detection_log.txt", "a") as f:
                f.write(f"--- Captured Frame ---\nTotal circles detected: {len(circles)}\n")
            for (x, y, r) in circles:
                if r < height * 0.003 or r > height * 0.015:
                    with open("detection_log.txt", "a") as f:
                        f.write(f"Filtered by radius: {r} (expected {height * 0.003}-{height * 0.015})\n")
                    continue
                y_min, y_max = max(y - r, 0), min(y + r, height)
                x_min, x_max = max(x - r, 0), min(x + r, width)
                if y_max <= y_min or x_max <= x_min:
                    continue
                roi = frame[y_min:y_max, x_min:x_max]
                hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                avg_color = np.mean(hsv_roi, axis=(0, 1))[:3]
                is_red = (0 <= avg_color[0] <= 10 or 160 <= avg_color[0] <= 180) and avg_color[1] > 40 and avg_color[2] > 80
                is_white = avg_color[1] < 50 and avg_color[2] > 150
                with open("detection_log.txt", "a") as f:
                    f.write(f"Circle at ({x}, {y}), radius {r}, HSV: {avg_color}, is_red: {is_red}, is_white: {is_white}\n")
                if is_red or is_white:
                    balls.append({"x": x, "y": y, "radius": r, "is_red": is_red})
                    with open("detection_log.txt", "a") as f:
                        f.write(f"Confirmed ball: {'red' if is_red else 'white'} at ({x}, {y})\n")
        else:
            with open("detection_log.txt", "a") as f:
                f.write("No circles detected by HoughCircles\n")
        logging.info(f"Detected {len(balls)} balls.")
        return balls
    except Exception as e:
        logging.error(f"Error in detect_balls: {e}")
        with open("detection_log.txt", "a") as f:
            f.write(f"Error in detect_balls: {e}\n")
        return []

def calculate_score(balls, holes):
    """Calculate the score based on balls in holes."""
    try:
        base_score = 0
        special_hole = next((h for h in holes if h["is_special"]), None)
        special_hole_hit = False
        scored_balls = set()

        for ball in balls:
            ball_id = f"{ball['x']}_{ball['y']}"
            if ball_id in scored_balls:
                continue
            for hole in holes:
                distance = np.sqrt((ball["x"] - hole["x"])**2 + (ball["y"] - hole["y"])**2)
                if distance < hole["radius"] * 1.5:
                    points = hole["points"] * 2 if ball["is_red"] else hole["points"]
                    base_score += points
                    scored_balls.add(ball_id)
                    with open("scoring_log.txt", "a") as f:
                        f.write(f"Scored ball at ({ball['x']}, {ball['y']}): {points} points "
                                f"(hole at {hole['x']}, {hole['y']}, points: {hole['points']}, red: {ball['is_red']})\n")
                    if hole == special_hole and not special_hole_hit:
                        special_hole_hit = True
                    break
        
        final_score = base_score * 2 if special_hole_hit else base_score
        with open("scoring_log.txt", "a") as f:
            f.write(f"Base Score: {base_score}, Special Hole Hit: {special_hole_hit}, Final Score: {final_score}\n")
        logging.info(f"Calculated score: {final_score}, Special Hole Hit: {special_hole_hit}")
        return final_score, special_hole_hit
    except Exception as e:
        logging.error(f"Error in calculate_score: {e}")
        with open("scoring_log.txt", "a") as f:
            f.write(f"Error in calculate_score: {e}\n")
        return 0, False

def draw_elements(frame, balls, holes, final_score, special_hole_hit):
    """Draw holes, balls, and score on the frame."""
    try:
        for hole in holes:
            color = (255, 0, 255) if hole["is_special"] else (0, 0, 255)
            cv2.circle(frame, (hole["x"], hole["y"]), 15, color, 2)
            cv2.putText(frame, str(hole["points"]), (hole["x"]-10, hole["y"]-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        for ball in balls:
            color = (0, 0, 255) if ball["is_red"] else (0, 255, 0)
            cv2.circle(frame, (ball["x"], ball["y"]), ball["radius"], color, 2)
            cv2.circle(frame, (ball["x"], ball["y"]), 2, (255, 0, 0), 3)
        if final_score is not None:
            cv2.putText(frame, f"Final Score: {final_score}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            if special_hole_hit:
                cv2.putText(frame, "Special Hole Hit!", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
            cv2.putText(frame, "Game Over! Play Again?", (frame.shape[1]//2 - 150, frame.shape[0]//2),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
    except Exception as e:
        logging.error(f"Error in draw_elements: {e}")

# Load or calibrate holes
scoring_holes = load_holes()
if scoring_holes is None and running:
    ret, frame = cap.read()
    if ret:
        scoring_holes = calibrate_holes(frame)
        if running:
            save_holes(scoring_holes)

if not running:
    cap.release()
    cv2.destroyAllWindows()
    logging.info("Program exited during calibration.")
    print("Program terminated.")
    exit()

# Initialize game state
high_score_data = load_high_score()
# Ensure high_score_data is a dictionary
if not isinstance(high_score_data, dict):
    logging.warning(f"High score data is not a dictionary: {high_score_data}. Converting.")
    high_score_data = {"score": int(high_score_data) if isinstance(high_score_data, (int, float)) else 0, "initials": "???"}
logging.info(f"Initialized high score data: {high_score_data}")
high_score_img = create_high_score_window(high_score_data)
game_over = False
final_score = None
special_hole_hit = False

# Create a single Tkinter root for the entire program
tk_root = tk.Tk()
tk_root.withdraw()

# Main loop
try:
    cv2.namedWindow("Whiffle 1931 Playfield")
    cv2.namedWindow("High Score")
    cv2.moveWindow("High Score", 0, 0)
    logging.info("Main windows created.")
except Exception as e:
    logging.error(f"Error creating windows: {e}")
    cap.release()
    cv2.destroyAllWindows()
    tk_root.destroy()
    exit()

while running:
    try:
        ret, frame = cap.read()
        if not ret:
            logging.error("Failed to capture frame. Check webcam connection.")
            print("Error: Failed to capture frame. Check webcam connection.")
            break

        blurred, display_frame = preprocess_frame(frame)
        if blurred is None:
            logging.warning("Frame preprocessing failed. Skipping frame.")
            continue

        balls = detect_balls(display_frame, blurred)
        draw_elements(display_frame, balls, scoring_holes, final_score, special_hole_hit)
        
        cv2.imshow("Whiffle 1931 Playfield", display_frame)
        cv2.imshow("High Score", high_score_img)

        key = cv2.waitKey(10) & 0xFF
        if key == ord('q'):
            logging.info("User pressed 'q'. Exiting.")
            running = False
        elif key == ord(' ') and not game_over:
            logging.info("User pressed spacebar to calculate score.")
            final_score, special_hole_hit = calculate_score(balls, scoring_holes)
            game_over = True
            with open("scoring_log.txt", "a") as f:
                f.write(f"Game Over! Final Score: {final_score}\n")
            if final_score > high_score_data.get("score", 0):  # Use .get() to avoid KeyError
                logging.info("New high score achieved. Prompting for initials.")
                try:
                    initials = simpledialog.askstring("New High Score!", "Enter your 3-character initials:",
                                                     initialvalue="???", parent=tk_root)
                    logging.info(f"User entered initials: {initials}")
                    if initials:
                        initials = (initials[:3] + "???")[:3].upper()
                    else:
                        initials = "???"
                    high_score_data = {"score": final_score, "initials": initials}
                    save_high_score(final_score, initials)
                    high_score_img = create_high_score_window(high_score_data)
                except Exception as e:
                    logging.error(f"Error prompting for initials: {e}")
                    initials = "???"
                    high_score_data = {"score": final_score, "initials": initials}
                    save_high_score(final_score, initials)
                    high_score_img = create_high_score_window(high_score_data)
            with open("detection_log.txt", "a") as f:
                f.write(f"Captured frame with {len(balls)} balls\n")
        elif key == ord('r') and game_over:
            logging.info("User pressed 'r' to reset game.")
            game_over = False
            final_score = None
            special_hole_hit = False
        elif key == -1:
            continue
        if (cv2.getWindowProperty("Whiffle 1931 Playfield", cv2.WND_PROP_VISIBLE) < 1 or
            cv2.getWindowProperty("High Score", cv2.WND_PROP_VISIBLE) < 1):
            logging.info("Window closed by user. Exiting.")
            running = False

    except Exception as e:
        logging.error(f"Error in main loop: {e}")
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()
tk_root.destroy()
logging.info("Program terminated successfully.")
print("Program terminated.")