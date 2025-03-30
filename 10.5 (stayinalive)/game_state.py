"""
Game state management for the Whiffle Tracker project.
Defines the GameState class to manage game variables and state transitions.
"""

import cv2
import logging
import pygame
import time
import numpy as np
from typing import Optional, List, Tuple, Dict, Any, Callable
from enum import Enum

from constants import UIConstants, GameConstants
from detection import BallDetector
from tracking import BallTracker
from menu import load_zones
from leaderboard import Leaderboard
from player import Player
from scoring import is_in_scoring_zone
from game_state_utils import (
    set_special_hole,
    initialize_sounds,
    initialize_balls_in_zone,
    initialize_achievements,
    load_achievements,
    save_achievements,
    load_hsv_ranges,
    save_hsv_ranges,
    is_ball_at_rest,
    is_ball_zone_stable
)

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
        self.ball_zone_history: Dict[int, List[Optional[int]]] = {}  # Tracks ball_id -> list of zone_ids over recent frames
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
        (self.white_hsv_min, self.white_hsv_max, self.red_hsv_min, self.red_hsv_max,
         self.red_hsv_min2, self.red_hsv_max2, self.red_hsv_calibrated) = load_hsv_ranges()

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
        self.achievements = initialize_achievements()
        load_achievements(self.achievements)

        # Sound initialization
        (self.score_sound, self.background_music, self.game_sounds_on,
         self.background_music_on) = initialize_sounds()

        self.leaderboard: Leaderboard = Leaderboard(supabase_url, supabase_key)

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

        self.debug_mode: bool = False  # Changed to False to disable debug logging by default
        if self.debug_mode:
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

        # Initialize balls in zones
        self.tracked_balls, self.next_ball_id = initialize_balls_in_zone(
            self.camera_available, self.cap, self.static_frame, self.frame_count,
            self.scoring_zones, self.ball_tracking_on, self.tracked_balls,
            self.next_ball_id, self.scored_positions, self.debug_mode,
            self.balls_in_zone, self.ball_states, self.previous_ball_states
        )

        # Initialize the special hole after loading scoring zones
        self.special_hole = set_special_hole(self.scoring_zones)

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
        self.ball_zone_history.clear()  # Clear zone history on player switch
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
                save_achievements(self.achievements)
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

    def update_score(self, frame: np.ndarray, tracked_detected_balls: List[Tuple[int, int, float, int, str]]) -> None:
        """
        Update the score based on detected balls, scoring only when a ball comes to rest and has been stable in a zone.
        """
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

            # Score the ball if it's in a scoring zone, hasn't scored in this zone before, is at rest, and has been stable in the zone
            if current_zone:
                current_zone_id = id(current_zone)
                last_scored_zone_id = self.ball_scored_zones.get(ball_id)

                # Check if the ball is at rest and stable in the current zone
                is_at_rest = is_ball_at_rest(ball_id, x, y, self.ball_positions_history, self.debug_mode)
                is_zone_stable = is_ball_zone_stable(ball_id, current_zone, self.ball_zone_history, self.debug_mode)

                if is_at_rest and is_zone_stable:
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
                # If the ball is no longer in a scoring zone, clear its scored zone to allow re-scoring
                if ball_id in self.ball_scored_zones:
                    del self.ball_scored_zones[ball_id]
                if ball_id in self.scored_balls:
                    self.scored_balls.remove(ball_id)
                if (x, y) in self.scored_positions:
                    del self.scored_positions[(x, y)]

        # Clean up balls_in_zone and other dictionaries to remove balls that are no longer tracked
        current_ball_ids = {ball[3] for ball in self.tracked_balls}
        self.balls_in_zone = {ball_id: zone for ball_id, zone in self.balls_in_zone.items() if ball_id in current_ball_ids}
        self.ball_states = {ball_id: state for ball_id, state in self.ball_states.items() if ball_id in current_ball_ids}
        self.ball_scored_zones = {ball_id: zone_id for ball_id, zone_id in self.ball_scored_zones.items() if ball_id in current_ball_ids}
        self.ball_positions_history = {ball_id: positions for ball_id, positions in self.ball_positions_history.items() if ball_id in current_ball_ids}
        self.ball_zone_history = {ball_id: zones for ball_id, zones in self.ball_zone_history.items() if ball_id in current_ball_ids}
        self.tracked_balls = [(x, y, radius, ball_id, self.frame_count, ball_type)
                              for x, y, radius, ball_id, ball_type in tracked_detected_balls]