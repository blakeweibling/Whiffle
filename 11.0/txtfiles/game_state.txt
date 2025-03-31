"""
Game state management for the Whiffle Tracker project.
Defines the GameState class to manage game variables and state transitions.
"""

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

# Import reconciled utils functions
from game_state_utils import (
    set_special_hole,
    initialize_sounds,  # Returns (score_sound, background_music)
    initialize_achievements,
    load_achievements,  # Takes game_state, filename
    save_achievements,  # Takes game_state, filename
    load_hsv_ranges,  # Takes filename, returns dict
    save_hsv_ranges,  # Takes dict, filename
    is_ball_at_rest,
    is_ball_zone_stable,
)

logger = logging.getLogger(__name__)


# Added SHOWING_SPLASH state
class CurrentGameState(Enum):
    PLAYING = auto()
    MENU = auto()
    GAME_OVER = auto()
    PAUSED = auto()
    SHOWING_SPLASH = auto()  # State for showing splash from menu


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
            logger.warning(
                f"Using static frame: {GameConstants.STATIC_FRAME_FILE}")
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
        self.start_x: int = 0
        self.start_y: int = 0
        self.temp_zone: Optional[Tuple[int, int, int, int]] = None
        self.special_hole: Optional[Tuple[int, int, int, int, int]] = None

        # Detection & Tracking
        logger.info("Initializing detection and tracking...")
        self.detector = BallDetector()
        self.tracker = BallTracker()
        self.tracked_balls: List[Tuple[int, int, float, int, int, str]] = []
        self.next_ball_id: int = 0
        self.ball_trails: Dict[int, List[Tuple[int, int]]] = {}
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
        self.scored_cooldown: Dict[int, float] = {}
        self.special_hole_hit_this_session: bool = False

        # Menu State
        self.submenu_active: Optional[str] = None
        self.submenu_items: List[Tuple[Tuple[int,
                                             int, int, int], Any, str]] = []
        self.menu_pos: Tuple[int, int] = (0, 0)
        self.menu_width: int = 400
        self.menu_height: int = 450
        self.menu_cache: Optional[np.ndarray] = None
        self.menu_cache_key: Optional[Any] = None

        # Zone Editing
        self.editing_zone_index: Optional[int] = None
        self.editing_zone_mode: Optional[str] = None
        self.editing_zone_points_input: Optional[str] = None

        # Player Name Editing State
        self.editing_player_index: Optional[int] = None
        self.editing_player_mode: Optional[str] = None
        self.editing_player_name_input: Optional[str] = None

        # Sounds
        self.game_sounds_on: bool = True
        self.background_music_on: bool = True
        self.score_sound: Optional[pygame.mixer.Sound] = None
        self.background_music: Optional[pygame.mixer.Sound] = None
        self.achievement_sound: Optional[pygame.mixer.Sound] = None

        # Game Mode / State
        self.game_mode: str = "classic"
        self.game_timer: Optional[float] = None
        self.current_state: CurrentGameState = CurrentGameState.PLAYING
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

        # --- Init Calls ---
        logger.info("Loading initial state...")
        self._load_initial_state()
        try:
            logger.info("Initializing sounds...")
            sound_results = initialize_sounds()
            if isinstance(sound_results, tuple) and len(sound_results) == 2:
                self.score_sound, self.background_music = sound_results
                self.achievement_sound = None
                logger.info("Sounds initialized (score, background).")
            else:
                logger.error(
                    f"initialize_sounds returned unexpected format: {type(sound_results)}. Sounds disabled."
                )
                self.score_sound, self.achievement_sound, self.background_music = (
                    None,
                    None,
                    None,
                )
        except Exception as e:
            logger.exception(
                f"Error during sound initialization: {e}. Sounds disabled."
            )
            self.score_sound, self.achievement_sound, self.background_music = (
                None,
                None,
                None,
            )
        self.game_sounds_on = True
        self.background_music_on = True
        logger.info("Initializing achievements...")
        self.achievements = initialize_achievements()
        logger.info("Loading achievements...")
        load_achievements(self, GameConstants.ACHIEVEMENTS_FILE)
        logger.info("Loading HSV ranges...")
        self.hsv_ranges = load_hsv_ranges(GameConstants.HSV_RANGES_FILE)
        if self.background_music_on and self.background_music:
            logger.info("Starting background music...")
            self.background_music.play(-1)
        if self.game_mode == "timed":
            self.game_timer = GameConstants.TIMED_MODE_DURATION

        logger.info("GameState initialized successfully.")

    def _load_initial_state(self):
        """Loads persistent state like zones and high score for current mode."""
        from menu import load_zones  # Local import

        load_zones(self)  # Call with self
        self.special_hole = set_special_hole(self.scoring_zones)
        try:  # Load High Score for current mode
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
        except (IOError, json.JSONDecodeError) as e:
            logger.error(
                f"Could not read/parse high score file ({GameConstants.HIGH_SCORE_FILE}): {e}. Will overwrite."
            )
            data = {}
        except Exception as e:
            logger.exception(f"Unexpected error reading high score file: {e}")
            data = {}

        if self.game_mode not in data:
            data[self.game_mode] = {}
        current_saved_high = data[self.game_mode].get("high_score", 0)

        # Compare the current game state's high_score (potentially doubled in save_score)
        # with the high score loaded from the file.
        if self.high_score > current_saved_high:
            data[self.game_mode][
                "high_score"
            ] = self.high_score  # Save the potentially doubled high score
            data[self.game_mode][
                "player"
            ] = (
                self.get_current_player().name
            )  # Save current player name with new high score
            data[self.game_mode]["date"] = time.strftime("%Y-%m-%d")
            logger.info(
                f"Updating high score file for mode '{self.game_mode}' to {self.high_score} by {self.get_current_player().name}"
            )
        else:
            logger.debug(
                f"Current session high score ({self.high_score}) not greater than saved high score ({current_saved_high}) for mode '{self.game_mode}'. No update needed."
            )

        try:
            with open(GameConstants.HIGH_SCORE_FILE, "w") as f:
                json.dump(data, f, indent=4)
            logger.debug(f"Saved high scores file.")
        except IOError as e:
            logger.error(f"Save high score fail: {e}")

    def get_current_player(self) -> Player:
        """Returns the current player object."""
        if 0 <= self.current_player_index < len(self.players):
            return self.players[self.current_player_index]
        logger.warning("Player index OOB.")
        return self.players[0] if self.players else Player("Default")

    def save_score(self, player_name: str, mode: Optional[str] = None) -> None:
        """Checks for special hole bonus, saves score to leaderboard, and updates high score."""
        final_score = self.score
        doubled = False
        if self.special_hole_hit_this_session:
            logger.info(
                f"Special hole was hit! Doubling final score {final_score} for {player_name}."
            )
            final_score *= 2
            doubled = True
            # Maybe show notification just before saving? Or maybe after game ends?
            # self.show_notification(f"Score Doubled! (Special Hole Bonus)", duration=4.0)

        score_to_save = final_score  # Use potentially doubled score
        current_mode = mode or self.game_mode

        if score_to_save > 0:
            logger.info(
                f"Saving score for {player_name}: {score_to_save} (Mode: {current_mode}){' (Doubled)' if doubled else ''}"
            )
            self.leaderboard.submit_score(
                player_name, score_to_save, current_mode
            )  # Use submit_score instead of add_score
            # Update high score using the potentially doubled score
            if current_mode == self.game_mode and score_to_save > self.high_score:
                logger.info(
                    f"New high score for mode '{current_mode}': {score_to_save}"
                )
                self.high_score = score_to_save
            # Save high scores to file (will check if self.high_score is > file high score)
            self._save_high_score()
        else:
            logger.info(f"Score is {score_to_save}, not saving.")

        # The special_hole_hit_this_session flag should be reset by reset_game

    def toggle_background_music(self) -> None:
        """Toggle background music."""
        if self.background_music:
            if self.background_music_on:
                self.background_music.play(-1)
                logger.info("BG music started.")
            else:
                self.background_music.stop()
                logger.info("BG music stopped.")
        else:
            logger.warning("BG music not loaded.")

    def play_sound(self, sound: Optional[pygame.mixer.Sound]) -> None:
        """Play sound effect if enabled."""
        if self.game_sounds_on and sound:
            try:
                sound.play()
            except pygame.error as e:
                logger.error(f"Sound play error: {e}")

    def check_achievements(self) -> None:
        """Check achievements and notify."""
        for ach in self.achievements:
            if ach.check(self):
                logger.info(f"Achieved: {ach.name}")
                self.show_notification(f"Unlocked: {ach.name}", duration=5.0)
                save_achievements(self, GameConstants.ACHIEVEMENTS_FILE)

    def update_achievement_notification(self, dt: float) -> None:
        if self.achievement_notification_timer > 0:
            self.achievement_notification_timer -= dt
            if self.achievement_notification_timer <= 0:
                self.achievement_notification = None

    def show_notification(
        self, text: str, duration: float = 2.0, is_error: bool = False
    ) -> None:
        self.notification_text = text
        self.notification_timer = duration
        self.notification_color = UIConstants.RED if is_error else UIConstants.GREEN
        logger.info(f"Notify: {text}" + (" (Err)" if is_error else ""))

    def update_notifications(self, dt: float) -> None:
        if self.notification_timer > 0:
            self.notification_timer -= dt
            if self.notification_timer <= 0:
                self.notification_text = None

    def update_scoring(self) -> None:
        """Processes tracked balls to determine scores and handle special hole bonus."""
        newly_scored_pts_this_frame = (
            0  # Track points added in this frame for sound trigger
        )
        current_time = time.time()

        for ball in self.tracked_balls:
            try:
                x, y, r, ball_id, age, b_type = ball
                center = (int(x), int(y))
            except ValueError:
                logger.warning(f"Skipping scoring malformed ball: {ball}")
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

            # Log the number of zones and debug status *before* the inner loop for this specific ball
            num_zones = len(self.scoring_zones)
            logger.debug(
                f"Ball {ball_id}: Checking {num_zones} zones. Debug Mode: {self.debug_mode}"
            )

            # Find current zone
            zone, zone_idx = None, -1
            for i, z in enumerate(self.scoring_zones):
                if is_in_scoring_zone((x, y, r, ball_id), z):
                    zone, zone_idx = z, i
                    break

            # Check stability conditions
            rest = is_ball_at_rest(
                ball_id, self.ball_positions_history, self.debug_mode
            )
            stable = is_ball_zone_stable(
                ball_id, zone, self.ball_zone_history, self.debug_mode
            )

            # Update ball state dictionary
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

            # Check scoring conditions
            if (
                zone
                and stable
                and ball_id not in self.ball_scored_zones
                and current_time >= self.scored_cooldown.get(ball_id, 0)
            ):
                _, _, _, _, pts = zone  # Original points assigned to the zone
                is_sp = zone == self.special_hole

                # Special Hole Logic
                if is_sp:
                    current_score_pts = 100  # Award fixed 100 for special hole hit
                    if not self.special_hole_hit_this_session:
                        logger.info(
                            f"*** First hit in Special Hole this session! End score will be doubled. ***"
                        )
                        self.show_notification(
                            "Special Hole Hit! Score will double!", duration=3.0
                        )
                    self.special_hole_hit_this_session = True  # Set flag
                else:
                    current_score_pts = pts  # Award zone's normal points

                # Apply ball type multiplier
                score_multiplier = 1.0
                if b_type == "red":
                    score_multiplier = 2.0
                elif b_type == "half":
                    score_multiplier = 1.5
                points_to_add = int(current_score_pts * score_multiplier)

                # Update scores
                self.score += points_to_add
                self.get_current_player().add_score(points_to_add)
                newly_scored_pts_this_frame += points_to_add  # Track points added

                # Update tracking states
                self.scored_balls.append(ball_id)
                self.balls_in_zone[ball_id] = zone
                self.ball_scored_zones[ball_id] = zone_idx
                self.scored_cooldown[ball_id] = (
                    current_time + GameConstants.SCORE_COOLDOWN_DURATION
                )

                logger.info(
                    f"Ball {ball_id}({b_type}) scored {points_to_add}pts Zone:{zone_idx}{' (Special Hole)' if is_sp else ''}. Score:{self.score}"
                )

                # Check win conditions (using potentially modified self.score)
                if (
                    self.game_mode == "timed"
                    and self.score >= self.win_score
                    and self.current_state != CurrentGameState.GAME_OVER
                ):
                    self.win_condition_met = True
                    self.current_state = CurrentGameState.GAME_OVER
                    logger.info(f"Win! Score {self.score}>={self.win_score}")
                    self.save_score(
                        self.get_current_player().name
                    )  # Save score immediately on win/game over

                # Update high score (using current self.score, not potentially doubled final score yet)
                if self.score > self.high_score:
                    # Don't update self.high_score with doubled value here, let save_score handle it
                    pass  # High score comparison happens in save_score

            # Clear scored status if ball leaves zone or becomes unstable
            elif ball_id in self.ball_scored_zones and (
                not stable or self.ball_scored_zones.get(ball_id) != zone_idx
            ):
                logger.debug(
                    f"Ball {ball_id} left/unstable zone {self.ball_scored_zones.get(ball_id)}. Clearing."
                )
                self.ball_scored_zones.pop(ball_id, None)
                if ball_id in self.scored_balls:
                    try:
                        self.scored_balls.remove(ball_id)
                    except ValueError:
                        pass

        # Play sound only if points were actually added in this frame
        if newly_scored_pts_this_frame > 0:
            self.play_sound(self.score_sound)

        # Cleanup dictionaries for untracked balls
        tracked_ids = {b[3] for b in self.tracked_balls}
        keys_to_remove = set(self.ball_states.keys()) - tracked_ids
        for ball_id in keys_to_remove:
            for d in [
                self.ball_states,
                self.previous_ball_states,
                self.ball_positions_history,
                self.ball_zone_history,
                self.balls_in_zone,
                self.ball_scored_zones,
                self.scored_cooldown,
                self.ball_trails,
            ]:
                d.pop(ball_id, None)
