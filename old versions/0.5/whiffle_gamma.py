import cv2
import numpy as np
import json
import os
import sys

# Suppress console on Windows (comment out for debugging)
if sys.platform == "win32":
    import ctypes
    # ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

# Fixed radius for scoring zones
ZONE_RADIUS = 30  # Scoring radius
CALIBRATION_VISUAL_RADIUS = 15  # Visual feedback radius

# Files
CALIBRATION_FILE = "whiffle_zones.json"
HIGH_SCORE_FILE = "whiffle_high_score.json"

# Detection settings
BALL_COLOR_RANGE = {"lower_white": [0, 0, 200], "upper_white": [180, 50, 255]}

# Game state
current_score = 0
high_score = 0

def load_point_zones(filename=CALIBRATION_FILE):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
            return [(zone['x'], zone['y'], ZONE_RADIUS, zone['points']) for zone in data]
    return []

def save_point_zones(point_zones, filename=CALIBRATION_FILE):
    data = [{'x': x, 'y': y, 'points': points} for (x, y, _, points) in point_zones]
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Zones saved to {filename}")  # Debug output

def load_high_score():
    global high_score
    if os.path.exists(HIGH_SCORE_FILE):
        with open(HIGH_SCORE_FILE, 'r') as f:
            high_score = json.load(f).get("high_score", 0)
    print(f"Loaded high score: {high_score}")  # Debug output
    return high_score

def save_high_score():
    with open(HIGH_SCORE_FILE, 'w') as f:
        json.dump({"high_score": high_score}, f, indent=4)
    print(f"Saved high score: {high_score}")  # Debug output

def get_text_input_near_click(window_name, frame, prompt, x, y):
    """Graphical text input near the clicked location."""
    input_text = ""
    while True:
        display_frame = frame.copy()
        cv2.putText(display_frame, prompt + input_text, (x, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 
                    0.7, (255, 255, 255), 2)
        cv2.imshow(window_name, display_frame)
        key = cv2.waitKey(0)
        if key == 13:  # Enter key
            break
        elif key == 8 and input_text:  # Backspace
            input_text = input_text[:-1]
        elif 48 <= key <= 57:  # Numbers 0-9
            input_text += chr(key)
    return input_text

def setup_point_zones_in_main(frame, window_name):
    """Perform calibration in the main window with input near clicked point."""
    point_zones = []
    clicked_points = []

    def mouse_callback(event, x, y, flags, param):
        nonlocal point_zones, clicked_points, frame
        if event == cv2.EVENT_LBUTTONDOWN:
            clicked_points.append((x, y))
            cv2.circle(frame, (x, y), CALIBRATION_VISUAL_RADIUS, (255, 0, 0), 2)
            prompt = "Points: "
            points_str = get_text_input_near_click(window_name, frame.copy(), prompt, x, y)
            try:
                points = int(points_str)
                point_zones.append((x, y, ZONE_RADIUS, points))
                cv2.putText(frame, str(points), (x - 10, y), cv2.FONT_HERSHEY_SIMPLEX, 
                            0.5, (255, 255, 255), 2)
            except ValueError:
                clicked_points.pop()  # Remove invalid point if input is invalid
            cv2.imshow(window_name, frame)

    cv2.setMouseCallback(window_name, mouse_callback)
    instruction_frame = frame.copy()
    cv2.putText(instruction_frame, "Click to define zones, press 's' to save", 
                (10, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    while True:
        cv2.imshow(window_name, instruction_frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            break
    
    cv2.setMouseCallback(window_name, lambda *args: None)  # Reset callback
    print(f"Calibration complete with {len(point_zones)} zones")  # Debug output
    return point_zones

def detect_balls(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_white = np.array(BALL_COLOR_RANGE["lower_white"])
    upper_white = np.array(BALL_COLOR_RANGE["upper_white"])
    mask = cv2.inRange(hsv, lower_white, upper_white)
    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    balls = []
    for contour in contours:
        ((x, y), radius) = cv2.minEnclosingCircle(contour)
        if radius > 10:
            balls.append((int(x), int(y), int(radius)))
    return balls

def calculate_score(balls, point_zones):
    total_score = 0
    for ball_x, ball_y, _ in balls:
        for zone_x, zone_y, zone_radius, points in point_zones:
            distance = np.sqrt((ball_x - zone_x)**2 + (ball_y - zone_y)**2)
            if distance <= zone_radius:
                total_score += points
                break
    return total_score

def draw_menu_bar(frame):
    menu_items = ["File", "New Game", "High Score", "Options", "Help"]
    menu_positions = {}
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 30), (200, 200, 200), -1)
    
    x_offset = 10
    for item in menu_items:
        text_width = cv2.getTextSize(item, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0][0]
        cv2.putText(frame, item, (x_offset, 20), cv2.FONT_HERSHEY_SIMPLEX, 
                    0.6, (0, 0, 0), 1, cv2.LINE_AA)
        menu_positions[item] = (x_offset, x_offset + text_width)
        x_offset += text_width + 20
    return menu_positions

def options_menu(window_name, frame):
    """Display a graphical menu for adjusting all HSV values at once."""
    global BALL_COLOR_RANGE
    fields = [
        ("Lower Hue (0-180)", BALL_COLOR_RANGE["lower_white"][0], 0, 180),
        ("Lower Sat (0-255)", BALL_COLOR_RANGE["lower_white"][1], 0, 255),
        ("Lower Val (0-255)", BALL_COLOR_RANGE["lower_white"][2], 0, 255),
        ("Upper Hue (0-180)", BALL_COLOR_RANGE["upper_white"][0], 0, 180),
        ("Upper Sat (0-255)", BALL_COLOR_RANGE["upper_white"][1], 0, 255),
        ("Upper Val (0-255)", BALL_COLOR_RANGE["upper_white"][2], 0, 255),
    ]
    values = [str(field[1]) for field in fields]
    selected_field = 0
    editing = False

    def mouse_callback(event, x, y, flags, param):
        nonlocal selected_field, editing
        if event == cv2.EVENT_LBUTTONDOWN:
            for i in range(len(fields)):
                field_y = frame.shape[0] // 2 - 60 + i * 30
                if field_y - 15 <= y <= field_y + 15 and frame.shape[1] // 2 - 150 <= x <= frame.shape[1] // 2 + 150:
                    selected_field = i
                    editing = True
                    break
            save_y = frame.shape[0] // 2 + 90
            if save_y - 15 <= y <= save_y + 15 and frame.shape[1] // 2 - 50 <= x <= frame.shape[1] // 2 + 50:
                try:
                    BALL_COLOR_RANGE["lower_white"] = [int(values[0]), int(values[1]), int(values[2])]
                    BALL_COLOR_RANGE["upper_white"] = [int(values[3]), int(values[4]), int(values[5])]
                except ValueError:
                    pass
                param[0] = False

    exit_flag = [True]
    original_callback = cv2.getMouseCallback(window_name)
    cv2.setMouseCallback(window_name, mouse_callback, exit_flag)
    
    while exit_flag[0]:
        display_frame = frame.copy()
        overlay = display_frame.copy()
        cv2.rectangle(overlay, (frame.shape[1] // 2 - 200, frame.shape[0] // 2 - 120), 
                      (frame.shape[1] // 2 + 200, frame.shape[0] // 2 + 120), (50, 50, 50), -1)
        cv2.addWeighted(overlay, 0.8, display_frame, 0.2, 0, display_frame)
        
        for i, (label, _, min_val, max_val) in enumerate(fields):
            y_pos = frame.shape[0] // 2 - 60 + i * 30
            color = (0, 255, 255) if i == selected_field and editing else (255, 255, 255)
            cv2.putText(display_frame, f"{label}: {values[i]}", (frame.shape[1] // 2 - 150, y_pos), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        save_y = frame.shape[0] // 2 + 90
        cv2.rectangle(display_frame, (frame.shape[1] // 2 - 50, save_y - 15), 
                      (frame.shape[1] // 2 + 50, save_y + 15), (0, 255, 0), -1)
        cv2.putText(display_frame, "Save", (frame.shape[1] // 2 - 20, save_y + 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        
        cv2.imshow(window_name, display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # Esc to exit without saving
            break
        elif key == 13:  # Enter to toggle editing
            editing = not editing
        elif key == ord('s'):  # Save
            try:
                BALL_COLOR_RANGE["lower_white"] = [int(values[0]), int(values[1]), int(values[2])]
                BALL_COLOR_RANGE["upper_white"] = [int(values[3]), int(values[4]), int(values[5])]
            except ValueError:
                pass
            break
        elif key == 8 and editing and values[selected_field]:  # Backspace
            values[selected_field] = values[selected_field][:-1]
        elif 48 <= key <= 57 and editing:  # Numbers 0-9
            values[selected_field] += chr(key)
        elif key == 82:  # Up arrow
            selected_field = (selected_field - 1) % len(fields)
            editing = False
        elif key == 84:  # Down arrow
            selected_field = (selected_field + 1) % len(fields)
            editing = False

    cv2.setMouseCallback(window_name, original_callback)

def handle_menu_click(x, y, menu_positions, frame, point_zones):
    global current_score, high_score
    window_name = "Whiffle Playfield"
    if 0 <= y <= 30:
        for item, (x_start, x_end) in menu_positions.items():
            if x_start <= x <= x_end:
                if item == "File":
                    action = get_text_input(window_name, frame, "Save (s) or Load (l): ", 10, frame.shape[0] - 40)
                    if action.lower() == 's':
                        filename = get_text_input(window_name, frame, "Enter filename: ", 10, frame.shape[0] - 40)
                        save_point_zones(point_zones, filename)
                    elif action.lower() == 'l':
                        filename = get_text_input(window_name, frame, "Enter filename: ", 10, frame.shape[0] - 40)
                        loaded_zones = load_point_zones(filename)
                        if loaded_zones:
                            return loaded_zones
                elif item == "New Game":
                    current_score = 0
                elif item == "High Score":
                    cv2.putText(frame, f"High Score: {high_score}", (frame.shape[1]//2 - 50, frame.shape[0]//2), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
                    cv2.imshow(window_name, frame)
                    cv2.waitKey(2000)
                elif item == "Options":
                    options_menu(window_name, frame)
                elif item == "Help":
                    help_frame = frame.copy()
                    cv2.putText(help_frame, "Hotkeys: 'q' to quit, 'c' to calibrate", (10, 50), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    cv2.putText(help_frame, "Menu: File (save/load), New Game (reset)", (10, 80), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    cv2.putText(help_frame, "High Score (view), Options (settings)", (10, 110), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    cv2.putText(help_frame, "Press any key to continue", (10, frame.shape[0] - 20), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    cv2.imshow(window_name, help_frame)
                    cv2.waitKey(0)
    return point_zones

def set_webcam_resolution(cap):
    # Try 1080p first
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width < 1920 or height < 1080:
        print("1080p not supported, falling back to 720p")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width < 1280 or height < 720:
            print("720p not supported, falling back to 480p")
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Set resolution to {width}x{height}")
    return width, height

def main():
    global current_score, high_score
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return
    
    width, height = set_webcam_resolution(cap)
    high_score = load_high_score()
    
    POINT_ZONES = load_point_zones()
    window_name = "Whiffle Playfield"
    cv2.namedWindow(window_name)
    
    if not POINT_ZONES:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            cap.release()
            return
        POINT_ZONES = setup_point_zones_in_main(frame, window_name)
        if POINT_ZONES:
            save_point_zones(POINT_ZONES)
        else:
            print("No zones defined during calibration.")
    
    def mouse_callback(event, x, y, flags, param):
        nonlocal POINT_ZONES
        POINT_ZONES = handle_menu_click(x, y, menu_positions, frame, POINT_ZONES)
    
    cv2.setMouseCallback(window_name, mouse_callback)
    
    while True:
        try:
            ret, frame = cap.read()
            if not ret:
                print("Failed to read frame, exiting.")
                break
        except Exception as e:
            print(f"Error reading frame: {e}")
            break
        
        menu_positions = draw_menu_bar(frame)
        balls = detect_balls(frame)
        total_balls = len(balls)
        round_score = calculate_score(balls, POINT_ZONES)
        current_score = max(current_score, round_score)
        high_score = max(high_score, current_score)
        
        for (x, y, r) in balls:
            cv2.circle(frame, (x, y), r, (0, 255, 0), 2)
        
        for (x, y, r, points) in POINT_ZONES:
            cv2.circle(frame, (x, y), r, (0, 0, 255), 2)
            cv2.putText(frame, str(points), (x - 10, y), cv2.FONT_HERSHEY_SIMPLEX, 
                        0.5, (255, 255, 255), 2)
        
        cv2.putText(frame, f"Res: {width}x{height}", (frame.shape[1] - 150, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame, f"Balls: {total_balls}", (10, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(frame, f"Score: {current_score}", (10, 90), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        cv2.imshow(window_name, frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            save_high_score()
            print("Exiting program.")
            break
        elif key == ord('c'):
            ret, frame = cap.read()
            if not ret:
                print("Failed to read frame during recalibration.")
                break
            POINT_ZONES = setup_point_zones_in_main(frame, window_name)
            if POINT_ZONES:
                save_point_zones(POINT_ZONES)
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()