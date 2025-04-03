# game_state.txt

import cv2
import logging
import pygame
import time
import numpy as np
import os
import json
from typing import Optional, List, Tuple, Dict, Any, Callable
from enum import Enum, auto

# Core dependencies
from constants import UIConstants, GameConstants, ScoringConstants
from detection import BallDetector
from tracking import BallTracker
from leaderboard import Leaderboard
from player import Player
from scoring import is_in_scoring_zone # Still needed for _load_initial_state potentially if logic isn't moved

# Import helper functions needed directly by GameState (init, load, save, reset)
from game_state_utils import (
    set_special_hole,
    initialize_sounds, # For initial loading
    initialize_achievements, # For initial loading
    load_achievements, # For initial loading
    save_achievements, # Needed if achievements checked outside handler? Keep for now.
    load_hsv_ranges, # For initial loading
    save_hsv_ranges, # Used? Keep for now. Maybe move to handler if saving happens there.
    is_ball_at_rest, # Likely needed by logic handler
    is_ball_zone_stable, # Likely needed by logic handler
)

# Import the new helper class
from game_logic import GameLogicHandler

logger = logging.getLogger(__name__)


# Enum defining the different states the game can be in
class CurrentGameState(Enum):
    GETTING_PLAYER_NAME = auto()
    PLAYING = auto()
    MENU = auto()
    ZONE_EDITING = auto()
    GAME_OVER = auto()
    PAUSED = auto()


class GameState:
    """
    Manages the overall state of the game, delegating specific logic
    (scoring, sounds, achievements, notifications) to GameLogicHandler.
    """
    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        logger.info("Starting GameState initialization...")

        # --- Core State Variables ---
        # Camera
        self.camera_available: bool = GameConstants.USE_CAMERA
        self.cap: Optional[cv2.VideoCapture] = None
        self.static_frame: Optional[np.ndarray] = None

        # Game Variables
        self.score: int = 0
        self.high_score: int = 0 # Loaded per mode
        self.scoring_zones: List[Tuple[int, int, int, int, int]] = []
        self.special_hole: Optional[Tuple[int, int, int, int, int]] = None
        self.drawing: bool = False
        self.start_x: Optional[int] = None
        self.start_y: Optional[int] = None
        self.temp_zone: Optional[Tuple[int, int, int, int]] = None
        self.drawing_points_input: str = "" # For zone creation

        # Detection & Tracking
        self.detector = BallDetector()
        self.tracker = BallTracker()
        self.tracked_balls: List[Tuple[int, int, float, int, int, str]] = []
        self.next_ball_id: int = 0
        self.ball_trails: Dict[int, List[Tuple[int, int]]] = {}
        self.frame_count: int = 0

        # Scoring State (managed primarily by GameLogicHandler, but initialized here)
        self.scored_balls: List[int] = [] # Potentially legacy
        # --- CORRECTION: Added scored_positions back ---
        self.scored_positions: Dict[Tuple[int, int], int] = {} # Used externally (e.g., drawing)
        # --- END CORRECTION ---
        self.balls_in_zone: Dict[int, Tuple[int, int, int, int, int]] = {}
        self.ball_scored_zones: Dict[int, int] = {}
        self.zone_cooldown: Dict[int, float] = {}
        self.special_hole_hit_this_session: bool = False

        # Ball Physics State (used by GameLogicHandler scoring)
        self.ball_states: Dict[int, Dict[str, Any]] = {}
        self.previous_ball_states: Dict[int, Dict[str, Any]] = {}
        self.ball_positions_history: Dict[int, List[Tuple[int, int]]] = {}
        self.ball_zone_history: Dict[int, List[Optional[int]]] = {}

        # Menu State
        self.submenu_active: Optional[str] = None
        self.submenu_items: List[Tuple[Tuple[int, int, int, int], Any, str]] = []
        self.menu_pos: Tuple[int, int] = (0, 0)
        self.menu_width: int = 400
        self.menu_height: int = 450
        self.menu_cache: Optional[np.ndarray] = None
        self.menu_cache_key: Optional[Any] = None

        # Zone Editing State (Menu/Interactive)
        self.editing_zone_index: Optional[int] = None
        self.editing_zone_mode: Optional[str] = None
        self.editing_zone_points_input: Optional[str] = None
        self.selected_zone_for_edit: Optional[int] = None
        self.zone_editing_action: Optional[str] = None
        self.drag_start_pos: Optional[Tuple[int, int]] = None
        self.original_zone_on_drag_start: Optional[Tuple[int, int, int, int, int]] = None

        # Player Name Input/Editing State
        self.player_name_input_active: bool = True
        self.current_player_name_input: str = ""
        self.editing_player_index: Optional[int] = None
        self.editing_player_mode: Optional[str] = None
        self.editing_player_name_input: Optional[str] = None

        # Sounds (References loaded by GameLogicHandler)
        self.game_sounds_on: bool = True
        self.background_music_on: bool = True
        self.score_sound: Optional[pygame.mixer.Sound] = None
        self.background_music: Optional[pygame.mixer.Sound] = None
        self.achievement_sound: Optional[pygame.mixer.Sound] = None # Handler may need separate access
        self.low_time_sound: Optional[pygame.mixer.Sound] = None
        self.low_time_warning_played: bool = False

        # Game Mode / State
        self.game_mode: str = "classic"
        self.game_timer: Optional[float] = None
        self.current_state: CurrentGameState = CurrentGameState.GETTING_PLAYER_NAME
        self.previous_state: Optional[CurrentGameState] = None
        self.win_score: int = GameConstants.TIMED_MODE_WIN_SCORE
        self.win_condition_met: bool = False

        # Achievements (Loaded initially, checked by GameLogicHandler)
        self.achievements: List[Any] = []
        self.achievement_notification: Optional[str] = None # Managed by Handler
        self.achievement_notification_timer: float = 0.0 # Managed by Handler

        # Notifications (Managed by GameLogicHandler)
        self.notification_text: Optional[str] = None
        self.notification_timer: float = 0.0
        self.notification_color: Tuple[int, int, int] = UIConstants.GREEN

        # Debug
        self.debug_mode: bool = False
        self.fps: float = 0.0
        self.show_debug_overlay: bool = False

        # Players
        self.players: List[Player] = [Player("Player 1")]
        self.current_player_index: int = 0

        # Leaderboard
        self.leaderboard = Leaderboard(supabase_url, supabase_key)
        self.leaderboard_mode: str = "classic" # Can be changed via menu

        # HSV
        self.hsv_ranges: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}

        # --- Initialization Steps ---

        # 1. Initialize Camera / Static Frame
        self._initialize_camera_or_static_frame()

        # 2. Instantiate the Logic Handler (Pass self)
        self.logic_handler = GameLogicHandler(self)

        # 3. Load Initial State (Zones, High Score for current mode)
        logger.info("Loading initial state (zones, high score)...")
        self._load_initial_state() # Uses self.game_mode

        # 4. Initialize Sounds via Handler
        logger.info("Initializing sounds...")
        self.logic_handler.initialize_and_load_sounds() # Handler loads sounds into self

        # 5. Initialize and Load Achievements
        logger.info("Initializing and loading achievements...")
        self.achievements = initialize_achievements() # Base definitions
        load_achievements(self, GameConstants.ACHIEVEMENTS_FILE) # Load saved status

        # 6. Load HSV Ranges
        logger.info("Loading HSV ranges...")
        self.hsv_ranges = load_hsv_ranges(GameConstants.HSV_RANGES_FILE)

        # 7. Set Initial Timer based on Mode
        self._set_initial_timer()

        logger.info("GameState initialized successfully.")

    def _initialize_camera_or_static_frame(self):
        """Handles setting up either the camera feed or loading the static frame."""
        if self.camera_available:
            logger.info(
                f"Attempting camera {GameConstants.CAMERA_INDEX} ({GameConstants.CAMERA_BACKEND})"
            )
            self.cap = cv2.VideoCapture(
                GameConstants.CAMERA_INDEX, GameConstants.CAMERA_BACKEND
            )
            if not self.cap.isOpened():
                logger.error(f"Failed to open camera {GameConstants.CAMERA_INDEX}. Disabling camera.")
                self.camera_available = False
                self.cap = None
            else:
                 # Set resolution
                 self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, UIConstants.WINDOW_WIDTH)
                 self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, UIConstants.WINDOW_HEIGHT)
                 w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                 h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                 logger.info(f"Camera {GameConstants.CAMERA_INDEX} opened. Resolution: {int(w)}x{int(h)}")
                 if w != UIConstants.WINDOW_WIDTH or h != UIConstants.WINDOW_HEIGHT:
                       logger.warning("Camera resolution mismatch.")

        if not self.camera_available: # Fallback or initial config
             logger.warning(f"Using static frame: {GameConstants.STATIC_FRAME_FILE}")
             try:
                self.static_frame = cv2.imread(GameConstants.STATIC_FRAME_FILE)
                if self.static_frame is None:
                    raise FileNotFoundError("Static frame file not found or invalid.")
                self.static_frame = cv2.resize(
                    self.static_frame,
                    (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT),
                )
                logger.info("Static frame loaded and resized.")
             except Exception as e:
                logger.exception(f"Failed to load/process static frame: {e}. Exiting.")
                raise # Indicate critical failure


    def _load_initial_state(self):
        """Loads zones and high score specific to the current game mode."""
        # Needs menu import locally as load_zones might be defined there
        try:
             from menu import load_zones
             load_zones(self) # Pass GameState instance
             logger.info(f"Loaded {len(self.scoring_zones)} zones.")
        except ImportError:
             logger.error("Cannot import load_zones from menu. Zones will not be loaded.")
        except Exception as e:
             logger.exception(f"Error loading zones: {e}")

        self.special_hole = set_special_hole(self.scoring_zones)
        if self.special_hole:
             logger.info(f"Special hole set based on loaded zones.")
        else:
             logger.warning("No special hole could be set.")

        # Load high score for the current self.game_mode
        try:
            if os.path.exists(GameConstants.HIGH_SCORE_FILE) and os.path.getsize(GameConstants.HIGH_SCORE_FILE) > 0:
                with open(GameConstants.HIGH_SCORE_FILE, "r") as f:
                    data = json.load(f)
                    self.high_score = data.get(self.game_mode, {}).get("high_score", 0)
                    player = data.get(self.game_mode, {}).get("player", "N/A")
                    logger.info(f"Loaded high score for mode '{self.game_mode}': {self.high_score} by {player}")
            else:
                self.high_score = 0
                logger.info(f"High score file not found or empty for mode '{self.game_mode}'. Setting high score to 0.")
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load high score for mode '{self.game_mode}': {e}")
            self.high_score = 0
        except Exception as e:
            logger.exception(f"Unexpected error loading high score for mode '{self.game_mode}': {e}")
            self.high_score = 0

    def _save_high_score(self):
        """Saves high score data back to file, preserving other modes."""
        data = {}
        try: # Try reading existing data first
            if os.path.exists(GameConstants.HIGH_SCORE_FILE) and os.path.getsize(GameConstants.HIGH_SCORE_FILE) > 0:
                with open(GameConstants.HIGH_SCORE_FILE, "r") as f:
                    data = json.load(f)
            else: # Initialize structure if file missing or empty
                 data = {"classic": {"high_score": 0, "player": ""}, "timed": {"high_score": 0, "player": ""}}
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Read/Parse error on {GameConstants.HIGH_SCORE_FILE}: {e}. Will overwrite.")
            data = {"classic": {"high_score": 0, "player": ""}, "timed": {"high_score": 0, "player": ""}}
        except Exception as e:
             logger.exception(f"Unexpected error reading high score file: {e}")
             data = {"classic": {"high_score": 0, "player": ""}, "timed": {"high_score": 0, "player": ""}}


        # Ensure current mode exists in data structure
        if self.game_mode not in data:
            data[self.game_mode] = {"high_score": 0, "player": ""}

        # Check if the final game score (self.score) is a new high score for this mode
        current_saved_high = data[self.game_mode].get("high_score", 0)
        final_score = self.score # Score at the point _save_high_score is called

        # Apply potential doubling from special hole JUST FOR THE COMPARISON/SAVE check
        # The actual doubling for leaderboard is handled in logic_handler.save_score
        score_for_saving = final_score * 2 if self.special_hole_hit_this_session else final_score

        if score_for_saving > current_saved_high:
            logger.info(
                f"New high score ({score_for_saving}) for mode '{self.game_mode}' beats old ({current_saved_high}). Saving."
            )
            data[self.game_mode]["high_score"] = score_for_saving
            data[self.game_mode]["player"] = self.get_current_player().name
            data[self.game_mode]["date"] = time.strftime("%Y-%m-%d %H:%M:%S")
            # Update the internal high score variable as well
            self.high_score = score_for_saving
        else:
             logger.debug(f"Final score ({score_for_saving}) not higher than saved high score ({current_saved_high}) for '{self.game_mode}'.")


        # Save the potentially updated data structure
        try:
            with open(GameConstants.HIGH_SCORE_FILE, "w") as f:
                json.dump(data, f, indent=4)
            logger.debug(f"High score file saved.")
        except IOError as e:
            logger.error(f"Failed to save high score file: {e}")
        except Exception as e:
             logger.exception(f"Unexpected error writing high score file: {e}")

    def _set_initial_timer(self):
        """Sets the game timer based on the current game mode."""
        if self.game_mode == "timed":
            self.game_timer = GameConstants.TIMED_MODE_DURATION
            logger.info(f"Timed mode. Timer set to {self.game_timer}s.")
        else:
            self.game_timer = None
            logger.info("Classic mode. No timer set.")

    def get_current_player(self) -> Player:
        """Returns the current active player object."""
        if self.players and 0 <= self.current_player_index < len(self.players):
            return self.players[self.current_player_index]
        else:
            # This should ideally not happen after initialization, but provides a fallback
            logger.error(f"Invalid current_player_index ({self.current_player_index}) or empty players list. Returning fallback Player.")
            if not self.players: # Create a default if list is somehow empty
                self.players.append(Player("Player_Fallback"))
                self.current_player_index = 0
            return self.players[0]

    def reset_game(self) -> None:
        """Resets game variables for a new round or mode switch."""
        logger.info(f"Resetting game state for player {self.get_current_player().name}...")
        self.score = 0
        self.tracked_balls.clear()
        self.scored_balls.clear() # Legacy?
        # --- CORRECTION: Clear scored_positions on reset ---
        self.scored_positions.clear()
        # --- END CORRECTION ---
        self.next_ball_id = 0
        self.ball_trails.clear()
        self.ball_states.clear()
        self.previous_ball_states.clear()
        self.balls_in_zone.clear()
        self.ball_scored_zones.clear()
        self.ball_positions_history.clear()
        self.ball_zone_history.clear()
        self.zone_cooldown.clear()
        self.win_condition_met = False
        self.special_hole_hit_this_session = False
        self.low_time_warning_played = False # Reset low time sound flag

        # Reset menu states
        self.submenu_active = None
        self.submenu_items = []
        self.editing_zone_index = None
        self.editing_zone_mode = None
        self.editing_zone_points_input = None
        self.editing_player_index = None
        self.editing_player_mode = None
        self.editing_player_name_input = None
        self.selected_zone_for_edit = None
        self.zone_editing_action = None
        self.drag_start_pos = None
        self.original_zone_on_drag_start = None

        # Reset notifications via handler (if handler manages display state)
        if self.logic_handler:
            self.logic_handler.reset_notifications()
        else: # Should not happen after init
             self.notification_text = None
             self.notification_timer = 0.0
             self.achievement_notification = None
             self.achievement_notification_timer = 0.0


        # Reset player score
        self.get_current_player().reset_score()

        # Reload zones and high score for the *current* game mode
        # High score loading depends on self.game_mode, which might have just changed
        self._load_initial_state()

        # Reset timer based on current mode
        self._set_initial_timer()

        logger.info("Game state reset complete.")

    # --- Delegated Methods ---
    # These methods now call the corresponding method in the GameLogicHandler instance

    def update_scoring(self) -> None:
        self.logic_handler.update_scoring()

    def save_final_score(self) -> None:
        """Called typically at game over or mode switch."""
        self.logic_handler.save_score(self.get_current_player().name, self.game_mode)
        # Saving the high score file happens after leaderboard submission within save_score
        # self._save_high_score() # Now called within logic_handler.save_score

    def play_sound_effect(self, sound_type: str) -> None:
        """Requests the logic handler to play a specific sound type."""
        self.logic_handler.play_sound_by_type(sound_type)

    def check_achievements(self) -> None:
        self.logic_handler.check_achievements()

    def update_notifications_and_timers(self, dt: float) -> None:
        """Updates timers for notifications and achievements."""
        self.logic_handler.update_achievement_notification(dt)
        self.logic_handler.update_notifications(dt)
        # Update game timer if applicable
        if self.game_timer is not None:
            self.game_timer -= dt
            # Low time warning (handled by logic handler?)
            if 5 < self.game_timer <= 5 + dt and not self.low_time_warning_played:
                 self.logic_handler.play_sound_by_type('low_time')
                 self.low_time_warning_played = True # Track locally maybe? Or handler?
                 logger.info("Playing low time warning sound.")

            if self.game_timer <= 0 and self.current_state == CurrentGameState.PLAYING:
                 logger.info("Game timer reached zero.")
                 self.game_timer = 0
                 self.current_state = CurrentGameState.GAME_OVER
                 # Save score when timer runs out
                 self.save_final_score()


    def show_notification(self, text: str, duration: float = 2.0, is_error: bool = False) -> None:
         self.logic_handler.show_notification(text, duration, is_error)

    def set_volume_levels(self):
         """Applies volume based on flags via handler."""
         self.logic_handler.set_volume()

    def toggle_music(self):
         """Toggles music playback via handler."""
         self.logic_handler.toggle_music()