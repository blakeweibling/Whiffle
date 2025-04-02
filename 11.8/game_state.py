# game_state.py

import cv2
import logging
import pygame # Ensure pygame is imported
import time
import numpy as np
import os
import json
from typing import Optional, List, Tuple, Dict, Any, Callable
from enum import Enum, auto

# --- MODIFIED: Import from game_constants ---
from game_constants import UIConstants, GameConstants, ScoringConstants

from detection import BallDetector
from tracking import BallTracker
from leaderboard import Leaderboard
from player import Player
# from scoring import is_in_scoring_zone # Keep if needed by game_state directly, else remove

# --- MODIFIED: Import scoring functions ---
from game_scoring import update_scoring, save_score, check_win_condition

# Import reconciled utils functions
from game_state_utils import (
    set_special_hole,
    initialize_sounds,
    initialize_achievements,
    load_achievements, # Takes game_state, filename
    save_achievements, # Takes game_state, filename
    load_hsv_ranges, # Takes filename, returns dict
    save_hsv_ranges, # Takes dict, filename
    # Remove is_ball_at_rest, is_ball_zone_stable if only used by game_scoring
)

logger = logging.getLogger(__name__)


class CurrentGameState(Enum):
    GETTING_PLAYER_NAME = auto()
    PLAYING = auto()
    MENU = auto()
    ZONE_EDITING = auto()
    GAME_OVER = auto()
    PAUSED = auto()


class GameState:
    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        logger.info("Starting GameState initialization...")


        # --- Camera Initialization ---
        self.camera_available: bool = GameConstants.USE_CAMERA
        self.static_frame: Optional[np.ndarray] = None
        self.cap: Optional[cv2.VideoCapture] = None # Initialize cap

        if self.camera_available:
            logger.info(f"Attempting to open camera at index {GameConstants.CAMERA_INDEX} with backend {GameConstants.CAMERA_BACKEND}")
            try:
                self.cap = cv2.VideoCapture(GameConstants.CAMERA_INDEX, GameConstants.CAMERA_BACKEND)
                if not self.cap.isOpened():
                    logger.error(f"Failed to open camera index {GameConstants.CAMERA_INDEX} with backend {GameConstants.CAMERA_BACKEND}. Falling back.")
                    self.camera_available = False
                else:
                    logger.info("Setting camera resolution...")
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, UIConstants.WINDOW_WIDTH)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, UIConstants.WINDOW_HEIGHT)
                    w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    if w != UIConstants.WINDOW_WIDTH or h != UIConstants.WINDOW_HEIGHT:
                        logger.warning(f"Camera resolution mismatch: Got {int(w)}x{int(h)}, expected {UIConstants.WINDOW_WIDTH}x{UIConstants.WINDOW_HEIGHT}")
                    else:
                        logger.info(f"Camera resolution set: {int(w)}x{int(h)}")
            except Exception as e:
                 logger.exception(f"Exception during camera initialization: {e}. Falling back.")
                 self.camera_available = False
                 if self.cap: # Release if partially opened
                      self.cap.release()
                 self.cap = None

        # Fallback to static frame if camera not available or failed
        if not self.camera_available:
            logger.warning(f"Using static frame: {GameConstants.STATIC_FRAME_FILE}")
            try:
                self.static_frame = cv2.imread(GameConstants.STATIC_FRAME_FILE)
                if self.static_frame is None:
                    raise FileNotFoundError(f"{GameConstants.STATIC_FRAME_FILE} not found or invalid.")
                if self.static_frame.shape[0] == 0 or self.static_frame.shape[1] == 0:
                    raise ValueError("Static image has invalid dimensions.")
                if len(self.static_frame.shape) != 3 or self.static_frame.shape[2] != 3:
                    raise ValueError("Static image not 3-channel BGR.")
                self.static_frame = cv2.resize(self.static_frame, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
                logger.info(f"Static frame loaded and resized: {GameConstants.STATIC_FRAME_FILE}.")
            except Exception as e:
                logger.exception(f"Static frame load/validation failed: {e}. Game cannot continue without video source.")
                raise # Re-raise critical error

        # --- Game Variables ---
        logger.info("Initializing game variables...")
        self.score: int = 0
        self.high_score: int = 0 # Will be loaded per mode
        self.scoring_zones: List[Tuple[int, int, int, int, int]] = []
        self.drawing: bool = False
        self.start_x: Optional[int] = None
        self.start_y: Optional[int] = None
        self.temp_zone: Optional[Tuple[int, int, int, int]] = None
        self.special_hole: Optional[Tuple[int, int, int, int, int]] = None
        self.drawing_points_input: str = ""

        # --- Detection & Tracking ---
        logger.info("Initializing detection and tracking...")
        self.detector = BallDetector()
        self.tracker = BallTracker()
        self.tracked_balls: List[Tuple[int, int, float, int, int, str]] = []
        self.next_ball_id: int = 0
        self.ball_trails: Dict[int, List[Tuple[int, int]]] = {}
        self.frame_count: int = 0
        self.ball_trails_enabled: bool = False # <<< ENSURE THIS IS FALSE FOR DEFAULT OFF >>>

        # --- Scoring State (Managed by game_scoring, but state stored here) ---
        self.scored_balls: List[int] = [] # Legacy list
        self.scored_positions: Dict[Tuple[int, int], int] = {} # Unused? Review later
        self.balls_in_zone: Dict[int, Tuple[int, int, int, int, int]] = {} # BallID -> ZoneTuple
        self.ball_scored_zones: Dict[int, int] = {} # BallID -> ZoneIndex (tracks if scored this entry)
        self.ball_states: Dict[int, Dict[str, Any]] = {} # Current calculated state (rest, stable, zone)
        self.previous_ball_states: Dict[int, Dict[str, Any]] = {} # Previous frame's state
        self.ball_positions_history: Dict[int, List[Tuple[int, int]]] = {} # For rest detection
        self.ball_zone_history: Dict[int, List[Optional[int]]] = {} # For stability detection (stores zone index or None)
        self.special_hole_hit_this_session: bool = False
        self.zone_cooldown: Dict[int, float] = {} # ZoneIndex -> CooldownEndTime

        # --- Menu State ---
        self.submenu_active: Optional[str] = None
        self.submenu_items: List[Tuple[Tuple[int, int, int, int], Any, str]] = []
        self.menu_pos: Tuple[int, int] = (0, 0)
        self.menu_width: int = UIConstants.MENU_WIDTH # Use constant
        self.menu_height: int = UIConstants.MENU_HEIGHT # Use constant
        self.menu_cache: Optional[np.ndarray] = None
        self.menu_cache_key: Optional[Any] = None
        # --- Additions for Menu Dragging ---
        self.is_dragging_menu: bool = False
        self.menu_drag_offset: Optional[Tuple[int, int]] = None
        # --- End Additions ---

        # --- Zone Menu Editing ---
        self.editing_zone_index: Optional[int] = None
        self.editing_zone_mode: Optional[str] = None
        self.editing_zone_points_input: Optional[str] = None
        self.edit_zones_page: int = 0
        self.edit_zones_per_page: int = 10

        # --- Interactive Zone Editing State ---
        self.selected_zone_for_edit: Optional[int] = None
        self.zone_editing_action: Optional[str] = None
        self.drag_start_pos: Optional[Tuple[int, int]] = None
        self.original_zone_on_drag_start: Optional[Tuple[int, int, int, int, int]] = None

        # --- Player Name Editing State (Menu) ---
        self.editing_player_index: Optional[int] = None
        self.editing_player_mode: Optional[str] = None
        self.editing_player_name_input: Optional[str] = None

        # --- Initial Player Name Input State ---
        self.player_name_input_active: bool = True
        self.current_player_name_input: str = ""

        # --- Sounds ---
        self.game_sounds_on: bool = True
        self.background_music_on: bool = True
        self.score_sound: Optional[pygame.mixer.Sound] = None
        self.background_music: Optional[pygame.mixer.Sound] = None
        self.achievement_sound: Optional[pygame.mixer.Sound] = None # Needs separate loading
        self.low_time_sound: Optional[pygame.mixer.Sound] = None
        self.low_time_warning_played: bool = False

        # --- Game Mode / State ---
        self.game_mode: str = "classic" # Default mode
        self.game_timer: Optional[float] = None
        self.current_state: CurrentGameState = CurrentGameState.GETTING_PLAYER_NAME
        self.previous_state: Optional[CurrentGameState] = None
        self.win_score: int = GameConstants.TIMED_MODE_WIN_SCORE # Target score for timed mode
        self.win_condition_met: bool = False


        # --- Achievements ---
        self.achievements: List[Any] = []
        self.achievement_notification: Optional[str] = None
        self.achievement_notification_timer: float = 0.0

        # --- Debug ---
        self.debug_mode: bool = False
        self.fps: float = 0.0
        self.show_debug_overlay: bool = False

        # --- Players ---
        self.players: List[Player] = [Player("Player 1")] # Initial player
        self.current_player_index: int = 0

        # --- Leaderboard ---
        self.leaderboard = Leaderboard(supabase_url, supabase_key)
        self.leaderboard_mode: str = "classic" # Used for leaderboard queries

        # --- HSV ---
        self.hsv_ranges: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}

        # --- Notifications ---
        self.notification_text: Optional[str] = None
        self.notification_timer: float = 0.0
        self.notification_color: Tuple[int, int, int] = UIConstants.GREEN

        # --- Init Calls ---
        logger.info("Loading initial state (zones, high score)...")
        self._load_initial_state() # Load zones and mode-specific high score

        logger.info("Initializing sounds...")
        try:
            # Expecting (score_sound, background_music, low_time_sound)
            sound_results = initialize_sounds()
            if isinstance(sound_results, tuple) and len(sound_results) == 3:
                self.score_sound, self.background_music, self.low_time_sound = sound_results
                # self.achievement_sound = None # Load achievement sound separately if needed
                logger.info("Sounds initialized (score, background, low_time).")
            else:
                raise ValueError(f"initialize_sounds returned unexpected format: {type(sound_results)}")
        except Exception as e:
            logger.exception(f"Error during sound initialization: {e}. Sounds disabled.")
            self.score_sound, self.background_music, self.low_time_sound, self.achievement_sound = None, None, None, None
            self.game_sounds_on = False # Ensure flags reflect state
            self.background_music_on = False

        self.set_volume() # Set initial volume based on flags

        logger.info("Initializing achievements...")
        self.achievements = initialize_achievements() # Get achievement definitions
        logger.info("Loading saved achievement progress...")
        load_achievements(self, GameConstants.ACHIEVEMENTS_FILE) # Update unlocked status

        logger.info("Loading HSV ranges...")
        self.hsv_ranges = load_hsv_ranges(GameConstants.HSV_RANGES_FILE)

        # Set timer only if starting in timed mode AFTER loading initial state
        if self.game_mode == "timed":
            self.game_timer = GameConstants.TIMED_MODE_DURATION
            logger.info(f"Initial game mode is timed. Timer set to {self.game_timer} seconds.")
        else:
            self.game_timer = None # Ensure timer is None otherwise

        logger.info("GameState initialized successfully.")


    def set_volume(self):
        """Sets volume based on current flags."""
        if self.score_sound:
             self.score_sound.set_volume(GameConstants.DEFAULT_SOUND_VOLUME if self.game_sounds_on else 0.0)
        if self.low_time_sound:
             self.low_time_sound.set_volume(GameConstants.DEFAULT_SOUND_VOLUME if self.game_sounds_on else 0.0)
        if self.achievement_sound:
            self.achievement_sound.set_volume(GameConstants.DEFAULT_SOUND_VOLUME if self.game_sounds_on else 0.0)
        if self.background_music:
             self.background_music.set_volume(GameConstants.DEFAULT_MUSIC_VOLUME if self.background_music_on else 0.0)
        logger.debug(f"Volumes set: Sounds={self.game_sounds_on}, Music={self.background_music_on}")

    def toggle_background_music(self) -> None:
        """Toggles background music playback based on the flag."""
        # Flag (self.background_music_on) should be toggled by the menu action
        # This function just enforces the state based on the flag
        if self.background_music:
            target_volume = GameConstants.DEFAULT_MUSIC_VOLUME if self.background_music_on else 0.0
            current_volume = self.background_music.get_volume()

            if self.background_music_on and current_volume == 0.0:
                 self.background_music.set_volume(target_volume)
                 self.background_music.play(-1) # Loop indefinitely
                 logger.info("Background music started/resumed.")
            elif not self.background_music_on and current_volume > 0.0:
                 self.background_music.set_volume(target_volume)
                 # Consider stopping vs just muting based on desired behavior
                 # self.background_music.stop()
                 logger.info("Background music muted (or stopped).")
            elif self.background_music_on:
                 # Ensure volume is correct if already playing
                 self.background_music.set_volume(target_volume)
                 logger.debug("Background music already playing, volume adjusted if needed.")
            else: # Not on and volume is 0
                 logger.debug("Background music already stopped/muted.")
        else:
            logger.warning("Cannot toggle: Background music not loaded.")


    def _load_initial_state(self):
        """Loads persistent state like zones and high score for current mode."""
        # Import locally to potentially break cycles if menu imports GameState
        from menu import load_zones
        from game_state_utils import set_special_hole

        # Load zones first
        load_zones(self) # Assumes load_zones modifies self.scoring_zones
        self.special_hole = set_special_hole(self.scoring_zones)

        # Load High Score for the current game_mode
        high_score_file = GameConstants.HIGH_SCORE_FILE
        self.high_score = 0 # Default
        try:
            if os.path.exists(high_score_file) and os.path.getsize(high_score_file) > 0:
                with open(high_score_file, "r") as f:
                    data = json.load(f)
                # Load high score specific to the current game_mode
                    self.high_score = data.get(self.game_mode, {}).get("high_score", 0)
                    player_name = data.get(self.game_mode, {}).get("player", "N/A")
                    logger.info(f"Loaded high score for mode '{self.game_mode}': {self.high_score} by {player_name}")
            else:
                if not os.path.exists(high_score_file):
                    logger.info(f"High score file not found: {high_score_file}. Setting high score to 0.")
                else: # File exists but is empty
                    logger.warning(f"High score file exists but is empty: {high_score_file}. Setting high score to 0.")
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load high score from {high_score_file}: {e}. Setting high score to 0.")
        except Exception as e:
            logger.exception(f"Unexpected error loading high score: {e}")
        # Ensure high_score is 0 if any error occurred


    # --- REMOVED: _save_high_score method (handled by game_scoring._update_local_high_score) ---


    def get_current_player(self) -> Player:
        """Returns the current player object."""
        if self.players and 0 <= self.current_player_index < len(self.players):
            return self.players[self.current_player_index]
        # Fallback
        logger.warning(f"Current player index {self.current_player_index} invalid for {len(self.players)} players. Using fallback.")
        if not self.players:
            logger.error("Player list is empty! Creating a default player.")
            self.players.append(Player("Player 1"))
            self.current_player_index = 0
        # Return first player if index was bad or list was empty
        return self.players[0]


    # --- REMOVED: save_score method (use imported game_scoring.save_score) ---
    # Example usage (e.g., in game over logic):
    # from game_scoring import save_score
    # save_score(self, self.get_current_player().name, self.game_mode)


    def play_sound(self, sound: Optional[pygame.mixer.Sound]) -> None:
        """Play sound effect if enabled and sound exists."""
        if self.game_sounds_on and sound:
            try:
                # Ensure volume is correct before playing (handles toggling sounds off/on)
                sound.set_volume(GameConstants.DEFAULT_SOUND_VOLUME)
                sound.play()
            except pygame.error as e:
                logger.error(f"Pygame sound playback error: {e}")
        elif not sound:
             logger.debug("Sound not played because sound object is None.")
        # No log needed if game_sounds_on is False, expected behavior


    def check_achievements(self) -> None:
        """Check achievements and notify if newly unlocked."""
        if not hasattr(self, 'achievements'):
             logger.error("Achievements list not found in game state.")
             return
        newly_unlocked = False
        for ach in self.achievements:
            # Check condition only if not already unlocked
            if not ach.unlocked and ach.check(self): # Pass game_state to check
                ach.unlocked = True
                logger.info(f"Achievement Unlocked: {ach.name} - {ach.description}")
                self.show_notification(f"Unlocked: {ach.name}", duration=5.0, is_error=False)
                self.play_sound(self.achievement_sound) # Play unlock sound
                newly_unlocked = True

        if newly_unlocked:
            # Save achievements immediately after any unlock
            save_achievements(self, GameConstants.ACHIEVEMENTS_FILE)


    def update_achievement_notification(self, dt: float) -> None:
        """Updates timer for achievement popup."""
        if self.achievement_notification_timer > 0:
            self.achievement_notification_timer -= dt
            if self.achievement_notification_timer <= 0:
                self.achievement_notification = None


    def show_notification(self, text: str, duration: float = UIConstants.NOTIFICATION_DURATION, is_error: bool = False) -> None:
        """Display a notification message."""
        self.notification_text = text
        self.notification_timer = duration if not is_error else UIConstants.NOTIFICATION_ERROR_DURATION
        self.notification_color = UIConstants.RED if is_error else UIConstants.GREEN
        log_level = logging.WARNING if is_error else logging.INFO
        logger.log(log_level, f"Notification: {text}")


    def update_notifications(self, dt: float) -> None:
        """Update notification timer."""
        if self.notification_timer > 0:
            self.notification_timer -= dt
            if self.notification_timer <= 0:
                self.notification_text = None


    # --- REMOVED: update_scoring method (use imported game_scoring.update_scoring) ---
    # Example usage (in main game loop):
    # from game_scoring import update_scoring
    # scored_this_frame = update_scoring(self)
    # if scored_this_frame:
    #     self.play_sound(self.score_sound)


    def reset_game(self) -> None:
        """Resets the game state for a new round."""
        logger.info("Resetting game state...")
        self.score = 0
        self.tracked_balls.clear()
        self.scored_balls.clear() # Legacy
        self.scored_positions.clear() # Unused?
        self.next_ball_id = 0
        self.submenu_active = None
        self.submenu_items = []
        self.game_timer = None # Will be set based on mode below
        self.ball_trails.clear()
        self.ball_states.clear()
        self.previous_ball_states.clear()
        self.achievement_notification = None
        self.achievement_notification_timer = 0.0
        self.balls_in_zone.clear()
        self.ball_scored_zones.clear()
        self.ball_positions_history.clear()
        self.ball_zone_history.clear()
        self.zone_cooldown.clear()
        self.win_condition_met = False
        self.special_hole_hit_this_session = False
        self.low_time_warning_played = False

        # Reset pagination state
        self.edit_zones_page = 0

        # Reset menu editing states
        self.editing_zone_index = None
        self.editing_zone_mode = None
        self.editing_zone_points_input = None
        self.editing_player_index = None
        self.editing_player_mode = None
        self.editing_player_name_input = None

        # Reset interactive zone editing states
        self.selected_zone_for_edit = None
        self.zone_editing_action = None
        self.drag_start_pos = None
        self.original_zone_on_drag_start = None

        # Reset current player's score
        current_player = self.get_current_player() # Use getter for safety
        if current_player:
             current_player.reset_score()
             logger.info(f"Reset score for player: {current_player.name}")
        else:
             logger.warning("Could not get current player during reset.")


        # Reload zones, set special hole, and load mode-specific high score
        # _load_initial_state already handles loading the correct high score based on self.game_mode
        if hasattr(self, "_load_initial_state") and callable(self._load_initial_state):
             self._load_initial_state()
             logger.info("Reloaded initial state (zones, high score).")
        else:
             logger.error("Cannot reload initial state during reset, _load_initial_state method not found!")


        # Set timer based on the current game mode AFTER loading initial state
        if self.game_mode == "timed":
            self.game_timer = GameConstants.TIMED_MODE_DURATION
            logger.info(f"Game reset in timed mode. Timer set to {self.game_timer} seconds.")
        else:
            self.game_timer = None
            logger.info("Game reset in classic mode. No timer.")

        # Don't change self.current_state here, let the calling function decide
        # e.g., game loop might set it back to PLAYING or MENU
        logger.info("Game state reset complete.")

    def release_camera(self):
        """Releases the camera resource."""
        if self.cap and self.cap.isOpened():
            logger.info("Releasing camera capture...")
            self.cap.release()
            self.cap = None # Ensure it's marked as released
            logger.info("Camera released.")

    # --- Add any other GameState specific methods below ---