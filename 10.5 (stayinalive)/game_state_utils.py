"""
Utility functions for the GameState class in the Whiffle Tracker project.
"""

import cv2
import logging
import pygame
import json
import os
import numpy as np
from typing import Optional, List, Tuple, Dict, Any # Added Any

# Import constants and classes
# Added ScoringConstants, removed unused BallDetector, BallTracker
from constants import UIConstants, GameConstants, ScoringConstants # [source: 47]
from scoring import is_in_scoring_zone # [source: 47]
from achievement import Achievement # [source: 47]

logger = logging.getLogger(__name__) # [source: 47]

def set_special_hole(scoring_zones: List[Tuple[int, int, int, int, int]]) -> Optional[Tuple[int, int, int, int, int]]: # [source: 47]
    """
    Identify the leftmost scoring zone as the special hole.
    """ # [source: 48]
    if not scoring_zones: # [source: 48]
        logger.info("No scoring zones available, special hole not set") # [source: 48]
        return None # [source: 48]
    special_hole = min(scoring_zones, key=lambda zone: zone[0]) # [source: 48]
    logger.info(f"Special hole set to leftmost zone: {special_hole}") # [source: 48]
    return special_hole # [source: 48]

# --- Reconciled Function ---
def initialize_sounds() -> Tuple[Optional[pygame.mixer.Sound], Optional[pygame.mixer.Sound]]: # [source: 114]
    """
    Initialize sound effects and background music using filenames from user's code.
    Returns:
        Tuple of (score_sound, background_music).
    """ # [source: 115]
    # [source: 116]
    pygame.mixer.init() # [source: 116]
    score_sound = None # [source: 116]
    background_music = None # [source: 116]
    # Removed boolean flags, handled in game_state now

    try: # [source: 116]
        # Use original filenames and constant path
        score_sound_path = os.path.join(GameConstants.SOUND_EFFECTS_PATH, "ding.wav") # [source: 116] # Uses user's filename
        background_music_path = os.path.join(GameConstants.SOUND_EFFECTS_PATH, "background_music.mp3") # [source: 117] # Uses user's filename and type

        if os.path.exists(score_sound_path): # [source: 116]
            score_sound = pygame.mixer.Sound(score_sound_path) # [source: 116]
            score_sound.set_volume(GameConstants.DEFAULT_SOUND_VOLUME) # Use constant # [source: 116]
            logger.info(f"Loaded score sound: {score_sound_path}") # [source: 117]
        else: # [source: 117]
            logger.warning(f"Score sound file not found: {score_sound_path}") # [source: 117]

        # Removed achievement sound loading logic

        if os.path.exists(background_music_path): # [source: 117]
            background_music = pygame.mixer.Sound(background_music_path) # [source: 117]
            background_music.set_volume(GameConstants.DEFAULT_MUSIC_VOLUME) # Use constant # [source: 117]
            logger.info(f"Loaded background music: {background_music_path}") # [source: 117]
        else: # [source: 117]
            logger.warning(f"Background music file not found: {background_music_path}") # [source: 117]

    except pygame.error as e: # [source: 117]
        logger.error(f"Pygame mixer initialization or sound loading failed: {e}") # [source: 117]
    except FileNotFoundError as e: # [source: 53]
         logger.error(f"Sound file not found during initialization: {e}") # [source: 53]
    except Exception as e: # [source: 53]
         logger.exception(f"Unexpected error during sound initialization: {e}") # [source: 53]

    # Return only the two expected sound objects
    return score_sound, background_music # [source: 117]


# --- Removed initialize_balls_in_zone as it's complex and likely redundant ---
# def initialize_balls_in_zone(...) -> ...: ...


def initialize_achievements() -> List[Achievement]: # [source: 129]
    """
    Initialize the list of achievements.
    """ # [source: 130]
    # [source: 131] - Keeping user's definitions
    return [ # [source: 131]
        Achievement("First Score", "Score your first points", lambda gs: gs.get_current_player().score >= 100), # [source: 131]
        Achievement("High Roller", "Score 1000 points in one game", lambda gs: gs.get_current_player().score >= 1000), # [source: 131]
        Achievement("Zone Master", "Create 5 scoring zones", lambda gs: len(gs.scoring_zones) >= 5), # [source: 131]
        Achievement("Marathon", "Play 10 games", lambda gs: gs.get_current_player().games_played >= 10) # [source: 131]
    ] # [source: 131]

# --- Corrected Function Signature and Implementation ---
def load_achievements(game_state: Any, filename: str) -> None: # [source: 131] # Changed signature
    """
    Load achievements status from a JSON file.
    Args:
        game_state: The game state object to update achievements in.
        filename: The path to the achievements status file.
    """ # [source: 132]
    # [source: 133]
    if not hasattr(game_state, 'achievements') or not game_state.achievements: # [source: 56]
         logger.warning("Attempted to load achievements, but game_state.achievements is empty or missing.") # [source: 57]
         return # [source: 57]

    achievements_file = filename # Use argument # [source: 57]
    try: # [source: 57]
        if os.path.exists(achievements_file): # [source: 57]
            with open(achievements_file, "r", encoding='utf-8') as f: # [source: 57]
                data = json.load(f) # [source: 57]
            if not isinstance(data, dict): # [source: 58]
                logger.error(f"Invalid format in {achievements_file}. Expected dict.") # [source: 59]
                return # [source: 59]
            loaded_count = 0 # [source: 59]
            # Update the unlocked status in the game_state's list
            for achievement in game_state.achievements: # [source: 59]
                # Check using .get() for safety
                if achievement.name in data and data.get(achievement.name, {}).get("unlocked"): # [source: 60]
                    achievement.unlocked = True # [source: 60]
                    loaded_count += 1 # [source: 60]
            logger.info(f"Loaded unlock status for {loaded_count} achievements from {achievements_file}.") # [source: 60]
        else: # [source: 60]
            logger.info(f"Achievement status file '{achievements_file}' not found. Starting fresh.") # [source: 61]
    except (json.JSONDecodeError, IOError) as e: # [source: 61]
        logger.error(f"Failed to load achievements from {achievements_file}: {e}") # [source: 61]
    except Exception as e: # [source: 61]
        logger.exception(f"Unexpected error loading achievements: {e}") # [source: 61]


# --- Corrected Function Signature and Implementation ---
def save_achievements(game_state: Any, filename: str) -> None: # [source: 134] # Changed signature
    """
    Save achievements status to a JSON file.
    Args:
        game_state: The game state object containing the achievements list.
        filename: The path to save the achievements status file.
    """ # [source: 135]
    # [source: 136]
    if not hasattr(game_state, 'achievements'): # [source: 62]
         logger.warning("Attempted to save achievements, but game_state.achievements is missing.") # [source: 62]
         return # [source: 62]

    achievements_file = filename # Use argument # [source: 62]
    try: # [source: 63]
        # Get status from the game_state's achievements list
        data = {a.name: {"unlocked": a.unlocked} for a in game_state.achievements} # [source: 63]
        with open(achievements_file, "w", encoding='utf-8') as f: # [source: 64]
            json.dump(data, f, indent=4) # [source: 64]
        logger.debug(f"Saved achievement status to {achievements_file}.") # [source: 64]
    except (IOError, PermissionError) as e: # [source: 64]
        logger.error(f"Failed to save achievements to {achievements_file}: {e}") # [source: 64]
    except Exception as e: # [source: 64]
        logger.exception(f"Unexpected error saving achievements: {e}") # [source: 64]


def load_hsv_ranges(filename: str = "hsv_ranges.json") -> Dict[str, Tuple[np.ndarray, np.ndarray]]: # [source: 136]
    """
    Load HSV ranges from a JSON file. Returns defaults if file not found/invalid.
    """ # [source: 137]
    # [source: 138] - Keeping user's version, adding filename arg usage
    hsv_ranges = { # [source: 138] # Defaults
        "white": (np.array([0, 0, 180], dtype=np.uint8), np.array([179, 30, 255], dtype=np.uint8)), # [source: 67]
        "red1": (np.array([0, 100, 100], dtype=np.uint8), np.array([10, 255, 255], dtype=np.uint8)), # [source: 67]
        "red2": (np.array([160, 100, 100], dtype=np.uint8), np.array([179, 255, 255], dtype=np.uint8)) # [source: 67]
    } # [source: 67]
    hsv_file = filename # Use argument # [source: 138]

    if os.path.exists(hsv_file): # [source: 138]
        try: # [source: 139]
            with open(hsv_file, "r", encoding='utf-8') as f: loaded_data = json.load(f) # [source: 139]
            for key in hsv_ranges.keys(): # Iterate through expected keys # [source: 139]
                if key in loaded_data and isinstance(loaded_data[key], list) and len(loaded_data[key]) == 2: # [source: 69]
                    lower = np.array(loaded_data[key][0], dtype=np.uint8) # [source: 69]
                    upper = np.array(loaded_data[key][1], dtype=np.uint8) # [source: 69]
                    if lower.shape == (3,) and upper.shape == (3,): hsv_ranges[key] = (lower, upper) # [source: 70]
                    else: logger.warning(f"Invalid HSV shape for '{key}' in {hsv_file}. Using default.") # [source: 70]
                else: logger.warning(f"Missing/invalid format for '{key}' in {hsv_file}. Using default.") # [source: 71]
            logger.info(f"Loaded custom HSV ranges from {hsv_file}") # [source: 71]
        except Exception as e: logger.error(f"Failed load/parse HSV ranges from {hsv_file}: {e}. Using defaults.") # [source: 72]
    else: logger.info(f"{hsv_file} not found, using defaults.") # [source: 72]
    return hsv_ranges # [source: 72]


def save_hsv_ranges(hsv_ranges: Dict[str, Tuple[np.ndarray, np.ndarray]], filename: str = "hsv_ranges.json") -> None: # [source: 142]
    """
    Save HSV ranges to a JSON file.
    """ # [source: 143]
    # [source: 144-148] - Keeping user's version, adding filename arg usage
    hsv_file = filename # Use argument # [source: 148]
    serializable_data = {} # [source: 148]
    for key, (lower, upper) in hsv_ranges.items(): # [source: 148]
        if isinstance(lower, np.ndarray) and isinstance(upper, np.ndarray): serializable_data[key] = (lower.tolist(), upper.tolist()) # [source: 148]
        else: logger.warning(f"Cannot serialize non-numpy HSV for '{key}'. Skipping."); return # [source: 75]
    try: # [source: 75]
        with open(hsv_file, "w", encoding='utf-8') as f: json.dump(serializable_data, f, indent=4) # [source: 75]
        logger.info(f"Saved HSV ranges to {hsv_file}") # [source: 75]
    except Exception as e: logger.exception(f"Error saving HSV ranges: {e}") # [source: 75]


# --- Ball State Checking Utilities ---
# Using GameConstants here instead of hardcoded values

def is_ball_at_rest(ball_id: int, ball_positions_history: Dict[int, List[Tuple[int, int]]], debug_mode: bool = False) -> bool: # [source: 150]
    """Check if a ball has remained relatively still.""" # [source: 151]
    # [source: 152-154]
    history = ball_positions_history.get(ball_id, []) # [source: 76]
    history_len_needed = GameConstants.POSITION_HISTORY_LENGTH # Use Constant # [source: 76]

    if len(history) < history_len_needed: # [source: 76]
        # [source: 155] - Combined debug log
        if debug_mode: logger.debug(f"Ball {ball_id} hist too short ({len(history)}/{history_len_needed}) for rest") # [source: 76]
        return False # [source: 76]

    # Check movement within the relevant history window
    relevant_history = history[-history_len_needed:] # [source: 76]
    start_pos = np.array(relevant_history[0]) # [source: 77]
    max_dist_sq = GameConstants.REST_THRESHOLD_DISTANCE ** 2 # Use Constant # [source: 77]

    for pos in relevant_history[1:]: # [source: 77]
        dist_sq = np.sum((np.array(pos) - start_pos)**2) # [source: 77]
        if dist_sq > max_dist_sq: # [source: 77]
            if debug_mode: logger.debug(f"Ball {ball_id} moved > {GameConstants.REST_THRESHOLD_DISTANCE}px, not at rest.") # [source: 77]
            return False # [source: 77]

    if debug_mode: logger.debug(f"Ball {ball_id} is at rest.") # [source: 77]
    return True # [source: 77]


def is_ball_zone_stable(ball_id: int, current_zone: Optional[Tuple], ball_zone_history: Dict[int, List[Optional[int]]], debug_mode: bool = False) -> bool: # [source: 156]
    """Check if a ball has been consistently in the same zone.""" # [source: 157]
    # [source: 158-161]
    if ball_id not in ball_zone_history: ball_zone_history[ball_id] = [] # [source: 78]

    current_zone_id = id(current_zone) if current_zone else None # [source: 78]
    # Only append if different from last entry to avoid filling history unnecessarily
    if not ball_zone_history[ball_id] or ball_zone_history[ball_id][-1] != current_zone_id: # [source: 78]
         ball_zone_history[ball_id].append(current_zone_id) # [source: 78]

    stability_frames_needed = GameConstants.ZONE_STABILITY_FRAMES # Use Constant # [source: 78]
    # Keep history length constrained efficiently
    if len(ball_zone_history[ball_id]) > stability_frames_needed: ball_zone_history[ball_id].pop(0) # [source: 79]

    if len(ball_zone_history[ball_id]) < stability_frames_needed: # [source: 79]
        if debug_mode: logger.debug(f"Ball {ball_id} zone hist too short ({len(ball_zone_history[ball_id])}/{stability_frames_needed})") # [source: 79]
        return False # [source: 79]

    # Check if all entries in history match the *current* zone ID
    if all(zone_id == current_zone_id for zone_id in ball_zone_history[ball_id]): # [source: 79]
        if current_zone_id is not None: # Stable *and* in a zone # [source: 79]
            if debug_mode: logger.debug(f"Ball {ball_id} stable in zone {current_zone_id}.") # [source: 80]
            return True # [source: 80]
        else: # Stable outside any zone # [source: 80]
             if debug_mode: logger.debug(f"Ball {ball_id} stable outside zones.") # [source: 80]
             return False # [source: 80]
    else: # [source: 80]
        if debug_mode: logger.debug(f"Ball {ball_id} not stable in current zone {current_zone_id}.") # [source: 80]
        return False # [source: 81]