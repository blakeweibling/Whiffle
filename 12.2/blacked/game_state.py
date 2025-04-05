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
from constants import UIConstants, GameConstants, ScoringConstants
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
        self.game_sounds_on: bool = (
            True  # Default to True, might be overridden if loading fails
        )
        self.background_music_on: bool = True  # Default to True
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
        self._load_initial_state()
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
        # Update music on flag based on loading success
        self.background_music_on = (
            self.background_music is not None and self.background_music_on
        )

        # --- UPDATED: Check specific sounds to set game_sounds_on ---
        # If any effect sound failed, consider sounds off.
        if (
            self.score_sound is None or self.low_time_sound is None
        ):  # Check specific sounds
            self.game_sounds_on = False
            logger.warning(
                "One or more sound effects failed to load. Disabling game sounds."
            )
        # --- END UPDATE ---

        self.set_volume()  # Set volumes for all loaded sounds

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
                # Set volume immediately after loading - use current flag state
                music.set_volume(
                    GameConstants.DEFAULT_MUSIC_VOLUME
                    if self.background_music_on
                    else 0.0
                )
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
            if self.background_music_on and not pygame.mixer.get_busy():
                self.background_music.play(-1)
            return

        logger.info(f"Changing background music track to index {new_index}...")
        self.selected_music_track_index = new_index

        if self.background_music:
            self.background_music.stop()
            logger.debug("Stopped previous background music track.")

        self.background_music = self._load_background_music(
            self.selected_music_track_index
        )

        if self.background_music:
            # Don't force music on, respect the user's toggle setting
            if self.background_music_on:
                self.background_music.play(-1)
                logger.info(
                    f"Started playing new track: {GameConstants.BACKGROUND_MUSIC_TRACKS[new_index]}"
                )
            else:
                self.background_music.set_volume(0.0)
        else:
            # Loading failed, ensure music flag reflects this if it was previously on
            if self.background_music_on:
                logger.error(
                    f"Failed to load track index {new_index}. Disabling background music."
                )
                self.background_music_on = False
            else:
                logger.error(f"Failed to load track index {new_index}.")

    def toggle_background_music(self) -> None:
        """Toggle background music ON/OFF based on the flag and loaded track."""
        self.background_music_on = not self.background_music_on
        logger.info(
            f"Background music toggled {'ON' if self.background_music_on else 'OFF'}"
        )

        if self.background_music:
            if self.background_music_on:
                self.background_music.set_volume(GameConstants.DEFAULT_MUSIC_VOLUME)
                # Check if mixer is busy *before* playing
                channel = pygame.mixer.find_channel(True)  # Find any free channel
                if channel:
                    channel.play(self.background_music, -1)
                    logger.debug("Played/Resumed background music on a free channel.")
                else:
                    logger.warning(
                        "No free channels available to play background music."
                    )

                # Old way - might conflict if other sounds use channel 0
                # if not pygame.mixer.get_busy():
                #    self.background_music.play(-1)
                # logger.debug("Played/Resumed background music.")
            else:
                self.background_music.stop()  # Stop playback
                self.background_music.set_volume(0.0)  # Also set volume to 0
                logger.debug("Stopped background music.")
        elif self.background_music_on:
            logger.warning("Background music toggled ON, but no track is loaded.")

    def set_volume(self):
        """Sets volume based on current flags."""
        if self.score_sound:
            self.score_sound.set_volume(
                GameConstants.DEFAULT_SOUND_VOLUME if self.game_sounds_on else 0.0
            )
        if self.low_time_sound:
            self.low_time_sound.set_volume(
                GameConstants.DEFAULT_SOUND_VOLUME if self.game_sounds_on else 0.0
            )
        if self.achievement_sound:
            self.achievement_sound.set_volume(
                GameConstants.DEFAULT_SOUND_VOLUME if self.game_sounds_on else 0.0
            )
        if self.background_music:
            self.background_music.set_volume(
                GameConstants.DEFAULT_MUSIC_VOLUME if self.background_music_on else 0.0
            )
        # Log level is debug, might not appear in user's log unless debug mode is on
        logger.debug(
            f"Volumes set: Sounds={self.game_sounds_on}, Music={self.background_music_on}"
        )

    def _load_initial_state(self):
        """Loads persistent state like zones and high score for current mode."""
        # (Content unchanged from previous version)
        from menu import load_zones
        from game_state_utils import set_special_hole

        load_zones(self)
        self.special_hole = set_special_hole(self.scoring_zones)
        try:
            if os.path.exists(GameConstants.HIGH_SCORE_FILE):
                if os.path.getsize(GameConstants.HIGH_SCORE_FILE) > 0:
                    with open(GameConstants.HIGH_SCORE_FILE, "r") as f:
                        data = json.load(f)
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
                    data = {}
            else:
                data = {
                    "classic": {},
                    "timed": {},
                    "fun": {},
                    "practice": {},
                    "survival": {},
                }
        except (IOError, json.JSONDecodeError) as e:
            logger.error(
                f"Could not read/parse high score file ({GameConstants.HIGH_SCORE_FILE}): {e}. Will overwrite."
            )
            data = {
                "classic": {},
                "timed": {},
                "fun": {},
                "practice": {},
                "survival": {},
            }
        except Exception as e:
            logger.exception(f"Unexpected error reading high score file: {e}")
            data = {
                "classic": {},
                "timed": {},
                "fun": {},
                "practice": {},
                "survival": {},
            }

        if self.game_mode not in data:
            data[self.game_mode] = {}
        current_saved_high = data[self.game_mode].get("high_score", 0)

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
        return self.players[0]

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

            if current_mode == self.game_mode and score_to_save > self.high_score:
                logger.info(
                    f"New high score for current mode '{current_mode}': {score_to_save}"
                )
                self.high_score = score_to_save

            self._save_high_score()
        else:
            logger.info(f"Score is {score_to_save}, not saving.")

    def play_sound(self, sound: Optional[pygame.mixer.Sound]) -> None:
        """Play sound effect if enabled."""
        # (Content unchanged from previous version)
        if self.game_sounds_on and sound:
            try:
                sound.set_volume(GameConstants.DEFAULT_SOUND_VOLUME)
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
        # (Content unchanged from previous version)
        newly_scored_pts_this_frame = 0
        current_time = time.time()
        tracked_ids_this_frame = {b[3] for b in self.tracked_balls if len(b) >= 6}
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
        keys_to_remove.update(set(self.active_trails.keys()) - tracked_ids_this_frame)
        if keys_to_remove:
            logger.debug(f"Cleaning up state for untracked ball IDs: {keys_to_remove}")
            dicts_to_clean = [
                self.ball_states,
                self.previous_ball_states,
                self.ball_positions_history,
                self.ball_zone_history,
                self.balls_in_zone,
                self.ball_scored_zones,
                self.active_trails,
            ]
            for ball_id in keys_to_remove:
                for d in dicts_to_clean:
                    d.pop(ball_id, None)
        for ball in self.tracked_balls:
            try:
                if len(ball) < 6:
                    continue
                x, y, r, ball_id, age, b_type = ball
                center = (int(x), int(y))
            except (ValueError, TypeError, IndexError) as e:
                continue
            if ball_id not in self.ball_positions_history:
                self.ball_positions_history[ball_id] = []
            self.ball_positions_history[ball_id].append(center)
            if (
                len(self.ball_positions_history[ball_id])
                > GameConstants.POSITION_HISTORY_LENGTH
            ):
                self.ball_positions_history[ball_id].pop(0)
            if self.game_mode == "fun":
                if ball_id not in self.active_trails:
                    self.active_trails[ball_id] = BallTrail(ball_id)
                self.active_trails[ball_id].add_position(center)
            zone, zone_idx = None, -1
            for i, z in enumerate(self.scoring_zones):
                try:
                    if is_in_scoring_zone((x, y, r, ball_id), z):
                        zone, zone_idx = z, i
                        break
                except Exception as e:
                    continue
            rest = is_ball_at_rest(
                ball_id, self.ball_positions_history, self.debug_mode
            )
            stable = is_ball_zone_stable(
                ball_id, zone, self.ball_zone_history, self.debug_mode
            )
            self.previous_ball_states[ball_id] = self.ball_states.get(
                ball_id, {}
            ).copy()
            self.ball_states[ball_id] = {
                "at_rest": rest,
                "stable": stable,
                "zone": zone,
                "idx": zone_idx,
                "time": current_time,
            }
            if zone and stable:
                zone_cooldown_time = self.zone_cooldown.get(zone_idx, 0)
                if current_time < zone_cooldown_time:
                    continue
                if self.ball_scored_zones.get(ball_id) == zone_idx:
                    continue
                _, _, _, _, base_pts = zone
                is_sp = zone == self.special_hole
                if is_sp:
                    current_score_pts = 100
                    if not self.special_hole_hit_this_session:
                        logger.info(
                            f"*** First hit in Special Hole this session! End score will be doubled. ***"
                        )
                        self.show_notification(
                            "Special Hole Hit! Score will double!", duration=3.0
                        )
                    self.special_hole_hit_this_session = True
                else:
                    current_score_pts = base_pts
                score_multiplier = 1.0
                if b_type == "red":
                    score_multiplier = 2.0
                elif b_type == "half":
                    score_multiplier = 1.5
                points_to_add = int(current_score_pts * score_multiplier)
                self.score += points_to_add
                self.get_current_player().add_score(points_to_add)
                newly_scored_pts_this_frame += points_to_add
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
                self.scored_balls.append(ball_id)
                self.balls_in_zone[ball_id] = zone
                self.ball_scored_zones[ball_id] = zone_idx
                cooldown_duration = GameConstants.SCORE_COOLDOWN_DURATION / 1000.0
                self.zone_cooldown[zone_idx] = current_time + cooldown_duration
                logger.info(
                    f"Ball {ball_id}({b_type}) scored {points_to_add}pts [Base:{base_pts}, Mult:{score_multiplier}] in Zone:{zone_idx}{' (Special Hole)' if is_sp else ''}. Total Score:{self.score}. Zone {zone_idx} cooldown until T+{cooldown_duration:.1f}s."
                )
                if self.game_mode == "fun":
                    zone_x, zone_y, zone_w, zone_h, _ = zone
                    explosion_center_x = int(zone_x + zone_w / 2)
                    explosion_center_y = int(zone_y + zone_h / 2)
                    self.active_explosions.append(
                        Explosion(explosion_center_x, explosion_center_y)
                    )
                    logger.debug(
                        f"Created explosion at ({explosion_center_x}, {explosion_center_y}) for score in zone {zone_idx}"
                    )
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
            elif ball_id in self.ball_scored_zones:
                last_scored_zone_idx = self.ball_scored_zones[ball_id]
                if not stable or zone_idx != last_scored_zone_idx:
                    del self.ball_scored_zones[ball_id]
                    self.balls_in_zone.pop(ball_id, None)
                    logger.debug(
                        f"Ball {ball_id} left/became unstable in zone {last_scored_zone_idx}. Cleared its scored status for this entry."
                    )
                    if ball_id in self.scored_balls:
                        try:
                            self.scored_balls.remove(ball_id)
                        except ValueError:
                            pass
        if newly_scored_pts_this_frame > 0:
            self.play_sound(self.score_sound)

    def _update_game_state(self, dt: float) -> None:
        """Handle timer decrement and low time warnings for Timed and Survival modes."""
        # (Content unchanged from previous version)
        if (
            self.current_state == CurrentGameState.PLAYING
            and self.game_mode in ["timed", "survival"]
            and self.game_timer is not None
        ):
            if (
                self.game_timer > 0
                and self.game_timer <= 10.0
                and not self.low_time_warning_played
            ):
                logger.info("Timer low.")
                self.play_sound(self.low_time_sound)
                self.low_time_warning_played = True
            self.game_timer -= dt
            if self.game_timer <= 0:
                self.game_timer = 0
                if self.current_state != CurrentGameState.GAME_OVER:
                    logger.info(f"Timer expired in {self.game_mode} mode.")
                    self.current_state = CurrentGameState.GAME_OVER
                    self.win_condition_met = False
                    if hasattr(self.get_current_player(), "name"):
                        self.save_score(self.get_current_player().name)
                    else:
                        logger.error(
                            "Cannot save score on game over, player name not found."
                        )
        if self.current_state == CurrentGameState.PLAYING:
            if hasattr(self, "update_scoring"):
                self.update_scoring()
            if hasattr(self, "check_achievements"):
                self.check_achievements()
            if self.game_mode == "fun":
                if hasattr(self, "active_explosions"):
                    for explosion in self.active_explosions:
                        explosion.update(dt)
                    self.active_explosions = [
                        exp for exp in self.active_explosions if exp.is_active()
                    ]
                else:
                    logger.warning("Missing 'active_explosions'.")
        if self.current_state != CurrentGameState.GETTING_PLAYER_NAME:
            if hasattr(self, "update_achievement_notification"):
                self.update_achievement_notification(dt)
            if hasattr(self, "update_notifications"):
                self.update_notifications(dt)

    def reset_game(self) -> None:
        """Reset the game state fully, preserving music selection."""
        # (Content unchanged from previous version)
        self.score = 0
        self.tracked_balls.clear()
        self.scored_balls.clear()
        self.scored_positions.clear()
        self.next_ball_id = 0
        self.submenu_active = None
        self.submenu_items = []
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
        self.special_hole_hit_this_session = False
        self.low_time_warning_played = False
        self.active_trails.clear()
        self.active_explosions.clear()
        if self.players and 0 <= self.current_player_index < len(self.players):
            self.players[self.current_player_index].reset_score()
        else:
            logger.warning("Player index out of bounds or no players during reset.")
        if self.game_mode == "timed":
            self.game_timer = GameConstants.TIMED_MODE_DURATION
            logger.info(f"Timed mode reset. Timer set to {self.game_timer} seconds.")
        elif self.game_mode == "survival":
            self.game_timer = GameConstants.SURVIVAL_MODE_START_TIME
            logger.info(f"Survival mode reset. Timer set to {self.game_timer} seconds.")
        else:
            self.game_timer = None
        if hasattr(self, "_load_initial_state") and callable(self._load_initial_state):
            self._load_initial_state()
        else:
            logger.warning(
                "Cannot reload initial state during reset, _load_initial_state not found."
            )
        if self.background_music and self.background_music_on:
            # Use find_channel to avoid conflicts if other sounds might be playing
            channel = pygame.mixer.find_channel(True)
            if channel:
                channel.play(self.background_music, -1)
            else:
                logger.warning("No free channels to resume music after reset.")
        logger.info(
            f"Game state reset for player: {self.get_current_player().name}, Mode: {self.game_mode}"
        )
