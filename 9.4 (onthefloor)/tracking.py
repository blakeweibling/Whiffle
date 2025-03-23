"""
Ball tracking for the Whiffle Tracker project.

This module provides functions to track balls across frames by assigning consistent IDs.
"""

import numpy as np
from typing import List, Tuple, Dict
import logging

from constants import TRACKING_DISTANCE_THRESHOLD, SCORED_DISTANCE_THRESHOLD, MAX_AGE_FRAMES

# Use existing logger
logger = logging.getLogger(__name__)

def _match_balls(
    new_balls: List[Tuple[int, int, float]],
    tracked_balls: List[Tuple[int, int, float, int, int]],
    distance_threshold: float
) -> Tuple[List[Tuple[int, int, float, int]], List[int]]:
    """
    Match new balls to existing tracked balls based on proximity.

    Args:
        new_balls: List of new balls as (x, y, radius) tuples.
        tracked_balls: List of tracked balls as (x, y, radius, ball_id, age) tuples.
        distance_threshold: Maximum distance for matching balls.

    Returns:
        Tuple of (matched_balls, used_indices), where matched_balls is a list of
        (x, y, radius, ball_id) tuples for matched balls, and used_indices is a list
        of indices of new balls that were matched.
    """
    matched_balls: List[Tuple[int, int, float, int]] = []
    used_indices: List[int] = []

    for i, (new_x, new_y, radius) in enumerate(new_balls):
        min_dist = float('inf')
        closest_ball_idx = None

        for j, (x, y, _, ball_id, _) in enumerate(tracked_balls):
            dist_squared = (new_x - x) ** 2 + (new_y - y) ** 2
            if dist_squared < min_dist and dist_squared < distance_threshold ** 2:
                min_dist = dist_squared
                closest_ball_idx = j

        if closest_ball_idx is not None:
            _, _, _, ball_id, _ = tracked_balls[closest_ball_idx]
            matched_balls.append((new_x, new_y, radius, ball_id))
            used_indices.append(i)
            tracked_balls[closest_ball_idx] = (new_x, new_y, radius, ball_id, tracked_balls[closest_ball_idx][4])
            logger.debug(f"Updated ball ID {ball_id} at ({new_x}, {new_y})")

    return matched_balls, used_indices

def track_balls(
    new_balls: List[Tuple[int, int, float]],
    tracked_balls: List[Tuple[int, int, float, int, int]],
    next_ball_id: int,
    frame_count: int,
    scored_positions: Dict[Tuple[int, int], int],
    debug_mode: bool = False
) -> Tuple[List[Tuple[int, int, float, int]], int]:
    """
    Track balls across frames by assigning consistent IDs.

    Args:
        new_balls: List of newly detected balls as (x, y, radius) tuples.
        tracked_balls: List of currently tracked balls as (x, y, radius, ball_id, age) tuples.
        next_ball_id: Next available ball ID to assign.
        frame_count: Current frame number for age tracking.
        scored_positions: Dictionary of (x, y) positions that have already scored, mapping to ball IDs.
        debug_mode: If True, log debug information.

    Returns:
        Tuple of (tracked_detected_balls, next_ball_id), where tracked_detected_balls is a list
        of (x, y, radius, ball_id) tuples for the current frame, and next_ball_id is the updated
        next available ball ID.
    """
    # Remove old balls
    tracked_balls[:] = [ball for ball in tracked_balls if frame_count - ball[4] < MAX_AGE_FRAMES]

    # Match new balls to existing tracked balls
    matched_balls, used_indices = _match_balls(new_balls, tracked_balls, TRACKING_DISTANCE_THRESHOLD)
    tracked_detected_balls = matched_balls

    # Add unmatched new balls
    for i, (new_x, new_y, radius) in enumerate(new_balls):
        if i in used_indices:
            continue

        # Check if this position has been scored recently
        scored_recently = False
        for (sx, sy), sid in scored_positions.items():
            dist_squared = (new_x - sx) ** 2 + (new_y - sy) ** 2
            if dist_squared < SCORED_DISTANCE_THRESHOLD ** 2:
                scored_recently = True
                break

        if not scored_recently:
            tracked_balls.append((new_x, new_y, radius, next_ball_id, frame_count))
            tracked_detected_balls.append((new_x, new_y, radius, next_ball_id))
            if debug_mode:
                logger.debug(f"New ball ID {next_ball_id} at ({new_x}, {new_y})")
            next_ball_id += 1

    # Log current tracked balls
    if debug_mode:
        logger.debug(f"Current tracked balls: {[(x, y, radius, ball_id) for x, y, radius, ball_id in tracked_detected_balls]}")

    return tracked_detected_balls, next_ball_id