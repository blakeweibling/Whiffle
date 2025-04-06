# game_state_utils.py
"""
Utility functions for the GameState class in the Whiffle Tracker project.
"""

import json
import logging
import os
import random  # <<< ADDED IMPORT
import time  # Keep for update_timers_and_state / Added for click feedback
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pygame

# scoring.py might still be needed if other utils use is_in_scoring_zone
# from scoring import is_in_scoring_zone
from achievement import Achievement
# Import constants and classes
from constants import (  # Added UIConstants for click feedback duration
    GameConstants, UIConstants)
from effects import BallTrail, Explosion  # Needed by reset_game
# Import the functions moved to the new helpers file
from game_state_helpers import set_special_hole  # Needed by load_initial_state
from game_state_helpers import (  # save_zones, clear_zones, flush_scoring_zones not directly needed here
    play_sound, save_score, show_notification)
# Import types/enums
from game_types import CurrentGameState  # Needed for update_timers_and_state
# Import classes needed by functions remaining here
from player import Player  # Needed by reset_game
# Import the refactored scoring logic
from scoring_logic import update_scoring as _update_scoring_logic

logger = logging.getLogger(__name__)

# --- Functions Remaining in game_state_utils ---


def initialize_sounds() -> (
    Tuple[Optional[pygame.mixer.Sound], Optional[pygame.mixer.Sound]]
):
    """Initialize sound effects (score, low time)."""
    # (Code unchanged)
    pygame.mixer.init()
    score_sound = None
    low_time_sound = None
    try:
        score_sound_path = os.path.join(GameConstants.SOUND_EFFECTS_PATH, "ding.wav")
        low_time_sound_path = os.path.join(
            GameConstants.SOUND_EFFECTS_PATH, "10_sec_timer.mp3"
        )
        if os.path.exists(score_sound_path):
            score_sound = pygame.mixer.Sound(score_sound_path)
        else:
            logger.warning(f"File not found: {score_sound_path}")
        if os.path.exists(low_time_sound_path):
            low_time_sound = pygame.mixer.Sound(low_time_sound_path)
        else:
            logger.warning(f"File not found: {low_time_sound_path}")
    except Exception as e:
        logger.error(f"Sound init error: {e}")
    return score_sound, low_time_sound


def initialize_achievements() -> List[Achievement]:
    """Initialize the list of achievements."""
    # (Code unchanged)
    return [
        Achievement(
            "First Score",
            "Score first points",
            lambda gs: gs.get_current_player().score >= 100,
        ),
        Achievement(
            "High Roller",
            "Score 1000 points",
            lambda gs: gs.get_current_player().score >= 1000,
        ),
        Achievement(
            "Zone Master", "Create 5 zones", lambda gs: len(gs.scoring_zones) >= 5
        ),
        Achievement(
            "Marathon",
            "Play 10 games",
            lambda gs: hasattr(gs.get_current_player(), "games_played")
            and gs.get_current_player().games_played >= 10,
        ),
    ]


def load_achievements(game_state: Any, filename: str) -> None:
    """Load achievements status from a JSON file."""
    # (Code unchanged)
    if not hasattr(game_state, "achievements") or not game_state.achievements:
        return
    achievements_file = filename
    try:
        if os.path.exists(achievements_file) and os.path.getsize(achievements_file) > 0:
            with open(achievements_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
            loaded_count = 0
            for achievement in game_state.achievements:
                if achievement.name in data and data.get(achievement.name, {}).get(
                    "unlocked"
                ):
                    achievement.unlocked = True
                    loaded_count += 1
            logger.info(f"Loaded {loaded_count} achievements from {achievements_file}.")
        else:
            logger.info(f"{achievements_file} not found/empty.")
    except Exception as e:
        logger.error(f"Failed load achievements: {e}")


def save_achievements(game_state: Any, filename: str) -> None:
    """Save achievements status to a JSON file."""
    # (Code unchanged)
    if not hasattr(game_state, "achievements"):
        return
    achievements_file = filename
    try:
        data = {a.name: {"unlocked": a.unlocked} for a in game_state.achievements}
        with open(achievements_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        logger.debug(f"Saved achievements to {achievements_file}.")
    except Exception as e:
        logger.error(f"Failed save achievements: {e}")


def load_hsv_ranges(
    filename: str = "hsv_ranges.json",
) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """Load HSV ranges from a JSON file."""
    # (Code unchanged)
    hsv_ranges = {
        "white": (
            np.array([0, 0, 180], dtype=np.uint8),
            np.array([179, 30, 255], dtype=np.uint8),
        ),
        "red1": (
            np.array([0, 100, 100], dtype=np.uint8),
            np.array([10, 255, 255], dtype=np.uint8),
        ),
        "red2": (
            np.array([160, 100, 100], dtype=np.uint8),
            np.array([179, 255, 255], dtype=np.uint8),
        ),
    }
    hsv_file = filename
    if os.path.exists(hsv_file) and os.path.getsize(hsv_file) > 0:
        try:
            with open(hsv_file, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
            for key in hsv_ranges.keys():
                if (
                    key in loaded_data
                    and isinstance(loaded_data[key], list)
                    and len(loaded_data[key]) == 2
                ):
                    lower = np.array(loaded_data[key][0], dtype=np.uint8)
                    upper = np.array(loaded_data[key][1], dtype=np.uint8)
                    if lower.shape == (3,) and upper.shape == (3,):
                        hsv_ranges[key] = (lower, upper)
                    else:
                        logger.warning(f"Invalid HSV shape for '{key}'. Using default.")
                else:
                    logger.warning(
                        f"Missing/invalid format for '{key}'. Using default."
                    )
            logger.info(f"Loaded custom HSV ranges from {hsv_file}")
        except Exception as e:
            logger.error(f"Failed load HSV ranges: {e}. Using defaults.")
    else:
        logger.info(f"{hsv_file} not found/empty, using defaults.")
    return hsv_ranges


def save_hsv_ranges(
    hsv_ranges: Dict[str, Tuple[np.ndarray, np.ndarray]],
    filename: str = "hsv_ranges.json",
) -> None:
    """Save HSV ranges to a JSON file."""
    # (Code unchanged)
    hsv_file = filename
    serializable_data = {}
    for key, (lower, upper) in hsv_ranges.items():
        if isinstance(lower, np.ndarray) and isinstance(upper, np.ndarray):
            serializable_data[key] = (lower.tolist(), upper.tolist())
        else:
            logger.warning(f"Cannot serialize HSV for '{key}'.")
    if not serializable_data:
        logger.warning("No valid HSV data to save.")
        return
    try:
        with open(hsv_file, "w", encoding="utf-8") as f:
            json.dump(serializable_data, f, indent=4)
        logger.info(f"Saved HSV ranges to {hsv_file}")
    except Exception as e:
        logger.error(f"Failed to save HSV ranges to {hsv_file}: {e}")


def load_settings(game_state: Any) -> None:
    """Loads settings like volume from the settings file."""
    # (Code unchanged)
    settings_file = GameConstants.SETTINGS_FILE
    try:
        if os.path.exists(settings_file) and os.path.getsize(settings_file) > 0:
            with open(settings_file, "r") as f:
                settings_data = json.load(f)
            loaded_sound_vol = settings_data.get("sound_volume")
            game_state.current_sound_volume = (
                float(loaded_sound_vol)
                if isinstance(loaded_sound_vol, (int, float))
                and 0.0 <= loaded_sound_vol <= 1.0
                else GameConstants.INITIAL_SOUND_VOLUME
            )
            loaded_music_vol = settings_data.get("music_volume")
            game_state.current_music_volume = (
                float(loaded_music_vol)
                if isinstance(loaded_music_vol, (int, float))
                and 0.0 <= loaded_music_vol <= 1.0
                else GameConstants.INITIAL_MUSIC_VOLUME
            )
            if "game_sounds_on" in settings_data and isinstance(
                settings_data["game_sounds_on"], bool
            ):
                game_state.game_sounds_on = settings_data["game_sounds_on"]
            if "background_music_on" in settings_data and isinstance(
                settings_data["background_music_on"], bool
            ):
                game_state.background_music_on = settings_data["background_music_on"]
            logger.info(f"Loaded settings from {settings_file}")
        else:
            logger.info(f"{settings_file} not found/empty. Using defaults.")
            game_state.current_sound_volume = GameConstants.INITIAL_SOUND_VOLUME
            game_state.current_music_volume = GameConstants.INITIAL_MUSIC_VOLUME
            game_state.game_sounds_on = True
            game_state.background_music_on = True
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed load settings: {e}. Using defaults.")
        game_state.current_sound_volume = GameConstants.INITIAL_SOUND_VOLUME
        game_state.current_music_volume = GameConstants.INITIAL_MUSIC_VOLUME
        game_state.game_sounds_on = True
        game_state.background_music_on = True
    except Exception as e:
        logger.exception(f"Unexpected error loading settings: {e}")
        game_state.current_sound_volume = GameConstants.INITIAL_SOUND_VOLUME
        game_state.current_music_volume = GameConstants.INITIAL_MUSIC_VOLUME
        game_state.game_sounds_on = True
        game_state.background_music_on = True


def save_settings(game_state: Any) -> None:
    """Saves current settings like volume to the settings file."""
    # (Code unchanged)
    settings_file = GameConstants.SETTINGS_FILE
    settings_data = {
        "sound_volume": game_state.current_sound_volume,
        "music_volume": game_state.current_music_volume,
        "game_sounds_on": game_state.game_sounds_on,
        "background_music_on": game_state.background_music_on,
    }
    try:
        with open(settings_file, "w") as f:
            json.dump(settings_data, f, indent=4)
        logger.debug(f"Saved settings to {settings_file}")
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")


def load_background_music(
    game_state: Any, track_index: int
) -> Optional[pygame.mixer.Sound]:
    """Loads a specific background music track by index."""
    # (Code unchanged)
    if not (0 <= track_index < len(GameConstants.BACKGROUND_MUSIC_TRACKS)):
        logger.warning(f"Invalid track index {track_index} requested.")
        return None
    track_filename = GameConstants.BACKGROUND_MUSIC_TRACKS[track_index]
    track_path = os.path.join(GameConstants.SOUND_EFFECTS_PATH, track_filename)
    logger.info(f"Loading background music: {track_path}")
    try:
        if os.path.exists(track_path):
            music = pygame.mixer.Sound(track_path)
            return music
        else:
            logger.warning(f"Music file not found: {track_path}")
            return None
    except Exception as e:
        logger.error(f"Error loading music {track_filename}: {e}")
    return None


def change_music_track(game_state: Any, new_index: int):
    """Stops current music, loads and plays the new track if music is enabled."""
    # (Code unchanged)
    num_tracks = len(GameConstants.BACKGROUND_MUSIC_TRACKS)
    if not (0 <= new_index < num_tracks):
        return
    if (
        new_index == game_state.selected_music_track_index
        and game_state.background_music
    ):
        # Ensure volume is correct even if track is the same
        set_volume(game_state)
        return
    logger.info(f"Changing music track to index {new_index}...")
    game_state.selected_music_track_index = new_index
    if game_state.background_music:
        game_state.background_music.stop()
    game_state.background_music = load_background_music(
        game_state, game_state.selected_music_track_index
    )
    set_volume(game_state)  # set_volume handles starting playback if needed


def toggle_background_music(game_state: Any) -> None:
    """Toggle background music ON/OFF flag and update playback/volume."""
    # (Code unchanged)
    game_state.background_music_on = not game_state.background_music_on
    logger.info(f"Music toggled {'ON' if game_state.background_music_on else 'OFF'}")
    set_volume(game_state)
    save_settings(game_state)


def toggle_game_sounds(game_state: Any) -> None:
    """Toggle game sounds ON/OFF flag and update volume."""
    # (Code unchanged)
    game_state.game_sounds_on = not game_state.game_sounds_on
    logger.info(f"Sounds toggled {'ON' if game_state.game_sounds_on else 'OFF'}")
    set_volume(game_state)
    save_settings(game_state)


def set_volume(game_state: Any):
    """Sets volume for all sounds based on current levels and on/off flags."""
    # (Code unchanged)
    sound_vol = game_state.current_sound_volume if game_state.game_sounds_on else 0.0
    music_vol = (
        game_state.current_music_volume if game_state.background_music_on else 0.0
    )
    try:
        if game_state.score_sound:
            game_state.score_sound.set_volume(sound_vol)
        if game_state.low_time_sound:
            game_state.low_time_sound.set_volume(sound_vol)
        if hasattr(game_state, "achievement_sound") and game_state.achievement_sound:
            game_state.achievement_sound.set_volume(sound_vol)
        if game_state.background_music:
            game_state.background_music.set_volume(music_vol)
            # Check if the specific sound object is playing on any channel
            is_playing = any(
                ch.get_sound() == game_state.background_music
                for i in range(pygame.mixer.get_num_channels())
                if (ch := pygame.mixer.Channel(i)).get_busy()
            )

            if game_state.background_music_on and not is_playing:
                logger.debug("Music is ON but not playing, starting playback.")
                game_state.background_music.play(-1)  # Loop indefinitely
            elif not game_state.background_music_on and is_playing:
                logger.debug("Music is OFF but playing, stopping playback.")
                game_state.background_music.stop()
    except Exception as e:
        logger.error(f"Error setting volume: {e}")
    logger.debug(f"Volumes applied: Sounds={sound_vol:.2f}, Music={music_vol:.2f}")


def load_initial_state(game_state: Any):
    """Loads persistent state like zones and high score for current mode."""
    # (Code unchanged)
    from game_state_helpers import load_zones  # Import moved here

    load_zones(game_state)  # Call function imported above
    game_state.special_hole = set_special_hole(
        game_state.scoring_zones
    )  # Use helper imported at top
    # (Code for loading high score - unchanged)
    try:
        high_score_file = GameConstants.HIGH_SCORE_FILE
        if os.path.exists(high_score_file) and os.path.getsize(high_score_file) > 0:
            with open(high_score_file, "r") as f:
                data = json.load(f)
            game_state.high_score = data.get(game_state.game_mode, {}).get(
                "high_score", 0
            )
            logger.info(
                f"Loaded high score for mode '{game_state.game_mode}': {game_state.high_score}"
            )
        else:
            game_state.high_score = 0
    except Exception as e:
        logger.error(f"Failed load high score: {e}")
        game_state.high_score = 0


def check_achievements(game_state: Any) -> None:
    """Check achievements and notify."""
    # (Code unchanged)
    # Needs play_sound and show_notification from helpers
    if not hasattr(game_state, "achievements"):
        return
    newly_unlocked = False
    for ach in game_state.achievements:
        if not ach.unlocked and ach.check(game_state):
            ach.unlocked = True
            logger.info(f"Achieved: {ach.name} - {ach.description}")
            show_notification(
                game_state, f"Unlocked: {ach.name}", duration=5.0
            )  # Use helper
            play_sound(game_state, game_state.achievement_sound)  # Use helper
            newly_unlocked = True
    if newly_unlocked:
        save_achievements(
            game_state, GameConstants.ACHIEVEMENTS_FILE
        )  # save_achievements is local


def update_achievement_notification(game_state: Any, dt: float) -> None:
    """Updates timer for achievement popup."""
    # (Code unchanged)
    if (
        hasattr(game_state, "achievement_notification_timer")
        and game_state.achievement_notification_timer > 0
    ):
        game_state.achievement_notification_timer -= dt
        if game_state.achievement_notification_timer <= 0:
            if hasattr(game_state, "achievement_notification"):
                game_state.achievement_notification = None


def update_notifications(game_state: Any, dt: float) -> None:
    """Update notification timer."""
    # (Code unchanged)
    if hasattr(game_state, "notification_timer") and game_state.notification_timer > 0:
        game_state.notification_timer -= dt
        if game_state.notification_timer <= 0:
            if hasattr(game_state, "notification_text"):
                game_state.notification_text = None


def update_timers_and_state(game_state: Any, dt: float) -> None:
    """Handle timer decrement, state changes, effects updates, and click feedback timeout."""
    # Needs play_sound and save_score from helpers
    # Needs CurrentGameState from game_types
    # Needs UIConstants for click feedback duration

    # --- ADDED: Check and clear click feedback state ---
    if hasattr(game_state, "click_feedback_state") and game_state.click_feedback_state:
        _rect, click_time = game_state.click_feedback_state
        if time.time() - click_time >= UIConstants.CLICK_FEEDBACK_DURATION:
            game_state.click_feedback_state = None
            # logger.debug("Cleared click feedback state") # Optional debug log
    # --- END ADDED ---

    # (Rest of the function remains the same)
    if (
        game_state.current_state == CurrentGameState.PLAYING
        and game_state.game_mode in ["timed", "survival"]
        and game_state.game_timer is not None
    ):
        if (
            game_state.game_timer > 0
            and game_state.game_timer <= 10.0
            and not game_state.low_time_warning_played
        ):
            logger.info("Timer low.")
            play_sound(game_state, game_state.low_time_sound)  # Use helper
            game_state.low_time_warning_played = True
        game_state.game_timer -= dt
        if game_state.game_timer <= 0:
            game_state.game_timer = 0
            if game_state.current_state != CurrentGameState.GAME_OVER:
                logger.info(f"Timer expired in {game_state.game_mode} mode.")
                game_state.current_state = CurrentGameState.GAME_OVER
                game_state.win_condition_met = False
                try:
                    player_name = (
                        game_state.get_current_player().name
                        if hasattr(game_state.get_current_player(), "name")
                        else None
                    )
                    if player_name:
                        save_score(game_state, player_name)  # Use helper
                    else:
                        logger.error(
                            "Cannot save score on timer expiry, player name missing."
                        )
                except Exception as e:
                    logger.error(f"Error saving score on timer expiry: {e}")

    if game_state.current_state == CurrentGameState.PLAYING:
        check_achievements(game_state)  # check_achievements is local
        if game_state.game_mode == "fun":
            if hasattr(game_state, "active_explosions"):
                for explosion in game_state.active_explosions:
                    explosion.update(dt)
                game_state.active_explosions = [
                    exp for exp in game_state.active_explosions if exp.is_active()
                ]

    if game_state.current_state != CurrentGameState.GETTING_PLAYER_NAME:
        update_achievement_notification(game_state, dt)  # Local
        update_notifications(game_state, dt)  # Local


# --- THIS FUNCTION MUST REMAIN HERE ---
def reset_game(game_state: Any) -> None:
    """Reset the game state fully, preserving music selection and volume levels."""
    # Needs load_initial_state and set_volume (local)
    # Needs Player, BallTrail, Explosion classes (imported)
    # Needs GameConstants (imported)
    logger.info("Resetting game state via game_state_utils...")
    game_state.score = 0
    # Clear lists/dicts safely
    attrs_to_clear = [
        "tracked_balls",
        "scored_balls",
        "scored_positions",
        "balls_in_zone",
        "ball_scored_zones",
        "ball_states",
        "previous_ball_states",
        "ball_positions_history",
        "ball_zone_history",
        "zone_cooldown",
        "active_trails",
        "active_explosions",
        "submenu_items",
    ]
    for attr_name in attrs_to_clear:
        if hasattr(game_state, attr_name):
            try:
                getattr(game_state, attr_name).clear()
            except AttributeError:
                logger.warning(f"Could not clear attribute: {attr_name}")

    # Reset other attributes
    game_state.next_ball_id = 0
    game_state.submenu_active = None
    game_state.achievement_notification = None
    game_state.achievement_notification_timer = 0.0
    game_state.win_condition_met = False
    game_state.edit_zones_current_page = 1
    game_state.editing_zone_index = None
    game_state.editing_zone_mode = None
    game_state.editing_zone_points_input = None
    game_state.editing_player_index = None
    game_state.editing_player_mode = None
    game_state.editing_player_name_input = None
    game_state.selected_zone_for_edit = None
    game_state.zone_editing_action = None
    game_state.drag_start_pos = None
    game_state.original_zone_on_drag_start = None
    game_state.special_hole_hit_this_session = False
    game_state.low_time_warning_played = False
    game_state.click_feedback_state = None  # Also reset click feedback

    # Reset player score
    if (
        hasattr(game_state, "players")
        and game_state.players
        and 0 <= game_state.current_player_index < len(game_state.players)
    ):
        game_state.players[game_state.current_player_index].reset_score()

    # Reset timer
    if game_state.game_mode == "timed":
        game_state.game_timer = GameConstants.TIMED_MODE_DURATION
    elif game_state.game_mode == "survival":
        game_state.game_timer = GameConstants.SURVIVAL_MODE_START_TIME
    else:
        game_state.game_timer = None

    load_initial_state(game_state)  # Local call

    # --- START CHANGE: Randomize music track on reset ---
    if GameConstants.BACKGROUND_MUSIC_TRACKS:
        num_tracks = len(GameConstants.BACKGROUND_MUSIC_TRACKS)
        new_track_index = random.randint(0, num_tracks - 1)

        # Avoid loading the same track if possible, unless only one track exists
        if num_tracks > 1 and new_track_index == game_state.selected_music_track_index:
            new_track_index = (new_track_index + 1) % num_tracks

        logger.info(f"Resetting music track randomly to index: {new_track_index}")
        # Stop current music if playing
        if game_state.background_music:
            game_state.background_music.stop()
        # Load the new track
        game_state.selected_music_track_index = new_track_index
        game_state.background_music = load_background_music(
            game_state, game_state.selected_music_track_index
        )
    else:
        logger.warning("Cannot randomize music on reset: No tracks defined.")
    # --- END CHANGE ---

    set_volume(game_state)  # Local call (will start playing new track if enabled)
    logger.info(f"Game state reset complete.")


# --- Wrapper for Scoring Logic ---
def update_scoring(game_state: Any) -> None:
    """Wrapper to call the scoring logic from scoring_logic.py"""
    # Delegate the actual work to the function in scoring_logic.py
    _update_scoring_logic(game_state)


# --- Functions Moved to game_state_helpers.py ---
# set_special_hole, is_ball_at_rest, is_ball_zone_stable, play_sound,
# show_notification, save_high_score, save_score, load_zones, save_zones,
# clear_zones, flush_scoring_zones
