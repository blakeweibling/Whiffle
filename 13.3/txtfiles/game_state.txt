# game_state.py

import logging
import random
import time # [ADD] Import time for camera init delay and feedback state
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
import pygame

# Import constants consistently
# [ADD] Import ResolutionConstants
from constants import GameConstants, UIConstants, ResolutionConstants, ScoringConstants

# Import necessary components
from detection import BallDetector

# Import effects for Fun Mode
from effects import BallTrail, Explosion

# Import utility functions
# [MODIFY] Make sure load_initial_state is imported (it likely is already)
# [MODIFY] Make sure set_special_hole is imported if used directly here (likely not)
from game_state_utils import (
    initialize_achievements,
    initialize_sounds,
    load_achievements,
    load_hsv_ranges,
    load_initial_state,
    load_settings,
    set_volume,
    load_background_music,
    set_special_hole, # Import this if needed for scaling
)

# Import types/enums from new location
from game_types import CurrentGameState
from leaderboard import Leaderboard
from player import Player
from tracking import BallTracker

# Import DataLogger [cite: 1465]
try:
    from data_logger import DataLogger
except ImportError:
    logger.error("Failed to import DataLogger. Stats functionality will be unavailable.") #
    DataLogger = None

logger = logging.getLogger(__name__)


class GameState:

    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        logger.info("Starting GameState initialization...")

        # [ADD] Resolution State
        self.current_resolution_key = ResolutionConstants.DEFAULT_RESOLUTION
        self.current_width, self.current_height = ResolutionConstants.RESOLUTIONS[self.current_resolution_key]
        self.previous_width, self.previous_height = self.current_width, self.current_height # For scaling zones

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

        # [MODIFY] Camera Initialization - Moved to helper
        self.cap: Optional[cv2.VideoCapture] = None
        self.camera_available: bool = False
        self.static_frame: Optional[np.ndarray] = None
        self._initialize_camera() # Call the helper BEFORE loading zones/state

        # Game Variables
        self.score: int = 0
        self.high_score: int = 0
        self.scoring_zones: List[Tuple[int, int, int, int, int]] = [] # Loaded by load_initial_state
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
        self.scored_balls: List[int] = []
        self.scored_positions: Dict[Tuple[int, int], int] = {}
        self.balls_in_zone: Dict[int, Tuple[int, int, int, int, int]] = ({})
        self.ball_scored_zones: Dict[int, int] = ({})
        self.ball_states: Dict[int, Dict[str, Any]] = {}
        self.previous_ball_states: Dict[int, Dict[str, Any]] = ({})
        self.ball_positions_history: Dict[int, List[Tuple[int, int]]] = ({})
        self.ball_zone_history: Dict[int, List[Optional[int]]] = ({})
        self.special_hole_hit_this_session: bool = False
        self.zone_cooldown: Dict[int, float] = ({})

        # Menu State Variables
        self.submenu_active: Optional[str] = None
        self.submenu_items: List[Tuple[Tuple[int, int, int, int], Any, str]] = ([])
        self.menu_pos: Tuple[int, int] = (0, 0)
        self.menu_width: int = 600 # Initial menu width, might need adjustment
        self.menu_height: int = 450 # Initial menu height, might need adjustment
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
        self.original_zone_on_drag_start: Optional[Tuple[int, int, int, int, int]] = None
        self.editing_player_index: Optional[int] = None
        self.editing_player_mode: Optional[str] = None
        self.editing_player_name_input: Optional[str] = None
        self.click_feedback_state: Optional[Tuple[Tuple[int, int, int, int], float]] = None

        # Initial Player Name Input State [cite: 1489]
        self.player_name_input_active: bool = True
        self.current_player_name_input: str = ""

        # Sound Objects
        self.score_sound: Optional[pygame.mixer.Sound] = None
        self.background_music: Optional[pygame.mixer.Sound] = None
        self.selected_music_track_index: int = 0
        if GameConstants.BACKGROUND_MUSIC_TRACKS: #
            self.selected_music_track_index = random.randint(0, len(GameConstants.BACKGROUND_MUSIC_TRACKS) - 1) #
            logger.info(f"Initial music track index randomly set to: {self.selected_music_track_index}") #
        else: logger.warning("No background music tracks defined in constants.") #
        self.achievement_sound: Optional[pygame.mixer.Sound] = None
        self.low_time_sound: Optional[pygame.mixer.Sound] = None
        self.low_time_warning_played: bool = False

        # Game Mode / State
        self.game_mode: str = "classic"
        self.game_timer: Optional[float] = None
        self.current_state: CurrentGameState = CurrentGameState.GETTING_PLAYER_NAME
        self.previous_state: Optional[CurrentGameState] = None
        self.previous_state_before_quit_confirm: Optional[CurrentGameState] = None
        self.win_score: int = GameConstants.TIMED_MODE_WIN_SCORE #
        self.win_condition_met: bool = False

        # Achievements [cite: 1493]
        self.achievements: List[Any] = []
        self.achievement_notification: Optional[str] = None
        self.achievement_notification_timer: float = 0.0

        # Debug Flags [cite: 1494]
        self.debug_mode: bool = False
        self.fps: float = 0.0
        self.show_debug_overlay: bool = False

        # Players
        self.players: List[Player] = [Player("Player 1")]
        self.current_player_index: int = 0

        # Leaderboard [cite: 1495]
        self.leaderboard = Leaderboard(supabase_url, supabase_key)
        self.leaderboard_mode: str = ("classic")

        # HSV Ranges [cite: 1496]
        self.hsv_ranges: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}

        # Notifications [cite: 1496]
        self.notification_text: Optional[str] = None
        self.notification_timer: float = 0.0
        self.notification_color: Tuple[int, int, int] = UIConstants.GREEN

        # Fun Mode Effects [cite: 1496]
        self.active_trails: Dict[int, BallTrail] = {}
        self.active_explosions: List[Explosion] = []

        # Heatmap state [cite: 1497]
        self.show_heatmap: bool = False

        # --- Init Calls Using Utility Functions ---
        logger.info("Loading settings via utils...") #
        load_settings(self) # [cite: 1498] # Loads volume levels etc.

        logger.info("Loading initial game state (zones, high score) via utils...") #
        # Zones are loaded based on current resolution (which is default at this point)
        load_initial_state(self) # [cite: 1498]

        try:
            logger.info("Initializing sounds via utils...") #
            sound_results = initialize_sounds() # [cite: 1499]
            if isinstance(sound_results, tuple) and len(sound_results) == 2:
                self.score_sound, self.low_time_sound = sound_results #
            else:
                logger.error(f"init sounds bad format: {type(sound_results)}") #
                self.score_sound, self.low_time_sound = None, None
        except Exception as e:
            logger.exception(f"Sound init error: {e}") #
            self.score_sound, self.low_time_sound = None, None

        logger.info("Loading background music via utils...") #
        self.background_music = load_background_music(self, self.selected_music_track_index) # [cite: 1501]
        if self.background_music is None: logger.warning("Failed to load initial background music track.") #

        # Apply loaded/default volume settings
        set_volume(self) # [cite: 1501]

        logger.info("Initializing achievements definitions via utils...") #
        self.achievements = initialize_achievements() # [cite: 1501]
        logger.info("Loading achievements status via utils...") #
        load_achievements(self, GameConstants.ACHIEVEMENTS_FILE) # [cite: 1502]

        logger.info("Loading HSV ranges via utils...") #
        self.hsv_ranges = load_hsv_ranges(GameConstants.HSV_RANGES_FILE) # [cite: 1502]

        # Set initial game timer based on mode
        if self.game_mode == "timed": self.game_timer = GameConstants.TIMED_MODE_DURATION
        elif self.game_mode == "survival": self.game_timer = GameConstants.SURVIVAL_MODE_START_TIME
        else: self.game_timer = None

        # Start initial data logging session
        if self.data_logger:
            current_player_name = "Player 1"
            if self.players:
                try: current_player_name = self.players[self.current_player_index].name
                except (IndexError, AttributeError): pass
            self.data_logger.start_new_session(current_player_name, self.game_mode)

        logger.info("GameState initialization complete.") #


    # [ADD] Helper to get current dimensions
    def get_current_resolution_dimensions(self) -> tuple[int, int]:
         """Helper to get current display/processing dimensions"""
         return self.current_width, self.current_height

    # [ADD] Camera Initialization Helper
    def _initialize_camera(self):
         """Initializes or re-initializes the camera capture based on current resolution."""
         logger.info(f"Initializing camera for {self.current_width}x{self.current_height}")
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
                  logger.error("Camera index/backend not determined. Cannot initialize camera.")
                  self.camera_available = False
             else:
                  logger.info(f"Attempting camera index {cam_index} w/ backend {cam_backend}")
                  self.cap = cv2.VideoCapture(cam_index, cam_backend) # Use determined index/backend

                  if not self.cap or not self.cap.isOpened():
                      logger.error(f"Failed to open camera index {cam_index} with backend {cam_backend}. Will attempt static frame.")
                      self.camera_available = False
                      self.cap = None
                  else:
                      logger.info(f"Setting camera properties for {self.current_width}x{self.current_height}")
                      # Set desired resolution
                      prop_width_set = self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.current_width)
                      prop_height_set = self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.current_height)
                      # Optional: Set other properties like FPS if needed
                      # self.cap.set(cv2.CAP_PROP_FPS, GameConstants.FRAME_RATE)

                      # Allow some time for settings to apply
                      time.sleep(0.5)

                      # Verify actual resolution
                      w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                      h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                      logger.info(f"Camera Get Properties: W={w}, H={h}. Set Success: Width={prop_width_set}, Height={prop_height_set}")

                      # Check if the resolution was actually set (allowing some tolerance)
                      if abs(int(w) - self.current_width) > 10 or abs(int(h) - self.current_height) > 10:
                           logger.warning(f"Camera resolution mismatch: Requested {self.current_width}x{self.current_height}, Got {int(w)}x{int(h)}. Check camera capabilities.")
                           # Consider falling back or accepting the camera's resolution
                           # For now, we keep the game state dimensions as the target
                      else:
                           logger.info(f"Camera resolution successfully configured to: {int(w)}x{int(h)}")
         else:
             self.cap = None # Explicitly set cap to None if camera isn't used

         # Handle static frame loading if camera failed or isn't used
         if not self.camera_available:
             logger.warning(f"Using static frame: {GameConstants.STATIC_FRAME_FILE}")
             try:
                 static_img = cv2.imread(GameConstants.STATIC_FRAME_FILE)
                 if static_img is None: raise FileNotFoundError("Static frame file not found or invalid.")
                 # Resize static frame to current target resolution
                 self.static_frame = cv2.resize(static_img, (self.current_width, self.current_height))
                 logger.info(f"Loaded and resized static frame to {self.current_width}x{self.current_height}")
             except Exception as e:
                 logger.exception(f"Static frame loading or resizing failed: {e}")
                 self.static_frame = None # Indicate failure

         # Handle case where neither camera nor static frame worked
         if not self.camera_available and self.static_frame is None:
              logger.critical("FATAL: Camera unavailable and static frame failed to load/resize.")
              # This is a critical failure, maybe raise an exception
              raise RuntimeError("Failed to initialize any video source (Camera or Static Frame).")

    # [ADD] Method to Scale Zones
    def _scale_scoring_zones(self, old_w: int, old_h: int, new_w: int, new_h: int):
        """Scales existing scoring zones when resolution changes."""
        if old_w <= 0 or old_h <= 0: # Prevent division by zero or invalid scaling
             logger.warning(f"Cannot scale zones, invalid old dimensions: {old_w}x{old_h}.")
             return
        logger.info(f"Scaling {len(self.scoring_zones)} zones from {old_w}x{old_h} to {new_w}x{new_h}")
        scale_x = new_w / old_w
        scale_y = new_h / old_h
        scaled_zones = []
        min_size = getattr(ScoringConstants, "MIN_ZONE_SIZE", 10) #

        for zone_index, zone_data in enumerate(self.scoring_zones):
             try:
                 x, y, w, h, points = zone_data # Assumes 5 elements
                 new_zone_x = int(x * scale_x)
                 new_zone_y = int(y * scale_y)
                 new_zone_w = int(w * scale_x)
                 new_zone_h = int(h * scale_y)

                 # Ensure minimum size after scaling
                 new_zone_w = max(min_size, new_zone_w)
                 new_zone_h = max(min_size, new_zone_h)

                 # Ensure zone stays within bounds (optional, but good practice)
                 new_zone_x = max(0, min(new_zone_x, new_w - new_zone_w))
                 new_zone_y = max(0, min(new_zone_y, new_h - new_zone_h))

                 scaled_zones.append((new_zone_x, new_zone_y, new_zone_w, new_zone_h, points))
                 # logger.debug(f"Zone {zone_index} scaled from ({x},{y},{w},{h}) to ({new_zone_x},{new_zone_y},{new_zone_w},{new_zone_h})")
             except Exception as e:
                  logger.error(f"Error scaling zone index {zone_index} ({zone_data}): {e}")
                  # Keep the original zone if scaling fails? Or skip? Skipping for now.

        self.scoring_zones = scaled_zones
        self.special_hole = set_special_hole(self.scoring_zones) # Re-evaluate special hole
        logger.info(f"Scaled {len(self.scoring_zones)} zones successfully.")
        # Note: Explicitly saving zones here might be needed if persistence between runs is desired after scaling
        # save_zones(self) # Consider implications

    # [ADD] Resolution Change Method
    def set_resolution(self, new_resolution_key: str):
        """Changes the game resolution, re-initializes camera, and scales zones."""
        if new_resolution_key not in ResolutionConstants.RESOLUTIONS:
            logger.warning(f"Attempted to set invalid resolution key: {new_resolution_key}")
            return
        if new_resolution_key == self.current_resolution_key:
            logger.debug(f"Resolution already set to {new_resolution_key}.")
            return # No change needed

        logger.info(f"Initiating resolution change from {self.current_resolution_key} to {new_resolution_key}")

        # Store old dimensions for scaling
        self.previous_width, self.previous_height = self.current_width, self.current_height

        # Update state variables for resolution
        self.current_resolution_key = new_resolution_key
        self.current_width, self.current_height = ResolutionConstants.RESOLUTIONS[self.current_resolution_key]

        # Scale existing scoring zones based on the dimension change
        if self.previous_width > 0 and self.previous_height > 0:
             self._scale_scoring_zones(self.previous_width, self.previous_height, self.current_width, self.current_height)
        else:
             logger.warning("Previous dimensions were invalid, cannot scale zones on resolution change.")

        # Re-initialize camera with the new resolution settings
        try:
            self._initialize_camera() # This will release the old capture and create a new one
        except Exception as e:
            logger.exception(f"CRITICAL: Error during camera re-initialization for new resolution: {e}")
            show_notification(self, "Camera Error! Check Logs.", is_error=True, duration=5.0)
            # Attempt to revert resolution state if camera fails?
            # self.current_resolution_key = old_key # Need to store old key before change
            # self.current_width, self.current_height = self.previous_width, self.previous_height
            # self._scale_scoring_zones(...) # Scale back
            # self._initialize_camera() # Try initializing again with old settings
            return # Stop the process if camera initialization fails

        # Resize the main application window if it exists
        try:
            window_visible = cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 1
            if window_visible:
                cv2.resizeWindow(UIConstants.WINDOW_NAME, self.current_width, self.current_height)
                logger.info(f"Resized application window to {self.current_width}x{self.current_height}")
            else:
                 logger.info("Window not found or not visible, skipping explicit window resize.")
        except cv2.error as e:
            # Ignore errors like "Window not found" if it was closed between check and resize
            if "could not find window" not in str(e).lower():
                 logger.warning(f"Could not resize application window: {e}")
        except Exception as e:
            logger.error(f"Unexpected error resizing application window: {e}")

        # Invalidate UI caches or trigger UI element recalculations
        self.menu_cache = None # Invalidate menu cache as its size might depend on resolution
        # Add any other necessary state resets related to UI layout or cached surfaces

        show_notification(self, f"Resolution set to {self.current_resolution_key}", duration=2.0)
        logger.info(f"Resolution change to {self.current_resolution_key} ({self.current_width}x{self.current_height}) complete.")


    def get_current_player(self) -> Player: #
        """Returns the current player object. Handles potential errors.""" # [cite: 1506]
        try:
            if self.players and 0 <= self.current_player_index < len(self.players): #
                return self.players[self.current_player_index] #
            else:
                logger.warning(f"Current player index {self.current_player_index} invalid for players list (len {len(self.players)}). Attempting recovery.") # [cite: 1507]
                if not self.players: #
                    self.players.append(Player("Player 1")) # [cite: 1508]
                    logger.info("Player list was empty, added default 'Player 1'.") #
                self.current_player_index = 0 # Reset index to 0 # [cite: 1509]
                return self.players[0] #
        except Exception as e:
            logger.exception(f"Unexpected error in get_current_player: {e}. Returning fallback.") #
            if not hasattr(self, "players") or not self.players: # [cite: 1510]
                self.players = [Player("FallbackPlayer")] #
                self.current_player_index = 0 #
            elif not isinstance(self.players[0], Player): #
                self.players[0] = Player("FallbackPlayer") # [cite: 1511]
            return self.players[0] #