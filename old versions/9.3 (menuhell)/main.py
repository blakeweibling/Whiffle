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
from menu_settings import MenuSettings
import os
import sys
import pygame
import warnings
from types import MethodType
from game_utils import resource_path, log_training_data, LabelingSession, save_labeled_data

# Suppress libpng warnings by redirecting stderr during image loading
import contextlib
import io

# Suppress OpenCV logging to reduce noise
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"
warnings.filterwarnings("ignore", message="iCCP: known incorrect sRGB profile")

class Game:
    def __init__(self):
        self.cap = None
        self.current_width = 1280
        self.current_height = 720
        self.settings = GameSettings()
        self.menu_settings = MenuSettings()
        self.sound_manager = SoundManager(self.menu_settings)
        self.tracker = BallTracker()
        self.scoring_zones = ScoringZones(
            reference_width=self.current_width,
            reference_height=self.current_height,
            sound_manager=self.sound_manager
        )
        self.zone_calibrator = ZoneCalibrator(self.scoring_zones)
        self.leaderboard = Leaderboard()
        self.menu = MenuSystem(self.scoring_zones, self.leaderboard, game_duration=120, sound_manager=self.sound_manager)
        self.menu.settings = self.menu_settings
        self.menu.mouse_callback = MethodType(MenuSystem.mouse_callback, self.menu)
        self.flip_horizontal = False
        self.debug = False
        self.full_processing = True
        self.initials_input = None
        self.use_still_image = False
        self.still_image = None
        self.is_splash_active = False
        self.splash_dissolve = False
        self.splash_alpha = 1.0
        self.splash_start_time = None
        # Add flag to track high score submission
        self.high_score_submitted = False
        # Mouse event variables
        self.mouse_event = None
        self.mouse_x = 0
        self.mouse_y = 0
        self.mouse_flags = 0
        # Track previous menu state for logging
        self.prev_menu_state = None
        self.prev_menu_active = None
        # Pre-load the splash image to minimize cv2.imread calls
        self.splash_img = None
        with contextlib.redirect_stderr(io.StringIO()):
            self.splash_img = cv2.imread(resource_path("splash.png"))
        if self.splash_img is None:
            print("Warning: Could not load splash.png. Splash screen will be skipped.")

    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events for the game."""
        self.mouse_event = event
        self.mouse_x = x
        self.mouse_y = y
        self.mouse_flags = flags
        self.menu.mouse_callback(event, x, y, flags, self)

    def initialize_camera(self):
        print("Opening camera with DirectShow backend")
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            print("Error: Could not open camera with index 0. Trying index 1...")
            self.cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                print("Warning: Could not open camera with index 0 or 1. Attempting to load a still image...")
                still_image_path = resource_path("last_frame.png")
                with contextlib.redirect_stderr(io.StringIO()):
                    self.still_image = cv2.imread(still_image_path)
                if self.still_image is None:
                    raise RuntimeError(f"Could not load still image from {still_image_path}.")
                print(f"Loaded still image from {still_image_path}")
                self.use_still_image = True
                self.current_width = self.still_image.shape[1]
                self.current_height = self.still_image.shape[0]
                print(f"Set resolution to {self.current_width}x{self.current_height} from still image")
                return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.current_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.current_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"Set base resolution to {self.current_width}x{self.current_height}")

    def show_splash(self, frame):
        if self.splash_img is None:
            print("Warning: Splash image not loaded. Proceeding without splash screen.")
            return

        splash_img = cv2.resize(self.splash_img, (self.current_width, self.current_height))
        display_duration = 4.0
        fade_duration = 0.5
        fade_steps = 50

        with contextlib.redirect_stderr(io.StringIO()):
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
        try:
            self.initialize_camera()
        except RuntimeError as e:
            print(f"Error initializing camera or loading still image: {e}")
            return

        cv2.namedWindow("Game", cv2.WINDOW_NORMAL)
        cv2.moveWindow("Game", 0, 0)
        cv2.setWindowProperty("Game", cv2.WND_PROP_VISIBLE, 1)
        cv2.setWindowProperty("Game", cv2.WND_PROP_AUTOSIZE, 0)
        cv2.resizeWindow("Game", self.current_width, self.current_height)
        cv2.setMouseCallback("Game", self.mouse_callback, self)

        if self.use_still_image:
            frame = self.still_image.copy()
        else:
            ret, frame = self.cap.read()
            if not ret:
                print("Error: Could not read initial frame.")
                self.cap.release()
                return

        frame = cv2.resize(frame, (self.current_width, self.current_height))
        self.show_splash(frame)

        print(f"Game started with initial score: {self.menu.total_score}")
        if self.tracker.model is None:
            print("Reminder: No CNN ball detector model loaded. Run train_ball_detector.py with labeled data to enable detection.")

        prev_frame_time = time.time()

        while True:
            frame_start_time = time.time()
            delta_time = frame_start_time - prev_frame_time
            prev_frame_time = frame_start_time

            if cv2.getWindowProperty("Game", cv2.WND_PROP_VISIBLE) < 1:
                print("Game window closed via 'X'. Exiting...")
                break

            if self.use_still_image:
                frame = self.still_image.copy()
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

            frame = cv2.resize(frame, (self.current_width, self.current_height))

            self.menu.update_timer()

            if self.is_splash_active and self.splash_img is not None:
                splash_img_resized = cv2.resize(self.splash_img, (self.current_width, self.current_height))
                if not self.splash_dissolve:
                    cv2.imshow("Game", splash_img_resized)
                    self.splash_start_time = time.time()
                    self.splash_dissolve = True
                    cv2.waitKey(1)
                    continue
                else:
                    elapsed = time.time() - self.splash_start_time
                    fade_duration = 0.5
                    if elapsed < fade_duration:
                        self.splash_alpha = 1.0 - (elapsed / fade_duration)
                        blended = frame.copy()
                        cv2.addWeighted(splash_img_resized, self.splash_alpha, frame, 1 - self.splash_alpha, 0, blended)
                        cv2.imshow("Game", blended)
                        cv2.waitKey(1)
                        continue
                    else:
                        self.is_splash_active = False
                        self.splash_dissolve = False
                        self.splash_alpha = 1.0

            if self.menu.confirmation_dialog:
                frame = self.menu.confirmation_dialog.draw(frame)
                cv2.imshow("Game", frame)
                key = cv2.waitKey(1) & 0xFF
                self.menu.confirmation_dialog.handle_key(key)
                if not self.menu.confirmation_dialog.is_active():
                    self.menu.restart_game()
                continue

            # Handle initials input for high score submission
            if self.initials_input:
                frame = self.initials_input.draw(frame)
                cv2.imshow("Game", frame)
                key = cv2.waitKey(1) & 0xFF
                self.initials_input.handle_key(key)
                if self.mouse_event is not None:
                    self.initials_input.handle_mouse(self.mouse_event, self.mouse_x, self.mouse_y)
                if self.initials_input.is_submitted():
                    initials = self.initials_input.get_initials()
                    if initials:
                        self.leaderboard.submit_score(initials, self.menu.total_score, self.menu.mode)
                    self.initials_input = None
                    self.high_score_submitted = True  # Mark high score as submitted
                    self.menu.set_state("closed")  # Transition out of game_over state
                    self.menu.timer_active = False
                    self.menu.is_game_in_progress = False
                continue

            # Process ball detection and scoring even when the menu is active
            if self.full_processing:
                balls = self.tracker.detect_balls(frame)
                filtered_balls = [
                    ball for ball in balls
                    if (ball[4] == "white" and self.menu_settings.config.white_ball_detection) or
                       (ball[4] == "red" and self.menu_settings.config.red_ball_detection) or
                       (ball[4] == "half" and (self.menu_settings.config.white_ball_detection or self.menu_settings.config.red_ball_detection))
                ]
                if filtered_balls:
                    self.tracker.update_physics(self.current_width, self.current_height, delta_time)
                frame = self.tracker.draw_balls(frame, self.current_width, self.current_height)
                frame_score = self.scoring_zones.check_scores(filtered_balls, self.current_width, self.current_height)
                self.menu.total_score += frame_score
                if frame_score > 0:
                    print(f"Adding {frame_score} to total score. New total: {self.menu.total_score}")

            # Only draw zones when the menu is not active
            if not self.menu.is_menu_active():
                frame = self.scoring_zones.draw_zones(frame, self.current_width, self.current_height)

            frame = self.menu.draw_menu_bar(frame)
            frame = self.menu.draw_menu(frame)

            current_state = self.menu.state
            current_active = self.menu.is_menu_active()
            if (current_state != self.prev_menu_state or current_active != self.prev_menu_active):
                print(f"After drawing menu - State: {current_state}, Menu Active: {current_active}")
                self.prev_menu_state = current_state
                self.prev_menu_active = current_active

            # Draw score text using the score from MenuSystem
            score_text = f"Score: {self.menu.total_score} (Mode: {self.menu.mode})"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            text_size = cv2.getTextSize(score_text, font, font_scale, thickness)[0]
            text_x = 10
            text_y = self.current_height - 10
            box_coords = ((text_x, text_y + 5), (text_x + text_size[0], text_y - text_size[1] - 5))
            cv2.rectangle(frame, box_coords[0], box_coords[1], (128, 128, 128), -1)
            cv2.putText(frame, score_text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)

            if self.menu.timer_active and not self.menu.is_menu_active():
                timer_text = self.menu.timer_text
                timer_size = cv2.getTextSize(timer_text, font, font_scale, thickness)[0]
                timer_x = self.current_width - timer_size[0] - 10
                timer_y = 20 + timer_size[1]
                timer_box_coords = ((timer_x - 5, timer_y + 5), (timer_x + timer_size[0] + 5, timer_y - timer_size[1] - 5))
                cv2.rectangle(frame, timer_box_coords[0], timer_box_coords[1], (128, 128, 128), -1)
                cv2.putText(frame, timer_text, (timer_x, timer_y), font, font_scale, (255, 255, 255), thickness)

            cv2.imshow("Game", frame)

            key = cv2.waitKey(1) & 0xFF
            if self.menu.handle_input(key):
                continue
            if key == ord('c'):
                if self.use_still_image:
                    calib_frame = self.still_image.copy()
                else:
                    ret, calib_frame = self.cap.read()
                    if not ret:
                        print("Error: Could not read frame during calibration.")
                        continue
                if self.flip_horizontal:
                    calib_frame = cv2.flip(calib_frame, 1)
                calib_frame = cv2.resize(calib_frame, (self.current_width, self.current_height))
                self.zone_calibrator.calibrate_zones(calib_frame, self.current_width, self.current_height)
            elif key == ord('r'):
                self.scoring_zones.reset_scored_balls()
                self.menu.total_score = 0  # Reset the menu's total score
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
                if self.menu.is_game_in_progress and not self.menu.timer_active:
                    self.menu.resume_game()
                self.full_processing = not self.full_processing
                print(f"Full processing mode: {self.full_processing}")
            elif key == ord('q') and not self.menu.is_menu_active():
                if not self.high_score_submitted:
                    self.initials_input = InitialsInput(frame)
                    self.menu.timer_active = False
            elif self.menu.state == "game_over" and not self.high_score_submitted:
                if not self.initials_input:  # Only create initials_input if it doesn't exist
                    self.initials_input = InitialsInput(frame)

        if not self.use_still_image:
            self.cap.release()
        cv2.destroyAllWindows()
        print("Program exited cleanly")

if __name__ == "__main__":
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            pygame.init()
            pygame.font.init()
            pygame.display.set_mode((1, 1), pygame.NOFRAME)
            print("Pygame video mode initialized successfully")
            game = Game()
            game.run()
        except Exception as e:
            print(f"Error: {e}")
            cv2.destroyAllWindows()
        finally:
            pygame.quit()