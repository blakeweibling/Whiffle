# game_state_utils.py
"""
Utility functions for the GameState class in the Whiffle Tracker project.
Handles initialization, saving/loading state, and state transitions like reset.
"""

import json
import logging
import os
import time
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

PLAY_DATES_FILE = "data/achievements/play_dates.json"

import numpy as np
import pygame  # Add pygame import

# Import local components
from achievement import Achievement
from constants import GameConstants, UIConstants, ResolutionConstants
from io_utils import atomic_write_json
from game_state_helpers import (
    set_special_hole,
    play_sound,
    save_score,
    show_notification,
)
from game_types import CurrentGameState
from scoring_logic import update_scoring as _update_scoring_logic  # Alias for clarity

# Import DataLogger for type hinting (optional but good practice)
try:
    from data_logger import DataLogger
except ImportError:
    DataLogger = None

logger = logging.getLogger(__name__)


def _get_current_player_name(game_state: Any) -> str:
    """
    Safely get the current player's name from game_state.
    Falls back to 'Player 1' if anything goes wrong.
    """
    try:
        # Prefer explicit helper if available
        if hasattr(game_state, "get_current_player"):
            player = game_state.get_current_player()
            if player is not None and hasattr(player, "name"):
                return str(player.name)

        # Fallback to players list + current_player_index
        if hasattr(game_state, "players") and getattr(game_state, "players", None):
            players = game_state.players
            index = getattr(game_state, "current_player_index", 0)
            if 0 <= index < len(players) and hasattr(players[index], "name"):
                return str(players[index].name)
    except Exception as e:
        logger.warning(f"Error determining current player name for achievements: {e}")

    return "Player 1"


# --- Functions Remaining in game_state_utils (Initialization, Load/Save, Volume etc.) ---
# These functions (initialize_sounds, initialize_achievements, load/save_achievements,
# load/save_hsv_ranges, load/save_settings, load/change/toggle music/sound, set_volume,
# load_initial_state, check_achievements, update_achievement_notification,
# update_notifications, update_timers_and_state) remain largely the same as before,
# unless they specifically need modification for the stats feature (which they mostly don't).
# For brevity, their original code is assumed here, focusing on the modified reset_game.
def initialize_sounds() -> (
    Tuple[Optional[pygame.mixer.Sound], Optional[pygame.mixer.Sound]]
):
    """Initialize sound effects (score, low time)."""
    pygame.mixer.init()
    score_sound = None
    low_time_sound = None
    # achievement_sound = None # Add if you have an achievement sound
    try:
        score_sound_path = os.path.join(GameConstants.SOUND_EFFECTS_PATH, "ding.wav")
        low_time_sound_path = os.path.join(
            GameConstants.SOUND_EFFECTS_PATH, "10_sec_timer.mp3"
        )
        # achievement_sound_path = os.path.join(GameConstants.SOUND_EFFECTS_PATH, "achievement.wav")

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


def _cached_on_any_leaderboard(game_state: Any, ttl_seconds: float = 30.0) -> bool:
    """Check if current player appears on any leaderboard. Cached to avoid 6 API calls every achievement check."""
    cache = getattr(game_state, "_on_board_cache", None)
    now = time.time()
    try:
        player = game_state.get_current_player() if hasattr(game_state, "get_current_player") else None
        current_name = player.name if (player and hasattr(player, "name")) else None
    except Exception:
        current_name = None
    if cache is not None and len(cache) == 3:
        cached_name, cached_time, result = cache
        if current_name == cached_name and (now - cached_time) < ttl_seconds:
            return result
    if not hasattr(game_state, "leaderboard") or game_state.leaderboard is None or not current_name:
        setattr(game_state, "_on_board_cache", (current_name, now, False))
        return False
    for mode in ["classic", "timed", "survival", "fun", "practice", "retro"]:
        try:
            scores, _ = game_state.leaderboard.get_top_scores(mode=mode, limit=100)
            for e in scores:
                if e.get("player_name") == current_name:
                    setattr(game_state, "_on_board_cache", (current_name, now, True))
                    return True
        except Exception:
            continue
    setattr(game_state, "_on_board_cache", (current_name, now, False))
    return False


def initialize_achievements() -> List[Achievement]:
    """Initialize the list of achievements."""
    return [
        # --- Scoring ---
        Achievement(
            "First Score",
            "Score first points",
            lambda gs: hasattr(gs, "players")
            and gs.players
            and gs.players[gs.current_player_index].score >= 100,
        ),
        Achievement(
            "Half Grand",
            "Score 500 points",
            lambda gs: hasattr(gs, "players")
            and gs.players
            and gs.players[gs.current_player_index].score >= 500,
        ),
        Achievement(
            "High Roller",
            "Score 1000 points",
            lambda gs: hasattr(gs, "players")
            and gs.players
            and gs.players[gs.current_player_index].score >= 1000,
        ),
        Achievement(
            "Victory Lap",
            "Reach 2000 (win score) in classic, timed, or survival",
            lambda gs: hasattr(gs, "players")
            and gs.players
            and gs.players[gs.current_player_index].score >= getattr(gs, "win_score", 2000)
            and getattr(gs, "game_mode", "") in ["classic", "timed", "survival"],
        ),
        Achievement(
            "Legend",
            "Score 3000 points in one game",
            lambda gs: hasattr(gs, "players")
            and gs.players
            and gs.players[gs.current_player_index].score >= 3000,
        ),
        Achievement(
            "Lucky Shot",
            "Score in the special hole once",
            lambda gs: getattr(gs, "special_hole_hit_this_session", False),
        ),
        Achievement(
            "Hole Hunter",
            "Score in the special hole 2 times in one game",
            lambda gs: getattr(gs, "special_hole_hits_this_session", 0) >= 2,
        ),
        # --- Zones & setup ---
        Achievement(
            "Zone Master",
            "Create 5 zones",
            lambda gs: len(gs.scoring_zones) >= 5,
        ),
        Achievement(
            "Architect",
            "Create 10 zones",
            lambda gs: len(gs.scoring_zones) >= 10,
        ),
        Achievement(
            "Tinkerer",
            "Edit points on any zone",
            lambda gs: getattr(gs, "has_edited_zone_points", False),
        ),
        Achievement(
            "Dual Threat",
            "Play in both Whiffle and Five Star layouts",
            lambda gs: hasattr(gs, "players")
            and gs.players
            and hasattr(gs.players[gs.current_player_index], "layouts_played")
            and len(gs.players[gs.current_player_index].layouts_played) >= 2,
        ),
        # --- Game modes ---
        Achievement(
            "Against the Clock",
            "Reach 2000 in timed mode",
            lambda gs: hasattr(gs, "players")
            and gs.players
            and hasattr(gs.players[gs.current_player_index], "modes_won")
            and "timed" in gs.players[gs.current_player_index].modes_won,
        ),
        Achievement(
            "Survivor",
            "Reach 2000 in survival mode",
            lambda gs: hasattr(gs, "players")
            and gs.players
            and hasattr(gs.players[gs.current_player_index], "modes_won")
            and "survival" in gs.players[gs.current_player_index].modes_won,
        ),
        Achievement(
            "Mode Hopper",
            "Play all 6 game modes",
            lambda gs: hasattr(gs, "players")
            and gs.players
            and hasattr(gs.players[gs.current_player_index], "modes_played")
            and len(gs.players[gs.current_player_index].modes_played) >= 6,
        ),
        Achievement(
            "Triple Crown",
            "Win in 3 different modes",
            lambda gs: hasattr(gs, "players")
            and gs.players
            and hasattr(gs.players[gs.current_player_index], "modes_won")
            and len(gs.players[gs.current_player_index].modes_won) >= 3,
        ),
        # --- Persistence ---
        Achievement(
            "Marathon",
            "Play 10 games",
            lambda gs: hasattr(gs, "players")
            and gs.players
            and hasattr(gs.players[gs.current_player_index], "games_played")
            and gs.players[gs.current_player_index].games_played >= 10,
        ),
        Achievement(
            "Regular",
            "Play 25 games",
            lambda gs: hasattr(gs, "players")
            and gs.players
            and hasattr(gs.players[gs.current_player_index], "games_played")
            and gs.players[gs.current_player_index].games_played >= 25,
        ),
        Achievement(
            "Dedicated",
            "Play 50 games",
            lambda gs: hasattr(gs, "players")
            and gs.players
            and hasattr(gs.players[gs.current_player_index], "games_played")
            and gs.players[gs.current_player_index].games_played >= 50,
        ),
        Achievement(
            "Identity Crisis",
            "Play as 5 different player names",
            lambda gs: hasattr(gs, "players") and len(gs.players) >= 5,
        ),
        Achievement(
            "Week Warrior",
            "Play on 7 different calendar days",
            lambda gs: _week_warrior_check(gs),
        ),
        # --- Replays & sharing ---
        Achievement(
            "Recorded",
            "Save at least one replay",
            lambda gs: (
                hasattr(gs, "replay_manager")
                and gs.replay_manager is not None
                and any(
                    r.get("player_name") == _get_current_player_name(gs)
                    for r in gs.replay_manager.get_all_replays()
                )
            ),
        ),
        Achievement(
            "Show Off",
            "Share a replay (Discord, YouTube, Local, or Share Link)",
            lambda gs: getattr(gs, "has_shared_replay", False),
        ),
        Achievement(
            "Highlight Reel",
            "Export a highlight clip from a replay",
            lambda gs: getattr(gs, "has_exported_highlight", False),
        ),
        # --- Misc ---
        Achievement(
            "On the Board",
            "Appear on any leaderboard",
            lambda gs: _cached_on_any_leaderboard(gs),
        ),
        Achievement(
            "Proof",
            "Upload a high-score screenshot once",
            lambda gs: getattr(gs, "has_uploaded_screenshot", False),
        ),
        Achievement(
            "Analyst",
            "View the heatmap after a session",
            lambda gs: getattr(gs, "has_viewed_heatmap", False),
        ),
        Achievement(
            "Inclusive",
            "Turn on colorblind mode",
            lambda gs: getattr(gs, "colorblind_mode", False),
        ),
        Achievement(
            "Take a Breather",
            "Pause and resume a game",
            lambda gs: getattr(gs, "has_paused_and_resumed", False),
        ),
        # --- Whiffle ball types ---
        Achievement(
            "Red Hot",
            "Score with a red (2x) ball",
            lambda gs: getattr(gs, "scored_red_ball_this_session", False),
        ),
        Achievement(
            "Split Decision",
            "Score with a half-red (1.5x) ball",
            lambda gs: getattr(gs, "scored_half_red_this_session", False),
        ),
        Achievement(
            "Multiplier Master",
            "Earn 500 points from 2x/1.5x balls in one game",
            lambda gs: getattr(gs, "points_from_multiplier_balls_this_game", 0) >= 500,
        ),
    ]


def _week_warrior_check(game_state: Any) -> bool:
    """True if current player has played on 7+ different calendar days."""
    try:
        if not os.path.exists(PLAY_DATES_FILE) or os.path.getsize(PLAY_DATES_FILE) == 0:
            return False
        with open(PLAY_DATES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False
        name = _get_current_player_name(game_state)
        dates = data.get(name, [])
        return len(set(dates)) >= 7
    except Exception:
        return False


def record_game_completed(game_state: Any) -> None:
    """
    Call when a game ends (GAME_OVER). Updates current player's modes_played,
    modes_won, layouts_played, and appends today to play_dates for Week Warrior.
    """
    # Treat completions from static-image (no live camera) runs as non-official:
    # do not update persistent per-game stats (modes played/won, layouts, play dates).
    if not getattr(game_state, "camera_available", True):
        logger.info(
            "Static image mode detected (no live camera). "
            "Skipping record_game_completed persistence."
        )
        return

    try:
        player = (
            game_state.get_current_player()
            if hasattr(game_state, "get_current_player")
            else None
        )
        if not player or not hasattr(player, "modes_played"):
            return
        game_mode = getattr(game_state, "game_mode", None)
        playfield_type = getattr(game_state, "playfield_type", "whiffle")
        win_condition_met = getattr(game_state, "win_condition_met", False)

        player.modes_played.add(game_mode)
        player.layouts_played.add(playfield_type)
        if win_condition_met:
            player.modes_won.add(game_mode)

        # Append today for Week Warrior achievement
        player_name = player.name
        try:
            data = {}
            if os.path.exists(PLAY_DATES_FILE) and os.path.getsize(PLAY_DATES_FILE) > 0:
                with open(PLAY_DATES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            if not isinstance(data, dict):
                data = {}
            dates = data.get(player_name, [])
            if not isinstance(dates, list):
                dates = []
            today_str = date.today().isoformat()
            if today_str not in dates:
                dates.append(today_str)
            data[player_name] = dates
            atomic_write_json(PLAY_DATES_FILE, data, indent=2)
        except Exception as e:
            logger.warning(f"Could not update play_dates for Week Warrior: {e}")
    except Exception as e:
        logger.warning(f"Error in record_game_completed: {e}")


def load_achievements(game_state: Any, filename: str) -> None:
    """Load achievements status from a JSON file."""
    if not hasattr(game_state, "achievements") or not game_state.achievements:
        logger.warning(
            "Cannot load achievements status: game_state.achievements is missing or empty."
        )
        return
    achievements_file = filename
    try:
        if os.path.exists(achievements_file) and os.path.getsize(achievements_file) > 0:
            with open(achievements_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logger.warning(
                    f"Invalid format in {achievements_file}, expected a dictionary."
                )
                return  # Reset or handle error? For now, just return.

            # Determine if file is legacy (global) or per-player structure
            achievement_names = {
                a.name for a in game_state.achievements if hasattr(a, "name")
            }
            is_legacy_format = any(key in achievement_names for key in data.keys())

            player_name = _get_current_player_name(game_state)
            if is_legacy_format:
                # Legacy format: top-level keys are achievement names
                # Treat this as the current player's data only
                player_data = data
                logger.info(
                    f"Loaded legacy achievements format for player '{player_name}'. "
                    "It will be converted to per-player format on next save."
                )
            else:
                # New per-player format: top-level keys are player names
                player_data = data.get(player_name, {})

            loaded_count = 0
            # Ensure achievement objects exist before trying to update them
            if isinstance(game_state.achievements, list):
                for achievement in game_state.achievements:
                    if (
                        hasattr(achievement, "name")
                        and achievement.name in player_data
                    ):
                        achievement_data = player_data.get(achievement.name, {})
                        if isinstance(achievement_data, dict) and achievement_data.get(
                            "unlocked"
                        ):
                            achievement.unlocked = True
                            achievement.unlocked_layout = achievement_data.get("layout")
                            loaded_count += 1
                logger.debug(
                    f"Loaded status for {loaded_count} achievements from {achievements_file} for player '{player_name}'."
                )
            else:
                logger.error(
                    "game_state.achievements is not a list, cannot load status."
                )
        else:
            logger.info(
                f"Achievements file '{achievements_file}' not found or empty. Initializing all as locked."
            )
            # Ensure all are marked as locked if file doesn't exist
            if isinstance(game_state.achievements, list):
                for achievement in game_state.achievements:
                    if hasattr(achievement, "unlocked"):
                        achievement.unlocked = False

    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed load achievements from {achievements_file}: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error loading achievements: {e}")


def save_achievements(game_state: Any, filename: str) -> None:
    """Save achievements status to a JSON file."""
    if not hasattr(game_state, "achievements") or not isinstance(
        game_state.achievements, list
    ):
        logger.warning(
            "Cannot save achievements status: game_state.achievements is missing or not a list."
        )
        return
    achievements_file = filename
    try:
        # Load existing data so we can preserve other players' achievements
        data: Dict[str, Any] = {}
        if os.path.exists(achievements_file) and os.path.getsize(achievements_file) > 0:
            try:
                with open(achievements_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
                else:
                    logger.warning(
                        f"Existing achievements file {achievements_file} is not a dict. "
                        "Overwriting with new per-player structure."
                    )
            except (IOError, json.JSONDecodeError) as e:
                logger.warning(
                    f"Could not read existing achievements file {achievements_file}: {e}. "
                    "Recreating file."
                )

        # Detect and convert legacy (global) structure if necessary
        achievement_names = {
            a.name for a in game_state.achievements if hasattr(a, "name")
        }
        is_legacy_format = any(key in achievement_names for key in data.keys())

        player_name = _get_current_player_name(game_state)

        if is_legacy_format:
            # Wrap legacy data under the current player's name
            logger.info(
                f"Converting legacy achievements file to per-player format for player '{player_name}'."
            )
            data = {player_name: data}

        # Build current player's achievement status (include layout for display)
        player_achievements = {
            a.name: {
                "unlocked": a.unlocked,
                "layout": getattr(a, "unlocked_layout", None),
            }
            for a in game_state.achievements
            if hasattr(a, "name") and hasattr(a, "unlocked")
        }

        # Update / insert this player's achievements into the file-wide dict
        data[player_name] = player_achievements

        if atomic_write_json(achievements_file, data, indent=4):
            logger.debug(
                f"Saved achievements status for player '{player_name}' to {achievements_file}."
            )
        else:
            logger.error(f"Failed to save achievements file {achievements_file}")
    except Exception as e:
        logger.exception(f"Unexpected error saving achievements: {e}")


def load_hsv_ranges(
    filename: str = None,
) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """Load HSV ranges from a JSON file."""
    # Default values
    hsv_ranges = {
        "silver": (
            np.array([0, 0, 180], dtype=np.uint8),
            np.array([179, 30, 255], dtype=np.uint8),
        ),
        "gold": (
            np.array([15, 100, 100], dtype=np.uint8),
            np.array([30, 255, 255], dtype=np.uint8),
        ),
        # Add defaults for other colors if needed
    }
    hsv_file = filename if filename is not None else GameConstants.HSV_RANGES_FILE
    if os.path.exists(hsv_file) and os.path.getsize(hsv_file) > 0:
        try:
            with open(hsv_file, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
            if not isinstance(loaded_data, dict):
                logger.warning(
                    f"Invalid format in {hsv_file} (expected dict), using defaults."
                )
                return hsv_ranges

            # Update defaults with loaded data, validating format
            for key in hsv_ranges.keys():  # Iterate through expected keys
                if key in loaded_data:
                    if (
                        isinstance(loaded_data[key], list)
                        and len(loaded_data[key]) == 2
                    ):
                        try:
                            lower = np.array(loaded_data[key][0], dtype=np.uint8)
                            upper = np.array(loaded_data[key][1], dtype=np.uint8)
                            if lower.shape == (3,) and upper.shape == (3,):
                                hsv_ranges[key] = (lower, upper)
                            else:
                                logger.warning(
                                    f"Invalid HSV array shape for '{key}' in {hsv_file}. Using default."
                                )
                        except (ValueError, TypeError) as e:
                            logger.warning(
                                f"Error parsing HSV values for '{key}' in {hsv_file}: {e}. Using default."
                            )
                    else:
                        logger.warning(
                            f"Invalid format for '{key}' in {hsv_file} (expected list of 2 arrays). Using default."
                        )
                # else: key not in loaded file, default remains
            logger.debug(f"Loaded custom HSV ranges from {hsv_file}")
        except (IOError, json.JSONDecodeError) as e:
            logger.error(
                f"Failed load HSV ranges from {hsv_file}: {e}. Using defaults."
            )
        except Exception as e:
            logger.exception(
                f"Unexpected error loading HSV ranges: {e}. Using defaults."
            )
    else:
        logger.info(f"HSV ranges file '{hsv_file}' not found or empty, using defaults.")
    return hsv_ranges


def save_hsv_ranges(
    hsv_ranges: Dict[str, Tuple[np.ndarray, np.ndarray]],
    filename: str = None,
) -> None:
    """Save HSV ranges to a JSON file."""
    hsv_file = filename if filename is not None else GameConstants.HSV_RANGES_FILE
    serializable_data = {}
    for key, (lower, upper) in hsv_ranges.items():
        # Ensure data is numpy array before converting
        if isinstance(lower, np.ndarray) and isinstance(upper, np.ndarray):
            try:
                serializable_data[key] = (lower.tolist(), upper.tolist())
            except Exception as e:
                logger.error(
                    f"Could not convert HSV numpy arrays to list for key '{key}': {e}"
                )
        else:
            logger.warning(
                f"Cannot serialize non-numpy HSV data for '{key}'. Skipping."
            )

    if not serializable_data:
        logger.warning("No valid HSV data to save.")
        return
    try:
        with open(hsv_file, "w", encoding="utf-8") as f:
            json.dump(serializable_data, f, indent=4)
        logger.info(f"Saved HSV ranges to {hsv_file}")
    except IOError as e:
        logger.error(f"Failed to save HSV ranges to {hsv_file}: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error saving HSV ranges: {e}")


def load_settings(game_state: Any) -> None:
    """Loads settings like volume from the settings file."""
    settings_file = GameConstants.SETTINGS_FILE
    # Default values from constants
    default_sound_vol = GameConstants.INITIAL_SOUND_VOLUME
    default_music_vol = GameConstants.INITIAL_MUSIC_VOLUME
    default_sound_on = True
    default_music_on = True
    default_colorblind_mode = UIConstants.DEFAULT_COLORBLIND_MODE
    default_playfield = "whiffle"
    default_game_mode = "classic"
    default_leaderboard_mode = "classic"
    default_resolution = ResolutionConstants.DEFAULT_RESOLUTION
    default_music_track = 0
    default_auto_record = False
    default_replay_sort = "newest"
    default_operator_remote_enabled = True
    default_operator_remote_port = 8765
    default_operator_remote_pin = "1234"
    valid_playfields = {"whiffle", "fivestar"}
    valid_game_modes = {"classic", "timed", "survival", "fun", "practice", "retro", "versus"}
    valid_leaderboard_modes = {"classic", "timed", "survival", "fun", "practice", "retro"}
    valid_replay_sorts = {"newest", "score", "player", "mode"}

    try:
        if os.path.exists(settings_file) and os.path.getsize(settings_file) > 0:
            with open(settings_file, "r") as f:
                settings_data = json.load(f)

            # Load sound volume safely
            loaded_sound_vol = settings_data.get("sound_volume", default_sound_vol)
            try:
                sound_vol_float = float(loaded_sound_vol)
                if 0.0 <= sound_vol_float <= 1.0:
                    game_state.current_sound_volume = sound_vol_float
                else:
                    game_state.current_sound_volume = default_sound_vol
                    logger.warning(
                        f"Invalid sound_volume '{loaded_sound_vol}' in settings, using default."
                    )
            except (ValueError, TypeError):
                game_state.current_sound_volume = default_sound_vol
                logger.warning(
                    f"Non-numeric sound_volume '{loaded_sound_vol}' in settings, using default."
                )

            # Load music volume safely
            loaded_music_vol = settings_data.get("music_volume", default_music_vol)
            try:
                music_vol_float = float(loaded_music_vol)
                if 0.0 <= music_vol_float <= 1.0:
                    game_state.current_music_volume = music_vol_float
                else:
                    game_state.current_music_volume = default_music_vol
                    logger.warning(
                        f"Invalid music_volume '{loaded_music_vol}' in settings, using default."
                    )
            except (ValueError, TypeError):
                game_state.current_music_volume = default_music_vol
                logger.warning(
                    f"Non-numeric music_volume '{loaded_music_vol}' in settings, using default."
                )

            # Load sound toggle safely
            loaded_sound_on = settings_data.get("game_sounds_on", default_sound_on)
            if isinstance(loaded_sound_on, bool):
                game_state.game_sounds_on = loaded_sound_on
            else:
                game_state.game_sounds_on = default_sound_on
                logger.warning(
                    f"Invalid game_sounds_on type '{type(loaded_sound_on)}' in settings, using default."
                )

            # Load music toggle safely
            loaded_music_on = settings_data.get("background_music_on", default_music_on)
            if isinstance(loaded_music_on, bool):
                game_state.background_music_on = loaded_music_on
            else:
                game_state.background_music_on = default_music_on
                logger.warning(
                    f"Invalid background_music_on type '{type(loaded_music_on)}' in settings, using default."
                )

            # Load colorblind mode toggle safely
            loaded_colorblind_mode = settings_data.get(
                "colorblind_mode", default_colorblind_mode
            )
            if isinstance(loaded_colorblind_mode, bool):
                game_state.colorblind_mode = loaded_colorblind_mode
            else:
                game_state.colorblind_mode = default_colorblind_mode
                logger.warning(
                    f"Invalid colorblind_mode type '{type(loaded_colorblind_mode)}' in settings, using default."
                )

            # <<< ADDED: Load Discord Webhook URL >>>
            game_state.discord_webhook_url = settings_data.get(
                "discord_webhook_url", None
            )
            if (
                not game_state.discord_webhook_url
                or game_state.discord_webhook_url == "YOUR_WEBHOOK_URL_HERE"
            ):

                logger.warning(
                    "Discord Webhook URL not found or not configured in settings.json."
                )
                game_state.discord_webhook_url = (
                    None  # Ensure it's None if invalid or placeholder
                )
            else:
                logger.debug("Loaded Discord Webhook URL from settings.")
            # Remember last player name for pre-fill
            game_state.last_player_name = settings_data.get("last_player_name", "") or ""

            loaded_playfield = str(
                settings_data.get("playfield_type", default_playfield) or default_playfield
            ).strip().lower()
            if loaded_playfield in valid_playfields:
                game_state.playfield_type = loaded_playfield
                game_state.model_path = (
                    GameConstants.FIVESTAR_MODEL_PATH
                    if loaded_playfield == "fivestar"
                    else GameConstants.WHIFFLE_MODEL_PATH
                )
                game_state.zones_file_path = (
                    GameConstants.FIVESTAR_ZONES_FILE
                    if loaded_playfield == "fivestar"
                    else GameConstants.ZONES_FILE
                )
            else:
                game_state.playfield_type = default_playfield
                game_state.model_path = GameConstants.WHIFFLE_MODEL_PATH
                game_state.zones_file_path = GameConstants.ZONES_FILE

            loaded_game_mode = str(
                settings_data.get("game_mode", default_game_mode) or default_game_mode
            ).strip().lower()
            game_state.game_mode = (
                loaded_game_mode if loaded_game_mode in valid_game_modes else default_game_mode
            )

            loaded_leaderboard_mode = str(
                settings_data.get("leaderboard_mode", default_leaderboard_mode)
                or default_leaderboard_mode
            ).strip().lower()
            game_state.leaderboard_mode = (
                loaded_leaderboard_mode
                if loaded_leaderboard_mode in valid_leaderboard_modes
                else default_leaderboard_mode
            )

            loaded_resolution = str(
                settings_data.get("current_resolution_key", default_resolution)
                or default_resolution
            ).strip()
            game_state.current_resolution_key = (
                loaded_resolution
                if loaded_resolution in ResolutionConstants.RESOLUTIONS
                else default_resolution
            )

            loaded_music_track = settings_data.get(
                "selected_music_track_index", default_music_track
            )
            if isinstance(loaded_music_track, int):
                game_state.selected_music_track_index = max(0, loaded_music_track)
            else:
                game_state.selected_music_track_index = default_music_track

            loaded_auto_record = settings_data.get(
                "auto_record_replays", default_auto_record
            )
            game_state.auto_record_replays = (
                loaded_auto_record if isinstance(loaded_auto_record, bool) else default_auto_record
            )

            loaded_replay_sort = str(
                settings_data.get("replay_browser_sort", default_replay_sort)
                or default_replay_sort
            ).strip().lower()
            game_state.replay_browser_sort = (
                loaded_replay_sort
                if loaded_replay_sort in valid_replay_sorts
                else default_replay_sort
            )

            loaded_operator_remote_enabled = settings_data.get(
                "operator_remote_enabled", default_operator_remote_enabled
            )
            game_state.operator_remote_enabled = (
                loaded_operator_remote_enabled
                if isinstance(loaded_operator_remote_enabled, bool)
                else default_operator_remote_enabled
            )

            loaded_operator_remote_port = settings_data.get(
                "operator_remote_port", default_operator_remote_port
            )
            try:
                port_value = int(loaded_operator_remote_port)
                game_state.operator_remote_port = (
                    port_value if 1 <= port_value <= 65535 else default_operator_remote_port
                )
            except (TypeError, ValueError):
                game_state.operator_remote_port = default_operator_remote_port

            loaded_operator_remote_pin = str(
                settings_data.get("operator_remote_pin", default_operator_remote_pin)
                or default_operator_remote_pin
            ).strip()
            game_state.operator_remote_pin = (
                loaded_operator_remote_pin if loaded_operator_remote_pin else default_operator_remote_pin
            )
            # <<< END ADDED >>>

            logger.debug(f"Loaded settings from {settings_file}")
        else:
            logger.info(
                f"Settings file '{settings_file}' not found or empty. Using default settings."
            )
            game_state.current_sound_volume = default_sound_vol
            game_state.current_music_volume = default_music_vol
            game_state.game_sounds_on = default_sound_on
            game_state.background_music_on = default_music_on
            game_state.discord_webhook_url = None  # Default to None if file not found
            game_state.last_player_name = ""
            game_state.playfield_type = default_playfield
            game_state.model_path = GameConstants.WHIFFLE_MODEL_PATH
            game_state.zones_file_path = GameConstants.ZONES_FILE
            game_state.game_mode = default_game_mode
            game_state.leaderboard_mode = default_leaderboard_mode
            game_state.current_resolution_key = default_resolution
            game_state.selected_music_track_index = default_music_track
            game_state.auto_record_replays = default_auto_record
            game_state.replay_browser_sort = default_replay_sort
            game_state.operator_remote_enabled = default_operator_remote_enabled
            game_state.operator_remote_port = default_operator_remote_port
            game_state.operator_remote_pin = default_operator_remote_pin
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed load settings from {settings_file}: {e}. Using defaults.")
        game_state.current_sound_volume = default_sound_vol
        game_state.current_music_volume = default_music_vol
        game_state.game_sounds_on = default_sound_on
        game_state.background_music_on = default_music_on
        game_state.discord_webhook_url = None  # Default to None on error
        game_state.last_player_name = ""
        game_state.playfield_type = default_playfield
        game_state.model_path = GameConstants.WHIFFLE_MODEL_PATH
        game_state.zones_file_path = GameConstants.ZONES_FILE
        game_state.game_mode = default_game_mode
        game_state.leaderboard_mode = default_leaderboard_mode
        game_state.current_resolution_key = default_resolution
        game_state.selected_music_track_index = default_music_track
        game_state.auto_record_replays = default_auto_record
        game_state.replay_browser_sort = default_replay_sort
        game_state.operator_remote_enabled = default_operator_remote_enabled
        game_state.operator_remote_port = default_operator_remote_port
        game_state.operator_remote_pin = default_operator_remote_pin
    except Exception as e:
        logger.exception(f"Unexpected error loading settings: {e}. Using defaults.")
        game_state.current_sound_volume = default_sound_vol
        game_state.current_music_volume = default_music_vol
        game_state.game_sounds_on = default_sound_on
        game_state.background_music_on = default_music_on
        game_state.discord_webhook_url = None  # Default to None on error
        game_state.last_player_name = ""
        game_state.playfield_type = default_playfield
        game_state.model_path = GameConstants.WHIFFLE_MODEL_PATH
        game_state.zones_file_path = GameConstants.ZONES_FILE
        game_state.game_mode = default_game_mode
        game_state.leaderboard_mode = default_leaderboard_mode
        game_state.current_resolution_key = default_resolution
        game_state.selected_music_track_index = default_music_track
        game_state.auto_record_replays = default_auto_record
        game_state.replay_browser_sort = default_replay_sort
        game_state.operator_remote_enabled = default_operator_remote_enabled
        game_state.operator_remote_port = default_operator_remote_port
        game_state.operator_remote_pin = default_operator_remote_pin


def save_settings(game_state: Any) -> None:
    """Saves current settings like volume to the settings file."""
    settings_file = GameConstants.SETTINGS_FILE
    # Ensure attributes exist before saving
    settings_data = {
        "sound_volume": getattr(
            game_state, "current_sound_volume", GameConstants.INITIAL_SOUND_VOLUME
        ),
        "music_volume": getattr(
            game_state, "current_music_volume", GameConstants.INITIAL_MUSIC_VOLUME
        ),
        "game_sounds_on": getattr(game_state, "game_sounds_on", True),
        "background_music_on": getattr(game_state, "background_music_on", True),
        "colorblind_mode": getattr(
            game_state, "colorblind_mode", UIConstants.DEFAULT_COLORBLIND_MODE
        ),
        # <<< ADDED: Save Discord Webhook URL >>>
        "discord_webhook_url": getattr(game_state, "discord_webhook_url", None),
        "last_player_name": getattr(game_state, "last_player_name", "") or "",
        "playfield_type": getattr(game_state, "playfield_type", "whiffle"),
        "game_mode": getattr(game_state, "game_mode", "classic"),
        "leaderboard_mode": getattr(game_state, "leaderboard_mode", "classic"),
        "current_resolution_key": getattr(
            game_state, "current_resolution_key", ResolutionConstants.DEFAULT_RESOLUTION
        ),
        "selected_music_track_index": getattr(game_state, "selected_music_track_index", 0),
        "auto_record_replays": getattr(game_state, "auto_record_replays", False),
        "replay_browser_sort": getattr(game_state, "replay_browser_sort", "newest"),
        "operator_remote_enabled": getattr(game_state, "operator_remote_enabled", True),
        "operator_remote_port": getattr(game_state, "operator_remote_port", 8765),
        "operator_remote_pin": getattr(game_state, "operator_remote_pin", "1234"),
        # <<< END ADDED >>>
    }
    if atomic_write_json(settings_file, settings_data, indent=4):
        logger.debug(f"Saved settings to {settings_file}")
    else:
        logger.error(f"Failed to save settings to {settings_file}")


def load_background_music(
    game_state: Any, track_index: int
) -> Optional[pygame.mixer.Sound]:
    """Loads a specific background music track by index."""
    # Use getattr to safely access BACKGROUND_MUSIC_TRACKS
    available_tracks = getattr(GameConstants, "BACKGROUND_MUSIC_TRACKS", [])
    if not available_tracks:
        logger.warning(
            "No background music tracks defined in constants. Cannot load music."
        )
        return None
    if not (0 <= track_index < len(available_tracks)):
        logger.warning(
            f"Invalid track index {track_index} requested (available: {len(available_tracks)})."
        )
        # Optionally default to index 0 if available
        if available_tracks:
            track_index = 0
            logger.info("Defaulting to track index 0.")
        else:
            return None

    track_filename = available_tracks[track_index]
    # Use getattr to safely access SOUND_EFFECTS_PATH
    sound_path_base = getattr(GameConstants, "SOUND_EFFECTS_PATH", "data/sounds/")
    track_path = os.path.join(sound_path_base, track_filename)

    logger.debug(f"Loading background music: {track_path}")
    try:
        if os.path.exists(track_path):
            music = pygame.mixer.Sound(track_path)
            return music
        else:
            logger.warning(f"Music file not found: {track_path}")
            return None
    except pygame.error as e:
        logger.error(f"Pygame error loading music '{track_filename}': {e}")
    except Exception as e:
        logger.exception(f"Unexpected error loading music '{track_filename}': {e}")
    return None


def change_music_track(game_state: Any, new_index: int):
    """Stops current music, loads and plays the new track if music is enabled."""
    available_tracks = getattr(GameConstants, "BACKGROUND_MUSIC_TRACKS", [])
    num_tracks = len(available_tracks)
    if num_tracks == 0:
        logger.warning("Cannot change music track: No tracks defined.")
        return
    # Ensure new_index is valid, wrap around if needed (or clamp)
    valid_index = new_index % num_tracks  # Simple wrap-around

    current_index = getattr(game_state, "selected_music_track_index", -1)
    current_music = getattr(game_state, "background_music", None)

    if valid_index == current_index and current_music:
        # Ensure volume is correct even if track is the same
        logger.debug(f"Track index {valid_index} already selected. Ensuring volume.")
        set_volume(game_state)  # Assumes set_volume handles starting if needed
        return

    logger.info(f"Changing music track from {current_index} to {valid_index}...")
    game_state.selected_music_track_index = valid_index

    # Stop previous music if it exists and is playing
    if (
        current_music
        and pygame.mixer.get_init()
        and any(
            ch.get_sound() == current_music
            for i in range(pygame.mixer.get_num_channels())
            if (ch := pygame.mixer.Channel(i)).get_busy()
        )
    ):
        logger.debug("Stopping previous background music track.")
        current_music.stop()

    # Load the new track
    game_state.background_music = load_background_music(
        game_state, game_state.selected_music_track_index
    )
    # Set volume and potentially start the new track
    set_volume(game_state)
    save_settings(game_state)


def toggle_background_music(game_state: Any) -> None:
    """Toggle background music ON/OFF flag and update playback/volume."""
    game_state.background_music_on = not getattr(
        game_state, "background_music_on", True
    )
    logger.info(f"Music toggled {'ON' if game_state.background_music_on else 'OFF'}")
    set_volume(game_state)  # Applies volume change and stops/starts playback
    save_settings(game_state)  # Persist the toggle state


def toggle_game_sounds(game_state: Any) -> None:
    """Toggle game sounds ON/OFF flag and update volume."""
    game_state.game_sounds_on = not getattr(game_state, "game_sounds_on", True)
    logger.info(f"Sounds toggled {'ON' if game_state.game_sounds_on else 'OFF'}")
    set_volume(game_state)  # Applies volume change to sound effects
    save_settings(game_state)  # Persist the toggle state


def set_volume(game_state: Any):
    """Sets volume for all sounds based on current levels and on/off flags."""
    # Safely get volume levels and on/off flags
    sound_vol_level = getattr(
        game_state, "current_sound_volume", GameConstants.INITIAL_SOUND_VOLUME
    )
    music_vol_level = getattr(
        game_state, "current_music_volume", GameConstants.INITIAL_MUSIC_VOLUME
    )
    sound_on = getattr(game_state, "game_sounds_on", True)
    music_on = getattr(game_state, "background_music_on", True)

    # Calculate final volumes
    sound_vol = sound_vol_level if sound_on else 0.0
    music_vol = music_vol_level if music_on else 0.0

    try:
        if not pygame.mixer.get_init():
            logger.warning("Pygame mixer not initialized, cannot set volume.")
            return

        # Set volume for individual sound effects
        if hasattr(game_state, "score_sound") and game_state.score_sound:
            game_state.score_sound.set_volume(sound_vol)
        if hasattr(game_state, "low_time_sound") and game_state.low_time_sound:
            game_state.low_time_sound.set_volume(sound_vol)
        if hasattr(game_state, "achievement_sound") and game_state.achievement_sound:
            game_state.achievement_sound.set_volume(sound_vol)
        # Add other sound effects here...

        # Handle background music volume and playback state
        if hasattr(game_state, "background_music") and game_state.background_music:
            current_music = game_state.background_music
            current_music.set_volume(music_vol)

            # Check if the specific sound object is playing on any channel
            is_playing = any(
                ch.get_sound() == current_music
                for i in range(pygame.mixer.get_num_channels())
                if (ch := pygame.mixer.Channel(i)).get_busy()
            )

            if music_on and music_vol > 0 and not is_playing:
                logger.debug(
                    "Music is ON and volume > 0, but not playing. Starting playback."
                )
                current_music.play(-1)  # Loop indefinitely
            elif (not music_on or music_vol == 0) and is_playing:
                logger.debug(
                    "Music is OFF or volume is 0, but playing. Stopping playback."
                )
                current_music.stop()

    except pygame.error as e:
        logger.error(f"Pygame error setting volume: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error setting volume: {e}")
    logger.debug(
        f"Volumes applied: Sounds={sound_vol:.2f}, Music={music_vol:.2f}. Music Playing: {music_on and music_vol > 0}"
    )


def load_initial_state(game_state: Any):
    """Loads persistent state like zones and high score for current mode."""
    # Need to import load_zones locally if it's in game_state_helpers
    try:
        from game_state_helpers import load_zones

        load_zones(game_state)  # Load scoring zones first
    except ImportError:
        logger.error("Could not import load_zones from game_state_helpers.")
        game_state.scoring_zones = []  # Default to empty zones

    # Set special hole based on loaded zones (disabled for Five Star)
    if hasattr(game_state, "is_fivestar_playfield"):
        is_fivestar = game_state.is_fivestar_playfield()
    else:
        is_fivestar = getattr(game_state, "playfield_type", "whiffle") == "fivestar"
    if is_fivestar:
        game_state.special_hole = None
    else:
        game_state.special_hole = set_special_hole(
            getattr(game_state, "scoring_zones", [])  # Use getattr for safety
        )

    # Load high score for the current game mode
    try:
        high_score_file = GameConstants.HIGH_SCORE_FILE
        current_mode = getattr(
            game_state, "game_mode", "classic"
        )  # Default to classic if mode not set
        game_state.high_score = 0  # Default high score
        game_state.high_score_player = ""

        if os.path.exists(high_score_file) and os.path.getsize(high_score_file) > 0:
            with open(high_score_file, "r") as f:
                data = json.load(f)
            if isinstance(data, dict):
                mode_data = data.get(current_mode, {})
                if isinstance(mode_data, dict):
                    game_state.high_score = mode_data.get("high_score", 0)
                    game_state.high_score_player = str(mode_data.get("player", "") or "")
                else:
                    logger.warning(
                        f"Data for mode '{current_mode}' in high score file is not a dict."
                    )
            else:
                logger.warning("High score file format is not a dict.")

        logger.debug(
            f"Loaded high score for mode '{current_mode}': {game_state.high_score}"
        )
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed load high score file '{high_score_file}': {e}")
        game_state.high_score = 0  # Reset on error
        game_state.high_score_player = ""
    except Exception as e:
        logger.exception(f"Unexpected error loading high score: {e}")
        game_state.high_score = 0  # Reset on error
        game_state.high_score_player = ""


def check_achievements(game_state: Any) -> None:
    """Check achievements and notify."""
    if not hasattr(game_state, "achievements") or not isinstance(
        game_state.achievements, list
    ):
        return  # Cannot check if achievements list doesn't exist

    newly_unlocked = False
    for ach in game_state.achievements:
        # Ensure achievement object is valid before checking
        if (
            not isinstance(ach, Achievement)
            or not hasattr(ach, "unlocked")
            or not hasattr(ach, "check")
        ):
            logger.warning(f"Invalid object found in achievements list: {ach}")
            continue

        if not ach.unlocked:
            try:
                # Pass game_state to the condition checker
                condition_met = ach.check(game_state)
                if condition_met:
                    ach.unlocked = True
                    ach.unlocked_layout = getattr(game_state, "playfield_type", "whiffle")
                    logger.info(f"Achieved: {ach.name} - {ach.description}")
                    # Use helper for notification
                    show_notification(game_state, f"Unlocked: {ach.name}", duration=5.0)
                    # Use helper for sound (ensure achievement_sound is loaded)
                    play_sound(
                        game_state, getattr(game_state, "achievement_sound", None)
                    )
                    newly_unlocked = True
            except Exception as e:
                logger.error(
                    f"Error checking achievement '{getattr(ach, 'name', 'Unknown')}': {e}"
                )

    if newly_unlocked:
        save_achievements(  # Call local save function
            game_state, GameConstants.ACHIEVEMENTS_FILE
        )


def update_achievement_notification(game_state: Any, dt: float) -> None:
    """Updates timer for achievement popup."""
    if (
        hasattr(game_state, "achievement_notification_timer")
        and game_state.achievement_notification_timer > 0
    ):
        game_state.achievement_notification_timer -= dt
        if game_state.achievement_notification_timer <= 0:
            game_state.achievement_notification_timer = 0  # Prevent negative values
            if hasattr(game_state, "achievement_notification"):
                game_state.achievement_notification = None  # Clear text


def update_notifications(game_state: Any, dt: float) -> None:
    """Update notification timer."""
    if hasattr(game_state, "notification_timer") and game_state.notification_timer > 0:
        game_state.notification_timer -= dt
        if game_state.notification_timer <= 0:
            game_state.notification_timer = 0  # Prevent negative values
            if hasattr(game_state, "notification_text"):
                game_state.notification_text = None  # Clear text


def update_timers_and_state(game_state: Any, dt: float) -> None:
    """Handle timer decrement, state changes based on timer, and click feedback timeout."""

    # --- Handle click feedback timeout ---
    if hasattr(game_state, "click_feedback_state") and game_state.click_feedback_state:
        _rect, click_time = game_state.click_feedback_state
        if time.time() - click_time >= UIConstants.CLICK_FEEDBACK_DURATION:
            game_state.click_feedback_state = None
    # --- End click feedback ---

    # --- Game Timer Logic (Timed/Survival Modes) ---
    current_state = getattr(game_state, "current_state", None)
    game_mode = getattr(game_state, "game_mode", None)

    # Only decrement timer when in PLAYING state, not in MENU or PAUSED
    if (
        current_state == CurrentGameState.PLAYING
        and game_mode in ["timed", "survival"]
        and hasattr(game_state, "game_timer")
        and game_state.game_timer is not None
    ):
        # Low time warning sound
        if (
            game_state.game_timer > 0
            and game_state.game_timer <= 10.0  # Threshold for warning
            and not getattr(game_state, "low_time_warning_played", False)
        ):
            logger.info("Timer low warning triggered.")
            play_sound(
                game_state, getattr(game_state, "low_time_sound", None)
            )  # Use helper
            game_state.low_time_warning_played = True  # Set flag

        # Decrement timer
        game_state.game_timer -= dt

        # Check if timer expired — trigger GAME_OVER for timed and survival modes
        if game_state.game_timer <= 0:
            game_state.game_timer = 0  # Clamp to zero
            if (
                game_mode in ["timed", "survival"]
                and current_state != CurrentGameState.GAME_OVER
            ):
                logger.info(
                    f"Timer expired in {game_mode} mode. Switching to GAME_OVER."
                )
                game_state.current_state = CurrentGameState.GAME_OVER
                game_state.win_condition_met = False  # Timer expired is not a win
                record_game_completed(game_state)

                # Save score when timer runs out
                try:
                    player_name = "Unknown"
                    if hasattr(game_state, "get_current_player"):
                        player = game_state.get_current_player()
                        if player and hasattr(player, "name"):
                            player_name = player.name
                    # Pass current player name and mode
                    save_score(game_state, player_name, mode=game_mode)  # Use helper
                except Exception as e:
                    logger.error(f"Error saving score on timer expiry: {e}")

    # Update achievement checks and notifications (if not in initial name input state)
    if current_state != CurrentGameState.GETTING_PLAYER_NAME:
        # Check achievements only during active play
        # Only allow achievements to unlock during live-camera games
        if current_state == CurrentGameState.PLAYING and getattr(
            game_state, "camera_available", True
        ):
            check_achievements(game_state)  # Calls local check function

        # Update notification timers regardless of play state (except name input)
        update_achievement_notification(game_state, dt)
        update_notifications(game_state, dt)

    # Update visual effects (Fun Mode)
    if game_mode == "fun" and current_state == CurrentGameState.PLAYING:
        if hasattr(game_state, "active_explosions") and isinstance(
            game_state.active_explosions, list
        ):
            active_explosions = game_state.active_explosions
            # Update existing explosions
            for explosion in active_explosions:
                if hasattr(explosion, "update") and hasattr(explosion, "is_active"):
                    explosion.update(dt)
                else:
                    logger.warning("Found invalid object in active_explosions list.")
            # Remove inactive explosions (iterate backwards or create new list)
            game_state.active_explosions = [
                exp
                for exp in active_explosions
                if hasattr(exp, "is_active") and exp.is_active()
            ]

    # Update replay playback if active
    if hasattr(game_state, "replay_playback") and game_state.replay_playback:
        replay_state = game_state.replay_playback
        if replay_state.get("playing", False):
            replay = replay_state.get("current_replay")
            if replay and replay.frames:
                current_time = time.time()
                time_since_last = current_time - replay_state.get(
                    "last_update_time", current_time
                )
                replay_state["last_update_time"] = current_time

                # Calculate frames to advance based on playback speed
                speed = replay_state.get("playback_speed", 1.0)
                frames_to_advance = max(
                    1, int(time_since_last * 30 * speed)
                )  # Assuming 30fps normal speed

                # Advance frames
                current_idx = replay_state.get("current_frame_idx", 0)
                max_idx = len(replay.frames) - 1
                new_idx = min(max_idx, current_idx + frames_to_advance)

                # Update frame index
                replay_state["current_frame_idx"] = new_idx

                # Check if we reached the end
                if new_idx >= max_idx:
                    replay_state["playing"] = False

                game_state.menu_cache = None  # Force UI update

                # If we're in playback mode, update the display with information from the current frame
                if (
                    current_state == CurrentGameState.MENU
                    and game_state.submenu_active == "replay_playback"
                ):
                    # Get current frame data
                    current_frame = replay.frames[new_idx]

                    # Update tracked_balls attribute to match current replay frame
                    if hasattr(current_frame, "balls"):
                        game_state.tracked_balls = current_frame.balls.copy()

                    # Update score to match replay frame
                    game_state.score = current_frame.score


def reset_game(game_state: Any) -> None:
    """Reset game state for a new game, while preserving player and leaderboard."""
    logger.info("Resetting game for new round.")
    
    # Reload XP data so levels stay current after reset
    try:
        from xp_system import xp_system
        xp_system.load_player_data()
    except Exception as e:
        logger.error(f"Error reloading XP data: {e}")

    # Preserve objects that should survive reset
    preserved_objects = {
        "leaderboard": getattr(game_state, "leaderboard", None),
        "leaderboard_mode": getattr(game_state, "leaderboard_mode", "classic"),
        "last_player_name": getattr(game_state, "last_player_name", "") or "",
        "playfield_type": getattr(game_state, "playfield_type", "whiffle"),
        "model_path": getattr(
            game_state, "model_path", GameConstants.WHIFFLE_MODEL_PATH
        ),
        "zones_file_path": getattr(
            game_state, "zones_file_path", GameConstants.ZONES_FILE
        ),
        "players": getattr(game_state, "players", None),
        "current_player_index": getattr(game_state, "current_player_index", 0),
        "scoring_zones": getattr(game_state, "scoring_zones", []),
        "special_hole": getattr(game_state, "special_hole", None),
        "hsv_ranges": getattr(game_state, "hsv_ranges", {}),
        "achievements": getattr(game_state, "achievements", []),
        "high_score": getattr(game_state, "high_score", 0),
        "high_score_player": getattr(game_state, "high_score_player", ""),
        "win_score": getattr(
            game_state, "win_score", GameConstants.CLASSIC_MODE_WIN_SCORE
        ),
        "game_mode": getattr(
            game_state, "game_mode", "classic"
        ),  # Preserve selected game mode
        "current_resolution_key": getattr(game_state, "current_resolution_key", None),
        "current_width": getattr(game_state, "current_width", 0),
        "current_height": getattr(game_state, "current_height", 0),
        "camera_available": getattr(game_state, "camera_available", False),
        "cap": getattr(game_state, "cap", None),
        "static_frame": getattr(game_state, "static_frame", None),
        "detector": getattr(game_state, "detector", None),
        "tracker": getattr(game_state, "tracker", None),
        # Sound-related objects to preserve
        "score_sound": getattr(game_state, "score_sound", None),
        "background_music": getattr(game_state, "background_music", None),
        "selected_music_track_index": getattr(
            game_state, "selected_music_track_index", 0
        ),
        "achievement_sound": getattr(game_state, "achievement_sound", None),
        "low_time_sound": getattr(game_state, "low_time_sound", None),
        # Audio settings
        "current_sound_volume": getattr(
            game_state, "current_sound_volume", GameConstants.INITIAL_SOUND_VOLUME
        ),
        "current_music_volume": getattr(
            game_state, "current_music_volume", GameConstants.INITIAL_MUSIC_VOLUME
        ),
        "game_sounds_on": getattr(game_state, "game_sounds_on", True),
        "background_music_on": getattr(game_state, "background_music_on", True),
        # Discord webhook URL
        "discord_webhook_url": getattr(game_state, "discord_webhook_url", None),
        # Operator remote configuration/runtime
        "operator_remote_enabled": getattr(game_state, "operator_remote_enabled", True),
        "operator_remote_port": getattr(game_state, "operator_remote_port", 8765),
        "operator_remote_pin": getattr(game_state, "operator_remote_pin", "1234"),
        "operator_remote_service": getattr(game_state, "operator_remote_service", None),
        "operator_remote_url": getattr(game_state, "operator_remote_url", ""),
        "remote_action_queue": getattr(game_state, "remote_action_queue", None),
        "remote_status_snapshot": getattr(game_state, "remote_status_snapshot", {}),
        "pending_remote_player_name": getattr(game_state, "pending_remote_player_name", ""),
        "remote_last_action_text": getattr(game_state, "remote_last_action_text", ""),
        "remote_last_action_timestamp": getattr(game_state, "remote_last_action_timestamp", 0.0),
        # Debug & UI preferences
        "debug_mode": getattr(game_state, "debug_mode", False),
        "show_debug_overlay": getattr(game_state, "show_debug_overlay", False),
        # Data logger to be preserved but reset
        "data_logger": getattr(game_state, "data_logger", None),
        # Replay system
        "replay_manager": getattr(game_state, "replay_manager", None),
    }

    # Reset player's game count and score before preserving
    try:
        if preserved_objects["players"]:
            current_player = preserved_objects["players"][
                preserved_objects["current_player_index"]
            ]
            # Only treat this as a real game for per-player stats when a live camera is used
            if preserved_objects.get("camera_available", False):
                if hasattr(current_player, "games_played"):
                    current_player.games_played += 1  # Increment games played count
                # Refresh XP data after clearing (will be level 1, 0 XP)
                if hasattr(current_player, "refresh_xp"):
                    current_player.refresh_xp()
            # Always reset per-game score for UI consistency
            if hasattr(current_player, "score"):
                current_player.score = 0
    except Exception as player_e:
        logger.error(f"Error updating player stats during reset: {player_e}")

    # Reset objects that have their own reset
    data_logger = preserved_objects.pop("data_logger", None)

    # Initialize clean state variables
    score = 0
    tracked_balls = []
    next_ball_id = 0
    frame_count = 0
    drawing = False
    scored_balls = []
    scored_positions = {}
    zone_cooldown = {}

    # Initialize all required dictionaries
    ball_positions_history = {}
    ball_zone_history = {}
    balls_in_zone = {}
    ball_scored_zones = {}
    ball_states = {}
    previous_ball_states = {}
    active_trails = {}
    active_explosions = []

    # Reset game timer and win score based on mode and layout (Five Star uses higher win scores per mode)
    is_fivestar = getattr(game_state, "playfield_type", "whiffle") == "fivestar"
    timer = None
    if preserved_objects["game_mode"] == "timed":
        timer = GameConstants.TIMED_MODE_DURATION
        game_state.win_score = (
            GameConstants.FIVESTAR_TIMED_MODE_WIN_SCORE
            if is_fivestar
            else GameConstants.TIMED_MODE_WIN_SCORE
        )
    elif preserved_objects["game_mode"] == "survival":
        timer = GameConstants.SURVIVAL_MODE_START_TIME
        game_state.win_score = (
            GameConstants.FIVESTAR_SURVIVAL_MODE_WIN_SCORE
            if is_fivestar
            else GameConstants.SURVIVAL_MODE_WIN_SCORE
        )
    else:
        game_state.win_score = (
            GameConstants.FIVESTAR_CLASSIC_MODE_WIN_SCORE
            if is_fivestar
            else GameConstants.CLASSIC_MODE_WIN_SCORE
        )

    # Set all non-preserved attributes to defaults
    for attr_name in list(vars(game_state).keys()):
        if attr_name not in preserved_objects:
            try:
                delattr(game_state, attr_name)
            except (AttributeError, Exception) as e:
                logger.warning(f"Error clearing attribute {attr_name}: {e}")

    # Restore preserved objects
    for name, obj in preserved_objects.items():
        setattr(game_state, name, obj)

    # Set new game state basics
    game_state.score = score
    game_state.final_score = 0
    game_state.score_saved_for_current_round = False
    game_state.tracked_balls = tracked_balls
    game_state.next_ball_id = next_ball_id
    game_state.frame_count = frame_count
    game_state.drawing = drawing
    game_state.scored_balls = scored_balls
    game_state.scored_positions = scored_positions
    game_state.zone_cooldown = zone_cooldown
    game_state.current_state = CurrentGameState.PLAYING
    game_state.previous_state = None
    game_state.ball_positions_history = ball_positions_history
    game_state.ball_zone_history = ball_zone_history
    game_state.balls_in_zone = balls_in_zone
    game_state.ball_scored_zones = ball_scored_zones
    game_state.ball_states = ball_states
    game_state.previous_ball_states = previous_ball_states
    game_state.active_trails = active_trails
    game_state.active_explosions = active_explosions
    game_state.game_timer = timer
    game_state.win_condition_met = False
    game_state.temp_zone = None
    game_state.drawing_points_input = ""
    game_state.submenu_active = None
    game_state.menu_cache = None
    game_state.menu_cache_key = None
    game_state.low_time_warning_played = False
    game_state.fps = 0.0  # Initialize fps counter
    game_state.special_hole_hit_this_session = False
    game_state.special_hole_hits_this_session = 0
    game_state.points_from_multiplier_balls_this_game = 0
    game_state.scored_red_ball_this_session = False
    game_state.scored_half_red_this_session = False
    game_state.current_session_stats = None

    # Initialize notification attributes
    game_state.achievement_notification = None
    game_state.achievement_notification_timer = 0.0
    game_state.notification_text = None
    game_state.notification_timer = 0.0

    # Initialize menu-related attributes
    game_state.submenu_items = []
    game_state.menu_scroll_offset = 0
    game_state.menu_selected_index = 0
    game_state.menu_visible = False
    game_state.menu_alpha = 0
    game_state.menu_fade_direction = 1
    game_state.menu_fade_speed = 0.1
    game_state.menu_max_alpha = 200

    # Reset menu/editing state
    _reset_all_menu_editing_states(game_state)

    # Start new data logging session if available (only for live camera games)
    if data_logger:
        try:
            # In static-image mode (no live camera), skip creating session stats.
            if getattr(game_state, "camera_available", True):
                current_player_name = "Player 1"
                if game_state.players:
                    current_player = game_state.players[game_state.current_player_index]
                    current_player_name = current_player.name
                data_logger.start_new_session(current_player_name, game_state.game_mode)
                game_state.data_logger = data_logger

                # If the current game state is not PLAYING, pause the session timer immediately
                current_state = getattr(game_state, "current_state", None)
                if current_state in [CurrentGameState.MENU, CurrentGameState.PAUSED]:
                    session = data_logger.get_current_session_data()
                    if session:
                        session.pause()
                        logger.debug(
                            f"Paused new session timer immediately because game state is {current_state}"
                        )

        except Exception as e:
            logger.error(f"Error starting new data logging session: {e}")

    logger.info("Game reset complete.")


# --- Helper to reset menu editing states (used locally by reset_game) ---
def _reset_all_menu_editing_states(game_state: Any) -> None:
    """Resets all flags and temporary inputs related to menu editing."""
    # Make sure attributes exist before trying to set them
    attrs_to_reset = {
        "editing_zone_index": None,
        "editing_zone_mode": None,
        "editing_zone_points_input": None,
        "editing_player_index": None,
        "editing_player_mode": None,
        "editing_player_name_input": None,
        "selected_zone_for_edit": None,
        "zone_editing_action": None,
        "drag_start_pos": None,
        "original_zone_on_drag_start": None,
        "move_all_zones": False,
        "original_zones_on_drag_start": None,
        "edit_zones_current_page": 1,
        "menu_cache": None,
        "click_feedback_state": None,  # Reset click feedback too
    }
    for attr, value in attrs_to_reset.items():
        if hasattr(game_state, attr):
            setattr(game_state, attr, value)


# --- >>> ADDED: Function to save historical stats on exit <<< ---
def save_historical_stats_on_exit(game_state: Any):
    """Saves the historical session data managed by the data logger."""
    if hasattr(game_state, "data_logger") and game_state.data_logger:
        logger.info("Saving historical session stats on exit...")
        try:
            # The _save_historical_stats method is internal to DataLogger,
            # called when end_current_session is invoked.
            # If we need explicit saving *without* ending a session (e.g., abrupt exit),
            # the DataLogger class might need a public save method, or we rely
            # on end_current_session being called by cleanup.
            # For now, let's assume end_current_session is called reliably by cleanup.
            # If not, uncomment the direct call (after making _save_historical_stats public or adding a save method).
            # game_state.data_logger._save_historical_stats() # Or game_state.data_logger.save_history()
            pass  # Assuming cleanup calls end_current_session which saves history
        except AttributeError:
            logger.error("DataLogger instance does not have the expected save method.")
        except Exception as e:
            logger.error(f"Error explicitly saving historical stats on exit: {e}")
    else:
        logger.warning(
            "Data logger not found in game_state. Cannot save historical stats."
        )


# --- >>> END ADDED <<< ---


# --- Wrapper for Scoring Logic ---
def update_scoring(game_state: Any) -> None:
    """Wrapper to call the scoring logic from scoring_logic.py"""
    # Delegate the actual work to the function in scoring_logic.py
    try:
        _update_scoring_logic(game_state)
    except Exception as e:
        logger.exception(f"Error occurred during update_scoring logic: {e}")


def toggle_debug_mode(game_state: Any) -> None:
    """Toggle debug mode and update logging level."""
    game_state.debug_mode = not getattr(game_state, "debug_mode", False)
    log_level = logging.DEBUG if game_state.debug_mode else logging.INFO
    logging.getLogger().setLevel(log_level)
    # Apply level to handlers too
    for h in logging.getLogger().handlers:
        h.setLevel(log_level)
    logger.info(f"Debug Mode: {'ON' if game_state.debug_mode else 'OFF'}")
    save_settings(game_state)  # Persist the toggle state


def toggle_colorblind_mode(game_state: Any) -> None:
    """Toggle colorblind mode for improved accessibility."""
    game_state.colorblind_mode = not getattr(
        game_state, "colorblind_mode", UIConstants.DEFAULT_COLORBLIND_MODE
    )
    logger.info(f"Colorblind Mode: {'ON' if game_state.colorblind_mode else 'OFF'}")
    show_notification(
        game_state, f"Colorblind Mode: {'ON' if game_state.colorblind_mode else 'OFF'}"
    )
    save_settings(game_state)  # Persist the toggle state
