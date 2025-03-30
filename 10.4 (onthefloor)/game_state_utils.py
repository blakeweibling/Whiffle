"""
Utility functions for the GameState class in the Whiffle Tracker project.
"""

import cv2
import logging
import pygame
import json
import os
import numpy as np
from typing import Optional, List, Tuple, Dict

from constants import UIConstants, GameConstants
from detection import BallDetector
from tracking import BallTracker
from scoring import is_in_scoring_zone  # Added missing import
from achievement import Achievement

logger = logging.getLogger(__name__)

def set_special_hole(scoring_zones: List[Tuple[int, int, int, int, int]]) -> Optional[Tuple[int, int, int, int, int]]:
    """
    Identify the leftmost scoring zone as the special hole.

    Args:
        scoring_zones: List of scoring zones, each as (x, y, width, height, points).

    Returns:
        The special hole as (x, y, width, height, points), or None if no zones are available.
    """
    if not scoring_zones:
        logger.info("No scoring zones available, special hole not set")
        return None

    # Find the leftmost zone (lowest x-coordinate)
    special_hole = min(scoring_zones, key=lambda zone: zone[0])
    logger.info(f"Special hole set to leftmost zone: {special_hole}")
    return special_hole

def initialize_sounds() -> Tuple[Optional[pygame.mixer.Sound], Optional[pygame.mixer.Sound], bool, bool]:
    """
    Initialize sound effects and background music.

    Returns:
        Tuple of (score_sound, background_music, game_sounds_on, background_music_on).
    """
    pygame.mixer.init()
    score_sound = None
    background_music = None
    game_sounds_on = True
    background_music_on = True

    try:
        score_sound = pygame.mixer.Sound("ding.wav")
    except pygame.error as e:
        logger.error(f"Failed to load score sound (ding.wav): {e}")
        game_sounds_on = False

    try:
        background_music = pygame.mixer.Sound("background_music.mp3")
        background_music.set_volume(GameConstants.DEFAULT_MUSIC_VOLUME)
    except pygame.error as e:
        logger.error(f"Failed to load background music (background_music.mp3): {e}")
        background_music_on = False

    return score_sound, background_music, game_sounds_on, background_music_on

def initialize_balls_in_zone(
    camera_available: bool,
    cap: Optional[cv2.VideoCapture],
    static_frame: Optional[np.ndarray],
    frame_count: int,
    scoring_zones: List[Tuple[int, int, int, int, int]],
    ball_tracking_on: bool,
    tracked_balls: List[Tuple[int, int, float, int, int, str]],
    next_ball_id: int,
    scored_positions: Dict[Tuple[int, int], int],
    debug_mode: bool,
    balls_in_zone: Dict[int, Optional[Tuple[int, int, int, int, int]]],
    ball_states: Dict[int, str],
    previous_ball_states: Dict[int, str]
) -> Tuple[List[Tuple[int, int, float, int, int, str]], int]:
    """
    Initialize the balls_in_zone dictionary by detecting balls in the initial frame.

    Args:
        camera_available: Whether the camera is available.
        cap: The video capture object.
        static_frame: The static frame to use if the camera is unavailable.
        frame_count: Current frame number.
        scoring_zones: List of scoring zones.
        ball_tracking_on: Whether ball tracking is enabled.
        tracked_balls: List of currently tracked balls.
        next_ball_id: Next available ball ID.
        scored_positions: Dictionary of scored positions.
        debug_mode: Whether to enable debug logging.
        balls_in_zone: Dictionary to store balls in zones.
        ball_states: Dictionary to store ball states.
        previous_ball_states: Dictionary to store previous ball states.

    Returns:
        Tuple of (updated tracked_balls, updated next_ball_id).
    """
    if not ball_tracking_on:
        logger.info("Ball tracking is disabled, skipping initial ball detection")
        return tracked_balls, next_ball_id

    if camera_available:
        ret, frame = cap.read()
        if not ret:
            logger.error("Failed to read initial frame for ball initialization")
            return tracked_balls, next_ball_id
    else:
        frame = static_frame
        logger.info("Using static frame for ball initialization")

    detector = BallDetector()
    white_balls, red_balls, half_balls = detector.detect_all_balls(
        frame, frame_count, None, scoring_zones=scoring_zones, debug_mode=debug_mode
    )
    tracker = BallTracker()
    tracked_detected_balls, next_ball_id = tracker.track_balls(
        white_balls, red_balls, half_balls, tracked_balls, next_ball_id,
        frame_count, scored_positions, debug_mode
    )
    tracked_balls = [(x, y, radius, ball_id, frame_count, ball_type)
                     for x, y, radius, ball_id, ball_type in tracked_detected_balls]
    for x, y, radius, ball_id, _, ball_type in tracked_balls:
        ball = (x, y, radius, ball_id)
        for zone in scoring_zones:
            if is_in_scoring_zone(ball, zone):
                balls_in_zone[ball_id] = zone
                ball_states[ball_id] = "in_hole"
                previous_ball_states[ball_id] = "on_playfield"  # Allow scoring on transition
                if debug_mode:
                    logger.info(f"Ball ID {ball_id} at ({x}, {y}) already in zone {zone} at startup")
                break
        if ball_id not in balls_in_zone:
            balls_in_zone[ball_id] = None
            ball_states[ball_id] = "on_playfield"
            previous_ball_states[ball_id] = "on_playfield"
    if debug_mode:
        logger.debug(f"Initialized balls in zones: {balls_in_zone}")

    return tracked_balls, next_ball_id

def initialize_achievements() -> List[Achievement]:
    """
    Initialize the list of achievements.

    Returns:
        List of Achievement objects.
    """
    return [
        Achievement("First Score", "Score your first points", lambda gs: gs.get_current_player().score >= 100),
        Achievement("High Roller", "Score 1000 points in one game", lambda gs: gs.get_current_player().score >= 1000),
        Achievement("Zone Master", "Create 5 scoring zones", lambda gs: len(gs.scoring_zones) >= 5),
        Achievement("Marathon", "Play 10 games", lambda gs: gs.get_current_player().games_played >= 10)
    ]

def load_achievements(achievements: List[Achievement]) -> None:
    """
    Load achievements from a JSON file.

    Args:
        achievements: List of Achievement objects to update.
    """
    try:
        if os.path.exists("achievements.json"):
            with open("achievements.json", "r", encoding='utf-8') as f:
                data = json.load(f)
                for achievement in achievements:
                    if achievement.name in data and data[achievement.name]["unlocked"]:
                        achievement.unlocked = True
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load achievements: {e}")

def save_achievements(achievements: List[Achievement]) -> None:
    """
    Save achievements to a JSON file.

    Args:
        achievements: List of Achievement objects to save.
    """
    try:
        data = {a.name: {"unlocked": a.unlocked} for a in achievements}
        with open("achievements.json", "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except (IOError, PermissionError) as e:
        logger.error(f"Failed to save achievements: {e}")

def load_hsv_ranges() -> Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int], bool]:
    """
    Load HSV ranges from a JSON file.

    Returns:
        Tuple of (white_hsv_min, white_hsv_max, red_hsv_min, red_hsv_max, red_hsv_min2, red_hsv_max2, red_hsv_calibrated).
    """
    white_hsv_min = (0, 0, 100)
    white_hsv_max = (179, 100, 255)
    red_hsv_min = (0, 100, 100)
    red_hsv_max = (10, 255, 255)
    red_hsv_min2 = (170, 100, 100)
    red_hsv_max2 = (179, 255, 255)
    red_hsv_calibrated = False

    hsv_file = "hsv_ranges.json"
    if os.path.exists(hsv_file):
        try:
            with open(hsv_file, "r", encoding='utf-8') as f:
                data = json.load(f)
                if "white_hsv_min" in data and "white_hsv_max" in data:
                    white_hsv_min = tuple(data["white_hsv_min"])
                    white_hsv_max = tuple(data["white_hsv_max"])
                    logger.info(f"Loaded white ball HSV ranges: min={white_hsv_min}, max={white_hsv_max}")
                if all(k in data for k in ["red_hsv_min", "red_hsv_max", "red_hsv_min2", "red_hsv_max2"]):
                    red_hsv_min = tuple(data["red_hsv_min"])
                    red_hsv_max = tuple(data["red_hsv_max"])
                    red_hsv_min2 = tuple(data["red_hsv_min2"])
                    red_hsv_max2 = tuple(data["red_hsv_max2"])
                    red_hsv_calibrated = True
                    logger.info(f"Loaded red ball HSV ranges: min={red_hsv_min}, max={red_hsv_max}, "
                                f"min2={red_hsv_min2}, max2={red_hsv_max2}")
        except (json.JSONDecodeError, IOError, KeyError) as e:
            logger.error(f"Failed to load HSV ranges from {hsv_file}: {e}")
    else:
        logger.info(f"{hsv_file} does not exist, using default HSV ranges")

    return white_hsv_min, white_hsv_max, red_hsv_min, red_hsv_max, red_hsv_min2, red_hsv_max2, red_hsv_calibrated

def save_hsv_ranges(
    white_hsv_min: Tuple[int, int, int],
    white_hsv_max: Tuple[int, int, int],
    red_hsv_min: Tuple[int, int, int],
    red_hsv_max: Tuple[int, int, int],
    red_hsv_min2: Tuple[int, int, int],
    red_hsv_max2: Tuple[int, int, int]
) -> bool:
    """
    Save HSV ranges to a JSON file.

    Args:
        white_hsv_min: Minimum HSV values for white balls.
        white_hsv_max: Maximum HSV values for white balls.
        red_hsv_min: Minimum HSV values for red balls (first range).
        red_hsv_max: Maximum HSV values for red balls (first range).
        red_hsv_min2: Minimum HSV values for red balls (second range).
        red_hsv_max2: Maximum HSV values for red balls (second range).

    Returns:
        bool: True if saved successfully, False otherwise.
    """
    hsv_file = "hsv_ranges.json"
    data = {
        "white_hsv_min": [int(val) for val in white_hsv_min],
        "white_hsv_max": [int(val) for val in white_hsv_max],
        "red_hsv_min": [int(val) for val in red_hsv_min],
        "red_hsv_max": [int(val) for val in red_hsv_max],
        "red_hsv_min2": [int(val) for val in red_hsv_min2],
        "red_hsv_max2": [int(val) for val in red_hsv_max2]
    }
    try:
        with open(hsv_file, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        logger.info(f"Saved HSV ranges to {hsv_file}")
        return True
    except (IOError, PermissionError) as e:
        logger.error(f"Failed to save HSV ranges to {hsv_file}: {e}")
        return False

def is_ball_at_rest(
    ball_id: int,
    x: int,
    y: int,
    ball_positions_history: Dict[int, List[Tuple[int, int]]],
    debug_mode: bool = False
) -> bool:
    """
    Determine if a ball has come to rest by checking its movement over recent frames.

    Args:
        ball_id: The ID of the ball to check.
        x: Current x-coordinate of the ball.
        y: Current y-coordinate of the ball.
        ball_positions_history: Dictionary tracking ball positions over recent frames.
        debug_mode: Whether to enable debug logging.

    Returns:
        bool: True if the ball is at rest, False otherwise.
    """
    # Constants for movement tracking
    HISTORY_LENGTH = 5  # Number of frames to track
    MOVEMENT_THRESHOLD = 5.0  # Maximum distance (in pixels) to consider the ball at rest

    # Update the position history for this ball
    if ball_id not in ball_positions_history:
        ball_positions_history[ball_id] = []
    ball_positions_history[ball_id].append((x, y))

    # Keep only the last HISTORY_LENGTH positions
    if len(ball_positions_history[ball_id]) > HISTORY_LENGTH:
        ball_positions_history[ball_id] = ball_positions_history[ball_id][-HISTORY_LENGTH:]

    # If we don't have enough history to determine movement, assume the ball is not at rest
    if len(ball_positions_history[ball_id]) < HISTORY_LENGTH:
        if debug_mode:
            logger.debug(f"Ball ID {ball_id} at ({x}, {y}) does not have enough history ({len(ball_positions_history[ball_id])}/{HISTORY_LENGTH}) to determine if at rest")
        return False

    # Calculate the total movement over the history
    positions = ball_positions_history[ball_id]
    first_x, first_y = positions[0]
    last_x, last_y = positions[-1]
    distance = np.sqrt((last_x - first_x) ** 2 + (last_y - first_y) ** 2)

    if debug_mode:
        logger.debug(f"Ball ID {ball_id} movement over {HISTORY_LENGTH} frames: {distance:.2f} pixels (threshold: {MOVEMENT_THRESHOLD})")

    return distance < MOVEMENT_THRESHOLD

def is_ball_zone_stable(
    ball_id: int,
    current_zone: Optional[Tuple[int, int, int, int, int]],
    ball_zone_history: Dict[int, List[Optional[int]]],
    debug_mode: bool = False
) -> bool:
    """
    Determine if a ball has been in the same zone for a sufficient number of frames to be considered stable.

    Args:
        ball_id: The ID of the ball to check.
        current_zone: The current zone the ball is in (or None if not in a zone).
        ball_zone_history: Dictionary tracking the zones a ball has been in over recent frames.
        debug_mode: Whether to enable debug logging.

    Returns:
        bool: True if the ball has been in the same zone for enough frames, False otherwise.
    """
    # Constants for zone stability tracking
    ZONE_STABILITY_FRAMES = 10  # Number of consecutive frames the ball must be in the same zone

    # Update the zone history for this ball
    if ball_id not in ball_zone_history:
        ball_zone_history[ball_id] = []
    current_zone_id = id(current_zone) if current_zone else None
    ball_zone_history[ball_id].append(current_zone_id)

    # Keep only the last ZONE_STABILITY_FRAMES entries
    if len(ball_zone_history[ball_id]) > ZONE_STABILITY_FRAMES:
        ball_zone_history[ball_id] = ball_zone_history[ball_id][-ZONE_STABILITY_FRAMES:]

    # If we don't have enough history, the ball is not stable yet
    if len(ball_zone_history[ball_id]) < ZONE_STABILITY_FRAMES:
        if debug_mode:
            logger.debug(f"Ball ID {ball_id} zone history too short ({len(ball_zone_history[ball_id])}/{ZONE_STABILITY_FRAMES}) to determine stability")
        return False

    # Check if the ball has been in the same zone for the last ZONE_STABILITY_FRAMES
    zone_history = ball_zone_history[ball_id]
    if all(zone_id == current_zone_id for zone_id in zone_history):
        if debug_mode:
            logger.debug(f"Ball ID {ball_id} has been stable in zone {current_zone_id} for {ZONE_STABILITY_FRAMES} frames")
        return True
    else:
        if debug_mode:
            logger.debug(f"Ball ID {ball_id} zone history: {zone_history}, not stable in current zone {current_zone_id}")
        return False