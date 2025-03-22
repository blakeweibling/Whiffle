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
from types import MethodType
from game_utils import resource_path, log_training_data, LabelingSession, save_labeled_data

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
        self.menu = MenuSystem(self.scoring_zones, game_duration=120, sound_manager=self.sound_manager)
        self.menu.mouse_callback = MethodType(MenuSystem.mouse_callback, self.menu)
        print(f"Initialized self.menu.mouse_callback: {self.menu.mouse_callback}")
        self.leaderboard = Leaderboard()
        self.total_score = 0
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

    def initialize_camera(self):
        print("Opening camera with DirectShow backend")
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            print("Error: Could not open camera with index 0. Trying index 1...")
            self.cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                print("Warning: Could not open camera with index 0 or 1. Attempting to load a still image...")
                still_image_path = resource_path("last_frame.png")
                self.still_image = cv2.imread(still_image_path)
                if self.still_image is None:
                    raise RuntimeError(f"Could not load still image from {still_image_path}. Please ensure the file exists.")
                print(f"Loaded still image from {still_image_path}")
                self.use_still_image = True
                self.current_width = self.still_image.shape[1]
                self.current_height = self.still_image.shape[0]
                print(f"Set resolution to {self.current_width}x{self.current_height} from still image")
                return

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
        try:
            self.initialize_camera()
        except RuntimeError as e:
            print(f"Error initializing camera or loading still image: {e}")
            return

        try:
            cv2.namedWindow("Game", cv2.WINDOW_NORMAL)
            cv2.moveWindow("Game", 0, 0)
            cv2.setWindowProperty("Game", cv2.WND_PROP_VISIBLE, 1)
            cv2.setWindowProperty("Game", cv2.WND_PROP_AUTOSIZE, 0)
            cv2.resizeWindow("Game", self.current_width, self.current_height)
            if not callable(self.menu.mouse_callback):
                print(f"Warning: self.menu.mouse_callback was {self.menu.mouse_callback}, resetting to method")
                self.menu.mouse_callback = MethodType(MenuSystem.mouse_callback, self.menu)
            print(f"Using self.menu.mouse_callback: {self.menu.mouse_callback}")
            try:
                cv2.setMouseCallback("Game", self.menu.mouse_callback, self)
                print("Mouse callback set successfully")
            except Exception as e:
                print(f"Error in cv2.setMouseCallback: {type(e).__name__}: {e}")
                raise
        except cv2.error as e:
            print(f"Error setting up game window: {e}")
            if not self.use_still_image:
                self.cap.release()
            return

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

        print(f"Game started with initial score: {self.total_score}")
        if self.tracker.model is None:
            print("Reminder: No CNN ball detector model loaded. Run train_ball_detector.py with labeled data to enable detection.")

        prev_frame_time = time.time()
        splash_img = cv2.imread(resource_path("splash.png"))
        if splash_img is not None:
            splash_img = cv2.resize(splash_img, (self.current_width, self.current_height))

        while True:
            try:
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

                if self.debug:
                    print(f"Zones in main loop: {self.scoring_zones.zones}")

                if self.is_splash_active and splash_img is not None:
                    if not self.splash_dissolve:
                        cv2.imshow("Game", splash_img)
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
                            cv2.addWeighted(splash_img, self.splash_alpha, frame, 1 - self.splash_alpha, 0, blended)
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

                if self.initials_input:
                    frame = self.initials_input.draw(frame)
                    cv2.imshow("Game", frame)
                    key = cv2.waitKey(1) & 0xFF
                    self.initials_input.handle_key(key)
                    self.initials_input.handle_mouse(event, x, y)  # Fixed to use mouse event
                    if self.initials_input.is_submitted():
                        initials = self.initials_input.get_initials()
                        if initials:
                            self.leaderboard.submit_score(initials, self.total_score, self.menu.mode)
                        self.initials_input = None
                        self.menu.timer_active = False
                    continue

                print(f"Processing conditions: full_processing={self.full_processing}, "
                      f"menu_active={self.menu.is_menu_active()}, timer_active={self.menu.timer_active}")
                if self.full_processing and not self.menu.is_menu_active():
                    balls = self.tracker.detect_balls(frame)
                    print(f"Detected balls: {balls}")
                    filtered_balls = [
                        ball for ball in balls
                        if (ball[4] == "white" and self.menu.settings.config.white_ball_detection) or
                           (ball[4] == "red" and self.menu.settings.config.red_ball_detection) or
                           (ball[4] == "half" and self.menu.settings.config.get('white_ball_detection', True))
                    ]
                    print(f"Filtered balls: {filtered_balls}")
                    if filtered_balls:
                        self.tracker.update_physics(self.current_width, self.current_height, delta_time)
                    frame = self.tracker.draw_balls(frame, self.current_width, self.current_height)
                    score = self.scoring_zones.check_scores(filtered_balls, self.current_width, self.current_height)
                    log_training_data(filtered_balls, self.scoring_zones, self.current_width, self.current_height, debug=self.debug)
                    self.total_score += score
                    self.menu.total_score = self.total_score
                    if score > 0:
                        print(f"Adding {score} to total score. New total: {self.total_score}")

                if not self.menu.is_menu_active():
                    if self.debug:
                        print(f"Drawing zones with current resolution {self.current_width}x{self.current_height}")
                    frame = self.scoring_zones.draw_zones(frame, self.current_width, self.current_height)
                    if self.debug and self.scoring_zones.zones:
                        print("Zones should now be drawn on the frame")

                frame = self.menu.draw_menu_bar(frame)
                frame = self.menu.draw_menu(frame)

                # Draw score text
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

                # Draw timer text during gameplay (when menu is not active)
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
                    try:
                        self.zone_calibrator.calibrate_zones(calib_frame, self.current_width, self.current_height)
                    except cv2.error as e:
                        print(f"Calibration error: {e}")
                elif key == ord('r'):
                    self.total_score = 0
                    self.scoring_zones.reset_scored_balls()
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
                    self.initials_input = InitialsInput(frame)
                    self.menu.timer_active = False
                elif self.menu.state == "game_over":
                    self.initials_input = InitialsInput(frame)

            except cv2.error as e:
                print(f"Error in game loop: {e}")
                break
            except Exception as e:
                print(f"Error: {e}")
                break

        if not self.use_still_image:
            self.cap.release()
        cv2.destroyAllWindows()
        print("Program exited cleanly")

if __name__ == "__main__":
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