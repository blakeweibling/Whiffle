# game.py
import cv2
import time
import numpy as np
from ball_tracker import BallTracker
from scoring_zones import ScoringZones
from zone_calibrator import ZoneCalibrator
from game_settings import GameSettings
from menu_system import MenuSystem
from leaderboard import Leaderboard
from initials_input import InitialsInput  # Import the new InitialsInput class
from sound_manager import SoundManager  # Import SoundManager
import pandas as pd
import os
import pickle
import sys  # Added for resource_path()

# Add resource_path() function to handle file paths for PyInstaller
def resource_path(relative_path):
    """Get the absolute path to a resource, works for dev and for PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores files there
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def log_training_data(balls, scoring_zones, current_width, current_height, filename="train_ball_detector.csv", debug=False):
    """Log training data for balls, including their position, type, and score."""
    # Update filename with resource_path()
    filename = resource_path(filename)
    
    data = []
    scale = min(current_width / 1920, current_height / 1080)
    for ball in balls:
        x, y, _, _, ball_type, _, ball_id = ball
        scaled_x = x * scale
        scaled_y = y * scale

        score = 0
        in_zone = False
        for zone_idx, zone in enumerate(scoring_zones.zones):
            points = zone[-1]
            if len(zone) == 4:  # Circle
                zx, zy, radius, _ = zone
                scaled_radius = radius * scale
                distance = np.sqrt((scaled_x - (zx * scale))**2 + (scaled_y - (zy * scale))**2)
                if distance <= scaled_radius:
                    in_zone = True
            else:  # Rectangle
                zx, zy, zw, zh, _ = zone
                scaled_zx = zx * scale
                scaled_zy = zy * scale
                scaled_zw = zw * scale
                scaled_zh = zh * scale
                if scaled_zx <= scaled_x <= scaled_x + scaled_zw and scaled_zy <= scaled_y <= scaled_zy + scaled_zh:
                    in_zone = True

            if in_zone:
                multiplier = 1.0
                if ball_type == "red":
                    multiplier = 2.0
                elif ball_type == "half":
                    multiplier = 1.5
                score = points * multiplier
                break

        data.append({
            "x": scaled_x,
            "y": scaled_y,
            "ball_type": ball_type,
            "score": score
        })

    df = pd.DataFrame(data)
    if os.path.exists(filename):
        df.to_csv(filename, mode='a', header=False, index=False)
    else:
        df.to_csv(filename, mode='w', header=True, index=False)
    if debug:
        print(f"Logged data to {filename}: {data}")

class LabelingSession:
    """Handles the labeling of balls in a frame for training data collection."""
    def __init__(self, frame):
        self.frame = frame.copy()
        self.labels = []  # List of (x, y, label) tuples
        self.current_label = None
        self.window_name = "Label Balls (r: red, w: white, h: half, b: background, s: skip)"
        print(f"Creating labeling window: {self.window_name}")
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.moveWindow(self.window_name, 0, 0)
        cv2.setWindowProperty(self.window_name, cv2.WND_PROP_VISIBLE, 1)
        cv2.setWindowProperty(self.window_name, cv2.WND_PROP_TOPMOST, 1)
        cv2.setMouseCallback(self.window_name, self.mouse_callback)

    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events for labeling balls."""
        if event == cv2.EVENT_LBUTTONDOWN and self.current_label is not None:
            self.labels.append((x, y, self.current_label))
            print(f"Labeled point at ({x}, {y}) as {self.current_label}")
            color = {
                "red": (0, 0, 255),
                "white": (255, 255, 255),
                "half": (0, 255, 255),
                "background": (0, 255, 0)
            }.get(self.current_label, (0, 255, 0))
            cv2.circle(self.frame, (x, y), 5, color, -1)
            cv2.imshow(self.window_name, self.frame)

    def run(self):
        """Run the labeling session, allowing the user to label balls."""
        while True:
            cv2.imshow(self.window_name, self.frame)
            key = cv2.waitKey(30) & 0xFF
            if key == ord('r'):
                self.current_label = "red"
                print("Labeling as red")
            elif key == ord('w'):
                self.current_label = "white"
                print("Labeling as white")
            elif key == ord('h'):
                self.current_label = "half"
                print("Labeling as half_red_white")
            elif key == ord('b'):
                self.current_label = "background"
                print("Labeling as background")
            elif key == ord('s'):
                self.current_label = None
                print("Skipping label")
            elif key == ord('q'):
                break
        cv2.destroyWindow(self.window_name)
        return self.labels

def save_labeled_data(frame, labels, filename="labeled_data.pkl"):
    """Save labeled data to a pickle file."""
    # Update filename with resource_path()
    filename = resource_path(filename)
    
    patch_size = 20
    data = []
    for x, y, label in labels:
        x_start = max(0, x - patch_size // 2)
        x_end = min(frame.shape[1], x + patch_size // 2)
        y_start = max(0, y - patch_size // 2)
        y_end = min(frame.shape[0], y + patch_size // 2)
        patch = frame[y_start:y_end, x_start:x_end]
        if patch.shape[0] > 0 and patch.shape[1] > 0:
            patch = cv2.resize(patch, (20, 20))
            data.append((patch, label))

    if os.path.exists(filename):
        with open(filename, "rb") as f:
            existing_data = pickle.load(f)
        data.extend(existing_data)

    try:
        with open(filename, "wb") as f:
            pickle.dump(data, f)
        print(f"Saved {len(data)} labeled patches to {filename}")
    except Exception as e:
        print(f"Error saving labeled data to {filename}: {e}")

class Game:
    """Encapsulates the game logic, including camera, tracking, scoring, and menu handling."""
    def __init__(self):
        self.cap = None
        self.current_width = 1280
        self.current_height = 720
        self.settings = GameSettings()
        # Initialize SoundManager with the settings
        self.sound_manager = SoundManager(self.settings)
        self.tracker = BallTracker()
        # Pass the SoundManager to ScoringZones
        self.scoring_zones = ScoringZones(
            reference_width=self.current_width,
            reference_height=self.current_height,
            sound_manager=self.sound_manager
        )
        self.zone_calibrator = ZoneCalibrator(self.scoring_zones)
        # Pass the SoundManager to MenuSystem
        self.menu = MenuSystem(self.scoring_zones, game_duration=120, sound_manager=self.sound_manager)
        self.leaderboard = Leaderboard()
        self.total_score = 0
        self.flip_horizontal = False
        self.debug = False
        self.full_processing = True
        self.initials_input = None  # Will hold the InitialsInput instance

    def initialize_camera(self):
        """Initialize the camera with the specified resolution."""
        print("Opening camera with DirectShow backend")
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            print("Error: Could not open camera with index 0. Trying index 1...")
            self.cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                raise RuntimeError("Could not open camera with index 0 or 1.")
        try:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.current_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.current_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"Set base resolution to {self.current_width}x{self.current_height}")
        except Exception as e:
            self.cap.release()
            raise RuntimeError(f"Failed to set camera properties: {e}")

    def show_splash(self, frame):
        """Display a splash screen with a fade-out effect."""
        # Update splash.png path with resource_path()
        splash_img = cv2.imread(resource_path("splash.png"))
        if splash_img is None:
            print("Warning: Could not load splash.png. Proceeding without splash screen.")
            return

        splash_img = cv2.resize(splash_img, (self.current_width, self.current_height))
        display_duration = 4.0
        fade_duration = 0.5
        fade_steps = 50

        start_time = time.time()
        while time.time() - start_time < display_duration:
            cv2.imshow("Game", splash_img)
            cv2.waitKey(1)

        for i in range(fade_steps + 1):
            alpha = 1.0 - (i / fade_steps)
            beta = 1.0 - alpha
            blended = frame.copy()
            cv2.addWeighted(splash_img, alpha, frame, beta, 0, blended)
            cv2.imshow("Game", blended)
            cv2.waitKey(int(1000 * fade_duration / fade_steps))

    def run(self):
        """Run the main game loop."""
        try:
            self.initialize_camera()
        except RuntimeError as e:
            print(f"Error initializing camera: {e}")
            return

        try:
            cv2.namedWindow("Game", cv2.WINDOW_NORMAL)
            cv2.moveWindow("Game", 0, 0)
            cv2.setWindowProperty("Game", cv2.WND_PROP_VISIBLE, 1)
            cv2.setWindowProperty("Game", cv2.WND_PROP_AUTOSIZE, 0)
            cv2.resizeWindow("Game", self.current_width, self.current_height)
            cv2.setMouseCallback("Game", self.menu.mouse_callback)
        except cv2.error as e:
            print(f"Error setting up game window: {e}")
            self.cap.release()
            return

        ret, frame = self.cap.read()
        if not ret:
            print("Error: Could not read initial frame.")
            self.cap.release()
            return

        frame = cv2.resize(frame, (self.current_width, self.current_height))
        self.show_splash(frame)

        print(f"Game started with initial score: {self.total_score}")
        if self.tracker.model is None:
            print("Reminder: No CNN ball detector model loaded. Run train_ball_detector.py with labeled data to enable detection.")

        while True:
            try:
                if cv2.getWindowProperty("Game", cv2.WND_PROP_VISIBLE) < 1:
                    print("Game window closed via 'X'. Exiting...")
                    break

                ret, frame = self.cap.read()
                if not ret:
                    print("Error: Could not read frame.")
                    break

                if self.flip_horizontal:
                    frame = cv2.flip(frame, 1)

                self.current_width = cv2.getWindowImageRect("Game")[2]
                self.current_height = cv2.getWindowImageRect("Game")[3]
                if self.current_width == 0 or self.current_height == 0:
                    self.current_width, self.current_height = 1280, 720

                # Resize frame once per loop
                frame = cv2.resize(frame, (self.current_width, self.current_height))

                self.menu.update_timer()

                # Debug: Print the current state of zones to verify they are loaded
                if self.debug:
                    print(f"Zones in main loop: {self.scoring_zones.zones}")

                # Handle initials input
                if self.initials_input:
                    frame = self.initials_input.draw(frame)
                    cv2.imshow("Game", frame)
                    key = cv2.waitKey(1) & 0xFF
                    self.initials_input.handle_key(key)
                    self.initials_input.handle_mouse(key, self.current_width // 2, self.current_height // 2)
                    if self.initials_input.is_submitted():
                        initials = self.initials_input.get_initials()
                        if initials:  # Only submit if initials were entered
                            self.leaderboard.submit_score(initials, self.total_score, self.menu.mode)
                        self.initials_input = None
                        self.menu.timer_active = False
                    continue

                # Game logic: Detect balls, update physics, and check scores
                if self.full_processing and not self.menu.is_menu_active() and self.menu.timer_active:
                    balls = self.tracker.detect_balls(frame, self.current_width, self.current_height)
                    filtered_balls = [
                        ball for ball in balls
                        if (ball[4] == "white" and self.menu.settings.config.white_ball_detection) or
                           (ball[4] == "red" and self.menu.settings.config.red_ball_detection) or
                           (ball[4] == "half" and self.menu.settings.config.get('white_ball_detection', True))
                    ]
                    if filtered_balls:
                        self.tracker.update_physics(self.current_width, self.current_height)
                    frame = self.tracker.draw_balls(frame, self.current_width, self.current_height)
                    score = self.scoring_zones.check_scores(filtered_balls, self.current_width, self.current_height)
                    log_training_data(filtered_balls, self.scoring_zones, self.current_width, self.current_height, debug=self.debug)
                    self.total_score += score
                    self.menu.total_score = self.total_score
                    if score > 0:
                        print(f"Adding {score} to total score. New total: {self.total_score}")

                # Always draw zones, unless the menu is active (to avoid cluttering the menu)
                if not self.menu.is_menu_active():
                    # Debug: Print before drawing zones to confirm the method is called
                    if self.debug:
                        print(f"Drawing zones with current resolution {self.current_width}x{self.current_height}")
                    frame = self.scoring_zones.draw_zones(frame, self.current_width, self.current_height)
                    # Debug: Verify that the frame has been modified (optional, can be removed if too verbose)
                    if self.debug and self.scoring_zones.zones:
                        print("Zones should now be drawn on the frame")

                frame = self.menu.draw_menu_bar(frame)
                frame = self.menu.draw_menu(frame)

                # Draw score at the bottom
                score_text = f"Score: {self.total_score} (Mode: {self.menu.mode})"
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.5
                thickness = 1
                text_size = cv2.getTextSize(score_text, font, font_scale, thickness)[0]
                text_x = 10
                text_y = self.current_height - 10
                box_coords = ((text_x, text_y + 5), (text_x + text_size[0], text_y - text_size[1] - 5))
                cv2.rectangle(frame, box_coords[0], box_coords[1], (128, 128, 128), -1)
                cv2.putText(frame, score_text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)

                cv2.imshow("Game", frame)

                key = cv2.waitKey(1) & 0xFF
                if self.menu.handle_input(key):
                    continue
                if key == ord('c'):
                    ret, calib_frame = self.cap.read()
                    if not ret:
                        print("Error: Could not read frame during calibration.")
                        continue
                    if self.flip_horizontal:
                        calib_frame = cv2.flip(calib_frame, 1)
                    calib_frame = cv2.resize(calib_frame, (self.current_width, self.current_height))
                    try:
                        self.zone_calibrator.calibrate_zones(calib_frame, self.current_width, self.current_height)
                    except cv2.error as e:
                        print(f"Calibration error: {e}")
                elif key == ord('r'):
                    self.total_score = 0
                    self.scoring_zones.scored_balls.clear()
                    print("Score reset to 0")
                elif key == ord('f'):
                    self.flip_horizontal = not self.flip_horizontal
                    print(f"Flip horizontal toggled to: {self.flip_horizontal}")
                elif key == ord('d'):
                    self.debug = not self.debug
                    self.tracker.debug = self.debug
                    self.scoring_zones.debug = self.debug
                    print(f"Debug mode toggled to: {self.debug}")
                elif key == ord('s'):
                    print("Capturing frame for labeling...")
                    labeling_session = LabelingSession(frame)
                    labels = labeling_session.run()
                    if labels:
                        save_labeled_data(frame, labels)
                    print("Labeling complete.")
                elif key == ord('p'):
                    self.full_processing = not self.full_processing
                    print(f"Full processing mode: {self.full_processing}")
                elif key == ord('q') and not self.menu.is_menu_active():  # Quit game and submit score
                    self.initials_input = InitialsInput(frame)
                    self.menu.timer_active = False
                elif self.menu.state == "game_over":  # Timed mode ended
                    self.initials_input = InitialsInput(frame)

            except cv2.error as e:
                print(f"Error in game loop: {e}")
                break

        self.cap.release()
        cv2.destroyAllWindows()
        print("Program exited cleanly")

if __name__ == "__main__":
    try:
        game = Game()
        game.run()
    except Exception as e:
        print(f"Error: {e}")
        cv2.destroyAllWindows()