import cv2
import time
import numpy as np
from ball_tracker import BallTracker
from scoring_zones import ScoringZones
from zone_calibrator import ZoneCalibrator
from game_settings import GameSettings
from menu_system import MenuSystem
from leaderboard import Leaderboard
from initials_input import InitialsInput
from sound_manager import SoundManager
import pandas as pd
import os
import pickle
import sys

# Import picamera2 for Raspberry Pi Camera Module
try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except ImportError:
    PICAMERA_AVAILABLE = False
    print("Picamera2 not available. Falling back to OpenCV camera capture (may not work with Pi Camera).")

def resource_path(relative_path):
    """Get the absolute path to a resource, works for dev and for PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# ... (rest of your existing imports and functions like log_training_data, LabelingSession, etc.)

class Game:
    """Encapsulates the game logic, including camera, tracking, scoring, and menu handling."""
    def __init__(self):
        self.cap = None  # Will hold cv2.VideoCapture or Picamera2 instance
        self.use_picamera = PICAMERA_AVAILABLE  # Flag to determine which camera API to use
        self.current_width = 1280
        self.current_height = 720
        self.settings = GameSettings()
        self.sound_manager = SoundManager(self.settings)
        self.tracker = BallTracker()
        self.scoring_zones = ScoringZones(
            reference_width=self.current_width,
            reference_height=self.current_height,
            sound_manager=self.sound_manager
        )
        self.zone_calibrator = ZoneCalibrator(self.scoring_zones)
        self.menu = MenuSystem(self.scoring_zones, game_duration=120, sound_manager=self.sound_manager)
        self.leaderboard = Leaderboard()
        self.total_score = 0
        self.flip_horizontal = False
        self.debug = False
        self.full_processing = True
        self.initials_input = None

    def initialize_camera(self):
        """Initialize the camera with the specified resolution."""
        if self.use_picamera:
            print("Initializing Raspberry Pi Camera with Picamera2")
            try:
                # Initialize Picamera2
                self.cap = Picamera2()
                # Configure the camera for video capture
                config = self.cap.create_video_configuration(
                    main={"size": (self.current_width, self.current_height), "format": "RGB888"}
                )
                self.cap.configure(config)
                # Start the camera
                self.cap.start()
                print(f"Set base resolution to {self.current_width}x{self.current_height} using Picamera2")
            except Exception as e:
                self.cap = None
                raise RuntimeError(f"Failed to initialize Picamera2: {e}")
        else:
            print("Opening camera with DirectShow backend (fallback for non-Raspberry Pi systems)")
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
            if self.use_picamera and self.cap:
                self.cap.stop()
            else:
                self.cap.release()
            return

        # Capture the initial frame
        if self.use_picamera:
            frame = self.cap.capture_array()
            if frame is None:
                print("Error: Could not read initial frame using Picamera2.")
                self.cap.stop()
                return
        else:
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

                # Capture frame
                if self.use_picamera:
                    frame = self.cap.capture_array()
                    if frame is None:
                        print("Error: Could not read frame using Picamera2.")
                        break
                else:
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
                        if initials:
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

                # Always draw zones, unless the menu is active
                if not self.menu.is_menu_active():
                    if self.debug:
                        print(f"Drawing zones with current resolution {self.current_width}x{self.current_height}")
                    frame = self.scoring_zones.draw_zones(frame, self.current_width, self.current_height)
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
                    if self.use_picamera:
                        frame = self.cap.capture_array()
                    else:
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
                elif key == ord('q') and not self.menu.is_menu_active():
                    self.initials_input = InitialsInput(frame)
                    self.menu.timer_active = False
                elif self.menu.state == "game_over":
                    self.initials_input = InitialsInput(frame)

            except cv2.error as e:
                print(f"Error in game loop: {e}")
                break

        # Cleanup
        if self.use_picamera and self.cap:
            self.cap.stop()
        else:
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