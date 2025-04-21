# game_state.py

import cv2
import logging
import pygame
import time
import numpy as np
import os
import json
from typing import Optional, List, Tuple, Dict, Any, Callable
from enum import Enum, auto

# Use constants consistently
# <<< MODIFIED: Import new constants >>>
from constants import (
    UIConstants,
    GameConstants,
    ScoringConstants,
    GameConstants,
    GameConstants,
    GameConstants,
    GameConstants,
    GameConstants,
    GameConstants,
    GameConstants,
    GameConstants,
)

from detection import BallDetector
from tracking import BallTracker
from leaderboard import Leaderboard
from player import Player
from scoring import is_in_scoring_zone

# Import effects for Fun Mode
from effects import BallTrail, Explosion

# Import reconciled utils functions
from game_state_utils import (
    set_special_hole,
    initialize_sounds,  # Keep this, it loads OTHER sounds
    initialize_achievements,
    load_achievements,
    save_achievements,
    load_hsv_ranges,
    save_hsv_ranges,
    is_ball_at_rest,
    is_ball_zone_stable,
)

logger = logging.getLogger(__name__)


# Add FUN mode
class CurrentGameState(Enum):
    GETTING_PLAYER_NAME = auto()
    PLAYING = auto()
    MENU = auto()
    ZONE_EDITING = auto()
    GAME_OVER = auto()
    PAUSED = auto()
    FUN = auto()


class GameState:
    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        logger.info("Starting GameState initialization...")

        # <<< NEW: Initialize Current Volume Levels >>>
        # Initialize with defaults, load_settings will overwrite if file exists
        self.current_sound_volume: float = GameConstants.INITIAL_SOUND_VOLUME
        self.current_music_volume: float = GameConstants.INITIAL_MUSIC_VOLUME
        # <<< END NEW >>>

        # Camera Initialization
        self.camera_available: bool = GameConstants.USE_CAMERA
        self.static_frame: Optional[np.ndarray] = None
        if self.camera_available:
            logger.info(
                f"Attempting to open camera at index {GameConstants.CAMERA_INDEX} with backend {GameConstants.CAMERA_BACKEND}"
            )
            self.cap: Optional[cv2.VideoCapture] = cv2.VideoCapture(
                GameConstants.CAMERA_INDEX, GameConstants.CAMERA_BACKEND
            )
            if not self.cap.isOpened():
                logger.error(
                    f"Failed to open camera at index {GameConstants.CAMERA_INDEX} with backend {GameConstants.CAMERA_BACKEND}, despite earlier success"
                )
                self.camera_available = False
        else:
            logger.info(
                "Camera not available based on configuration. Skipping camera initialization."
            )
            self.cap = None

        if self.camera_available:
            logger.info("Setting camera resolution...")
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, UIConstants.WINDOW_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, UIConstants.WINDOW_HEIGHT)
            w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            if w != UIConstants.WINDOW_WIDTH or h != UIConstants.WINDOW_HEIGHT:
                logger.warning(
                    f"Cam res mismatch: Got {int(w)}x{int(h)}, expected {UIConstants.WINDOW_WIDTH}x{UIConstants.WINDOW_HEIGHT}"
                )
            else:
                logger.info(f"Camera resolution: {int(w)}x{int(h)}")
        else:
            logger.warning(f"Using static frame: {GameConstants.STATIC_FRAME_FILE}")
            logger.info("Loading static frame...")
            try:
                self.static_frame = cv2.imread(GameConstants.STATIC_FRAME_FILE)
                if self.static_frame is None:
                    raise FileNotFoundError(
                        f"{GameConstants.STATIC_FRAME_FILE} not found or invalid."
                    )
                if self.static_frame.shape[0] == 0 or self.static_frame.shape[1] == 0:
                    raise ValueError("Static image has invalid dimensions.")
                if len(self.static_frame.shape) != 3 or self.static_frame.shape[2] != 3:
                    raise ValueError("Static image not 3-channel BGR.")
                self.static_frame = cv2.resize(
                    self.static_frame,
                    (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT),
                )
                logger.info(f"Using {GameConstants.STATIC_FRAME_FILE}.")
            except Exception as e:
                logger.exception(f"Static frame load/validate fail: {e}")
                raise

        # Game Variables
        logger.info("Initializing game variables...")
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
        logger.info("Initializing detection and tracking...")
        self.detector = BallDetector()
        self.tracker = BallTracker()
        self.tracked_balls: List[Tuple[int, int, float, int, int, str]] = []
        self.next_ball_id: int = 0
        self.frame_count: int = 0

        # Scoring State
        self.scored_balls: List[int] = []
        self.scored_positions: Dict[Tuple[int, int], int] = {}
        self.balls_in_zone: Dict[int, Tuple[int, int, int, int, int]] = {}
        self.ball_scored_zones: Dict[int, int] = {}
        self.ball_states: Dict[int, Dict[str, Any]] = {}
        self.previous_ball_states: Dict[int, Dict[str, Any]] = {}
        self.ball_positions_history: Dict[int, List[Tuple[int, int]]] = {}
        self.ball_zone_history: Dict[int, List[Optional[int]]] = {}
        self.special_hole_hit_this_session: bool = False

        # Zone Cooldown State
        self.zone_cooldown: Dict[int, float] = {}

        # Menu State
        self.submenu_active: Optional[str] = None
        self.submenu_items: List[Tuple[Tuple[int, int, int, int], Any, str]] = []
        self.menu_pos: Tuple[int, int] = (0, 0)
        self.menu_width: int = 400
        self.menu_height: int = 450
        self.menu_cache: Optional[np.ndarray] = None
        self.menu_cache_key: Optional[Any] = None
        self.edit_zones_items_per_page: int = 8
        self.edit_zones_current_page: int = 1

        # Zone Menu Editing (Points)
        self.editing_zone_index: Optional[int] = None
        self.editing_zone_mode: Optional[str] = None
        self.editing_zone_points_input: Optional[str] = None

        # Interactive Zone Editing State (Move/Resize)
        self.selected_zone_for_edit: Optional[int] = None
        self.zone_editing_action: Optional[str] = None
        self.drag_start_pos: Optional[Tuple[int, int]] = None
        self.original_zone_on_drag_start: Optional[Tuple[int, int, int, int, int]] = (
            None
        )

        # Player Name Editing State (Menu)
        self.editing_player_index: Optional[int] = None
        self.editing_player_mode: Optional[str] = None
        self.editing_player_name_input: Optional[str] = None

        # Initial Player Name Input State
        self.player_name_input_active: bool = True
        self.current_player_name_input: str = ""

        # Sounds
        # <<< MODIFIED: Keep flags separate from volume for mute functionality >>>
        self.game_sounds_on: bool = True  # User can toggle this for mute
        self.background_music_on: bool = True  # User can toggle this for mute
        # <<< END MODIFIED >>>
        self.score_sound: Optional[pygame.mixer.Sound] = None
        self.background_music: Optional[pygame.mixer.Sound] = None
        self.selected_music_track_index: int = 0
        self.achievement_sound: Optional[pygame.mixer.Sound] = (
            None  # Needs separate loading if desired
        )
        self.low_time_sound: Optional[pygame.mixer.Sound] = None
        self.low_time_warning_played: bool = False

        # Game Mode / State
        self.game_mode: str = "classic"
        self.game_timer: Optional[float] = None
        self.current_state: CurrentGameState = CurrentGameState.GETTING_PLAYER_NAME
        self.previous_state: Optional[CurrentGameState] = None
        self.win_score: int = GameConstants.TIMED_MODE_WIN_SCORE
        self.win_condition_met: bool = False

        # Achievements
        self.achievements: List[Any] = []
        self.achievement_notification: Optional[str] = None
        self.achievement_notification_timer: float = 0.0

        # Debug
        self.debug_mode: bool = False
        self.fps: float = 0.0
        self.show_debug_overlay: bool = False

        # Players
        self.players: List[Player] = [Player("Player 1")]
        self.current_player_index: int = 0

        # Leaderboard
        self.leaderboard = Leaderboard(supabase_url, supabase_key)
        self.leaderboard_mode: str = "classic"

        # HSV
        self.hsv_ranges: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}

        # Notifications
        self.notification_text: Optional[str] = None
        self.notification_timer: float = 0.0
        self.notification_color: Tuple[int, int, int] = UIConstants.GREEN

        # Fun Mode Effects
        self.active_trails: Dict[int, BallTrail] = {}
        self.active_explosions: List[Explosion] = []

        # --- Init Calls ---
        logger.info("Loading initial state...")
        self._load_initial_state()  # Includes loading zones and high scores
        self._load_settings()  # <<< NEW: Load volume settings >>>

        try:
            logger.info("Initializing sounds (excluding background music)...")
            # --- UPDATED: Correctly unpack only two return values ---
            sound_results = initialize_sounds()
            if (
                isinstance(sound_results, tuple) and len(sound_results) == 2
            ):  # Expecting 2 now
                self.score_sound, self.low_time_sound = sound_results  # Unpack 2
                logger.info(
                    "Sounds initialized (score, low_time). Background music loaded separately."
                )
            else:
                # Log error but don't disable *all* sounds if format is wrong
                logger.error(
                    f"initialize_sounds returned unexpected format: {type(sound_results)}. Score/LowTime sounds may be disabled."
                )
                self.score_sound, self.low_time_sound = None, None
            # --- END UPDATE ---
        except Exception as e:
            logger.exception(
                f"Error during sound initialization: {e}. Score/LowTime sounds disabled."
            )
            self.score_sound, self.low_time_sound = None, None

        # Load the selected background music track
        self.background_music = self._load_background_music(
            self.selected_music_track_index
        )
        # Update music on flag based on loading success - DO NOT OVERWRITE USER SETTING
        # self.background_music_on = (
        #     self.background_music is not None and self.background_music_on
        # ) # <<< REMOVED this logic >>>

        # --- Check if sounds *could* be loaded to set initial 'on' state if desired ---
        # (Keeping toggles defaulting to True for now)
        # if self.score_sound is None or self.low_time_sound is None:
        #     # self.game_sounds_on = False # Option: default to off if loading fails
        #     logger.warning(
        #         "One or more sound effects failed to load."
        #     )

        self.set_volume()  # <<< MODIFIED: Set volumes using current levels and flags >>>

        logger.info("Initializing achievements...")
        self.achievements = initialize_achievements()
        logger.info("Loading achievements...")
        load_achievements(self, GameConstants.ACHIEVEMENTS_FILE)
        logger.info("Loading HSV ranges...")
        self.hsv_ranges = load_hsv_ranges(GameConstants.HSV_RANGES_FILE)

        # Initialize timer based on game_mode
        if self.game_mode == "timed":
            self.game_timer = GameConstants.TIMED_MODE_DURATION
            logger.info(
                f"Initial game mode is timed. Timer set to {self.game_timer} seconds."
            )
        elif self.game_mode == "survival":
            self.game_timer = GameConstants.SURVIVAL_MODE_START_TIME
            logger.info(
                f"Initial game mode is survival. Timer set to {self.game_timer} seconds."
            )
        else:
            self.game_timer = None

        logger.info("GameState initialized successfully.")

    # <<< NEW: Load Settings Method >>>
    def _load_settings(self) -> None:
        """Loads settings like volume from the settings file."""
        settings_file = GameConstants.SETTINGS_FILE
        try:
            if os.path.exists(settings_file) and os.path.getsize(settings_file) > 0:
                with open(settings_file, "r") as f:
                    settings_data = json.load(f)
                    # Load volume if present and valid, otherwise keep initial default
                    loaded_sound_vol = settings_data.get("sound_volume")
                    if (
                        isinstance(loaded_sound_vol, (int, float))
                        and 0.0 <= loaded_sound_vol <= 1.0
                    ):
                        self.current_sound_volume = float(loaded_sound_vol)
                    else:
                        logger.warning(
                            f"Invalid/missing 'sound_volume' in {settings_file}, using default."
                        )
                        self.current_sound_volume = (
                            GameConstants.INITIAL_SOUND_VOLUME
                        )  # Fallback

                    loaded_music_vol = settings_data.get("music_volume")
                    if (
                        isinstance(loaded_music_vol, (int, float))
                        and 0.0 <= loaded_music_vol <= 1.0
                    ):
                        self.current_music_volume = float(loaded_music_vol)
                    else:
                        logger.warning(
                            f"Invalid/missing 'music_volume' in {settings_file}, using default."
                        )
                        self.current_music_volume = (
                            GameConstants.INITIAL_MUSIC_VOLUME
                        )  # Fallback

                    # Load on/off flags if they exist
                    if "game_sounds_on" in settings_data and isinstance(
                        settings_data["game_sounds_on"], bool
                    ):
                        self.game_sounds_on = settings_data["game_sounds_on"]
                    if "background_music_on" in settings_data and isinstance(
                        settings_data["background_music_on"], bool
                    ):
                        self.background_music_on = settings_data["background_music_on"]

                    logger.info(
                        f"Loaded settings from {settings_file}: SoundVol={self.current_sound_volume:.2f}, MusicVol={self.current_music_volume:.2f}, SoundsOn={self.game_sounds_on}, MusicOn={self.background_music_on}"
                    )

            else:
                logger.info(
                    f"{settings_file} not found or empty. Using initial default volumes."
                )
                self.current_sound_volume = GameConstants.INITIAL_SOUND_VOLUME
                self.current_music_volume = GameConstants.INITIAL_MUSIC_VOLUME
                # Keep default True for flags if file doesn't exist
                self.game_sounds_on = True
                self.background_music_on = True
        except (IOError, json.JSONDecodeError) as e:
            logger.error(
                f"Failed to load settings from {settings_file}: {e}. Using defaults."
            )
            self.current_sound_volume = GameConstants.INITIAL_SOUND_VOLUME
            self.current_music_volume = GameConstants.INITIAL_MUSIC_VOLUME
            self.game_sounds_on = True
            self.background_music_on = True
        except Exception as e:
            logger.exception(f"Unexpected error loading settings: {e}")
            self.current_sound_volume = GameConstants.INITIAL_SOUND_VOLUME
            self.current_music_volume = GameConstants.INITIAL_MUSIC_VOLUME
            self.game_sounds_on = True
            self.background_music_on = True

    # <<< NEW: Save Settings Method >>>
    def _save_settings(self) -> None:
        """Saves current settings like volume to the settings file."""
        settings_file = GameConstants.SETTINGS_FILE
        settings_data = {
            "sound_volume": self.current_sound_volume,
            "music_volume": self.current_music_volume,
            "game_sounds_on": self.game_sounds_on,
            "background_music_on": self.background_music_on,
            # Add other settings here if needed in the future
        }
        try:
            with open(settings_file, "w") as f:
                json.dump(settings_data, f, indent=4)
            logger.debug(f"Saved settings to {settings_file}")
        except IOError as e:
            logger.error(f"Failed to save settings to {settings_file}: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error saving settings: {e}")

    def _load_background_music(self, track_index: int) -> Optional[pygame.mixer.Sound]:
        """Loads a specific background music track by index."""
        if not (0 <= track_index < len(GameConstants.BACKGROUND_MUSIC_TRACKS)):
            logger.error(f"Invalid background music track index: {track_index}")
            return None

        track_filename = GameConstants.BACKGROUND_MUSIC_TRACKS[track_index]
        track_path = os.path.join(GameConstants.SOUND_EFFECTS_PATH, track_filename)
        logger.info(f"Attempting to load background music: {track_path}")

        try:
            if os.path.exists(track_path):
                music = pygame.mixer.Sound(track_path)
                # <<< MODIFIED: Set initial volume using set_volume method later >>>
                # music.set_volume(
                #     self.current_music_volume # Use current setting
                #     if self.background_music_on
                #     else 0.0
                # )
                logger.info(f"Successfully loaded background music: {track_filename}")
                return music
            else:
                logger.warning(f"Background music file not found: {track_path}")
                return None
        except pygame.error as e:
            logger.error(f"Pygame error loading background music {track_filename}: {e}")
            return None
        except Exception as e:
            logger.exception(
                f"Unexpected error loading background music {track_filename}: {e}"
            )
            return None

    def change_music_track(self, new_index: int):
        """Stops current music, loads and plays the new track if music is enabled."""
        num_tracks = len(GameConstants.BACKGROUND_MUSIC_TRACKS)
        if not (0 <= new_index < num_tracks):
            logger.warning(f"Attempted to change to invalid track index: {new_index}")
            return

        if new_index == self.selected_music_track_index and self.background_music:
            logger.debug(f"Track {new_index + 1} is already selected and loaded.")
            # Ensure it plays if music is on and it stopped somehow
            self.set_volume()  # Apply current volume/mute state
            if self.background_music_on and not pygame.mixer.get_busy():
                try:
                    self.background_music.play(-1)
                except pygame.error as e:
                    logger.error(f"Error re-playing music track {new_index+1}: {e}")
            return

        logger.info(f"Changing background music track to index {new_index}...")
        self.selected_music_track_index = new_index

        if self.background_music:
            self.background_music.stop()
            logger.debug("Stopped previous background music track.")

        self.background_music = self._load_background_music(
            self.selected_music_track_index
        )

        # Apply volume/play state AFTER loading the new track
        self.set_volume()

        # Try to play immediately if music is on
        if self.background_music and self.background_music_on:
            try:
                self.background_music.play(-1)
                logger.info(
                    f"Started playing new track: {GameConstants.BACKGROUND_MUSIC_TRACKS[new_index]}"
                )
            except pygame.error as e:
                logger.error(
                    f"Error playing newly loaded music track {new_index+1}: {e}"
                )
                self.background_music_on = False  # Turn off if play fails
                self.set_volume()
        elif not self.background_music:
            logger.error(f"Failed to load track index {new_index}.")
            # Ensure music is marked as off if loading failed
            self.background_music_on = False
            self.set_volume()

    def toggle_background_music(self) -> None:
        """Toggle background music ON/OFF flag and update playback/volume."""
        self.background_music_on = not self.background_music_on
        logger.info(
            f"Background music toggled {'ON' if self.background_music_on else 'OFF'}"
        )
        self.set_volume()  # Apply the change (stops or starts/sets volume)
        self._save_settings()  # Save the toggle state

    # <<< MODIFIED: set_volume applies current volume levels AND on/off flags >>>
    def set_volume(self):
        """Sets volume for all sounds based on current levels and on/off flags."""
        sound_vol = self.current_sound_volume if self.game_sounds_on else 0.0
        music_vol = self.current_music_volume if self.background_music_on else 0.0

        if self.score_sound:
            try:
                self.score_sound.set_volume(sound_vol)
            except Exception as e:
                logger.error(f"Error setting score_sound volume: {e}")
        if self.low_time_sound:
            try:
                self.low_time_sound.set_volume(sound_vol)
            except Exception as e:
                logger.error(f"Error setting low_time_sound volume: {e}")
        if self.achievement_sound:
            try:
                self.achievement_sound.set_volume(sound_vol)
            except Exception as e:
                logger.error(f"Error setting achievement_sound volume: {e}")

        if self.background_music:
            try:
                self.background_music.set_volume(music_vol)
                # Start or stop music based on the flag
                is_playing = any(
                    ch and ch.get_sound() == self.background_music
                    for ch in [
                        pygame.mixer.Channel(i)
                        for i in range(pygame.mixer.get_num_channels())
                        if pygame.mixer.Channel(i).get_busy()
                    ]
                )

                if self.background_music_on and not is_playing:
                    self.background_music.play(-1)
                    logger.debug(f"Played background music at volume {music_vol:.2f}")
                elif not self.background_music_on and is_playing:
                    self.background_music.stop()
                    logger.debug("Stopped background music.")
            except Exception as e:
                logger.error(f"Error setting/playing music volume: {e}")

        logger.debug(
            f"Volumes applied: Sounds={sound_vol:.2f} (Flag:{self.game_sounds_on}), Music={music_vol:.2f} (Flag:{self.background_music_on})"
        )
        # Note: We don't call _save_settings here, only when user *changes* the volume via UI

    def _load_initial_state(self):
        """Loads persistent state like zones and high score for current mode."""
        from menu import load_zones
        from game_state_utils import set_special_hole

        load_zones(self)  # Load scoring zones first
        self.special_hole = set_special_hole(
            self.scoring_zones
        )  # Set special hole based on loaded zones

        # Load high scores
        try:
            if os.path.exists(GameConstants.HIGH_SCORE_FILE):
                if os.path.getsize(GameConstants.HIGH_SCORE_FILE) > 0:
                    with open(GameConstants.HIGH_SCORE_FILE, "r") as f:
                        data = json.load(f)
                        # Ensure game_mode exists in data, default to 0 if not
                        self.high_score = data.get(self.game_mode, {}).get(
                            "high_score", 0
                        )
                        logger.info(
                            f"Loaded high score for mode '{self.game_mode}': {self.high_score}"
                        )
                else:
                    self.high_score = 0
                    logger.warning(f"High score file exists but is empty.")
            else:
                self.high_score = 0
                logger.info(f"High score file not found.")
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed load high score: {e}")
            self.high_score = 0
        except Exception as e:
            logger.exception(f"Unexpected error loading high score: {e}")
            self.high_score = 0

    def _save_high_score(self):
        """Saves high score data for all modes."""
        # (Content unchanged from previous version)
        data = {}
        try:
            if os.path.exists(GameConstants.HIGH_SCORE_FILE):
                if os.path.getsize(GameConstants.HIGH_SCORE_FILE) > 0:
                    with open(GameConstants.HIGH_SCORE_FILE, "r") as f:
                        data = json.load(f)
                else:
                    logger.warning(
                        f"High score file exists but is empty: {GameConstants.HIGH_SCORE_FILE}"
                    )
                    data = {}  # Initialize empty if file was empty
            else:
                # If file doesn't exist, initialize structure
                data = {
                    mode: {}
                    for mode in ["classic", "timed", "fun", "practice", "survival"]
                }

            # Ensure current game mode exists in the dictionary
            if self.game_mode not in data:
                data[self.game_mode] = {}

        except (IOError, json.JSONDecodeError) as e:
            logger.error(
                f"Could not read/parse high score file ({GameConstants.HIGH_SCORE_FILE}): {e}. Will overwrite."
            )
            data = {
                mode: {} for mode in ["classic", "timed", "fun", "practice", "survival"]
            }
        except Exception as e:
            logger.exception(f"Unexpected error reading high score file: {e}")
            data = {
                mode: {} for mode in ["classic", "timed", "fun", "practice", "survival"]
            }

        current_saved_high = data.get(self.game_mode, {}).get("high_score", 0)

        if self.score > current_saved_high:
            data[self.game_mode]["high_score"] = self.score
            data[self.game_mode]["player"] = self.get_current_player().name
            data[self.game_mode]["date"] = time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(
                f"Updating high score file for mode '{self.game_mode}' to {self.score} by {self.get_current_player().name}"
            )
        else:
            logger.debug(
                f"Current session score ({self.score}) not greater than saved high score ({current_saved_high}) for mode '{self.game_mode}'. No update needed."
            )

        try:
            with open(GameConstants.HIGH_SCORE_FILE, "w") as f:
                json.dump(data, f, indent=4)
            logger.debug(f"Saved high scores file.")
        except IOError as e:
            logger.error(f"Save high score fail: {e}")

    def get_current_player(self) -> Player:
        """Returns the current player object."""
        # (Content unchanged from previous version)
        if self.players and 0 <= self.current_player_index < len(self.players):
            return self.players[self.current_player_index]
        logger.warning(
            f"Player index {self.current_player_index} out of bounds for {len(self.players)} players. Returning fallback."
        )
        if not self.players:
            self.players.append(Player("Player 1"))
            self.current_player_index = 0
        return self.players[0]  # Return first player as fallback

    def save_score(self, player_name: str, mode: Optional[str] = None) -> None:
        """Checks for special hole bonus, saves score to leaderboard, and updates high score."""
        # (Content unchanged from previous version)
        final_score = self.score
        doubled = False
        if self.special_hole_hit_this_session:
            logger.info(
                f"Special hole was hit! Doubling final score {final_score} for {player_name}."
            )
            final_score *= 2
            doubled = True

        score_to_save = final_score
        current_mode = mode or self.game_mode

        if score_to_save > 0:
            logger.info(
                f"Saving score for {player_name}: {score_to_save} (Mode: {current_mode}){' (Doubled)' if doubled else ''}"
            )
            if hasattr(self, "leaderboard") and self.leaderboard:
                self.leaderboard.submit_score(player_name, score_to_save, current_mode)
            else:
                logger.error(
                    "Leaderboard object not available in game_state. Cannot submit score online."
                )

            # Use score_to_save for high score check
            if current_mode == self.game_mode and score_to_save > self.high_score:
                logger.info(
                    f"New high score for current mode '{current_mode}': {score_to_save}"
                )
                self.high_score = score_to_save  # Update internal high score

            self._save_high_score()  # Save potentially updated high score to file
        else:
            logger.info(f"Score is {score_to_save}, not saving.")

    def play_sound(self, sound: Optional[pygame.mixer.Sound]) -> None:
        """Play sound effect if enabled and sound exists."""
        # <<< MODIFIED: Volume is now handled by set_volume, just play if enabled >>>
        if self.game_sounds_on and sound:
            try:
                # sound.set_volume(self.current_sound_volume) # Removed, volume set globally by set_volume
                sound.play()
            except pygame.error as e:
                logger.error(f"Sound play error: {e}")
        elif not self.game_sounds_on:
            logger.debug("Sound not played because game_sounds_on is False.")
        elif not sound:
            logger.debug("Sound not played because sound object is None.")

    def check_achievements(self) -> None:
        """Check achievements and notify."""
        # (Content unchanged from previous version)
        if not hasattr(self, "achievements"):
            return
        newly_unlocked = False
        for ach in self.achievements:
            if not ach.unlocked and ach.check(self):
                ach.unlocked = True
                logger.info(f"Achieved: {ach.name} - {ach.description}")
                self.show_notification(f"Unlocked: {ach.name}", duration=5.0)
                self.play_sound(
                    self.achievement_sound
                )  # achievement_sound needs separate loading if desired
                newly_unlocked = True

        if newly_unlocked:
            save_achievements(self, GameConstants.ACHIEVEMENTS_FILE)

    def update_achievement_notification(self, dt: float) -> None:
        """Updates timer for achievement popup."""
        # (Content unchanged from previous version)
        if self.achievement_notification_timer > 0:
            self.achievement_notification_timer -= dt
            if self.achievement_notification_timer <= 0:
                self.achievement_notification = None

    def show_notification(
        self, text: str, duration: float = 2.0, is_error: bool = False
    ) -> None:
        """Display a notification message."""
        # (Content unchanged from previous version)
        self.notification_text = text
        self.notification_timer = duration
        self.notification_color = UIConstants.RED if is_error else UIConstants.GREEN
        log_level = logging.WARNING if is_error else logging.INFO
        logger.log(log_level, f"Notify: {text}")

    def update_notifications(self, dt: float) -> None:
        """Update notification timer."""
        # (Content unchanged from previous version)
        if self.notification_timer > 0:
            self.notification_timer -= dt
            if self.notification_timer <= 0:
                self.notification_text = None

    def update_scoring(self) -> None:
        """Processes tracked balls to determine scores using ZONE-BASED cooldown."""
        # (Content mostly unchanged, added debug logs)
        newly_scored_pts_this_frame = 0
        current_time = time.time()
        tracked_ids_this_frame = {b[3] for b in self.tracked_balls if len(b) >= 6}

        # Clean up state for balls that are no longer tracked
        keys_to_remove = set()
        keys_to_remove.update(set(self.ball_states.keys()) - tracked_ids_this_frame)
        keys_to_remove.update(
            set(self.previous_ball_states.keys()) - tracked_ids_this_frame
        )
        keys_to_remove.update(
            set(self.ball_positions_history.keys()) - tracked_ids_this_frame
        )
        keys_to_remove.update(
            set(self.ball_zone_history.keys()) - tracked_ids_this_frame
        )
        keys_to_remove.update(set(self.balls_in_zone.keys()) - tracked_ids_this_frame)
        keys_to_remove.update(
            set(self.ball_scored_zones.keys()) - tracked_ids_this_frame
        )
        # Also clean up trails for untracked balls
        if hasattr(self, "active_trails"):
            keys_to_remove.update(
                set(self.active_trails.keys()) - tracked_ids_this_frame
            )

        if keys_to_remove:
            logger.debug(f"Cleaning up state for untracked ball IDs: {keys_to_remove}")
            dicts_to_clean = [
                self.ball_states,
                self.previous_ball_states,
                self.ball_positions_history,
                self.ball_zone_history,
                self.balls_in_zone,
                self.ball_scored_zones,
            ]
            # Add active_trails if it exists
            if hasattr(self, "active_trails"):
                dicts_to_clean.append(self.active_trails)

            for ball_id in keys_to_remove:
                for d in dicts_to_clean:
                    d.pop(ball_id, None)

        # Process currently tracked balls
        for ball in self.tracked_balls:
            try:
                if len(ball) < 6:
                    logger.warning(
                        f"Skipping scoring update for malformed ball data: {ball}"
                    )
                    continue
                x, y, r, ball_id, age, b_type = ball
                center = (int(x), int(y))
            except (ValueError, TypeError, IndexError) as e:
                logger.warning(
                    f"Error unpacking ball data in scoring update: {ball} - {e}"
                )
                continue

            # Update position history
            if ball_id not in self.ball_positions_history:
                self.ball_positions_history[ball_id] = []
            self.ball_positions_history[ball_id].append(center)
            if (
                len(self.ball_positions_history[ball_id])
                > GameConstants.POSITION_HISTORY_LENGTH
            ):
                self.ball_positions_history[ball_id].pop(0)

            # Update trail (Fun Mode)
            if self.game_mode == "fun" and hasattr(self, "active_trails"):
                if ball_id not in self.active_trails:
                    self.active_trails[ball_id] = BallTrail(ball_id)
                self.active_trails[ball_id].add_position(center)

            # Check current zone
            zone, zone_idx = None, -1
            for i, z in enumerate(self.scoring_zones):
                try:
                    if is_in_scoring_zone((x, y, r, ball_id), z):
                        zone, zone_idx = z, i
                        break
                except Exception as e:
                    logger.error(
                        f"Error checking if ball {ball_id} is in zone {i}: {e}"
                    )
                    continue

            # Check rest and stability
            rest = is_ball_at_rest(
                ball_id, self.ball_positions_history, self.debug_mode
            )
            stable = is_ball_zone_stable(
                ball_id,
                zone,
                self.ball_zone_history,
                self.debug_mode,  # Pass current zone object
            )

            # Store current state and check against previous
            self.previous_ball_states[ball_id] = self.ball_states.get(
                ball_id, {}
            ).copy()
            self.ball_states[ball_id] = {
                "at_rest": rest,
                "stable": stable,
                "zone": zone,  # Store zone object itself for comparison
                "idx": zone_idx,
                "time": current_time,
            }

            # Scoring Logic
            if zone and stable:  # Must be in a zone and stable within it
                # Check zone cooldown
                zone_cooldown_time = self.zone_cooldown.get(zone_idx, 0)
                if current_time < zone_cooldown_time:
                    if self.debug_mode:
                        logger.debug(
                            f"Ball {ball_id} in zone {zone_idx}, but zone is on cooldown."
                        )
                    continue  # Zone is on cooldown

                # Check if this specific ball already scored in this specific zone *on this entry*
                if self.ball_scored_zones.get(ball_id) == zone_idx:
                    if self.debug_mode:
                        logger.debug(
                            f"Ball {ball_id} already scored in zone {zone_idx} this entry."
                        )
                    continue  # Already scored here this time

                # --- Score Calculation ---
                _, _, _, _, base_pts = zone
                is_sp = zone == self.special_hole  # Check if it's the special one
                if is_sp:
                    current_score_pts = 100  # Special hole base points
                    if not self.special_hole_hit_this_session:
                        logger.info(
                            f"*** First hit in Special Hole this session! End score will be doubled. ***"
                        )
                        self.show_notification(
                            "Special Hole Hit! Score will double!", duration=3.0
                        )
                    self.special_hole_hit_this_session = True
                else:
                    current_score_pts = base_pts  # Use zone's defined points

                # Apply multiplier based on ball type
                score_multiplier = 1.0
                if b_type == "red":
                    score_multiplier = 2.0
                elif b_type == "half":
                    score_multiplier = 1.5
                points_to_add = int(current_score_pts * score_multiplier)

                # --- Update Score & State ---
                self.score += points_to_add
                self.get_current_player().add_score(points_to_add)
                newly_scored_pts_this_frame += points_to_add

                # Survival Mode Time Gain
                if self.game_mode == "survival":
                    time_gain = GameConstants.SURVIVAL_MODE_TIME_GAIN_PER_SCORE
                    if self.game_timer is not None:
                        self.game_timer += time_gain
                        logger.info(
                            f"Survival Mode: Gained {time_gain:.1f} seconds for scoring. New time: {self.game_timer:.1f}s"
                        )
                        self.show_notification(
                            f"+{time_gain:.0f} Secs!", duration=1.0, is_error=False
                        )
                    else:
                        logger.warning(
                            "Attempted to add survival time, but timer is None."
                        )

                # Record score event
                self.scored_balls.append(ball_id)  # Legacy list, maybe remove later
                self.balls_in_zone[ball_id] = zone  # Store which zone the ball is in
                self.ball_scored_zones[ball_id] = (
                    zone_idx  # Mark ball scored in this zone index for this entry
                )
                # Set cooldown for this *zone index*
                cooldown_duration = GameConstants.SCORE_COOLDOWN_DURATION / 1000.0
                self.zone_cooldown[zone_idx] = current_time + cooldown_duration

                logger.info(
                    f"Ball {ball_id}({b_type}) scored {points_to_add}pts [Base:{base_pts}, Mult:{score_multiplier}] in Zone:{zone_idx}{' (Special Hole)' if is_sp else ''}. Total Score:{self.score}. Zone {zone_idx} cooldown until T+{cooldown_duration:.1f}s."
                )

                # Fun Mode Explosion
                if self.game_mode == "fun" and hasattr(self, "active_explosions"):
                    zone_x, zone_y, zone_w, zone_h, _ = zone
                    explosion_center_x = int(zone_x + zone_w / 2)
                    explosion_center_y = int(zone_y + zone_h / 2)
                    self.active_explosions.append(
                        Explosion(explosion_center_x, explosion_center_y)
                    )
                    logger.debug(
                        f"Created explosion at ({explosion_center_x}, {explosion_center_y}) for score in zone {zone_idx}"
                    )

                # Check Timed Mode Win Condition
                if (
                    self.game_mode == "timed"
                    and self.score >= self.win_score
                    and self.current_state != CurrentGameState.GAME_OVER
                ):
                    self.win_condition_met = True
                    self.current_state = CurrentGameState.GAME_OVER
                    logger.info(
                        f"Win condition met! Score {self.score} >= {self.win_score}"
                    )
                    self.save_score(self.get_current_player().name)

            # If ball was previously scored in a zone, check if it left or became unstable
            elif ball_id in self.ball_scored_zones:
                last_scored_zone_idx = self.ball_scored_zones[ball_id]
                # Ball is no longer stable OR it's not in the same zone it scored in
                if not stable or zone_idx != last_scored_zone_idx:
                    del self.ball_scored_zones[
                        ball_id
                    ]  # Clear score status for this entry
                    self.balls_in_zone.pop(
                        ball_id, None
                    )  # Remove from current zone tracking
                    logger.debug(
                        f"Ball {ball_id} left/became unstable in zone {last_scored_zone_idx}. Cleared its scored status for this entry."
                    )
                    # Also remove from legacy list if present
                    if ball_id in self.scored_balls:
                        try:
                            self.scored_balls.remove(ball_id)
                        except ValueError:
                            pass  # Ignore if not found

        # Play score sound if any points were scored this frame
        if newly_scored_pts_this_frame > 0:
            self.play_sound(self.score_sound)

    # <<< Method renamed for clarity, same logic >>>
    def update_timers_and_state(self, dt: float) -> None:
        """Handle timer decrement, state changes based on time, and effects updates."""
        # (Content unchanged from previous version - update_scoring is separate now)
        # Timer logic for Timed and Survival modes
        if (
            self.current_state == CurrentGameState.PLAYING
            and self.game_mode in ["timed", "survival"]
            and self.game_timer is not None
        ):
            # Low time warning
            if (
                self.game_timer > 0
                and self.game_timer <= 10.0
                and not self.low_time_warning_played
            ):
                logger.info("Timer low.")
                self.play_sound(self.low_time_sound)
                self.low_time_warning_played = True

            # Decrement timer
            self.game_timer -= dt

            # Check for timer expiration
            if self.game_timer <= 0:
                self.game_timer = 0
                if self.current_state != CurrentGameState.GAME_OVER:
                    logger.info(f"Timer expired in {self.game_mode} mode.")
                    self.current_state = CurrentGameState.GAME_OVER
                    self.win_condition_met = False  # Timer ran out, not a score win
                    # Save score on game over
                    if hasattr(self.get_current_player(), "name"):
                        try:
                            self.save_score(self.get_current_player().name)
                        except Exception as e:
                            logger.error(f"Error saving score on timer expiry: {e}")
                    else:
                        logger.error(
                            "Cannot save score on game over (timer expiry), player name not found."
                        )

        # Updates specific to PLAYING state (excluding scoring logic)
        if self.current_state == CurrentGameState.PLAYING:
            # self.update_scoring() # Scoring is now called separately if needed
            if hasattr(self, "check_achievements"):
                self.check_achievements()
            if self.game_mode == "fun":
                if hasattr(self, "active_explosions"):
                    for explosion in self.active_explosions:
                        explosion.update(dt)
                    # Clean up inactive explosions
                    self.active_explosions = [
                        exp for exp in self.active_explosions if exp.is_active()
                    ]
                else:
                    logger.warning("Missing 'active_explosions'.")

        # Updates for notifications (run unless getting initial name)
        if self.current_state != CurrentGameState.GETTING_PLAYER_NAME:
            if hasattr(self, "update_achievement_notification"):
                self.update_achievement_notification(dt)
            if hasattr(self, "update_notifications"):
                self.update_notifications(dt)

    def reset_game(self) -> None:
        """Reset the game state fully, preserving music selection and volume levels."""
        # <<< MODIFIED: Preserves volume, resets other state >>>
        logger.info("Resetting game state...")
        self.score = 0
        self.tracked_balls.clear()
        self.scored_balls.clear()
        self.scored_positions.clear()
        self.next_ball_id = 0
        # self.submenu_active = None # Keep current menu if resetting from there? No, reset.
        self.submenu_active = None
        self.submenu_items = []
        # self.game_timer = None # Reset below based on mode
        # self.ball_trails.clear() # Removed this line
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
        self.edit_zones_current_page = 1

        # Reset menu editing states
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

        # Reset session flags
        self.special_hole_hit_this_session = False
        self.low_time_warning_played = False

        # Reset Fun Mode effects
        if hasattr(self, "active_trails"):
            self.active_trails.clear()
        if hasattr(self, "active_explosions"):
            self.active_explosions.clear()

        # Reset current player's score
        if self.players and 0 <= self.current_player_index < len(self.players):
            self.players[self.current_player_index].reset_score()
        else:
            logger.warning("Player index out of bounds or no players during reset.")

        # Reset timer based on current game mode
        if self.game_mode == "timed":
            self.game_timer = GameConstants.TIMED_MODE_DURATION
            logger.info(f"Timed mode reset. Timer set to {self.game_timer} seconds.")
        elif self.game_mode == "survival":
            self.game_timer = GameConstants.SURVIVAL_MODE_START_TIME
            logger.info(f"Survival mode reset. Timer set to {self.game_timer} seconds.")
        else:
            self.game_timer = None  # Classic, practice modes have no timer

        # Reload zones and high score, DO NOT reload volume settings
        if hasattr(self, "_load_initial_state") and callable(self._load_initial_state):
            self._load_initial_state()
        else:
            logger.warning(
                "Cannot reload initial state during reset, _load_initial_state not found."
            )

        # Ensure music state is correct after reset
        self.set_volume()  # Re-apply volume and ensures music plays/stops based on flag

        logger.info(
            f"Game state reset for player: {self.get_current_player().name}, Mode: {self.game_mode}"
        )
