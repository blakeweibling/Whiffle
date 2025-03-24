"""
Scoring zone management for the Whiffle Tracker project.

This module provides functions to define, validate, and draw scoring zones where
balls can score points in the game.
"""

import cv2
import numpy as np
from typing import Tuple, Optional, List

from constants import GREEN, YELLOW, WHITE, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_NAME

# Scoring zone configuration constants
DEFAULT_POINTS: int = 100
MAX_POINTS: int = 300
FONT_SCALE: float = 0.6
FONT_THICKNESS: int = 2
TEXT_OFFSET_X: int = 10
TEXT_OFFSET_Y: int = 20
TEXT_SAFE_DISTANCE: int = 100

def _get_text_position(
    x: int, y: int, w: int, h: int, frame_width: int, frame_height: int
) -> Tuple[int, int]:
    """
    Determine the position to place text to avoid going off-screen.

    Args:
        x: X-coordinate of the rectangle's top-left corner.
        y: Y-coordinate of the rectangle's top-left corner.
        w: Width of the rectangle.
        h: Height of the rectangle.
        frame_width: Width of the frame.
        frame_height: Height of the frame.

    Returns:
        Tuple of (text_x, text_y) for placing the text.
    """
    text_x = x + w + TEXT_OFFSET_X if x + w + TEXT_SAFE_DISTANCE < frame_width else x
    text_y = y if x + w + TEXT_SAFE_DISTANCE < frame_width else y + h + TEXT_OFFSET_Y
    return text_x, text_y

def define_scoring_zone(
    frame: np.ndarray,
    cap: cv2.VideoCapture,
    trackbar_created: bool,  # Kept for compatibility, but no longer used
    scoring_zones: List[Tuple[int, int, int, int, int]]
) -> Tuple[Optional[Tuple[int, int, int, int, int]], bool]:
    """
    Define a scoring zone with points, allowing user input via mouse and keyboard.

    Args:
        frame: Input BGR frame to draw on.
        cap: Video capture object to check if the camera is open.
        trackbar_created: Flag indicating if the trackbar has been created (unused).
        scoring_zones: List of existing scoring zones.

    Returns:
        Tuple of (zone, trackbar_created), where zone is (x, y, w, h, points) or None,
        and trackbar_created is always False since we no longer use a trackbar.
    """
    if frame.shape[0] == 0 or frame.shape[1] == 0:
        raise ValueError("Invalid frame dimensions")

    temp_zone: Optional[Tuple[int, int, int, int]] = None
    drawing: bool = False
    start_x, start_y = -1, -1
    points_input: str = ""  # String to build the points value from keyboard input

    # Set up a local mouse callback for drawing
    def local_mouse_callback(event: int, x: int, y: int, flags: int, param: None) -> None:
        nonlocal drawing, start_x, start_y, temp_zone
        if event == cv2.EVENT_LBUTTONDOWN:
            drawing = True
            start_x, start_y = x, y
        elif event == cv2.EVENT_MOUSEMOVE and drawing:
            temp_zone = (start_x, start_y, x - start_x, y - start_y)
        elif event == cv2.EVENT_LBUTTONUP:
            drawing = False
            if temp_zone:
                x1, y1, w, h = temp_zone
                x = min(x1, x1 + w)
                y = min(y1, y1 + h)
                w = abs(w)
                h = abs(h)
                temp_zone = (x, y, w, h)

    cv2.setMouseCallback(WINDOW_NAME, local_mouse_callback)

    while True:
        if not cap.isOpened():
            return None, False

        temp_frame = frame.copy()

        # Draw existing scoring zones
        for zone in scoring_zones:
            x, y, w, h, points = zone
            cv2.rectangle(temp_frame, (x, y), (x + w, y + h), GREEN, FONT_THICKNESS)
            text_x, text_y = _get_text_position(x, y, w, h, temp_frame.shape[1], temp_frame.shape[0])
            cv2.putText(temp_frame, f"{points} pts", (text_x, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, GREEN, FONT_THICKNESS)

        # Draw the temporary zone being created
        if temp_zone:
            x, y, w, h = temp_zone
            cv2.rectangle(temp_frame, (x, y), (x + w, y + h), YELLOW, FONT_THICKNESS)
            points_display = points_input if points_input else str(DEFAULT_POINTS)
            text_x, text_y = _get_text_position(x, y, w, h, temp_frame.shape[1], temp_frame.shape[0])
            cv2.putText(temp_frame, f"{points_display} pts", (text_x, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, YELLOW, FONT_THICKNESS)

        # Display instructions
        instructions = "Drag to draw zone, release to input points (0-9), Enter to confirm, 'c' to cancel"
        cv2.putText(temp_frame, instructions, (TEXT_OFFSET_X, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, WHITE, FONT_THICKNESS)

        cv2.imshow(WINDOW_NAME, temp_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 13 and temp_zone and not drawing:  # Enter to confirm
            if not points_input:  # If no input, use default
                points = DEFAULT_POINTS
            else:
                try:
                    points = int(points_input)
                    points = max(1, min(points, MAX_POINTS))  # Clamp between 1 and MAX_POINTS
                except ValueError:
                    points = DEFAULT_POINTS  # Fallback to default if invalid
            zone = (temp_zone[0], temp_zone[1], temp_zone[2], temp_zone[3], points)
            return zone, False
        elif key == ord('c'):  # Cancel
            return None, False
        elif not drawing and temp_zone and ord('0') <= key <= ord('9'):  # Numeric input
            points_input += chr(key)

def is_in_scoring_zone(ball: Tuple[int, int, float, int], zone: Tuple[int, int, int, int, int]) -> bool:
    """
    Check if a ball's center is within a scoring zone.

    Args:
        ball: Tuple of (x, y, radius, ball_id) representing the ball.
        zone: Tuple of (x, y, w, h, points) representing the scoring zone.

    Returns:
        bool: True if the ball's center is within the zone, False otherwise.
    """
    x, y, _, _ = ball
    zx, zy, zw, zh, _ = zone
    return (zx <= x <= zx + zw) and (zy <= y <= zy + zh)

def draw_scoring_zones(frame: np.ndarray, scoring_zones: List[Tuple[int, int, int, int, int]]) -> None:
    """
    Draw all scoring zones on the frame with their point values.

    Args:
        frame: Input BGR frame to draw on.
        scoring_zones: List of scoring zones as (x, y, w, h, points) tuples.
    """
    for zone in scoring_zones:
        x, y, w, h, points = zone
        cv2.rectangle(frame, (x, y), (x + w, y + h), GREEN, FONT_THICKNESS)
        text_x, text_y = _get_text_position(x, y, w, h, frame.shape[1], frame.shape[0])
        cv2.putText(frame, f"{points} pts", (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, GREEN, FONT_THICKNESS)