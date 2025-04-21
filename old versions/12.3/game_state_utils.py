# game_state_utils.py
"""
Utility functions for the GameState class in the Whiffle Tracker project.
"""

import cv2
import logging
import pygame
import json
import os
import numpy as np
from typing import Optional, List, Tuple, Dict, Any

# Import constants and classes
# <<< MODIFIED: Import INITIAL_SOUND_VOLUME >>>
from constants import (
    UIConstants,
    GameConstants,
    ScoringConstants,
    GameConstants,
)
from scoring import is_in_scoring_zone
from achievement import Achievement

logger = logging.getLogger(__name__)


def set_special_hole(
    scoring_zones: List[Tuple[int, int, int, int, int]],
) -> Optional[Tuple[int, int, int, int, int]]:
    """
    Identify the leftmost scoring zone as the special hole.
    """
    if not scoring_zones:
        logger.info("No scoring zones available, special hole not set")
        return None
    # Use min based on the first element (x-coordinate) of each zone tuple
    try:
        special_hole = min(scoring_zones, key=lambda zone: zone[0])
        logger.info(f"Special hole set to leftmost zone: {special_hole}")
        return special_hole
    except (IndexError, TypeError) as e:
        logger.error(f"Error finding special hole (invalid zone data?): {e}")
        return None


# --- UPDATED: Use INITIAL_SOUND_VOLUME ---
def initialize_sounds() -> Tuple[
    Optional[pygame.mixer.Sound],  # score_sound
    Optional[pygame.mixer.Sound],  # low_time_sound
]:
    """
    Initialize sound effects (score, low time) using filenames from constants.
    Background music is handled separately by GameState.
    Returns:
        Tuple of (score_sound, low_time_sound).
    """
    pygame.mixer.init()  # Ensure mixer is initialized
    score_sound = None
    low_time_sound = None

    try:
        # Use original filenames and constant path
        score_sound_path = os.path.join(GameConstants.SOUND_EFFECTS_PATH, "ding.wav")
        low_time_sound_path = os.path.join(
            GameConstants.SOUND_EFFECTS_PATH, "10_sec_timer.mp3"
        )

        if os.path.exists(score_sound_path):
            score_sound = pygame.mixer.Sound(score_sound_path)
            # <<< MODIFIED: Use INITIAL_SOUND_VOLUME >>>
            score_sound.set_volume(GameConstants.INITIAL_SOUND_VOLUME)
            logger.info(f"Loaded score sound: {score_sound_path}")
        else:
            logger.warning(f"Score sound file not found: {score_sound_path}")

        if os.path.exists(low_time_sound_path):
            low_time_sound = pygame.mixer.Sound(low_time_sound_path)
            # <<< MODIFIED: Use INITIAL_SOUND_VOLUME >>>
            low_time_sound.set_volume(GameConstants.INITIAL_SOUND_VOLUME)
            logger.info(f"Loaded low time warning sound: {low_time_sound_path}")
        else:
            logger.warning(
                f"Low time warning sound file not found: {low_time_sound_path}"
            )

    except pygame.error as e:
        logger.error(f"Pygame mixer initialization or sound loading failed: {e}")
    except FileNotFoundError as e:
        logger.error(f"Sound file not found during initialization: {e}")
    # <<< MODIFIED: Catch potential AttributeError here too >>>
    except AttributeError as e:
        logger.error(
            f"AttributeError during sound initialization (likely constant name change): {e}"
        )
    except Exception as e:
        logger.exception(f"Unexpected error during sound initialization: {e}")

    # Return only the effects loaded here
    return score_sound, low_time_sound


# --- END UPDATE ---


def initialize_achievements() -> List[Achievement]:
    """
    Initialize the list of achievements.
    """
    # - Keeping user's definitions
    return [
        Achievement(
            "First Score",
            "Score your first points",
            lambda gs: gs.get_current_player().score >= 100,
        ),
        Achievement(
            "High Roller",
            "Score 1000 points in one game",
            lambda gs: gs.get_current_player().score >= 1000,
        ),
        Achievement(
            "Zone Master",
            "Create 5 scoring zones",
            lambda gs: len(gs.scoring_zones) >= 5,
        ),
        Achievement(
            "Marathon",
            "Play 10 games",
            # Ensure games_played is incremented somewhere, e.g., on game reset or game over
            lambda gs: hasattr(gs.get_current_player(), "games_played")
            and gs.get_current_player().games_played >= 10,
        ),
    ]


# --- Corrected Function Signature and Implementation ---
def load_achievements(game_state: Any, filename: str) -> None:
    """
    Load achievements status from a JSON file.
    Args:
        game_state: The game state object to update achievements in.
        filename: The path to the achievements status file.
    """
    if not hasattr(game_state, "achievements") or not game_state.achievements:
        logger.warning(
            "Attempted to load achievements, but game_state.achievements is empty or missing."
        )
        return

    achievements_file = filename
    try:
        if os.path.exists(achievements_file):
            # Check file size to avoid error on empty file
            if os.path.getsize(achievements_file) > 0:
                with open(achievements_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    logger.error(
                        f"Invalid format in {achievements_file}. Expected dict."
                    )
                    return
                loaded_count = 0
                # Update the unlocked status in the game_state's list
                for achievement in game_state.achievements:
                    # Check using .get() for safety
                    if achievement.name in data and data.get(achievement.name, {}).get(
                        "unlocked"
                    ):
                        achievement.unlocked = True
                        loaded_count += 1
                logger.info(
                    f"Loaded unlock status for {loaded_count} achievements from {achievements_file}."
                )
            else:
                logger.warning(
                    f"Achievement status file '{achievements_file}' is empty. Starting fresh."
                )
        else:
            logger.info(
                f"Achievement status file '{achievements_file}' not found. Starting fresh."
            )
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load achievements from {achievements_file}: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error loading achievements: {e}")


# --- Corrected Function Signature and Implementation ---
def save_achievements(game_state: Any, filename: str) -> None:
    """
    Save achievements status to a JSON file.
    Args:
        game_state: The game state object containing the achievements list.
        filename: The path to save the achievements status file.
    """
    if not hasattr(game_state, "achievements"):
        logger.warning(
            "Attempted to save achievements, but game_state.achievements is missing."
        )
        return

    achievements_file = filename
    try:
        # Get status from the game_state's achievements list
        data = {a.name: {"unlocked": a.unlocked} for a in game_state.achievements}
        with open(achievements_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        logger.debug(f"Saved achievement status to {achievements_file}.")
    except (IOError, PermissionError) as e:
        logger.error(f"Failed to save achievements to {achievements_file}: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error saving achievements: {e}")


def load_hsv_ranges(
    filename: str = "hsv_ranges.json",
) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """
    Load HSV ranges from a JSON file.
    Returns defaults if file not found/invalid.
    """
    # - Keeping user's version, adding filename arg usage
    hsv_ranges = {  # Defaults
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

    if os.path.exists(hsv_file):
        try:
            # Check file size
            if os.path.getsize(hsv_file) > 0:
                with open(hsv_file, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                for key in hsv_ranges.keys():  # Iterate through expected keys
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
                            logger.warning(
                                f"Invalid HSV shape for '{key}' in {hsv_file}. Using default."
                            )
                    else:
                        logger.warning(
                            f"Missing/invalid format for '{key}' in {hsv_file}. Using default."
                        )
                logger.info(f"Loaded custom HSV ranges from {hsv_file}")
            else:
                logger.warning(
                    f"HSV ranges file '{hsv_file}' is empty. Using defaults."
                )

        except (
            json.JSONDecodeError,
            IOError,
            ValueError,
        ) as e:  # Added ValueError for np.array
            logger.error(
                f"Failed load/parse HSV ranges from {hsv_file}: {e}. Using defaults."
            )
        except Exception as e:
            logger.exception(
                f"Unexpected error loading HSV ranges: {e}. Using defaults."
            )
    else:
        logger.info(f"HSV ranges file '{hsv_file}' not found, using defaults.")
    return hsv_ranges


def save_hsv_ranges(
    hsv_ranges: Dict[str, Tuple[np.ndarray, np.ndarray]],
    filename: str = "hsv_ranges.json",
) -> None:
    """
    Save HSV ranges to a JSON file.
    """
    hsv_file = filename
    serializable_data = {}
    for key, (lower, upper) in hsv_ranges.items():
        if isinstance(lower, np.ndarray) and isinstance(upper, np.ndarray):
            serializable_data[key] = (lower.tolist(), upper.tolist())
        else:
            logger.warning(f"Cannot serialize non-numpy HSV for '{key}'. Skipping.")
            # Decide if you should return or continue saving what you can
            # For now, we continue saving other valid ranges
            # return # Or: raise TypeError(f"Invalid type for HSV range '{key}'")

    # Only proceed if there's data to save
    if not serializable_data:
        logger.warning("No valid HSV data to save.")
        return

    try:
        with open(hsv_file, "w", encoding="utf-8") as f:
            json.dump(serializable_data, f, indent=4)
        logger.info(f"Saved HSV ranges to {hsv_file}")
    except (IOError, PermissionError) as e:
        logger.error(f"Failed to save HSV ranges to {hsv_file}: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error saving HSV ranges: {e}")


# --- Ball State Checking Utilities ---
# Using GameConstants here instead of hardcoded values


def is_ball_at_rest(
    ball_id: int,
    ball_positions_history: Dict[int, List[Tuple[int, int]]],
    debug_mode: bool = False,
) -> bool:
    """Check if a ball has remained relatively still."""
    history = ball_positions_history.get(ball_id, [])
    history_len_needed = GameConstants.POSITION_HISTORY_LENGTH

    if len(history) < history_len_needed:
        if debug_mode:
            logger.debug(
                f"Ball {ball_id} hist too short ({len(history)}/{history_len_needed}) for rest check"
            )
        return False

    relevant_history = history[-history_len_needed:]
    start_pos = np.array(relevant_history[0])
    max_dist_sq = GameConstants.REST_THRESHOLD_DISTANCE**2

    for pos in relevant_history[1:]:
        dist_sq = np.sum((np.array(pos) - start_pos) ** 2)
        if dist_sq > max_dist_sq:
            if debug_mode:
                logger.debug(
                    f"Ball {ball_id} moved > {GameConstants.REST_THRESHOLD_DISTANCE}px (dist_sq={dist_sq:.1f}), not at rest."
                )
            return False

    if debug_mode:
        logger.debug(f"Ball {ball_id} is at rest.")
    return True


def is_ball_zone_stable(
    ball_id: int,
    current_zone: Optional[Tuple],  # Pass the zone tuple itself
    ball_zone_history: Dict[int, List[Optional[int]]],  # Stores zone IDs
    debug_mode: bool = False,
) -> bool:
    """Check if a ball has been consistently in the same zone (or None)."""
    if ball_id not in ball_zone_history:
        ball_zone_history[ball_id] = []  # Initialize if needed

    # Use object ID for zones, None otherwise. Efficient way to check if it's the *same* zone object.
    # If zone definitions change (e.g., loading), this comparison remains valid for stability check.
    current_zone_id = id(current_zone) if current_zone else None

    # Append the current zone status ID to the history
    ball_zone_history[ball_id].append(current_zone_id)

    stability_frames_needed = GameConstants.ZONE_STABILITY_FRAMES

    # Keep history length constrained
    if len(ball_zone_history[ball_id]) > stability_frames_needed:
        ball_zone_history[ball_id].pop(0)

    # Check if the history has reached the required length
    if len(ball_zone_history[ball_id]) < stability_frames_needed:
        if debug_mode:
            logger.debug(
                f"Ball {ball_id} zone hist too short ({len(ball_zone_history[ball_id])}/{stability_frames_needed}) for stability"
            )
        return False  # Not enough history yet

    # Check if all entries in the history match the *current* zone ID
    if all(zone_id == current_zone_id for zone_id in ball_zone_history[ball_id]):
        if current_zone_id is not None:  # Stable *and* in a zone
            if debug_mode:
                # Find the index of the current zone for logging if needed
                zone_idx_log = -1
                try:
                    # Requires access to the full scoring_zones list if you want the index
                    # This function doesn't have it, so log ID or maybe pass game_state?
                    # For now, just log the object ID.
                    zone_idx_log = id(current_zone)
                except:
                    pass  # Ignore errors finding index for logging
                logger.debug(f"Ball {ball_id} stable in zone ID {zone_idx_log}.")
            return True  # Stable in the zone!
        else:  # Stable outside any zone
            if debug_mode:
                logger.debug(f"Ball {ball_id} stable outside zones.")
            return False  # Stable, but not in a scoreable zone
    else:  # History contains different zone IDs (or None)
        if debug_mode:
            current_zone_idx_log = id(current_zone) if current_zone else "None"
            logger.debug(
                f"Ball {ball_id} not stable in current zone {current_zone_idx_log} (history differs)."
            )
        return False
