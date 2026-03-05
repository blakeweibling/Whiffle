# game_state.py

import logging
import os
import random
import time
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

import cv2
import numpy as np
import pygame
from pygame import mixer

# Import constants consistently
from constants import GameConstants, UIConstants, ResolutionConstants, ScoringConstants

# Import necessary components
from detection import BallDetector
from game_state_helpers import show_notification

# Import effects for Fun Mode
from effects import BallTrail, Explosion

# Import utility functions
from game_state_utils import (
    initialize_achievements,
    initialize_sounds,
    load_achievements,
    load_hsv_ranges,
    load_initial_state,
    load_settings,
    set_volume,
    load_background_music,
    set_special_hole,
)

# Import types/enums from new location
from game_types import CurrentGameState
from leaderboard import Leaderboard
from player import Player
from tracking import BallTracker
from xp_system import xp_system

# Import the replay manager
from replay_manager import ReplayManager

# Import DataLogger
try:
    from data_logger import DataLogger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.error(
        "Failed to import DataLogger. Stats functionality will be unavailable."
    )
    DataLogger = None

logger = logging.getLogger(__name__)

# Constants for memory management
MAX_BALL_POSITIONS_HISTORY = 200  # Maximum positions to track per ball
MAX_BALL_ZONE_HISTORY = 100  # Maximum zone entries to track per ball
MAX_TRACKED_BALLS = 20  # Maximum number of balls to track simultaneously


class GameState:

    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        logger.info("Starting GameState initialization...")

        # Clear XP data at the start of each application session
        try:
            from xp_system import xp_system
            xp_system.clear_all_xp()
            logger.debug("Cleared player XP data at application startup.")
        except Exception as e:
            logger.error(f"Error clearing XP data at startup: {e}")

        # Try to update loading screen if available
        try:
            from loading_screen import update_loading_progress

            update_loading_progress("Initializing game state...", 0.05)
        except ImportError:
            # Loading screen not available, continue without updates
            pass

        # Store Supabase credentials for later use
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key

        # Resolution State
        self.current_resolution_key = ResolutionConstants.DEFAULT_RESOLUTION
        self.current_width, self.current_height = ResolutionConstants.RESOLUTIONS[
            self.current_resolution_key
        ]
        self.previous_width, self.previous_height = (
            self.current_width,
            self.current_height,
        )

        # Try to update loading screen
        try:
            from loading_screen import update_loading_progress

            update_loading_progress("Setting up data logger...", 0.05)
        except ImportError:
            pass

        # DataLogger Initialization
        if DataLogger:
            self.data_logger: Optional[DataLogger] = DataLogger()
        else:
            self.data_logger: Optional[DataLogger] = None
        self.current_session_stats: Optional[Dict[str, Any]] = None

        # Initial Volume Levels & Flags
        self.current_sound_volume: float = GameConstants.INITIAL_SOUND_VOLUME
        self.current_music_volume: float = GameConstants.INITIAL_MUSIC_VOLUME
        self.game_sounds_on: bool = True
        self.background_music_on: bool = True

        # Camera Initialization
        self.cap: Optional[cv2.VideoCapture] = None
        self.camera_available: bool = False
        self.static_frame: Optional[np.ndarray] = None
        self._initialize_camera()

        # Game Variables
        self.score: int = 0
        self.final_score: int = 0  # Add final_score to track the score at game end
        self.high_score: int = 0
        self.scoring_zones: List[Tuple[int, int, int, int, int]] = []
        self.drawing: bool = False
        self.start_x: Optional[int] = None
        self.start_y: Optional[int] = None
        self.temp_zone: Optional[Tuple[int, int, int, int]] = None
        self.special_hole: Optional[Tuple[int, int, int, int, int]] = None
        self.drawing_points_input: str = ""

        # Playfield / Model selection
        self.playfield_type: str = "whiffle"
        self.model_path: str = GameConstants.WHIFFLE_MODEL_PATH
        self.zones_file_path: str = GameConstants.ZONES_FILE

        # Detection & Tracking
        self.detector = BallDetector(self.model_path)
        self.tracker = BallTracker()
        self.tracked_balls: List[Tuple[int, int, float, int, int, str]] = []
        self.next_ball_id: int = 0
        self.frame_count: int = 0

        # Scoring State Variables
        self.scored_balls: List[int] = []
        self.scored_positions: Dict[Tuple[int, int], int] = {}
        self.balls_in_zone: Dict[int, Tuple[int, int, int, int, int]] = {}
        self.ball_scored_zones: Dict[int, int] = {}
        self.ball_states: Dict[int, Dict[str, Any]] = {}
        self.previous_ball_states: Dict[int, Dict[str, Any]] = {}
        # Limited size history collections
        self.ball_positions_history: Dict[int, List[Tuple[int, int]]] = {}
        self.ball_zone_history: Dict[int, List[Optional[int]]] = {}
        self.special_hole_hit_this_session: bool = False
        self.special_hole_hits_this_session: int = 0  # Count for Hole Hunter achievement
        self.zone_cooldown: Dict[int, float] = {}
        # Achievement tracking (persistent or session)
        self.has_edited_zone_points: bool = False
        self.has_viewed_heatmap: bool = False
        self.has_paused_and_resumed: bool = False
        self.has_uploaded_screenshot: bool = False
        self.has_shared_replay: bool = False
        self.has_exported_highlight: bool = False
        self.scored_red_ball_this_session: bool = False
        self.scored_half_red_this_session: bool = False
        self.points_from_multiplier_balls_this_game: int = 0

        # Menu State Variables
        self.submenu_active: Optional[str] = None
        self.submenu_items: List[Tuple[Tuple[int, int, int, int], Any, str]] = []
        self.menu_pos: Tuple[int, int] = (0, 0)
        self.menu_width: int = 600
        self.menu_height: int = 450
        self.menu_cache: Optional[np.ndarray] = None
        self.menu_cache_key: Optional[Any] = None
        self.edit_zones_items_per_page: int = 8
        self.edit_zones_current_page: int = 1
        self.editing_zone_index: Optional[int] = None
        self.editing_zone_mode: Optional[str] = None
        self.editing_zone_points_input: Optional[str] = None
        self.selected_zone_for_edit: Optional[int] = None
        self.zone_editing_action: Optional[str] = None
        self.drag_start_pos: Optional[Tuple[int, int]] = None
        self.original_zone_on_drag_start: Optional[Tuple[int, int, int, int, int]] = (
            None
        )
        self.move_all_zones: bool = False
        self.original_zones_on_drag_start: Optional[List[Tuple[int, int, int, int, int]]] = None
        self.editing_player_index: Optional[int] = None
        self.editing_player_mode: Optional[str] = None
        self.editing_player_name_input: Optional[str] = None
        self.click_feedback_state: Optional[Tuple[Tuple[int, int, int, int], float]] = (
            None
        )
        # Add hover feedback state
        self.hover_feedback_state: Optional[Tuple[int, int, int, int]] = None

        # Menu minimized state
        self.menu_minimized: bool = False

        # UI visibility for scoring zones: start hidden by default
        self.show_scoring_zones: bool = False

        # Initial Player Name Input State
        self.player_name_input_active: bool = True
        self.current_player_name_input: str = ""

        # Sound Objects
        self.score_sound: Optional[pygame.mixer.Sound] = None
        self.background_music: Optional[pygame.mixer.Sound] = None
        self.selected_music_track_index: int = 0
        if GameConstants.BACKGROUND_MUSIC_TRACKS:
            self.selected_music_track_index = random.randint(
                0, len(GameConstants.BACKGROUND_MUSIC_TRACKS) - 1
            )
            logger.debug(
                f"Initial music track index randomly set to: {self.selected_music_track_index}"
            )
        else:
            logger.warning("No background music tracks defined in constants.")
        self.achievement_sound: Optional[pygame.mixer.Sound] = None
        self.low_time_sound: Optional[pygame.mixer.Sound] = None
        self.low_time_warning_played: bool = False

        # Game Mode / State
        self.game_mode: str = "classic"
        self.game_timer: Optional[float] = None
        self.current_state: CurrentGameState = CurrentGameState.GETTING_PLAYER_NAME
        self.previous_state: Optional[CurrentGameState] = None
        self.previous_state_before_quit_confirm: Optional[CurrentGameState] = None
        self.win_score: int = GameConstants.TIMED_MODE_WIN_SCORE
        self.win_condition_met: bool = False

        # Versus Mode
        self.versus_mode_active: bool = False
        self.current_turn_player_index: int = 0
        self.versus_players: List[Player] = []
        self.versus_scores: List[int] = [0, 0]
        self.versus_stats: List[Dict] = [{}, {}]

        # Achievements
        self.achievements: List[Any] = []
        self.achievement_notification: Optional[str] = None
        self.achievement_notification_timer: float = 0.0

        # Debug Flags
        self.debug_mode: bool = False
        self.fps: float = 0.0
        self.show_debug_overlay: bool = False

        # Accessibility options
        self.colorblind_mode: bool = UIConstants.DEFAULT_COLORBLIND_MODE

        # Players
        self.players: List[Player] = [Player("Player 1")]
        self.current_player_index: int = 0

        # Leaderboard
        self.leaderboard = Leaderboard(supabase_url, supabase_key)
        self.leaderboard_mode: str = "classic"

        # HSV Ranges
        self.hsv_ranges: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}

        # Notifications
        self.notification_text: Optional[str] = None
        self.notification_timer: float = 0.0
        self.notification_color: Tuple[int, int, int] = UIConstants.GREEN

        # Fun Mode Effects
        self.active_trails: Dict[int, BallTrail] = {}
        self.active_explosions: List[Explosion] = []

        # Heatmap state
        self.show_heatmap: bool = False

        # --- START CHANGE: Initialize game_over_buttons ---
        # Dictionary to store the rectangles of buttons on the game over screen
        self.game_over_buttons: Dict[str, Tuple[int, int, int, int]] = {}
        # --- END CHANGE ---

        # --- Initialize replay system ---
        self.replay_manager: Optional[ReplayManager] = None
        self.current_replay: Optional[Any] = None
        self.replay_recording: bool = False

        # --- END Initialize replay system ---

        # --- Init Calls Using Utility Functions ---
        logger.debug("Loading settings via utils...")
        load_settings(self)
        self.current_player_name_input = getattr(self, "last_player_name", "") or ""

        logger.debug("Loading initial game state (zones, high score) via utils...")
        load_initial_state(self)

        try:
            logger.debug("Initializing sounds via utils...")
            sound_results = initialize_sounds()
            if isinstance(sound_results, tuple) and len(sound_results) == 2:
                self.score_sound, self.low_time_sound = sound_results
            else:
                logger.error(f"init sounds bad format: {type(sound_results)}")
                self.score_sound, self.low_time_sound = None, None
        except Exception as e:
            logger.exception(f"Sound init error: {e}")
            self.score_sound, self.low_time_sound = None, None

        logger.debug("Loading background music via utils...")
        self.background_music = load_background_music(
            self, self.selected_music_track_index
        )
        if self.background_music is None:
            logger.warning("Failed to load initial background music track.")

        # Apply loaded/default volume settings
        set_volume(self)

        logger.debug("Initializing achievements definitions via utils...")
        self.achievements = initialize_achievements()
        logger.debug("Loading achievements status via utils...")
        load_achievements(self, GameConstants.ACHIEVEMENTS_FILE)

        logger.debug("Loading HSV ranges via utils...")
        self.hsv_ranges = load_hsv_ranges(GameConstants.HSV_RANGES_FILE)

        # Set initial game timer based on mode
        if self.game_mode == "timed":
            self.game_timer = GameConstants.TIMED_MODE_DURATION
        elif self.game_mode == "survival":
            self.game_timer = GameConstants.SURVIVAL_MODE_START_TIME
        else:
            self.game_timer = None

        # Start initial data logging session (only for live camera games)
        if self.data_logger:
            # In static-image mode (no live camera), skip creating session stats.
            # This avoids adding entries to session_stats_history.json for non-live games.
            if getattr(self, "camera_available", True):
                current_player_name = "Player 1"
                if self.players:
                    try:
                        current_player_name = self.players[self.current_player_index].name
                    except (IndexError, AttributeError):
                        pass
                self.data_logger.start_new_session(current_player_name, self.game_mode)

        # Leaderboard already created in __init__; no need to re-initialize

        # Initialize the replay manager
        try:
            self.replay_manager = ReplayManager()
            logger.debug("Replay manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize replay manager: {e}")
            self.replay_manager = None

        # Ensure the high_score_screenshots bucket exists
        from screenshot_utils import ensure_supabase_bucket_exists

        bucket_name = "high-score-screenshots"
        bucket_exists = ensure_supabase_bucket_exists(
            supabase_url, supabase_key, bucket_name
        )
        if not bucket_exists:
            logger.warning(
                f"Failed to create or verify '{bucket_name}' bucket in Supabase Storage"
            )
        else:
            logger.debug(
                f"Successfully verified '{bucket_name}' bucket in Supabase Storage"
            )

        logger.info("GameState initialization complete.")

    def set_playfield(self, playfield: str) -> bool:
        """Set playfield type and load the appropriate detection model."""
        playfield_key = (playfield or "").strip().lower()
        model_map = {
            "whiffle": GameConstants.WHIFFLE_MODEL_PATH,
            "fivestar": GameConstants.FIVESTAR_MODEL_PATH,
            "five star": GameConstants.FIVESTAR_MODEL_PATH,
        }
        zones_map = {
            "whiffle": GameConstants.ZONES_FILE,
            "fivestar": GameConstants.FIVESTAR_ZONES_FILE,
            "five star": GameConstants.FIVESTAR_ZONES_FILE,
        }
        if playfield_key not in model_map:
            logger.warning(f"Unknown playfield selection: {playfield}")
            show_notification(self, "Unknown playfield selection", is_error=True)
            return False

        model_path = model_map[playfield_key]
        if not os.path.exists(model_path):
            logger.error(f"Model file not found: {model_path}")
            show_notification(
                self,
                f"Model not found: {model_path}",
                is_error=True,
                duration=3.0,
            )
            return False

        try:
            self.playfield_type = "fivestar" if "five" in playfield_key else "whiffle"
            self.model_path = model_path
            self.zones_file_path = zones_map[playfield_key]
            
            # Clear old zones before loading new ones to prevent stale data
            self.scoring_zones = []
            self.special_hole = None
            # Reset scoring/tracking state when switching playfields
            self._reset_scoring_state_for_layout_change()
            
            # Reload detector with new model (this also extracts class names from the new model)
            self.detector = BallDetector(self.model_path)
            logger.info(f"Reloaded detector with model: {self.model_path}")
            
            # Load zones for the new layout
            try:
                from game_state_helpers import load_zones

                load_zones(self, zones_file_path=self.zones_file_path)
                logger.info(f"Loaded zones from {self.zones_file_path} for {self.playfield_type} layout")
            except Exception as e:
                logger.error(f"Failed to load zones for {self.playfield_type}: {e}")
                show_notification(
                    self, "Failed to load scoring zones", is_error=True, duration=2.5
                )
            
            # Set special hole for Whiffle (Five Star doesn't have one)
            if not self.is_fivestar_playfield():
                from game_state_helpers import set_special_hole
                self.special_hole = set_special_hole(self.scoring_zones)
            
            # Default to hiding scoring zones when loading a layout (same as Whiffle initial load)
            self.show_scoring_zones = False
            
            show_notification(
                self,
                f"Loaded {self.playfield_type} model",
                duration=2.0,
            )
            # Reload static frame if camera is not available (to use correct image for playfield type)
            if not self.camera_available:
                self._load_static_frame()
            return True
        except Exception as e:
            logger.error(f"Failed to load model {model_path}: {e}")
            show_notification(self, "Failed to load model", is_error=True)
            return False

    def _reset_scoring_state_for_layout_change(self) -> None:
        """Clear scoring/tracking state so layout switches don't carry over scores."""
        self.tracked_balls = []
        self.next_ball_id = 0
        self.frame_count = 0
        self.scored_balls = []
        self.scored_positions = {}
        self.balls_in_zone = {}
        self.ball_scored_zones = {}
        self.ball_states = {}
        self.previous_ball_states = {}
        self.ball_positions_history = {}
        self.ball_zone_history = {}
        self.zone_cooldown = {}
        self.special_hole_hit_this_session = False
        self.special_hole_hits_this_session = 0
        self.points_from_multiplier_balls_this_game = 0
        self.scored_red_ball_this_session = False
        self.scored_half_red_this_session = False
        self.active_trails = {}
        self.active_explosions = []
        self.tracker = BallTracker()

    def is_fivestar_playfield(self) -> bool:
        """Return True when the active playfield is Five Star."""
        playfield_type = getattr(self, "playfield_type", "whiffle")
        model_path = os.path.normpath(
            getattr(self, "model_path", GameConstants.WHIFFLE_MODEL_PATH)
        )
        zones_path = os.path.normpath(
            getattr(self, "zones_file_path", GameConstants.ZONES_FILE)
        )
        return (
            playfield_type == "fivestar"
            or model_path == os.path.normpath(GameConstants.FIVESTAR_MODEL_PATH)
            or zones_path == os.path.normpath(GameConstants.FIVESTAR_ZONES_FILE)
        )

    def get_static_frame_file(self) -> str:
        """Get the appropriate static frame file based on current playfield type."""
        if self.is_fivestar_playfield():
            return GameConstants.STATIC_FIVESTAR_FRAME_FILE
        return GameConstants.STATIC_FRAME_FILE

    def _load_static_frame(self) -> None:
        """Load the appropriate static frame based on current playfield type."""
        static_frame_file = self.get_static_frame_file()
        logger.warning(f"Using static frame: {static_frame_file}")

        # Try to update loading screen
        try:
            from loading_screen import update_loading_progress

            update_loading_progress("Loading static frame...", 0.1)
        except ImportError:
            pass

        try:
            static_img = cv2.imread(static_frame_file)
            if static_img is None:
                raise FileNotFoundError(f"Static frame file not found or invalid: {static_frame_file}")
            # Resize static frame to current target resolution
            self.static_frame = cv2.resize(
                static_img, (self.current_width, self.current_height)
            )
            logger.debug(
                f"Loaded and resized static frame to {self.current_width}x{self.current_height}"
            )
        except Exception as e:
            logger.exception(f"Static frame loading or resizing failed: {e}")
            self.static_frame = None

    # Helper to get current dimensions
    def get_current_resolution_dimensions(self) -> tuple[int, int]:
        """Helper to get current display/processing dimensions"""
        return self.current_width, self.current_height

    def get_duration(self) -> float:
        """Get the current session duration in seconds."""
        if self.data_logger and self.data_logger.get_current_session_data():
            return self.data_logger.get_current_session_data().get_duration()
        return 0.0

    # Method to trim history collections to prevent memory bloat
    def trim_history_collections(self) -> None:
        """Trim history collections to prevent unbounded growth"""
        # Trim ball positions history
        for ball_id in list(self.ball_positions_history.keys()):
            if len(self.ball_positions_history[ball_id]) > MAX_BALL_POSITIONS_HISTORY:
                # Keep only the most recent positions
                self.ball_positions_history[ball_id] = self.ball_positions_history[
                    ball_id
                ][-MAX_BALL_POSITIONS_HISTORY:]

        # Trim ball zone history
        for ball_id in list(self.ball_zone_history.keys()):
            if len(self.ball_zone_history[ball_id]) > MAX_BALL_ZONE_HISTORY:
                # Keep only the most recent zone entries
                self.ball_zone_history[ball_id] = self.ball_zone_history[ball_id][
                    -MAX_BALL_ZONE_HISTORY:
                ]

        # Trim tracked balls list if it exceeds maximum
        if len(self.tracked_balls) > MAX_TRACKED_BALLS:
            # Sort by age (5th element) and keep newest
            self.tracked_balls.sort(key=lambda ball: ball[4], reverse=True)
            self.tracked_balls = self.tracked_balls[:MAX_TRACKED_BALLS]
            # Clean up any related dictionaries for removed balls
            tracked_ids = {ball[3] for ball in self.tracked_balls}
            for ball_dict in [
                self.ball_positions_history,
                self.ball_zone_history,
                self.ball_states,
                self.previous_ball_states,
                self.ball_scored_zones,
                self.balls_in_zone,
            ]:
                # Only operate on dictionary types
                if isinstance(ball_dict, dict):
                    for ball_id in list(ball_dict.keys()):
                        if ball_id not in tracked_ids:
                            ball_dict.pop(ball_id, None)

    # Camera Initialization Helper
    def _initialize_camera(self):
        """Initializes or re-initializes the camera capture based on current resolution."""
        logger.debug(
            f"Initializing camera for {self.current_width}x{self.current_height}"
        )

        # Try to update loading screen
        try:
            from loading_screen import update_loading_progress

            update_loading_progress("Connecting to camera...", 0.15)
        except ImportError:
            pass

        self.camera_available = GameConstants.USE_CAMERA
        # Ensure previous capture is released if resetting
        if self.cap and self.cap.isOpened():
            self.cap.release()
            self.cap = None
            logger.info("Released previous camera capture.")

        if self.camera_available:
            # Use the index and backend determined by CameraConfig
            cam_index = GameConstants.CAMERA_INDEX
            cam_backend = GameConstants.CAMERA_BACKEND
            if cam_index is None or cam_backend is None:
                logger.error(
                    "Camera index/backend not determined. Cannot initialize camera."
                )
                self.camera_available = False
            else:
                logger.info(
                    f"Attempting camera index {cam_index} w/ backend {cam_backend}"
                )

                # Try to update loading screen
                try:
                    from loading_screen import update_loading_progress

                    update_loading_progress("Opening camera...", 0.1)
                except ImportError:
                    pass

                self.cap = cv2.VideoCapture(cam_index, cam_backend)

                if not self.cap or not self.cap.isOpened():
                    logger.error(
                        f"Failed to open camera index {cam_index} with backend {cam_backend}. Will attempt static frame."
                    )
                    self.camera_available = False
                    self.cap = None
                else:
                    logger.info(
                        f"Setting camera properties for {self.current_width}x{self.current_height}"
                    )

                    # Try to update loading screen
                    try:
                        from loading_screen import update_loading_progress

                        update_loading_progress("Configuring camera settings...", 0.1)
                    except ImportError:
                        pass

                    # Set desired resolution
                    prop_width_set = self.cap.set(
                        cv2.CAP_PROP_FRAME_WIDTH, self.current_width
                    )
                    prop_height_set = self.cap.set(
                        cv2.CAP_PROP_FRAME_HEIGHT, self.current_height
                    )
                    # Optional: Set other properties like FPS if needed
                    # self.cap.set(cv2.CAP_PROP_FPS, GameConstants.FRAME_RATE)

                    # Allow some time for settings to apply
                    time.sleep(0.5)

                    # Verify actual resolution
                    w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    logger.info(
                        f"Camera Get Properties: W={w}, H={h}. Set Success: Width={prop_width_set}, Height={prop_height_set}"
                    )

                    # Check if the resolution was actually set (allowing some tolerance)
                    if (
                        abs(int(w) - self.current_width) > 10
                        or abs(int(h) - self.current_height) > 10
                    ):
                        logger.warning(
                            f"Camera resolution mismatch: Requested {self.current_width}x{self.current_height}, Got {int(w)}x{int(h)}. Check camera capabilities."
                        )
                    else:
                        logger.info(
                            f"Camera resolution successfully configured to: {int(w)}x{int(h)}"
                        )
        else:
            self.cap = None

        # Handle static frame loading if camera failed or isn't used
        if not self.camera_available:
            self._load_static_frame()

        # Handle case where neither camera nor static frame worked
        if not self.camera_available and self.static_frame is None:
            logger.critical(
                "FATAL: Camera unavailable and static frame failed to load/resize."
            )
            raise RuntimeError(
                "Failed to initialize any video source (Camera or Static Frame)."
            )

    # Method to Scale Zones
    def _scale_scoring_zones(self, old_w: int, old_h: int, new_w: int, new_h: int):
        """Scales existing scoring zones when resolution changes."""
        if old_w <= 0 or old_h <= 0:
            logger.warning(
                f"Cannot scale zones, invalid old dimensions: {old_w}x{old_h}."
            )
            return
        logger.info(
            f"Scaling {len(self.scoring_zones)} zones from {old_w}x{old_h} to {new_w}x{new_h}"
        )
        scale_x = new_w / old_w
        scale_y = new_h / old_h
        scaled_zones = []
        min_size = getattr(ScoringConstants, "MIN_ZONE_SIZE", 10)

        for zone_index, zone_data in enumerate(self.scoring_zones):
            try:
                x, y, w, h, points = zone_data
                new_zone_x = int(x * scale_x)
                new_zone_y = int(y * scale_y)
                new_zone_w = int(w * scale_x)
                new_zone_h = int(h * scale_y)

                # Ensure minimum size after scaling
                new_zone_w = max(min_size, new_zone_w)
                new_zone_h = max(min_size, new_zone_h)

                # Ensure zone stays within bounds
                new_zone_x = max(0, min(new_zone_x, new_w - new_zone_w))
                new_zone_y = max(0, min(new_zone_y, new_h - new_zone_h))

                scaled_zones.append(
                    (new_zone_x, new_zone_y, new_zone_w, new_zone_h, points)
                )
            except Exception as e:
                logger.error(
                    f"Error scaling zone index {zone_index} ({zone_data}): {e}"
                )

        self.scoring_zones = scaled_zones
        if self.is_fivestar_playfield():
            self.special_hole = None
        else:
            self.special_hole = set_special_hole(self.scoring_zones)
        logger.info(f"Scaled {len(self.scoring_zones)} zones successfully.")

    # Resolution Change Method
    def cycle_resolution(self) -> None:
        """Cycle to the next resolution (1080p <-> 720p)."""
        keys = list(ResolutionConstants.RESOLUTIONS.keys())
        if not keys:
            return
        try:
            idx = keys.index(self.current_resolution_key)
            next_key = keys[(idx + 1) % len(keys)]
            self.set_resolution(next_key)
        except ValueError:
            self.set_resolution(keys[0])

    def set_resolution(self, new_resolution_key: str):
        """Changes the game resolution, re-initializes camera, and scales zones."""
        if new_resolution_key not in ResolutionConstants.RESOLUTIONS:
            logger.warning(
                f"Attempted to set invalid resolution key: {new_resolution_key}"
            )
            return
        if new_resolution_key == self.current_resolution_key:
            logger.debug(f"Resolution already set to {new_resolution_key}.")
            return

        logger.info(
            f"Initiating resolution change from {self.current_resolution_key} to {new_resolution_key}"
        )

        # Store old dimensions for scaling
        old_key = self.current_resolution_key  # Store the key in case of failure
        self.previous_width, self.previous_height = (
            self.current_width,
            self.current_height,
        )

        # Update state variables for resolution
        self.current_resolution_key = new_resolution_key
        self.current_width, self.current_height = ResolutionConstants.RESOLUTIONS[
            self.current_resolution_key
        ]

        # Scale existing scoring zones based on the dimension change
        if self.previous_width > 0 and self.previous_height > 0:
            self._scale_scoring_zones(
                self.previous_width,
                self.previous_height,
                self.current_width,
                self.current_height,
            )
        else:
            logger.warning(
                "Previous dimensions were invalid, cannot scale zones on resolution change."
            )

        # Re-initialize camera with the new resolution settings
        try:
            self._initialize_camera()
        except Exception as e:
            logger.exception(
                f"CRITICAL: Error during camera re-initialization for new resolution: {e}"
            )
            # --- Attempt to Revert ---
            logger.warning(
                "Attempting to revert to previous resolution due to camera init failure..."
            )
            self.current_resolution_key = old_key
            self.current_width, self.current_height = (
                self.previous_width,
                self.previous_height,
            )
            # Rescale zones back
            if self.current_width > 0 and self.current_height > 0:
                self._scale_scoring_zones(
                    self.current_width,
                    self.current_height,
                    self.previous_width,
                    self.previous_height,
                )  # Note: Reversed order might be needed
            else:
                logger.warning("Cannot scale zones back, target dimensions invalid.")
            # Try re-initializing camera with old settings
            try:
                self._initialize_camera()
                logger.info(
                    "Successfully reverted to previous resolution and re-initialized camera."
                )
                show_notification(
                    self,
                    f"Camera error! Reverted to {self.current_resolution_key}.",
                    is_error=True,
                    duration=5.0,
                )
            except Exception as revert_e:
                logger.critical(
                    f"FATAL: Failed to revert to previous resolution after error: {revert_e}"
                )
                show_notification(
                    self,
                    "FATAL Camera Error! Check Logs.",
                    is_error=True,
                    duration=10.0,
                )
                # Consider raising a specific exception or exiting if this fails
            return  # Stop processing the failed resolution change

        # Resize the main application window if it exists
        try:
            window_visible = (
                cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE)
                >= 1
            )
            if window_visible:
                cv2.resizeWindow(
                    UIConstants.WINDOW_NAME, self.current_width, self.current_height
                )
                logger.info(
                    f"Resized application window to {self.current_width}x{self.current_height}"
                )
            else:
                logger.info(
                    "Window not found or not visible, skipping explicit window resize."
                )
        except cv2.error as e:
            if "could not find window" not in str(e).lower():
                logger.warning(f"Could not resize application window: {e}")
        except Exception as e:
            logger.error(f"Unexpected error resizing application window: {e}")

        # Invalidate UI caches or trigger UI element recalculations
        self.menu_cache = None

        show_notification(
            self, f"Resolution set to {self.current_resolution_key}", duration=2.0
        )
        logger.info(
            f"Resolution change to {self.current_resolution_key} ({self.current_width}x{self.current_height}) complete."
        )

    def get_current_player(self) -> Player:
        """Returns the current player object. Handles potential errors."""
        try:
            if self.players and 0 <= self.current_player_index < len(self.players):
                return self.players[self.current_player_index]
            else:
                logger.warning(
                    f"Current player index {self.current_player_index} invalid for players list (len {len(self.players)}). Attempting recovery."
                )
                if not self.players:
                    self.players.append(Player("Player 1"))
                    logger.info("Player list was empty, added default 'Player 1'.")
                self.current_player_index = 0
                return self.players[0]
        except Exception as e:
            logger.exception(
                f"Unexpected error in get_current_player: {e}. Returning fallback."
            )
            if not hasattr(self, "players") or not self.players:
                self.players = [Player("FallbackPlayer")]
                self.current_player_index = 0
            elif not isinstance(self.players[0], Player):
                self.players[0] = Player("FallbackPlayer")
            return self.players[0]

    def reset_game(self, player_name: str = "Player", game_mode: str = "Classic"):
        """Reset the game state to initial values."""
        # Clear all XP data at the start of each game session
        xp_system.clear_all_xp()
        
        # Reset game state variables
        self.score = 0
        self.final_score = 0

        # Set the game mode
        self.game_mode = game_mode

        # Reset timers according to game mode
        if game_mode == "timed":
            self.game_timer = GameConstants.TIMED_MODE_DURATION
        elif game_mode == "survival":
            self.game_timer = GameConstants.SURVIVAL_MODE_START_TIME
        else:
            self.game_timer = None

        # Reset player if provided
        if player_name and len(player_name.strip()) > 0:
            # Find the player or create a new one
            found = False
            for i, player in enumerate(self.players):
                if player.name == player_name:
                    self.current_player_index = i
                    # Refresh XP data after clearing (will be level 1, 0 XP)
                    player.refresh_xp()
                    found = True
                    break
            if not found:
                self.players.append(Player(player_name))
                self.current_player_index = len(self.players) - 1

        # Reset session data (only for live camera games)
        if self.data_logger and getattr(self, "camera_available", True):
            self.data_logger.start_new_session(player_name, game_mode)
            self.current_session_stats = None

        # Reload achievements for the (potentially) new current player so they are per-player
        try:
            load_achievements(self, GameConstants.ACHIEVEMENTS_FILE)
        except Exception as e:
            logger.error(f"Error loading achievements during reset_game: {e}")
