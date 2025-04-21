# game_state_utils.py
"""
Utility functions for the GameState class in the Whiffle Tracker project.
"""

import cv2
import logging
import pygame # --- CHANGE: Ensure pygame is imported ---
import json
import os
import numpy as np
from typing import Optional, List, Tuple, Dict, Any # Added Any

# Import constants and classes
# Added ScoringConstants, removed unused BallDetector, BallTracker
from constants import UIConstants, GameConstants, ScoringConstants
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
    special_hole = min(scoring_zones, key=lambda zone: zone[0])
    logger.info(f"Special hole set to leftmost zone: {special_hole}")
    return special_hole


# --- CHANGE: Modified Function to load and return low_time_sound ---
def initialize_sounds() -> (
    Tuple[Optional[pygame.mixer.Sound], Optional[pygame.mixer.Sound], Optional[pygame.mixer.Sound]]
):
    """
    Initialize sound effects and background music using filenames from user's code.
    Returns:
        Tuple of (score_sound, background_music, low_time_sound).
    """
    pygame.mixer.init()
    score_sound = None
    background_music = None
    low_time_sound = None # --- CHANGE: Added variable for low time sound ---

    try:
        # Use original filenames and constant path
        score_sound_path = os.path.join(
            GameConstants.SOUND_EFFECTS_PATH, "ding.wav")
        background_music_path = os.path.join(
            GameConstants.SOUND_EFFECTS_PATH, "background_music.mp3"
        )
        # --- CHANGE: Path for low time sound ---
        low_time_sound_path = os.path.join(
            GameConstants.SOUND_EFFECTS_PATH, "10_sec_timer.mp3"
        )


        if os.path.exists(score_sound_path):
            score_sound = pygame.mixer.Sound(score_sound_path)
            score_sound.set_volume(
                GameConstants.DEFAULT_SOUND_VOLUME)  # Use constant
            logger.info(f"Loaded score sound: {score_sound_path}")
        else:
            logger.warning(f"Score sound file not found: {score_sound_path}")

        if os.path.exists(background_music_path):
            background_music = pygame.mixer.Sound(background_music_path)
            background_music.set_volume(
                GameConstants.DEFAULT_MUSIC_VOLUME
            )  # Use constant
            logger.info(f"Loaded background music: {background_music_path}")
        else:
            logger.warning(
                f"Background music file not found: {background_music_path}")

        # --- CHANGE: Load low time sound ---
        if os.path.exists(low_time_sound_path):
            low_time_sound = pygame.mixer.Sound(low_time_sound_path)
            low_time_sound.set_volume(
                GameConstants.DEFAULT_SOUND_VOLUME) # Use same volume as other effects
            logger.info(f"Loaded low time warning sound: {low_time_sound_path}")
        else:
            logger.warning(f"Low time warning sound file not found: {low_time_sound_path}")
        # --- End Change ---

    except pygame.error as e:
        logger.error(
            f"Pygame mixer initialization or sound loading failed: {e}")
    except FileNotFoundError as e:
        logger.error(f"Sound file not found during initialization: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error during sound initialization: {e}")

    # --- CHANGE: Return all three sound objects ---
    return score_sound, background_music, low_time_sound


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
            lambda gs: gs.get_current_player().games_played >= 10,
        ),
    ]


# --- Corrected Function Signature and Implementation ---
def load_achievements(game_state: Any, filename: str) -> None:  # Changed signature
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

    achievements_file = filename  # Use argument
    try:
        if os.path.exists(achievements_file):
            with open(achievements_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logger.error(
                    f"Invalid format in {achievements_file}. Expected dict.")
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
            logger.info(
                f"Achievement status file '{achievements_file}' not found. Starting fresh."
            )
    except (json.JSONDecodeError, IOError) as e:
        logger.error(
            f"Failed to load achievements from {achievements_file}: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error loading achievements: {e}")


# --- Corrected Function Signature and Implementation ---
def save_achievements(game_state: Any, filename: str) -> None:  # Changed signature
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

    achievements_file = filename  # Use argument
    try:
        # Get status from the game_state's achievements list
        data = {a.name: {"unlocked": a.unlocked}
                for a in game_state.achievements}
        with open(achievements_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        logger.debug(f"Saved achievement status to {achievements_file}.")
    except (IOError, PermissionError) as e:
        logger.error(
            f"Failed to save achievements to {achievements_file}: {e}")
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
    hsv_file = filename  # Use argument

    if os.path.exists(hsv_file):
        try:
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
        except Exception as e:
            logger.error(
                f"Failed load/parse HSV ranges from {hsv_file}: {e}. Using defaults."
            )
    else:
        logger.info(f"{hsv_file} not found, using defaults.")
    return hsv_ranges


def save_hsv_ranges(
    hsv_ranges: Dict[str, Tuple[np.ndarray, np.ndarray]],
    filename: str = "hsv_ranges.json",
) -> None:
    """
    Save HSV ranges to a JSON file.
    """
    # - Keeping user's version, adding filename arg usage
    hsv_file = filename  # Use argument
    serializable_data = {}
    for key, (lower, upper) in hsv_ranges.items():
        if isinstance(lower, np.ndarray) and isinstance(upper, np.ndarray):
            serializable_data[key] = (lower.tolist(), upper.tolist())
        else:
            logger.warning(
                f"Cannot serialize non-numpy HSV for '{key}'. Skipping.")
            return
    try:
        with open(hsv_file, "w", encoding="utf-8") as f:
            json.dump(serializable_data, f, indent=4)
        logger.info(f"Saved HSV ranges to {hsv_file}")
    except Exception as e:
        logger.exception(f"Error saving HSV ranges: {e}")


# --- Ball State Checking Utilities ---
# Using GameConstants here instead of hardcoded values


def is_ball_at_rest(
    ball_id: int,
    ball_positions_history: Dict[int, List[Tuple[int, int]]],
    debug_mode: bool = False,
) -> bool:
    """Check if a ball has remained relatively still."""
    history = ball_positions_history.get(ball_id, [])
    history_len_needed = GameConstants.POSITION_HISTORY_LENGTH  # Use Constant

    if len(history) < history_len_needed:
        # - Combined debug log
        if debug_mode:
            logger.debug(
                f"Ball {ball_id} hist too short ({len(history)}/{history_len_needed}) for rest"
            )
        return False

    # Check movement within the relevant history window
    relevant_history = history[-history_len_needed:]
    start_pos = np.array(relevant_history[0])
    max_dist_sq = GameConstants.REST_THRESHOLD_DISTANCE**2  # Use Constant

    for pos in relevant_history[1:]:
        dist_sq = np.sum((np.array(pos) - start_pos) ** 2)
        if dist_sq > max_dist_sq:
            if debug_mode:
                logger.debug(
                    f"Ball {ball_id} moved > {GameConstants.REST_THRESHOLD_DISTANCE}px, not at rest."
                )
            return False

    if debug_mode:
        logger.debug(f"Ball {ball_id} is at rest.")
    return True


def is_ball_zone_stable(
    ball_id: int,
    current_zone: Optional[Tuple],
    ball_zone_history: Dict[int, List[Optional[int]]],
    debug_mode: bool = False,
) -> bool:
    """Check if a ball has been consistently in the same zone."""
    if ball_id not in ball_zone_history:
        ball_zone_history[ball_id] = []  # Initialize if needed

    current_zone_id = id(current_zone) if current_zone else None

    # --- Corrected Logic ---
    # Always append the current zone status to the history
    ball_zone_history[ball_id].append(current_zone_id)
    # --- End Corrected Logic ---

    stability_frames_needed = (
        GameConstants.ZONE_STABILITY_FRAMES
    )  # Use Constant (e.g., 5)

    # Keep history length constrained efficiently - Remove oldest entry if > needed
    if len(ball_zone_history[ball_id]) > stability_frames_needed:
        ball_zone_history[ball_id].pop(0)

    # Check if the history has reached the required length
    if len(ball_zone_history[ball_id]) < stability_frames_needed:
        if debug_mode:
            logger.debug(
                f"Ball {ball_id} zone hist too short ({len(ball_zone_history[ball_id])}/{stability_frames_needed})"
            )
        return False  # Not enough history yet

    # Check if all entries in the (now correctly sized) history match the *current* zone ID
    if all(zone_id == current_zone_id for zone_id in ball_zone_history[ball_id]):
        if current_zone_id is not None:  # Stable *and* in a zone
            if debug_mode:
                logger.debug(
                    f"Ball {ball_id} stable in zone {current_zone_id}.")
            return True  # Stable in the zone!
        else:  # Stable outside any zone
            if debug_mode:
                logger.debug(f"Ball {ball_id} stable outside zones.")
            return False  # Stable, but not in a scoreable zone
    # History contains different zone IDs (or None) - ball was moving between zones or just entered
    else:
        if debug_mode:
            logger.debug(
                f"Ball {ball_id} not stable in current zone {current_zone_id}."
            )
        # --- Indentation Fixed Here ---
        return False