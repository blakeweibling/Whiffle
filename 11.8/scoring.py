"""
Scoring zone management for the Whiffle Tracker project.

This module provides functions to define, validate, and draw scoring zones where
balls can score points in the game.
"""

import cv2
import numpy as np
import logging
from typing import Tuple, Optional, List

# Updated to class-based imports
from game_constants import UIConstants, ScoringConstants

# Scoring zone configuration constants (moved to ScoringConstants in constants.py ideally)
DEFAULT_POINTS: int = ScoringConstants.DEFAULT_POINTS  # Updated
MAX_POINTS: int = ScoringConstants.MAX_POINTS  # Updated
# Updated from 0.6 to use UIConstants
FONT_SCALE: float = UIConstants.FONT_SCALE_MEDIUM
FONT_THICKNESS: int = UIConstants.FONT_THICKNESS  # Updated
TEXT_OFFSET_X: int = UIConstants.TEXT_OFFSET_X  # Updated
TEXT_OFFSET_Y: int = UIConstants.TEXT_OFFSET_Y  # Updated
TEXT_SAFE_DISTANCE: int = UIConstants.TEXT_SAFE_DISTANCE  # Updated

# Set up logging
logger = logging.getLogger(__name__)


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


def _validate_frame(frame: np.ndarray) -> bool:
    """Validate the input frame for processing."""
    if frame is None or frame.shape[0] == 0 or frame.shape[1] == 0:
        logger.error("Invalid frame dimensions or null frame")
        return False
    return True


def _handle_mouse_event(event: int, x: int, y: int, drawing_state: dict) -> None:
    """Handle mouse events for drawing scoring zones."""
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing_state["drawing"] = True
        drawing_state["start"] = (x, y)
        logger.debug(f"Drawing started at ({x}, {y})")
    elif event == cv2.EVENT_MOUSEMOVE and drawing_state["drawing"]:
        drawing_state["temp_zone"] = (
            drawing_state["start"][0],
            drawing_state["start"][1],
            x - drawing_state["start"][0],
            y - drawing_state["start"][1],
        )
    elif event == cv2.EVENT_LBUTTONUP:
        drawing_state["drawing"] = False
        if drawing_state["temp_zone"]:
            x1, y1, w, h = drawing_state["temp_zone"]
            x = min(x1, x1 + w)
            y = min(y1, y1 + h)
            w = abs(w)
            h = abs(h)
            drawing_state["temp_zone"] = (x, y, w, h)
            logger.debug(f"Drawing ended, temp zone: ({x}, {y}, {w}, {h})")


def _draw_existing_zones(
    overlay: np.ndarray,
    scoring_zones: List[Tuple[int, int, int, int, int]],
    special_hole: Optional[Tuple[int, int, int, int, int]] = None,
) -> None:
    """Draw existing scoring zones onto a static overlay, highlighting the special hole."""
    for zone in scoring_zones:
        x, y, w, h, points = zone
        # Use blue for the special hole, green for others
        color = UIConstants.CV2_BLUE if zone == special_hole else UIConstants.GREEN
        cv2.rectangle(overlay, (x, y), (x + w, y + h), color, FONT_THICKNESS)
        text_x, text_y = _get_text_position(
            x, y, w, h, overlay.shape[1], overlay.shape[0]
        )
        # Add "Special Hole" label if this is the special hole
        label = (
            f"{points} pts (Special Hole)" if zone == special_hole else f"{points} pts"
        )
        cv2.putText(
            overlay,
            label,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            FONT_SCALE,
            color,
            FONT_THICKNESS,
        )


def _zones_overlap(
    new_zone: Tuple[int, int, int, int],
    existing_zones: List[Tuple[int, int, int, int, int]],
) -> bool:
    """Check if the new zone overlaps with any existing zones."""
    x1, y1, w1, h1 = new_zone
    for x2, y2, w2, h2, _ in existing_zones:
        if not (x1 + w1 < x2 or x2 + w2 < x1 or y1 + h1 < y2 or y2 + h2 < y1):
            logger.warning(
                f"New zone ({x1}, {y1}, {w1}, {h1}) overlaps with existing zone ({x2}, {y2}, {w2}, {h2})"
            )
            return True
    return False


def _run_drawing_loop(
    frame: np.ndarray,
    cap: cv2.VideoCapture,
    drawing_state: dict,
    scoring_zones: List[Tuple[int, int, int, int, int]],
) -> Optional[Tuple[int, int, int, int, int]]:
    """Run the drawing loop to define a scoring zone."""
    overlay = np.zeros_like(frame)  # Static overlay for existing zones
    _draw_existing_zones(overlay, scoring_zones)

    while True:
        if not cap.isOpened():
            logger.error("Camera closed during zone definition")
            return None

        temp_frame = frame.copy()
        temp_frame = cv2.addWeighted(
            temp_frame, 0.8, overlay, 0.2, 0
        )  # Composite overlay

        if drawing_state["temp_zone"]:
            x, y, w, h = drawing_state["temp_zone"]
            cv2.rectangle(
                temp_frame, (x, y), (x + w, y + h), UIConstants.YELLOW, FONT_THICKNESS
            )  # Updated
            points_display = (
                drawing_state["points"]
                if drawing_state["points"]
                else str(DEFAULT_POINTS)
            )
            text_x, text_y = _get_text_position(
                x, y, w, h, temp_frame.shape[1], temp_frame.shape[0]
            )
            cv2.putText(
                temp_frame,
                f"{points_display} pts",
                (text_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                FONT_SCALE,
                UIConstants.YELLOW,
                FONT_THICKNESS,
            )  # Updated

        instructions = "Drag to draw zone, 0-9 to input points, Backspace to edit, Enter to confirm, 'c' to cancel"
        cv2.putText(
            temp_frame,
            instructions,
            (TEXT_OFFSET_X, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            FONT_SCALE,
            UIConstants.WHITE,
            FONT_THICKNESS,
        )  # Updated

        cv2.imshow(UIConstants.WINDOW_NAME, temp_frame)  # Updated

        key = cv2.waitKey(1) & 0xFF
        if (
            key == 13 and drawing_state["temp_zone"] and not drawing_state["drawing"]
        ):  # Enter
            if _zones_overlap(drawing_state["temp_zone"], scoring_zones):
                logger.warning("Zone overlaps with existing zone, cancelling")
                return None
            points = (
                DEFAULT_POINTS
                if not drawing_state["points"]
                else int(drawing_state["points"])
            )
            points = max(1, min(points, MAX_POINTS))
            zone = (
                drawing_state["temp_zone"][0],
                drawing_state["temp_zone"][1],
                drawing_state["temp_zone"][2],
                drawing_state["temp_zone"][3],
                points,
            )
            logger.info(f"Scoring zone defined: {zone}")
            return zone
        elif key == ord("c"):  # Cancel
            logger.info("Scoring zone definition cancelled")
            return None
        elif not drawing_state["drawing"] and drawing_state["temp_zone"]:
            if ord("0") <= key <= ord("9"):
                drawing_state["points"] += chr(key)
                logger.debug(f"Added digit to points: {drawing_state['points']}")
            elif key == 8:  # Backspace
                drawing_state["points"] = drawing_state["points"][:-1]
                logger.debug(f"Backspace applied, points: {drawing_state['points']}")


def define_scoring_zone(
    frame: np.ndarray,
    cap: cv2.VideoCapture,
    trackbar_created: bool,  # Kept for compatibility, unused
    scoring_zones: List[Tuple[int, int, int, int, int]],
) -> Tuple[Optional[Tuple[int, int, int, int, int]], bool]:
    """
    Define a scoring zone with points, allowing user input via mouse and keyboard.
    """
    if not _validate_frame(frame):
        return None, False

    drawing_state = {
        "drawing": False,
        "start": (-1, -1),
        "temp_zone": None,
        "points": "",
    }
    cv2.setMouseCallback(
        UIConstants.WINDOW_NAME,
        lambda e, x, y, f, p: _handle_mouse_event(e, x, y, drawing_state),
    )  # Updated
    zone = _run_drawing_loop(frame, cap, drawing_state, scoring_zones)
    return zone, False


def is_in_scoring_zone(
    ball: Tuple[int, int, float, int], zone: Tuple[int, int, int, int, int]
) -> bool:
    """
    Check if a ball's center is within a scoring zone.
    """
    x, y, _, _ = ball
    zx, zy, zw, zh, _ = zone
    return (zx <= x <= zx + zw) and (zy <= y <= zy + zh)


def draw_scoring_zones(
    frame: np.ndarray,
    scoring_zones: List[Tuple[int, int, int, int, int]],
    special_hole: Optional[Tuple[int, int, int, int, int]] = None,
) -> None:
    """
    Draw all scoring zones on the frame with their point values, highlighting the special hole.

    Args:
        frame: The frame to draw on.
        scoring_zones: List of scoring zones, each as (x, y, width, height, points).
        special_hole: The designated special hole to highlight, if any.
    """
    for zone in scoring_zones:
        x, y, w, h, points = zone
        # Use blue for the special hole, green for others
        color = UIConstants.CV2_BLUE if zone == special_hole else UIConstants.GREEN
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, FONT_THICKNESS)
        text_x, text_y = _get_text_position(x, y, w, h, frame.shape[1], frame.shape[0])
        # Add "Special Hole" label if this is the special hole
        label = (
            f"{points} pts (Special Hole)" if zone == special_hole else f"{points} pts"
        )
        cv2.putText(
            frame,
            label,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            FONT_SCALE,
            color,
            FONT_THICKNESS,
        )
