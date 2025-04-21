"""
Ball detection functions for the Whiffle Tracker project.

This module provides functions to detect balls in a video frame using HSV color
filtering and contour detection, with support for handling close and small balls.
"""

import cv2
import numpy as np
from typing import List, Tuple, Dict, Optional
import logging

from constants import UIConstants  # Import the class instead

# Detection configuration constants (these should ideally come from DetectionConstants class, but we'll adjust as provided)
MIN_CONTOUR_AREA: int = 50
STANDARD_BALL_AREA: int = 100
MIN_CIRCULARITY: float = 0.5
MIN_SMALL_CIRCULARITY: float = 0.3
MIN_RADIUS: int = 5
MIN_SMALL_RADIUS: int = 3
EXCLUSION_DISTANCE: int = 10
ASPECT_RATIO_MIN: float = 1.5
ASPECT_RATIO_MAX: float = 3.0
MERGED_CONTOUR_AREA: int = 200
SMALL_BALL_FRAME_THRESHOLD: int = 5
SMALL_BALL_COUNT_THRESHOLD: int = 3
KERNEL_SIZE: Tuple[int, int] = (5, 5)
ERODE_ITERATIONS: int = 2
DILATE_ITERATIONS: int = 3

# HSV color ranges for ball detection
WHITE_HSV_LOWER: np.ndarray = np.array([0, 0, 220])
WHITE_HSV_UPPER: np.ndarray = np.array([180, 30, 255])
RED_HSV_LOWER1: np.ndarray = np.array([0, 120, 70])
RED_HSV_UPPER1: np.ndarray = np.array([10, 255, 255])
RED_HSV_LOWER2: np.ndarray = np.array([170, 120, 70])
RED_HSV_UPPER2: np.ndarray = np.array([180, 255, 255])

# Set up logging
logger = logging.getLogger(__name__)

def _is_position_excluded(x: int, y: int, excluded_positions: List[Tuple[int, int]]) -> bool:
    """
    Check if a position is within the exclusion distance of any excluded position.
    """
    return any(np.sqrt((x - ex) ** 2 + (y - ey) ** 2) < EXCLUSION_DISTANCE
               for ex, ey in excluded_positions)

def detect_balls(
    frame: np.ndarray,
    frame_count: int,
    potential_small_balls: Dict[Tuple[int, int], Tuple[int, int]],
    hsv_lower: np.ndarray,
    hsv_upper: np.ndarray,
    hsv_lower2: Optional[np.ndarray] = None,
    hsv_upper2: Optional[np.ndarray] = None,
    excluded_positions: Optional[List[Tuple[int, int]]] = None,
    debug_mode: bool = False,
    hsv_frame: Optional[np.ndarray] = None
) -> List[Tuple[int, int, float]]:
    """
    Detect balls in a frame using HSV color filtering and contours.
    """
    if excluded_positions is None:
        excluded_positions = []

    # Use provided HSV frame or convert the frame to HSV
    hsv = hsv_frame if hsv_frame is not None else cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Create mask based on HSV range
    mask = cv2.inRange(hsv, hsv_lower, hsv_upper)
    if hsv_lower2 is not None and hsv_upper2 is not None:
        mask2 = cv2.inRange(hsv, hsv_lower2, hsv_upper2)
        mask = cv2.bitwise_or(mask, mask2)

    # Apply morphological operations to separate close balls and reduce noise
    kernel = np.ones(KERNEL_SIZE, np.uint8)
    mask = cv2.erode(mask, kernel, iterations=ERODE_ITERATIONS)
    mask = cv2.dilate(mask, kernel, iterations=DILATE_ITERATIONS)

    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    balls: List[Tuple[int, int, float]] = []
    potential_balls: List[Tuple[int, int, float]] = []

    if debug_mode:
        logger.debug(f"Found {len(contours)} contours before filtering")

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < MIN_CONTOUR_AREA:
            continue

        # Compute circularity
        perimeter = cv2.arcLength(contour, True)
        circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0

        # Standard ball detection (larger, more circular)
        if area > STANDARD_BALL_AREA and circularity > MIN_CIRCULARITY:
            ((x, y), radius) = cv2.minEnclosingCircle(contour)
            if radius > MIN_RADIUS:
                if not _is_position_excluded(x, y, excluded_positions):
                    balls.append((int(x), int(y), radius))
                elif debug_mode:
                    logger.debug(f"Ball at ({int(x)}, {int(y)}) excluded due to position")
        else:
            # Possible merged contour (oblong shape), try to split into two balls
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 1

            if ASPECT_RATIO_MIN < aspect_ratio < ASPECT_RATIO_MAX and area > MERGED_CONTOUR_AREA:
                if w > h:  # Horizontal split
                    center1_x, center2_x = x + w // 4, x + 3 * w // 4
                    center_y = y + h // 2
                    exclude1 = _is_position_excluded(center1_x, center_y, excluded_positions)
                    exclude2 = _is_position_excluded(center2_x, center_y, excluded_positions)
                    if not exclude1:
                        balls.append((center1_x, center_y, w // 4))
                    if not exclude2:
                        balls.append((center2_x, center_y, w // 4))
                else:  # Vertical split
                    center_x = x + w // 2
                    center1_y, center2_y = y + h // 4, y + 3 * h // 4
                    exclude1 = _is_position_excluded(center_x, center1_y, excluded_positions)
                    exclude2 = _is_position_excluded(center_x, center2_y, excluded_positions)
                    if not exclude1:
                        balls.append((center_x, center1_y, h // 4))
                    if not exclude2:
                        balls.append((center_x, center2_y, h // 4))
            elif area >= MIN_CONTOUR_AREA and circularity >= MIN_SMALL_CIRCULARITY:
                # Potential small, less circular ball
                ((x, y), radius) = cv2.minEnclosingCircle(contour)
                if radius >= MIN_SMALL_RADIUS:
                    if not _is_position_excluded(x, y, excluded_positions):
                        potential_balls.append((int(x), int(y), radius))
                    elif debug_mode:
                        logger.debug(f"Potential ball at ({int(x)}, {int(y)}) excluded")

    # Process potential small balls for consistency
    confirmed_balls: List[Tuple[int, int, float]] = []
    new_potential: Dict[Tuple[int, int], Tuple[int, int]] = {}
    for x, y, radius in potential_balls:
        pos_key = (x, y)
        found = False
        for (px, py), (count, last_frame) in potential_small_balls.items():
            if np.sqrt((x - px) ** 2 + (y - py) ** 2) < EXCLUSION_DISTANCE:
                if frame_count - last_frame <= SMALL_BALL_FRAME_THRESHOLD:
                    count += 1
                    if count >= SMALL_BALL_COUNT_THRESHOLD:
                        if not _is_position_excluded(x, y, excluded_positions):
                            confirmed_balls.append((x, y, radius))
                        elif debug_mode:
                            logger.debug(f"Confirmed ball at ({x}, {y}) excluded")
                    else:
                        new_potential[pos_key] = (count, frame_count)
                found = True
                break
        if not found:
            new_potential[pos_key] = (1, frame_count)

    potential_small_balls.clear()
    potential_small_balls.update(new_potential)
    balls.extend(confirmed_balls)

    if debug_mode:
        logger.debug(f"Detected {len(balls)} balls at positions: {[(x, y) for x, y, _ in balls]}")

    return balls

def detect_white_balls(
    frame: np.ndarray,
    frame_count: int,
    potential_small_balls: Dict[Tuple[int, int], Tuple[int, int]],
    excluded_positions: Optional[List[Tuple[int, int]]] = None,
    debug_mode: bool = False,
    hsv_frame: Optional[np.ndarray] = None
) -> List[Tuple[int, int, float]]:
    """
    Detect white balls in a frame using HSV color filtering and contours.
    """
    return detect_balls(
        frame, frame_count, potential_small_balls,
        WHITE_HSV_LOWER, WHITE_HSV_UPPER,
        excluded_positions=excluded_positions, debug_mode=debug_mode, hsv_frame=hsv_frame
    )

def detect_red_balls(
    frame: np.ndarray,
    frame_count: int,
    potential_small_balls: Dict[Tuple[int, int], Tuple[int, int]],
    excluded_positions: Optional[List[Tuple[int, int]]] = None,
    debug_mode: bool = False,
    hsv_frame: Optional[np.ndarray] = None
) -> List[Tuple[int, int, float]]:
    """
    Detect red balls in a frame using HSV color filtering and contours.
    """
    return detect_balls(
        frame, frame_count, potential_small_balls,
        RED_HSV_LOWER1, RED_HSV_UPPER1,
        RED_HSV_LOWER2, RED_HSV_UPPER2,
        excluded_positions=excluded_positions, debug_mode=debug_mode, hsv_frame=hsv_frame
    )