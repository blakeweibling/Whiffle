"""
Game state management for the Whiffle Tracker project.
Defines the GameState class to manage game variables and state transitions.
"""

import cv2
import logging
import pygame
import time
import json
import os
import numpy as np
from typing import Optional, List, Tuple, Dict, Any, Callable
from enum import Enum

from constants import UIConstants, GameConstants
from detection import BallDetector
from tracking import BallTracker
from menu import load_zones
from leaderboard import Leaderboard
from player import Player
from achievement import Achievement
from scoring import is_in_scoring_zone

logger = logging.getLogger(__name__)

class MenuState(Enum):
    CLOSED = "closed"
    MAIN = "main"
    SUBMENU = "submenu"

class GameState:
    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        self.cap: Optional[cv2.VideoCapture] = cv2.VideoCapture(0)
        self.camera_available: bool = True
        self.static_frame: Optional[np.ndarray] = None

        # Attempt to set camera properties and check resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, UIConstants.WINDOW_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, UIConstants.WINDOW_HEIGHT)
        width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if width != UIConstants.WINDOW_WIDTH or height != UIConstants.WINDOW_HEIGHT:
            logger.warning(f"Camera resolution {width}x{height} does not match {UIConstants.WINDOW_WIDTH}x{UIConstants.WINDOW_HEIGHT}")
        logger.info(f"Camera resolution: {width}x{height}")

        if not self.cap.isOpened():
            logger.error("Failed to open camera, attempting to load static image")
            self.camera_available = False
            self.static_frame = cv2.imread("last_frame.png")
            if self.static_frame is None:
                logger.error("Failed to load last_frame.png, cannot proceed without camera or static image")
                raise RuntimeError("Camera initialization failed and no static image available")
            # Validate the static frame dimensions and type
            if self.static_frame.shape[0] == 0 or self.static_frame.shape[1] == 0:
                logger.error("last_frame.png has invalid dimensions (height or width is 0)")
                raise RuntimeError("Invalid static image dimensions")
            if len(self.static_frame.shape) != 3 or self.static_frame.shape[2] != 3:
                logger.error("last_frame.png is not a 3-channel BGR image")
                raise RuntimeError("Invalid static image format (must be 3-channel BGR)")
            self.static_frame = cv2.resize(self.static_frame, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
            logger.info("Loaded static image last_frame.png as fallback")

        self.score: int = 0  # Managed by Player class
        self.high_score: int = 0
        self.scoring_zones: List[Tuple[int, int, int, int, int]] = []
        self.tracked_balls: List[Tuple[int, int, float, int, int, str]] = []  # (x, y, radius, ball_id, frame_count, ball_type)
        self.scored_balls: set = set()  # Tracks ball_ids that have scored
        self.scored_positions: Dict[Tuple[int, int], int] = {}  # Tracks (x, y) positions that have scored
        self.ball_scored_zones: Dict[int, int] = {}  # Tracks ball_id -> zone_id where it last scored
        self.ball_positions_history: Dict[int, List[Tuple[int, int]]] = {}  # Tracks ball_id -> list of (x, y) positions over recent frames
        self.potential_small_balls_white: Dict[Tuple[int, int], Tuple[int, int]] = {}  # Used by new detection.py
        self.potential_small_balls_red: Dict[Tuple[int, int], Tuple[int, int]] = {}  # Used by new detection.py
        self.next_ball_id: int = 0
        self.frame_count: int = 0
        self.balls_in_zone: Dict[int, Optional[Tuple[int, int, int, int, int]]] = {}
        self.time_limit: int = GameConstants.DEFAULT_TIME_LIMIT
        self.game_timer: Optional[float] = None
        self.start_time: Optional[float] = None
        self.ball_trails: Dict[int, List[Tuple[int, int, int]]] = {}
        self.scored_cooldown: Dict[int, int] = {}  # ball_id -> frames remaining for cooldown

        # Add ball_states and previous_ball_states for state tracking
        self.ball_states: Dict[int, str] = {}  # ball_id -> state (on_playfield or in_hole)
        self.previous_ball_states: Dict[int, str] = {}  # ball_id -> previous state for transition detection

        # Special hole tracking
        self.special_hole: Optional[Tuple[int, int, int, int, int]] = None  # The designated special hole
        self.special_hole_scored: bool = False  # Tracks if a ball has landed in the special hole

        # Game mode: "classic" or "timed"
        self.game_mode: str = "classic"  # Default to classic mode (no timer)

        # HSV ranges for ball detection
        self.white_hsv_min = (0, 0, 100)
        self.white_hsv_max = (179, 100, 255)
        self.red_hsv_min = (0, 100, 100)    # Adjusted for broader red detection
        self.red_hsv_max = (10, 255, 255)
        self.red_hsv_min2 = (170, 100, 100) # Adjusted for broader red detection
        self.red_hsv_max2 = (179, 255, 255)

        self._load_hsv_ranges()
        self.red_hsv_calibrated: bool = False

        # Calibration mode state
        self.calibrating_color: Optional[str] = None
        self.calibration_point: Optional[Tuple[int, int]] = None
        self.calibration_hsv: Optional[Tuple[int, int, int]] = None

        # Multiplayer support
        self.players: List[Player] = [Player("Player 1")]
        self.current_player_index: int = 0

        # Achievements support
        self.achievements: List[Achievement] = []
        self.achievement_notification: Optional[str] = None
        self.achievement_notification_timer: float = 0
        self._initialize_achievements()
        self._load_achievements()

        self.score_sound: Optional[pygame.mixer.Sound] = None
        self.background_music: Optional[pygame.mixer.Sound] = None
        self._initialize_sounds()

        self.leaderboard: Leaderboard = Leaderboard(supabase_url, supabase_key)

        self.game_sounds_on: bool = True
        self.background_music_on: bool = True
        self.ball_tracking_on: bool = True  # New setting to enable/disable ball tracking

        self.toggle_background_music()

        self.drawing: bool = False
        self.start_x: int = -1
        self.start_y: int = -1
        self.temp_zone: Optional[Tuple[int, int, int]] = None
        self.drawing_mode: bool = False

        self.menu_state: MenuState = MenuState.CLOSED
        self.submenu_active: Optional[str] = None
        self.menu_items: List[Tuple[int, int, int, int, str, Optional[Callable[[], None]]]] = [
            (10, 140, 60, 30, "File", None),
            (90, 140, 80, 30, "Players", None),
            (190, 140, 80, 30, "Settings", None),
            (290, 140, 80, 30, "Game Mode", None),  # Added Game Mode menu item
            (390, 140, 60, 30, "Help", None),
            (470, 140, 60, 30, "About", None),
            (550, 140, 100, 30, "Leaderboard", None),
            (670, 140, 100, 30, "Achievements", None)
        ]
        self.submenu_items: List[Any] = []
        self.menu_width: int = UIConstants.MENU_WIDTH
        self.menu_height: int = UIConstants.MENU_HEIGHT
        self.menu_pos_x: int = (UIConstants.WINDOW_WIDTH - self.menu_width) // 2
        self.menu_pos_y: int = (UIConstants.WINDOW_HEIGHT - self.menu_height) // 2
        self.dragging_menu: bool = False
        self.drag_start_x: int = 0
        self.drag_start_y: int = 0
        self.menu_active: bool = False

        self.debug_mode: bool = True  # Enabled to get profiling logs
        logger.info("Debug mode enabled for profiling")

        # Toggle for displaying scoring zones (green rectangles)
        self.show_scoring_zones: bool = True  # Toggle to show/hide scoring zones display

        # Flag to track if the red ball has scored in the current game session
        self.red_ball_scored: bool = False  # Tracks if the red ball has scored

        # Add scored_zones for tracking which zones have been scored in
        self.scored_zones: set = set()

        # Pass self as game_state to load_zones
        self.scoring_zones = load_zones(self.scoring_zones, self)
        # Sort scoring zones by area (smallest to largest) to prioritize smaller zones
        self.scoring_zones.sort(key=lambda zone: zone[2] * zone[3])
        logger.info(f"Sorted scoring zones by area: {self.scoring_zones}")
        self._initialize_balls_in_zone()

        # Initialize the special hole after loading scoring zones
        self._set_special_hole()

    def _set_special_hole(self) -> None:
        """Identify the leftmost scoring zone as the special hole."""
        if not self.scoring_zones:
            self.special_hole = None
            logger.info("No scoring zones available, special hole not set")
            return

        # Find the leftmost zone (lowest x-coordinate)
        self.special_hole = min(self.scoring_zones, key=lambda zone: zone[0])
        logger.info(f"Special hole set to leftmost zone: {self.special_hole}")

    def _initialize_sounds(self) -> None:
        pygame.mixer.init()
        try:
            self.score_sound = pygame.mixer.Sound("ding.wav")
        except pygame.error as e:
            logger.error(f"Failed to load score sound (ding.wav): {e}")
            self.game_sounds_on = False
        try:
            self.background_music = pygame.mixer.Sound("background_music.mp3")
            self.background_music.set_volume(GameConstants.DEFAULT_MUSIC_VOLUME)
        except pygame.error as e:
            logger.error(f"Failed to load background music (background_music.mp3): {e}")
            self.background_music_on = False

    def _initialize_balls_in_zone(self) -> None:
        if not self.ball_tracking_on:
            logger.info("Ball tracking is disabled, skipping initial ball detection")
            return

        if self.camera_available:
            ret, frame = self.cap.read()
            if not ret:
                logger.error("Failed to read initial frame for ball initialization")
                return
        else:
            frame = self.static_frame
            logger.info("Using static frame for ball initialization")

        detector = BallDetector()
        white_balls, red_balls, half_balls = detector.detect_all_balls(
            frame, self.frame_count, self, scoring_zones=self.scoring_zones, debug_mode=self.debug_mode
        )
        tracker = BallTracker()
        tracked_detected_balls, self.next_ball_id = tracker.track_balls(
            white_balls, red_balls, half_balls, self.tracked_balls, self.next_ball_id,
            self.frame_count, self.scored_positions, self.debug_mode
        )
        self.tracked_balls = [(x, y, radius, ball_id, self.frame_count, ball_type)
                              for x, y, radius, ball_id, ball_type in tracked_detected_balls]
        for x, y, radius, ball_id, _, ball_type in self.tracked_balls:
            ball = (x, y, radius, ball_id)
            for zone in self.scoring_zones:
                if is_in_scoring_zone(ball, zone):
                    self.balls_in_zone[ball_id] = zone
                    self.ball_states[ball_id] = "in_hole"
                    self.previous_ball_states[ball_id] = "on_playfield"  # Allow scoring on transition
                    if self.debug_mode:
                        logger.info(f"Ball ID {ball_id} at ({x}, {y}) already in zone {zone} at startup")
                    break
            if ball_id not in self.balls_in_zone:
                self.balls_in_zone[ball_id] = None
                self.ball_states[ball_id] = "on_playfield"
                self.previous_ball_states[ball_id] = "on_playfield"
        if self.debug_mode:
            logger.debug(f"Initialized balls in zones: {self.balls_in_zone}")

    def _initialize_achievements(self) -> None:
        self.achievements = [
            Achievement("First Score", "Score your first points", lambda gs: gs.get_current_player().score >= 100),
            Achievement("High Roller", "Score 1000 points in one game", lambda gs: gs.get_current_player().score >= 1000),
            Achievement("Zone Master", "Create 5 scoring zones", lambda gs: len(gs.scoring_zones) >= 5),
            Achievement("Marathon", "Play 10 games", lambda gs: gs.get_current_player().games_played >= 10)
        ]

    def _load_achievements(self) -> None:
        try:
            if os.path.exists("achievements.json"):
                with open("achievements.json", "r", encoding='utf-8') as f:
                    data = json.load(f)
                    for achievement in self.achievements:
                        if achievement.name in data and data[achievement.name]["unlocked"]:
                            achievement.unlocked = True
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load achievements: {e}")

    def _save_achievements(self) -> None:
        try:
            data = {a.name: {"unlocked": a.unlocked} for a in self.achievements}
            with open("achievements.json", "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except (IOError, PermissionError) as e:
            logger.error(f"Failed to save achievements: {e}")

    def _load_hsv_ranges(self) -> None:
        hsv_file = "hsv_ranges.json"
        if os.path.exists(hsv_file):
            try:
                with open(hsv_file, "r", encoding='utf-8') as f:
                    data = json.load(f)
                    if "white_hsv_min" in data and "white_hsv_max" in data:
                        self.white_hsv_min = tuple(data["white_hsv_min"])
                        self.white_hsv_max = tuple(data["white_hsv_max"])
                        logger.info(f"Loaded white ball HSV ranges: min={self.white_hsv_min}, max={self.white_hsv_max}")
                    if all(k in data for k in ["red_hsv_min", "red_hsv_max", "red_hsv_min2", "red_hsv_max2"]):
                        self.red_hsv_min = tuple(data["red_hsv_min"])
                        self.red_hsv_max = tuple(data["red_hsv_max"])
                        self.red_hsv_min2 = tuple(data["red_hsv_min2"])
                        self.red_hsv_max2 = tuple(data["red_hsv_max2"])
                        self.red_hsv_calibrated = True
                        logger.info(f"Loaded red ball HSV ranges: min={self.red_hsv_min}, max={self.red_hsv_max}, "
                                    f"min2={self.red_hsv_min2}, max2={self.red_hsv_max2}")
            except (json.JSONDecodeError, IOError, KeyError) as e:
                logger.error(f"Failed to load HSV ranges from {hsv_file}: {e}")
        else:
            logger.info(f"{hsv_file} does not exist, using default HSV ranges")

    def _save_hsv_ranges(self) -> None:
        hsv_file = "hsv_ranges.json"
        data = {
            "white_hsv_min": [int(val) for val in self.white_hsv_min],
            "white_hsv_max": [int(val) for val in self.white_hsv_max],
            "red_hsv_min": [int(val) for val in self.red_hsv_min],
            "red_hsv_max": [int(val) for val in self.red_hsv_max],
            "red_hsv_min2": [int(val) for val in self.red_hsv_min2],
            "red_hsv_max2": [int(val) for val in self.red_hsv_max2]
        }
        try:
            with open(hsv_file, "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            self.red_hsv_calibrated = True
            logger.info(f"Saved HSV ranges to {hsv_file}")
        except (IOError, PermissionError) as e:
            logger.error(f"Failed to save HSV ranges to {hsv_file}: {e}")

    def get_current_player(self) -> Player:
        return self.players[self.current_player_index]

    def switch_player(self) -> None:
        current_player = self.get_current_player()
        # Apply the special hole multiplier before saving
        final_score = current_player.score
        if self.special_hole_scored:
            final_score *= 2
            logger.info(f"Special hole scored, doubling score from {current_player.score} to {final_score}")
        self.save_score(current_player.name, mode=self.game_mode)  # Use current game mode
        current_player.reset_score()
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        self.scored_balls.clear()
        self.scored_positions.clear()
        self.ball_scored_zones.clear()  # Clear scored zones on player switch
        self.ball_positions_history.clear()  # Clear position history on player switch
        self.tracked_balls.clear()
        self.balls_in_zone.clear()
        self.ball_trails.clear()
        self.potential_small_balls_white.clear()
        self.potential_small_balls_red.clear()
        self.scored_cooldown.clear()
        self.red_ball_scored = False
        self.ball_states.clear()
        self.previous_ball_states.clear()
        # Reset the special hole scored flag for the new player
        self.special_hole_scored = False
        # Reset the timer for the new player if in timed mode
        if self.game_mode == "timed":
            self.game_timer = self.time_limit
            self.start_time = time.time()
        logger.info(f"Switched to player: {self.get_current_player().name}")

    def add_player(self, name: str) -> None:
        self.players.append(Player(name))
        logger.info(f"Added player: {name}")

    def set_game_mode(self, mode: str) -> None:
        """Set the game mode and reset the timer if switching to timed mode."""
        if mode not in ["classic", "timed"]:
            logger.warning(f"Invalid game mode '{mode}', defaulting to 'classic'")
            mode = "classic"
        self.game_mode = mode
        if mode == "timed":
            self.game_timer = self.time_limit
            self.start_time = time.time()
            logger.info("Switched to timed mode, timer started at 120 seconds")
        else:
            self.game_timer = None
            self.start_time = None
            logger.info("Switched to classic mode, timer disabled")

    def check_achievements(self) -> None:
        for achievement in self.achievements:
            if achievement.check(self):
                self.achievement_notification = f"Achievement Unlocked: {achievement.name}"
                self.achievement_notification_timer = 3.0
                self._save_achievements()
                if self.game_sounds_on and self.score_sound:
                    self.score_sound.play()
                logger.info(f"Achievement unlocked: {achievement.name}")

    def update_achievement_notification(self, delta_time: float) -> None:
        if self.achievement_notification:
            self.achievement_notification_timer -= delta_time
            if self.achievement_notification_timer <= 0:
                self.achievement_notification = None
                self.achievement_notification_timer = 0

    def load_high_score(self) -> None:
        scores, _ = self.leaderboard.get_top_scores("classic", 1)
        self.high_score = scores[0]["score"] if scores else 0

    def save_score(self, player_name: str, mode: str = "classic") -> None:
        current_player = self.get_current_player()
        # Apply the special hole multiplier if applicable
        final_score = current_player.score
        if self.special_hole_scored:
            final_score *= 2
            logger.info(f"Special hole scored, doubling score from {current_player.score} to {final_score}")
        self.leaderboard.submit_score(player_name, final_score, mode)
        if final_score > self.high_score:
            self.high_score = final_score

    def toggle_background_music(self) -> None:
        if self.background_music is None:
            logger.warning("Background music not loaded, skipping toggle")
            return
        if self.background_music_on:
            if not pygame.mixer.get_busy():
                self.background_music.play(-1)
        else:
            self.background_music.stop()

    def update_timer(self) -> None:
        if self.game_mode != "timed":
            return  # Only update timer in timed mode
        if self.game_timer is not None and self.start_time is not None:
            elapsed = time.time() - self.start_time
            self.game_timer = max(0, self.time_limit - elapsed)

    def _is_ball_at_rest(self, ball_id: int, x: int, y: int) -> bool:
        """
        Determine if a ball has come to rest by checking its movement over recent frames.

        Args:
            ball_id: The ID of the ball to check.
            x: Current x-coordinate of the ball.
            y: Current y-coordinate of the ball.

        Returns:
            bool: True if the ball is at rest, False otherwise.
        """
        # Constants for movement tracking
        HISTORY_LENGTH = 5  # Number of frames to track
        MOVEMENT_THRESHOLD = 5.0  # Maximum distance (in pixels) to consider the ball at rest

        # Update the position history for this ball
        if ball_id not in self.ball_positions_history:
            self.ball_positions_history[ball_id] = []
        self.ball_positions_history[ball_id].append((x, y))

        # Keep only the last HISTORY_LENGTH positions
        if len(self.ball_positions_history[ball_id]) > HISTORY_LENGTH:
            self.ball_positions_history[ball_id] = self.ball_positions_history[ball_id][-HISTORY_LENGTH:]

        # If we don't have enough history to determine movement, assume the ball is not at rest
        if len(self.ball_positions_history[ball_id]) < HISTORY_LENGTH:
            if self.debug_mode:
                logger.debug(f"Ball ID {ball_id} at ({x}, {y}) does not have enough history ({len(self.ball_positions_history[ball_id])}/{HISTORY_LENGTH}) to determine if at rest")
            return False

        # Calculate the total movement over the history
        positions = self.ball_positions_history[ball_id]
        first_x, first_y = positions[0]
        last_x, last_y = positions[-1]
        distance = np.sqrt((last_x - first_x) ** 2 + (last_y - first_y) ** 2)

        if self.debug_mode:
            logger.debug(f"Ball ID {ball_id} movement over {HISTORY_LENGTH} frames: {distance:.2f} pixels (threshold: {MOVEMENT_THRESHOLD})")

        return distance < MOVEMENT_THRESHOLD

    def update_score(self, frame: np.ndarray, tracked_detected_balls: List[Tuple[int, int, float, int, str]]) -> None:
        """
        Update the score based on detected balls, scoring only when a ball comes to rest in a zone.
        """
        logger.debug("Updating score")

        # Log all tracked balls' positions for debugging
        logger.info(f"Tracked balls in frame {self.frame_count}: {[(x, y, ball_type, ball_id) for x, y, _, ball_id, ball_type in tracked_detected_balls]}")

        # Update ball states and balls_in_zone based on current positions
        for x, y, radius, ball_id, ball_type in tracked_detected_balls:
            ball = (x, y, radius, ball_id)
            # Use is_in_scoring_zone to determine if the ball is in a zone
            current_zone = None
            for zone in self.scoring_zones:
                if is_in_scoring_zone(ball, zone):
                    current_zone = zone
                    break

            # Update balls_in_zone and ball_states
            previous_zone = self.balls_in_zone.get(ball_id)
            self.balls_in_zone[ball_id] = current_zone
            state = "in_hole" if current_zone else "on_playfield"
            self.ball_states[ball_id] = state

            if self.debug_mode:
                logger.debug(f"Ball ID {ball_id} at ({x}, {y}) type: {ball_type}, state: {state}, current_zone: {current_zone}, previous_zone: {previous_zone}")

            # Score the ball if it's in a scoring zone, hasn't scored in this zone before, and is at rest
            if current_zone:
                current_zone_id = id(current_zone)
                last_scored_zone_id = self.ball_scored_zones.get(ball_id)

                # Check if the ball is at rest
                if self._is_ball_at_rest(ball_id, x, y):
                    # Score if the ball hasn't scored in this zone before
                    if last_scored_zone_id != current_zone_id:
                        current_player = self.get_current_player()
                        points = current_zone[4]
                        if ball_type == "red":
                            points *= 2
                            self.red_ball_scored = True
                        elif ball_type == "half":
                            points *= 1.5
                        current_player.add_score(points)
                        self.scored_balls.add(ball_id)
                        self.scored_positions[(x, y)] = ball_id
                        self.ball_scored_zones[ball_id] = current_zone_id
                        self.scored_zones.add(current_zone_id)
                        if self.game_sounds_on and self.score_sound:
                            self.score_sound.play()
                        logger.info(f"{ball_type} ball ID {ball_id} at ({x}, {y}) scored {points} points in zone {current_zone}")
                    else:
                        if self.debug_mode:
                            logger.debug(f"Ball ID {ball_id} ({ball_type}) is in zone {current_zone} but already scored in this zone")
                else:
                    if self.debug_mode:
                        logger.debug(f"Ball ID {ball_id} ({ball_type}) is in zone {current_zone} but is still moving, not scoring yet")
            else:
                # If the ball is no longer in a scoring zone, clear its scored zone to allow re-scoring
                if ball_id in self.ball_scored_zones:
                    logger.debug(f"Ball ID {ball_id} ({ball_type}) is no longer in a scoring zone, clearing scored zone")
                    del self.ball_scored_zones[ball_id]
                if ball_id in self.scored_balls:
                    logger.debug(f"Ball ID {ball_id} ({ball_type}) is no longer in a scoring zone, removing from scored_balls")
                    self.scored_balls.remove(ball_id)
                if (x, y) in self.scored_positions:
                    del self.scored_positions[(x, y)]

        # Clean up balls_in_zone and other dictionaries to remove balls that are no longer tracked
        current_ball_ids = {ball[3] for ball in self.tracked_balls}
        self.balls_in_zone = {ball_id: zone for ball_id, zone in self.balls_in_zone.items() if ball_id in current_ball_ids}
        self.ball_states = {ball_id: state for ball_id, state in self.ball_states.items() if ball_id in current_ball_ids}
        self.ball_scored_zones = {ball_id: zone_id for ball_id, zone_id in self.ball_scored_zones.items() if ball_id in current_ball_ids}
        self.ball_positions_history = {ball_id: positions for ball_id, positions in self.ball_positions_history.items() if ball_id in current_ball_ids}
        self.tracked_balls = [(x, y, radius, ball_id, self.frame_count, ball_type)
                              for x, y, radius, ball_id, ball_type in tracked_detected_balls]