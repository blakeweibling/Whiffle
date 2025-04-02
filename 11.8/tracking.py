"""
Ball tracking for the Whiffle Tracker project.

This module provides functions to track balls across frames by assigning consistent IDs.
"""

import numpy as np
from typing import List, Tuple, Dict
import logging

try:
    from scipy.spatial import KDTree  # Optional, requires scipy installation

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

from game_constants import TrackingConstants

# Use existing logger
logger = logging.getLogger(__name__)


def _filter_old_balls(
    tracked_balls: List[Tuple[int, int, float, int, int, str]], frame_count: int
) -> None:
    """
    Remove balls that have exceeded the maximum age from tracked_balls in-place.

    Args:
        tracked_balls: List of tracked balls as (x, y, radius, ball_id, age, ball_type) tuples.
        frame_count: Current frame number for age comparison.
    """
    initial_count = len(tracked_balls)
    tracked_balls[:] = [
        ball
        for ball in tracked_balls
        if frame_count - ball[4] < TrackingConstants.MAX_AGE_FRAMES
    ]
    dropped = initial_count - len(tracked_balls)
    if dropped > 0:
        logger.info(
            f"Dropped {dropped} balls due to age exceeding {TrackingConstants.MAX_AGE_FRAMES} frames"
        )


def _match_balls(
    new_balls: List[Tuple[int, int, float, str]],
    tracked_balls: List[Tuple[int, int, float, int, int, str]],
    distance_threshold: float,
    debug_mode: bool = False,
) -> Tuple[List[Tuple[int, int, float, int, str]], List[int]]:
    """
    Match new balls to existing tracked balls based on proximity.

    Args:
        new_balls: List of new balls as (x, y, radius, ball_type) tuples.
        tracked_balls: List of tracked balls as (x, y, radius, ball_id, age, ball_type) tuples.
        distance_threshold: Maximum distance for matching balls.
        debug_mode: If True, log debug information.

    Returns:
        Tuple of (matched_balls, matched_new_indices), where matched_balls is a list of
        (x, y, radius, ball_id, ball_type) tuples for matched balls, and matched_new_indices is a list
        of indices of new balls that were matched.
    """
    matched_balls: List[Tuple[int, int, float, int, str]] = []
    matched_new_indices: List[int] = []
    # Track which tracked balls have been matched
    used_tracked_indices: List[int] = []

    if not new_balls or not tracked_balls:
        logger.debug("No new balls or tracked balls to match")
        return matched_balls, matched_new_indices

    if SCIPY_AVAILABLE:
        # Optimized KD-tree approach
        logger.debug("Using KD-tree for ball matching")
        new_positions = np.array([(x, y) for x, y, _, _ in new_balls])
        tracked_positions = np.array([(x, y) for x, y, _, _, _, _ in tracked_balls])
        tree = KDTree(tracked_positions)
        distances, indices = tree.query(
            new_positions, distance_upper_bound=distance_threshold
        )

        for i, (dist, idx) in enumerate(zip(distances, indices)):
            if (
                dist != float("inf")
                and idx < len(tracked_balls)
                and idx not in used_tracked_indices
            ):
                new_x, new_y, radius, ball_type = new_balls[i]
                tracked_x, tracked_y, _, ball_id, age, tracked_type = tracked_balls[idx]
                matched_balls.append((new_x, new_y, radius, ball_id, ball_type))
                matched_new_indices.append(i)
                used_tracked_indices.append(idx)
                tracked_balls[idx] = (
                    new_x,
                    new_y,
                    radius,
                    ball_id,
                    age,
                    ball_type,
                )  # Update position and type
                if debug_mode:
                    logger.debug(
                        f"Matched ball ID {ball_id} at ({new_x}, {new_y}) with distance {dist}, type {ball_type}"
                    )
            else:
                if debug_mode:
                    logger.debug(
                        f"No match found for new ball at ({new_balls[i][0]}, {new_balls[i][1]}) within {distance_threshold}, distance={dist}"
                    )
    else:
        # Fallback to original method if scipy isn't available
        logger.info("SciPy not available, using fallback matching method")
        for i, (new_x, new_y, radius, ball_type) in enumerate(new_balls):
            min_dist = float("inf")
            closest_ball_idx = None
            for j, (x, y, _, ball_id, age, _) in enumerate(tracked_balls):
                if j in used_tracked_indices:
                    continue
                dist_squared = (new_x - x) ** 2 + (new_y - y) ** 2
                if dist_squared < min_dist and dist_squared < distance_threshold**2:
                    min_dist = dist_squared
                    closest_ball_idx = j
            if closest_ball_idx is not None:
                tracked_x, tracked_y, _, ball_id, age, tracked_type = tracked_balls[
                    closest_ball_idx
                ]
                matched_balls.append((new_x, new_y, radius, ball_id, ball_type))
                matched_new_indices.append(i)
                used_tracked_indices.append(closest_ball_idx)
                tracked_balls[closest_ball_idx] = (
                    new_x,
                    new_y,
                    radius,
                    ball_id,
                    age,
                    ball_type,
                )
                if debug_mode:
                    logger.debug(
                        f"Matched ball ID {ball_id} at ({new_x}, {new_y}) with distance {min_dist**0.5}, type {ball_type}"
                    )
            else:
                if debug_mode:
                    logger.debug(
                        f"No match found for new ball at ({new_x}, {new_y}) within {distance_threshold}"
                    )

    return matched_balls, matched_new_indices


def _is_scored_recently(
    new_x: int,
    new_y: int,
    scored_positions: Dict[Tuple[int, int], int],
    threshold: float,
) -> bool:
    """Check if a position has been scored recently within the threshold."""
    for (sx, sy), _ in scored_positions.items():
        dist_squared = (new_x - sx) ** 2 + (new_y - sy) ** 2
        if dist_squared < threshold**2:
            logger.debug(
                f"Position ({new_x}, {new_y}) matches scored position ({sx}, {sy})"
            )
            return True
    return False


def _add_new_balls(
    new_balls: List[Tuple[int, int, float, str]],
    tracked_balls: List[Tuple[int, int, float, int, int, str]],
    matched_new_indices: List[int],
    next_ball_id: int,
    scored_positions: Dict[Tuple[int, int], int],
    frame_count: int,
    debug_mode: bool,
) -> Tuple[List[Tuple[int, int, float, int, str]], int]:
    """
    Add unmatched new balls to the tracked list with new IDs.

    Args:
        new_balls: List of newly detected balls as (x, y, radius, ball_type) tuples.
        tracked_balls: List of currently tracked balls as (x, y, radius, ball_id, age, ball_type) tuples.
        matched_new_indices: Indices of new balls already matched.
        next_ball_id: Next available ball ID to assign.
        scored_positions: Dictionary of (x, y) positions that have already scored, mapping to ball IDs.
        frame_count: Current frame number for age tracking.
        debug_mode: If True, log debug information.

    Returns:
        Tuple of (tracked_detected_balls, next_ball_id), where tracked_detected_balls is a list of
        (x, y, radius, ball_id, ball_type) tuples for all tracked balls in the current frame.
    """
    tracked_detected_balls = [
        (x, y, radius, ball_id, ball_type)
        for x, y, radius, ball_id, _, ball_type in tracked_balls
    ]

    for i, (new_x, new_y, radius, ball_type) in enumerate(new_balls):
        if i in matched_new_indices:
            continue
        if not _is_scored_recently(
            new_x, new_y, scored_positions, TrackingConstants.SCORED_DISTANCE_THRESHOLD
        ):
            tracked_balls.append(
                (new_x, new_y, radius, next_ball_id, frame_count, ball_type)
            )
            tracked_detected_balls.append(
                (new_x, new_y, radius, next_ball_id, ball_type)
            )
            if debug_mode:
                logger.debug(
                    f"New ball ID {next_ball_id} at ({new_x}, {new_y}), type {ball_type}"
                )
            next_ball_id += 1

    return tracked_detected_balls, next_ball_id


def track_balls(
    new_balls: List[Tuple[int, int, float, str]],
    tracked_balls: List[Tuple[int, int, float, int, int, str]],
    next_ball_id: int,
    frame_count: int,
    scored_positions: Dict[Tuple[int, int], int],
    debug_mode: bool = False,
) -> Tuple[List[Tuple[int, int, float, int, str]], int]:
    """
    Track balls across frames by assigning consistent IDs.

    Args:
        new_balls: List of newly detected balls as (x, y, radius, ball_type) tuples.
        tracked_balls: List of currently tracked balls as (x, y, radius, ball_id, age, ball_type) tuples.
        next_ball_id: Next available ball ID to assign.
        frame_count: Current frame number for age tracking.
        scored_positions: Dictionary of (x, y) positions that have already scored, mapping to ball IDs.
        debug_mode: If True, log debug information.

    Returns:
        Tuple of (tracked_detected_balls, next_ball_id), where tracked_detected_balls is a list
        of (x, y, radius, ball_id, ball_type) tuples for the current frame, and next_ball_id is the updated
        next available ball ID.
    """
    if not new_balls:
        logger.debug("No new balls to track")
        return [
            (x, y, radius, ball_id, ball_type)
            for x, y, radius, ball_id, _, ball_type in tracked_balls
        ], next_ball_id

    if not tracked_balls:
        logger.debug("No tracked balls to match against")

    _filter_old_balls(tracked_balls, frame_count)
    matched_balls, matched_new_indices = _match_balls(
        new_balls,
        tracked_balls,
        TrackingConstants.TRACKING_DISTANCE_THRESHOLD,
        debug_mode,
    )
    tracked_detected_balls, next_ball_id = _add_new_balls(
        new_balls,
        tracked_balls,
        matched_new_indices,
        next_ball_id,
        scored_positions,
        frame_count,
        debug_mode,
    )

    #    logger.info(f"Tracked {len(tracked_detected_balls)} balls in frame {frame_count}")
    if debug_mode:
        logger.debug(
            f"Tracked balls: {[(x, y, radius, ball_id, ball_type) for x, y, radius, ball_id, ball_type in tracked_detected_balls]}"
        )

    return tracked_detected_balls, next_ball_id


# Wrapper class to maintain compatibility with existing codebase
class BallTracker:
    def track_balls(
        self,
        white_balls: List[Tuple[int, int, float]],
        red_balls: List[Tuple[int, int, float]],
        half_balls: List[Tuple[int, int, float]],
        tracked_balls: List[Tuple[int, int, float, int, int, str]],
        next_ball_id: int,
        frame_count: int,
        scored_positions: Dict[Tuple[int, int], int],
        debug_mode: bool,
    ) -> Tuple[List[Tuple[int, int, float, int, str]], int]:
        """
        Track balls across frames, assigning IDs and updating positions.

        Args:
            white_balls: List of (x, y, radius) for white balls.
            red_balls: List of (x, y, radius) for red balls.
            half_balls: List of (x, y, radius) for half red/half white balls.
            tracked_balls: List of currently tracked balls (x, y, radius, ball_id, frame_count, ball_type).
            next_ball_id: Next available ball ID.
            frame_count: Current frame number.
            scored_positions: Dictionary of scored positions.
            debug_mode: Whether to enable debug logging.

        Returns:
            Tuple of (updated tracked balls, updated next_ball_id).
        """
        # Combine all detected balls with their types
        new_balls = (
            [(x, y, radius, "white") for x, y, radius in white_balls]
            + [(x, y, radius, "red") for x, y, radius in red_balls]
            + [(x, y, radius, "half") for x, y, radius in half_balls]
        )

        return track_balls(
            new_balls,
            tracked_balls,
            next_ball_id,
            frame_count,
            scored_positions,
            debug_mode,
        )
