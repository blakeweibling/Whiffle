# game_state.py

import logging
import random
from typing import Any, Dict, List, Optional, Tuple, Union  # Keep existing imports

import cv2
import numpy as np
import pygame

# Import constants consistently
from constants import GameConstants, UIConstants

# Import necessary components
from detection import BallDetector

# Import effects for Fun Mode
from effects import BallTrail, Explosion

# Import utility functions (ensure load_background_music is imported if still used here, check game_state_utils)
from game_state_utils import (
    initialize_achievements,
    initialize_sounds,
    load_achievements,
    load_hsv_ranges,
    load_initial_state,
    load_settings,
    set_volume,
    load_background_music,
)  # Added load_background_music back if used here

# Import types/enums from new location
from game_types import CurrentGameState
from leaderboard import Leaderboard
from player import Player
from tracking import BallTracker

# --- >>> ADDED: Import DataLogger <<< ---
try:
    from data_logger import DataLogger
except ImportError:
    logger.error(
        "Failed to import DataLogger. Stats functionality will be unavailable."
    )
    DataLogger = None
# --- >>> END ADDED <<< ---

logger = logging.getLogger(__name__)


class GameState:

    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        logger.info("Starting GameState initialization...")

        # --- >>> ADDED: Initialize DataLogger <<< ---
        if DataLogger:
            self.data_logger: Optional[DataLogger] = DataLogger()
        else:
            self.data_logger: Optional[DataLogger] = None
        # Holds calculated stats for the *current* session, computed just before display
        self.current_session_stats: Optional[Dict[str, Any]] = None
        # --- >>> END ADDED <<< ---

        # Initial Volume Levels & Flags (Defaults, overwritten by load_settings)
        self.current_sound_volume: float = GameConstants.INITIAL_SOUND_VOLUME
        self.current_music_volume: float = GameConstants.INITIAL_MUSIC_VOLUME
        self.game_sounds_on: bool = True
        self.background_music_on: bool = True

        # Camera Initialization
        self.camera_available: bool = GameConstants.USE_CAMERA
        self.static_frame: Optional[np.ndarray] = None
        if self.camera_available:
            logger.info(
                f"Attempting camera {GameConstants.CAMERA_INDEX} w/ backend {GameConstants.CAMERA_BACKEND}"
            )
            self.cap: Optional[cv2.VideoCapture] = cv2.VideoCapture(
                GameConstants.CAMERA_INDEX, GameConstants.CAMERA_BACKEND)
            if not self.cap or not self.cap.isOpened():
                logger.error("Failed to open camera.")
                self.camera_available = False
                self.cap = None
            else:
                logger.info("Setting camera resolution...")
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,
                             UIConstants.WINDOW_WIDTH)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT,
                             UIConstants.WINDOW_HEIGHT)
                w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                if w != UIConstants.WINDOW_WIDTH or h != UIConstants.WINDOW_HEIGHT:
                    logger.warning(f"Cam res mismatch: {int(w)}x{int(h)}")
                else:
                    logger.info(f"Camera resolution: {int(w)}x{int(h)}")
        else:
            self.cap = None

        if not self.camera_available:
            logger.warning(
                f"Using static frame: {GameConstants.STATIC_FRAME_FILE}")
            try:
                self.static_frame = cv2.imread(GameConstants.STATIC_FRAME_FILE)
                if self.static_frame is None:
                    raise FileNotFoundError("Static frame not found/invalid.")
                if self.static_frame.shape[0] == 0 or self.static_frame.shape[
                        1] == 0:
                    raise ValueError("Static image invalid dims.")
                if len(self.static_frame.shape
                       ) != 3 or self.static_frame.shape[2] != 3:
                    raise ValueError("Static image not BGR.")
                self.static_frame = cv2.resize(
                    self.static_frame,
                    (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT),
                )
            except Exception as e:
                logger.exception(f"Static frame load fail: {e}")
                raise  # Re-raise critical error

        # Game Variables
        self.score: int = 0
        self.high_score: int = 0
        self.scoring_zones: List[Tuple[int, int, int, int, int]] = []
        self.drawing: bool = False
        self.start_x: Optional[int] = None
        self.start_y: Optional[int] = None
        self.temp_zone: Optional[Tuple[int, int, int, int]] = None
        self.special_hole: Optional[Tuple[int, int, int, int, int]] = None
        self.drawing_points_input: str = ""

        # Detection & Tracking
        self.detector = BallDetector()
        self.tracker = BallTracker()
        self.tracked_balls: List[Tuple[int, int, float, int, int, str]] = []
        self.next_ball_id: int = 0
        self.frame_count: int = 0

        # Scoring State Variables
        self.scored_balls: List[int] = [
        ]  # Potentially legacy, review if needed
        self.scored_positions: Dict[Tuple[int, int],
                                    int] = {}  # Check if still needed
        self.balls_in_zone: Dict[int,
                                 Tuple[int, int, int, int,
                                       int]] = ({})  # Check if still needed
        self.ball_scored_zones: Dict[int, int] = (
            {})  # Tracks if ball scored in *this* zone entry
        self.ball_states: Dict[int,
                               Dict[str,
                                    Any]] = {}  # Current stability/zone state
        self.previous_ball_states: Dict[int, Dict[str, Any]] = (
            {})  # Previous frame's state
        self.ball_positions_history: Dict[int, List[Tuple[int, int]]] = (
            {})  # Short history for rest check
        self.ball_zone_history: Dict[int, List[Optional[int]]] = (
            {})  # Short history for zone stability check
        self.special_hole_hit_this_session: bool = False
        self.zone_cooldown: Dict[int, float] = (
            {})  # Zone index -> timestamp when cooldown ends

        # Menu State Variables
        self.submenu_active: Optional[str] = None
        self.submenu_items: List[Tuple[
            Tuple[int, int, int, int], Any,
            str]] = ([])  # Holds clickable items [(rect, action, label), ...]
        self.menu_pos: Tuple[int,
                             int] = (0, 0
                                     )  # Top-left corner of the menu window
        self.menu_width: int = 600
        self.menu_height: int = 450
        self.menu_cache: Optional[
            np.ndarray] = None  # Cached rendered menu surface
        self.menu_cache_key: Optional[
            Any] = None  # Key to check if cache is valid
        self.edit_zones_items_per_page: int = 8
        self.edit_zones_current_page: int = 1
        self.editing_zone_index: Optional[
            int] = None  # Zone being edited (points)
        self.editing_zone_mode: Optional[str] = (
            None  # e.g., 'edit_points', 'confirm_delete'
        )
        self.editing_zone_points_input: Optional[
            str] = None  # Temp input for points
        self.selected_zone_for_edit: Optional[int] = (
            None  # Zone selected for interactive move/resize
        )
        self.zone_editing_action: Optional[
            str] = None  # 'move', 'resize_tl', etc.
        self.drag_start_pos: Optional[Tuple[int, int]] = (
            None  # Mouse position when drag started
        )
        self.original_zone_on_drag_start: Optional[Tuple[
            int, int, int, int, int]] = (
                None  # Zone state before dragging
            )
        self.editing_player_index: Optional[
            int] = None  # Player index being edited
        self.editing_player_mode: Optional[str] = None  # e.g., 'edit_name'
        self.editing_player_name_input: Optional[
            str] = None  # Temp input for name
        self.click_feedback_state: Optional[Tuple[Tuple[
            int, int, int, int], float]] = (
                None  # (rect, timestamp) for visual click feedback
            )

        # Initial Player Name Input State
        self.player_name_input_active: bool = True
        self.current_player_name_input: str = ""

        # Sound Objects
        self.score_sound: Optional[pygame.mixer.Sound] = None
        self.background_music: Optional[pygame.mixer.Sound] = None
        self.selected_music_track_index: int = 0
        if GameConstants.BACKGROUND_MUSIC_TRACKS:
            self.selected_music_track_index = random.randint(
                0,
                len(GameConstants.BACKGROUND_MUSIC_TRACKS) - 1)
            logger.info(
                f"Initial music track index randomly set to: {self.selected_music_track_index}"
            )
        else:
            logger.warning("No background music tracks defined in constants.")
        self.achievement_sound: Optional[pygame.mixer.Sound] = (
            None  # Should be loaded by initialize_sounds
        )
        self.low_time_sound: Optional[pygame.mixer.Sound] = None
        self.low_time_warning_played: bool = False

        # Game Mode / State
        self.game_mode: str = "classic"  # Default mode
        self.game_timer: Optional[float] = None
        self.current_state: CurrentGameState = CurrentGameState.GETTING_PLAYER_NAME
        self.previous_state: Optional[CurrentGameState] = (
            None  # Used for interactive zone editing cancel
        )
        self.previous_state_before_quit_confirm: Optional[CurrentGameState] = (
            None  # State before quit confirmation
        )
        self.win_score: int = GameConstants.TIMED_MODE_WIN_SCORE
        self.win_condition_met: bool = False

        # Achievements
        self.achievements: List[Any] = []  # List of Achievement objects
        self.achievement_notification: Optional[str] = None
        self.achievement_notification_timer: float = 0.0

        # Debug Flags
        self.debug_mode: bool = False  # Toggle verbose logging
        self.fps: float = 0.0  # Calculated FPS
        self.show_debug_overlay: bool = False  # Toggle visual debug info

        # Players
        self.players: List[Player] = [Player("Player 1")
                                      ]  # Default player list
        self.current_player_index: int = 0

        # Leaderboard
        self.leaderboard = Leaderboard(supabase_url, supabase_key)
        self.leaderboard_mode: str = (
            "classic"  # Mode currently viewed in leaderboard menu
        )

        # HSV Ranges (Loaded from file)
        self.hsv_ranges: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}

        # Notifications
        self.notification_text: Optional[str] = None
        self.notification_timer: float = 0.0
        self.notification_color: Tuple[int, int, int] = UIConstants.GREEN

        # Fun Mode Effects
        self.active_trails: Dict[int, BallTrail] = {}
        self.active_explosions: List[Explosion] = []

        # --- >>> ADDED: Heatmap state <<< ---
        self.show_heatmap: bool = False  # Flag to indicate if heatmap overlay is active
        # self.heatmap_cache: Optional[np.ndarray] = None # Optional: Cache the generated heatmap
        # --- >>> END ADDED <<< ---

        # --- Init Calls Using Utility Functions ---
        # Important: Load settings before sounds/music to apply volume correctly
        logger.info("Loading settings via utils...")
        load_settings(self)  # Loads volume levels etc.

        logger.info(
            "Loading initial game state (zones, high score) via utils...")
        load_initial_state(self)  # Loads zones, high score for current mode

        try:
            logger.info("Initializing sounds via utils...")
            sound_results = initialize_sounds()
            if isinstance(sound_results, tuple) and len(sound_results) == 2:
                self.score_sound, self.low_time_sound = sound_results
                # Load achievement sound here if applicable (or adjust initialize_sounds)
                # Example: self.achievement_sound = pygame.mixer.Sound(...)
            else:
                logger.error(f"init sounds bad format: {type(sound_results)}")
                self.score_sound, self.low_time_sound = None, None
        except Exception as e:
            logger.exception(f"Sound init error: {e}")
            self.score_sound, self.low_time_sound = None, None

        logger.info("Loading background music via utils...")
        # Pass self, as load_background_music might need game_state attributes
        self.background_music = load_background_music(
            self, self.selected_music_track_index)
        if self.background_music is None:
            logger.warning("Failed to load initial background music track.")

        # Apply loaded/default volume settings
        set_volume(self)

        logger.info("Initializing achievements definitions via utils...")
        self.achievements = initialize_achievements()
        logger.info("Loading achievements status via utils...")
        load_achievements(self, GameConstants.ACHIEVEMENTS_FILE)

        logger.info("Loading HSV ranges via utils...")
        self.hsv_ranges = load_hsv_ranges(GameConstants.HSV_RANGES_FILE)

        # Set initial game timer based on mode
        if self.game_mode == "timed":
            self.game_timer = GameConstants.TIMED_MODE_DURATION
        elif self.game_mode == "survival":
            self.game_timer = GameConstants.SURVIVAL_MODE_START_TIME
        else:
            self.game_timer = None  # Classic, Practice, Fun modes might not have timers

        # --- >>> ADDED: Start initial data logging session <<< ---
        if self.data_logger:
            current_player_name = "Player 1"  # Default before input
            if self.players:
                try:
                    current_player_name = self.players[
                        self.current_player_index].name
                except (IndexError, AttributeError):
                    pass  # Stick with default if error
            self.data_logger.start_new_session(current_player_name,
                                               self.game_mode)
        # --- >>> END ADDED <<< ---

        logger.info("GameState initialized successfully.")

    def get_current_player(self) -> Player:
        """Returns the current player object. Handles potential errors."""
        try:
            if self.players and 0 <= self.current_player_index < len(
                    self.players):
                return self.players[self.current_player_index]
            else:
                # Attempt to recover if index is bad or list is empty
                logger.warning(
                    f"Current player index {self.current_player_index} invalid for players list (len {len(self.players)}). Attempting recovery."
                )
                if not self.players:
                    self.players.append(
                        Player("Player 1"))  # Add default player
                    logger.info(
                        "Player list was empty, added default 'Player 1'.")
                self.current_player_index = 0  # Reset index to 0
                return self.players[0]
        except Exception as e:
            logger.exception(
                f"Unexpected error in get_current_player: {e}. Returning fallback."
            )
            # Ensure players list exists and return first element as fallback
            if not hasattr(self, "players") or not self.players:
                self.players = [Player("FallbackPlayer")]
                self.current_player_index = 0
            elif not isinstance(self.players[0], Player):
                self.players[0] = Player(
                    "FallbackPlayer")  # Overwrite if first element is corrupt
            return self.players[
                0]  # Return the (potentially new/overwritten) first player
