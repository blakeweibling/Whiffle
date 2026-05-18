"""
Ball tracking for the Whiffle Tracker project.

This module provides functions to track balls across frames by assigning consistent IDs.
"""

import logging
from typing import Dict, List, Tuple

import numpy as np

try:
    from scipy.spatial import KDTree  # Optional, requires scipy installation

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

from constants import TrackingConstants

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


def _is_solid_red_ball_type(ball_type: str) -> bool:
    if not ball_type:
        return False
    name = ball_type.lower().replace("_", " ").replace("-", " ")
    if "half" in name:
        return False
    return "red" in name


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

    # Throttle adding new balls if we're tracking too many already
    # This improves performance by not adding unnecessary balls
    if len(tracked_balls) > 15:  # Only add new balls if there's room
        return tracked_detected_balls, next_ball_id

    for i, (x, y, radius, ball_type) in enumerate(new_balls):
        if i not in matched_new_indices:
            suppress_r = float(radius) * 2.0
            if _is_solid_red_ball_type(str(ball_type)):
                suppress_r = max(
                    suppress_r,
                    float(TrackingConstants.RED_BALL_SCORED_POSITION_SUPPRESS_RADIUS_PX),
                )
            if _is_scored_recently(x, y, scored_positions, suppress_r):
                if debug_mode:
                    logger.debug(
                        f"Skipped adding new ball at ({x}, {y}) - recently scored position"
                    )
                continue

            # Add the new ball with a new ID
            tracked_detected_balls.append((x, y, radius, next_ball_id, ball_type))
            # Create a new tracked ball
            tracked_balls.append((x, y, radius, next_ball_id, frame_count, ball_type))
            if debug_mode:
                logger.debug(
                    f"Added new ball ID {next_ball_id} at ({x}, {y}), type {ball_type}"
                )
            next_ball_id += 1

    return tracked_detected_balls, next_ball_id


# Optimized and more efficient version of the track_balls function
def track_balls(
    new_balls: List[Tuple[int, int, float, str]],
    tracked_balls: List[Tuple[int, int, float, int, int, str]],
    next_ball_id: int,
    frame_count: int,
    scored_positions: Dict[Tuple[int, int], int],
    debug_mode: bool = False,
) -> Tuple[List[Tuple[int, int, float, int, str]], int]:
    """
    Track and match balls between frames, assigning consistent IDs.

    This is an optimized version that reduces computational load and improves performance.

    Args:
        new_balls: List of newly detected balls as (x, y, radius, ball_type) tuples.
        tracked_balls: List of currently tracked balls as (x, y, radius, ball_id, age, ball_type) tuples.
        next_ball_id: Next available ball ID to assign.
        frame_count: Current frame number for age tracking.
        scored_positions: Dictionary of (x, y) positions that have already scored, mapping to ball IDs.
        debug_mode: If True, log debug information.

    Returns:
        Tuple of (tracked_detected_balls, next_ball_id), where tracked_detected_balls is a list of
        (x, y, radius, ball_id, ball_type) tuples for all tracked balls in the current frame.
    """
    if debug_mode:
        logger.debug(
            f"Tracking {len(new_balls)} new balls with {len(tracked_balls)} existing tracked balls"
        )

    # Remove balls that have exceeded maximum age
    _filter_old_balls(tracked_balls, frame_count)

    # Match existing balls with new detections
    distance_threshold = TrackingConstants.TRACKING_DISTANCE_THRESHOLD
    matched_balls, matched_new_indices = _match_balls(
        new_balls, tracked_balls, distance_threshold, debug_mode
    )

    # Add new unmatched balls
    tracked_detected_balls, next_ball_id = _add_new_balls(
        new_balls,
        tracked_balls,
        matched_new_indices,
        next_ball_id,
        scored_positions,
        frame_count,
        debug_mode,
    )

    return tracked_detected_balls, next_ball_id


# Wrapper class to maintain compatibility with existing codebase
class BallTracker:
    """Manages ball tracking between frames."""

    # Store distance threshold and last validation time at class level for optimization
    _distance_threshold = TrackingConstants.TRACKING_DISTANCE_THRESHOLD
    _last_validation_time = 0
    _validation_interval = 5.0  # Only validate scipy every 5 seconds

    def __init__(self):
        """Initialize the BallTracker."""
        # Confirm SciPy availability only once on initialization
        self.use_scipy = SCIPY_AVAILABLE
        if self.use_scipy:
            logger.debug("SciPy available - using KDTree for efficient ball tracking")
        else:
            logger.info("SciPy not available - using fallback ball tracking method")

        # Throttling state variables
        self._skip_counter = 0

    def track_balls(
        self,
        silver_balls: List[Tuple[int, int, float]],
        gold_balls: List[Tuple[int, int, float]],
        tracked_balls: List[Tuple[int, int, float, int, int, str]],
        next_ball_id: int,
        frame_count: int,
        scored_positions: Dict[Tuple[int, int], int],
        debug_mode: bool,
    ) -> Tuple[List[Tuple[int, int, float, int, str]], int]:
        """
        Combine and track silver and gold balls between frames.

        Args:
            silver_balls: List of silver balls as (x, y, radius) tuples.
            gold_balls: List of gold balls as (x, y, radius) tuples.
            tracked_balls: List of currently tracked balls as (x, y, radius, ball_id, age, ball_type) tuples.
            next_ball_id: Next available ball ID to assign.
            frame_count: Current frame number for age tracking.
            scored_positions: Dictionary of (x, y) positions that have already scored, mapping to ball IDs.
            debug_mode: If True, log debug information.

        Returns:
            Tuple of (tracked_detected_balls, next_ball_id), where tracked_detected_balls is a list of
            (x, y, radius, ball_id, ball_type) tuples for all tracked balls in the current frame.
        """
        # Throttle tracking for performance improvement
        self._skip_counter += 1
        if self._skip_counter % 2 != 0 and len(tracked_balls) > 0:
            # Skip tracking on some frames if we already have tracked balls
            # Just return existing tracked balls
            return [
                (x, y, r, ball_id, ball_type)
                for x, y, r, ball_id, _, ball_type in tracked_balls
            ], next_ball_id

        # Repackage balls with type information
        # Handle both old format (x, y, r) and new format (x, y, r, ball_type)
        silver_balls_with_type = []
        for ball in silver_balls:
            if len(ball) == 4:
                x, y, r, ball_type = ball
                silver_balls_with_type.append((x, y, r, ball_type))
            else:
                x, y, r = ball
                silver_balls_with_type.append((x, y, r, "silver"))  # Fallback to "silver" for old format
        
        gold_balls_with_type = []
        for ball in gold_balls:
            if len(ball) == 4:
                x, y, r, ball_type = ball
                gold_balls_with_type.append((x, y, r, ball_type))
            else:
                x, y, r = ball
                gold_balls_with_type.append((x, y, r, "gold"))  # Fallback to "gold" for old format

        # Combine all balls with type information
        all_balls = silver_balls_with_type + gold_balls_with_type

        # If tracking too many balls, limit new additions for performance
        if len(tracked_balls) > 15 and len(all_balls) > 5:
            # Sample only a subset of new balls to process
            # This significantly reduces computational load when there are many balls
            all_balls = all_balls[:5]

        # Perform the actual tracking
        tracked_detected_balls, next_ball_id = track_balls(
            all_balls,
            tracked_balls,
            next_ball_id,
            frame_count,
            scored_positions,
            debug_mode,
        )

        return tracked_detected_balls, next_ball_id
