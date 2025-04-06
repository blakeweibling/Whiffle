# game_state.py

import cv2
import logging
import pygame
import time
import numpy as np
import os
import json
from typing import Optional, List, Tuple, Dict, Any, Callable

# Import constants consistently
from constants import (
    UIConstants,
    GameConstants,
    ScoringConstants,
)

# Import necessary components
from detection import BallDetector
from tracking import BallTracker
from leaderboard import Leaderboard
from player import Player

# Import effects for Fun Mode
from effects import BallTrail, Explosion

# Import types/enums from new location
from game_types import CurrentGameState

# Import utility functions
# Removed: is_ball_at_rest, is_ball_zone_stable (no longer needed here)
from game_state_utils import (
    initialize_sounds,
    initialize_achievements,
    load_achievements,
    save_achievements,
    load_hsv_ranges,
    load_settings,
    load_initial_state,
    set_volume,
    load_background_music, # <--- Ensure this is imported
    # play_sound, check_achievements, show_notification etc. are now helpers or utils called elsewhere
)

logger = logging.getLogger(__name__)


# CurrentGameState enum moved to game_types.py


class GameState:
    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        logger.info("Starting GameState initialization...")

        # Initial Volume Levels & Flags (Defaults, overwritten by load_settings)
        self.current_sound_volume: float = GameConstants.INITIAL_SOUND_VOLUME
        self.current_music_volume: float = GameConstants.INITIAL_MUSIC_VOLUME
        self.game_sounds_on: bool = True
        self.background_music_on: bool = True

        # Camera Initialization
        self.camera_available: bool = GameConstants.USE_CAMERA
        self.static_frame: Optional[np.ndarray] = None
        if self.camera_available:
            logger.info(f"Attempting camera {GameConstants.CAMERA_INDEX} w/ backend {GameConstants.CAMERA_BACKEND}")
            self.cap: Optional[cv2.VideoCapture] = cv2.VideoCapture(GameConstants.CAMERA_INDEX, GameConstants.CAMERA_BACKEND)
            if not self.cap or not self.cap.isOpened(): logger.error("Failed to open camera."); self.camera_available=False; self.cap=None
            else:
                 logger.info("Setting camera resolution..."); self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, UIConstants.WINDOW_WIDTH); self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, UIConstants.WINDOW_HEIGHT)
                 w=self.cap.get(cv2.CAP_PROP_FRAME_WIDTH); h=self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                 if w!=UIConstants.WINDOW_WIDTH or h!=UIConstants.WINDOW_HEIGHT: logger.warning(f"Cam res mismatch: {int(w)}x{int(h)}")
                 else: logger.info(f"Camera resolution: {int(w)}x{int(h)}")
        else: self.cap = None

        if not self.camera_available: # If camera failed or was configured off
            logger.warning(f"Using static frame: {GameConstants.STATIC_FRAME_FILE}")
            try:
                self.static_frame = cv2.imread(GameConstants.STATIC_FRAME_FILE)
                if self.static_frame is None: raise FileNotFoundError("Static frame not found/invalid.")
                if self.static_frame.shape[0]==0 or self.static_frame.shape[1]==0: raise ValueError("Static image invalid dims.")
                if len(self.static_frame.shape)!=3 or self.static_frame.shape[2]!=3: raise ValueError("Static image not BGR.")
                self.static_frame=cv2.resize(self.static_frame, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
            except Exception as e: logger.exception(f"Static frame load fail: {e}"); raise

        # Game Variables
        self.score: int = 0; self.high_score: int = 0
        self.scoring_zones: List[Tuple[int, int, int, int, int]] = []
        self.drawing: bool = False; self.start_x: Optional[int] = None; self.start_y: Optional[int] = None
        self.temp_zone: Optional[Tuple[int, int, int, int]] = None; self.special_hole: Optional[Tuple[int, int, int, int, int]] = None
        self.drawing_points_input: str = ""

        # Detection & Tracking
        self.detector = BallDetector(); self.tracker = BallTracker()
        self.tracked_balls: List[Tuple[int, int, float, int, int, str]] = []
        self.next_ball_id: int = 0; self.frame_count: int = 0

        # Scoring State Variables
        self.scored_balls: List[int] = []; self.scored_positions: Dict[Tuple[int, int], int] = {}
        self.balls_in_zone: Dict[int, Tuple[int, int, int, int, int]] = {}; self.ball_scored_zones: Dict[int, int] = {}
        self.ball_states: Dict[int, Dict[str, Any]] = {}; self.previous_ball_states: Dict[int, Dict[str, Any]] = {}
        self.ball_positions_history: Dict[int, List[Tuple[int, int]]] = {}; self.ball_zone_history: Dict[int, List[Optional[int]]] = {}
        self.special_hole_hit_this_session: bool = False; self.zone_cooldown: Dict[int, float] = {}

        # Menu State Variables
        self.submenu_active: Optional[str] = None; self.submenu_items: List[Tuple[Tuple[int, int, int, int], Any, str]] = []
        self.menu_pos: Tuple[int, int] = (0,0); self.menu_width: int = 600; self.menu_height: int = 450
        self.menu_cache: Optional[np.ndarray] = None; self.menu_cache_key: Optional[Any] = None
        self.edit_zones_items_per_page: int = 8; self.edit_zones_current_page: int = 1
        self.editing_zone_index: Optional[int]=None; self.editing_zone_mode: Optional[str]=None; self.editing_zone_points_input: Optional[str]=None
        self.selected_zone_for_edit: Optional[int]=None; self.zone_editing_action: Optional[str]=None; self.drag_start_pos: Optional[Tuple[int,int]]=None; self.original_zone_on_drag_start: Optional[Tuple[int,int,int,int,int]]=None
        self.editing_player_index: Optional[int]=None; self.editing_player_mode: Optional[str]=None; self.editing_player_name_input: Optional[str]=None

        # Initial Player Name Input State
        self.player_name_input_active: bool = True; self.current_player_name_input: str = ""

        # Sound Objects
        self.score_sound: Optional[pygame.mixer.Sound] = None; self.background_music: Optional[pygame.mixer.Sound] = None
        self.selected_music_track_index: int = 0; self.achievement_sound: Optional[pygame.mixer.Sound] = None
        self.low_time_sound: Optional[pygame.mixer.Sound] = None; self.low_time_warning_played: bool = False

        # Game Mode / State
        self.game_mode: str = "classic"; self.game_timer: Optional[float] = None
        self.current_state: CurrentGameState = CurrentGameState.GETTING_PLAYER_NAME
        self.previous_state: Optional[CurrentGameState] = None
        self.win_score: int = GameConstants.TIMED_MODE_WIN_SCORE; self.win_condition_met: bool = False

        # Achievements
        self.achievements: List[Any] = []; self.achievement_notification: Optional[str] = None; self.achievement_notification_timer: float = 0.0

        # Debug Flags
        self.debug_mode: bool = False; self.fps: float = 0.0; self.show_debug_overlay: bool = False

        # Players
        self.players: List[Player] = [Player("Player 1")]; self.current_player_index: int = 0

        # Leaderboard
        self.leaderboard = Leaderboard(supabase_url, supabase_key); self.leaderboard_mode: str = "classic"

        # HSV Ranges
        self.hsv_ranges: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}

        # Notifications
        self.notification_text: Optional[str] = None; self.notification_timer: float = 0.0; self.notification_color: Tuple[int, int, int] = UIConstants.GREEN

        # Fun Mode Effects
        self.active_trails: Dict[int, BallTrail] = {}; self.active_explosions: List[Explosion] = []

        # --- Init Calls Using Utility Functions ---
        logger.info("Loading initial state via utils...")
        load_settings(self)
        load_initial_state(self)

        try:
            logger.info("Initializing sounds via utils..."); sound_results = initialize_sounds()
            if isinstance(sound_results, tuple) and len(sound_results) == 2: self.score_sound, self.low_time_sound = sound_results
            else: logger.error(f"init sounds bad format: {type(sound_results)}"); self.score_sound, self.low_time_sound = None, None
        except Exception as e: logger.exception(f"Sound init error: {e}"); self.score_sound, self.low_time_sound = None, None

        # --- Start CORRECTED Block for loading background music ---
        # Directly call the imported utility function
        logger.info("Loading background music via utils...")
        self.background_music = load_background_music(self, self.selected_music_track_index)
        if self.background_music is None:
            logger.warning("Failed to load initial background music track.")
        # --- End CORRECTED Block ---

        # Set initial volumes based on loaded settings and flags
        set_volume(self)

        logger.info("Initializing achievements via utils..."); self.achievements = initialize_achievements()
        logger.info("Loading achievements status via utils..."); load_achievements(self, GameConstants.ACHIEVEMENTS_FILE)
        logger.info("Loading HSV ranges via utils..."); self.hsv_ranges = load_hsv_ranges(GameConstants.HSV_RANGES_FILE)

        # Initialize timer based on game_mode
        if self.game_mode == "timed": self.game_timer = GameConstants.TIMED_MODE_DURATION
        elif self.game_mode == "survival": self.game_timer = GameConstants.SURVIVAL_MODE_START_TIME
        else: self.game_timer = None

        logger.info("GameState initialized successfully.")


    # --- Methods remaining in GameState ---

    def get_current_player(self) -> Player:
        """Returns the current player object."""
        # (Code unchanged)
        if self.players and 0 <= self.current_player_index < len(self.players): return self.players[self.current_player_index]
        logger.warning(f"Player index {self.current_player_index} invalid. Returning fallback.")
        if not self.players: self.players.append(Player("Player 1")); self.current_player_index = 0
        return self.players[0]

    # --- Methods removed from GameState (now in helpers or utils) ---