# menu_utils.py
"""
Utility functions for menu rendering in the Whiffle Tracker project.

This module contains shared functions used by both menu.py and submenus.py to avoid circular imports.
"""

import cv2
import logging
import numpy as np
from typing import Tuple, Any, Callable

# Import constants
from constants import UIConstants

# Set up logging
logger = logging.getLogger(__name__)


# --- CHANGE: Updated _draw_button function ---
def _draw_button(
    frame: cv2.typing.MatLike,
    x: int,
    y: int,
    w: int,
    h: int,
    text: str,
    color: Tuple[int, int, int],
    font_scale: float = UIConstants.FONT_SCALE_MEDIUM, # Use medium scale default
    font_thickness: int = 2, # Increased thickness for bolder text
    text_color: Tuple[int, int, int] = UIConstants.WHITE,
    shadow_offset: int = 3, # Offset for drop shadow
    shadow_color: Tuple[int, int, int] = UIConstants.BLACK # Shadow color
) -> None:
    """
    Draws a button with centered text, specified color, and a drop shadow.

    Args:
        frame: The image frame to draw on.
        x, y, w, h: The position and dimensions of the button.
        text: The text label for the button.
        color: The background color of the button (BGR).
        font_scale: The scale of the font.
        font_thickness: The thickness of the font.
        text_color: The color of the text (BGR).
        shadow_offset: Pixel offset for the drop shadow.
        shadow_color: Color of the drop shadow (BGR).
    """
    try:
        # Draw Drop Shadow
        shadow_x = x + shadow_offset
        shadow_y = y + shadow_offset
        # Ensure shadow stays within frame bounds (optional, but good practice)
        shadow_x2 = min(frame.shape[1], shadow_x + w)
        shadow_y2 = min(frame.shape[0], shadow_y + h)
        shadow_x = max(0, shadow_x)
        shadow_y = max(0, shadow_y)
        if shadow_x < shadow_x2 and shadow_y < shadow_y2:
             cv2.rectangle(frame, (shadow_x, shadow_y), (shadow_x2, shadow_y2), shadow_color, -1)

        # Draw the main button rectangle
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, -1)

        # Center Text
        # Get text size to calculate center position
        (text_width, text_height), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness
        )

        # Calculate text coordinates for centering
        text_x = x + (w - text_width) // 2
        # Adjust y based on text height for vertical centering
        text_y = y + (h + text_height) // 2 # Adjust for baseline if needed for perfect centering

        # Draw the text
        cv2.putText(
            frame,
            text,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            text_color,
            font_thickness,
            cv2.LINE_AA, # Nicer text rendering
        )

    except Exception as e:
        logger.error(f"Error drawing button '{text}': {e}")
# --- End Change ---


def _mouse_callback_splash(event: int, x: int, y: int, flags: int, param: dict) -> None:
    """Handle mouse events for dismissing the splash screen."""
    if event == cv2.EVENT_LBUTTONDOWN:
        param["dismissed"] = True
        logger.info("Splash screen dismissed via mouse click")


def show_splash_on_click(
    frame: np.ndarray, game_state: Any, main_callback: Callable, callback_param: Any
) -> None:
    """
    Display splash screen until a keypress, mouse click, or window closure.
    Args:
        frame (np.ndarray): The current game frame to return to after dismissing the splash.
        game_state (Any): The current game state.
        main_callback (Callable): The main mouse callback to restore after dismissing the splash.
        callback_param (Any): The parameter to pass to the main callback (usually game_state).
    """
    splash = cv2.imread("splash.png")
    if splash is None:
        logger.error(
            "Failed to load splash.png for About menu, skipping splash screen")
        cv2.putText(
            frame,
            "Splash unavailable",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.RED,
            UIConstants.FONT_THICKNESS,
        )
        cv2.imshow(UIConstants.WINDOW_NAME, frame)
        cv2.waitKey(1000)  # Show error briefly
        return
    splash = cv2.resize(
        splash, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))

    # Add instructions to the splash screen
    cv2.putText(
        splash,
        "Click or press Esc to continue",
        (50, UIConstants.WINDOW_HEIGHT - 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.YELLOW,
        UIConstants.FONT_THICKNESS,
    )

    # Set up mouse callback to detect clicks
    param = {"dismissed": False}
    cv2.setMouseCallback(UIConstants.WINDOW_NAME,
                         _mouse_callback_splash, param)

    while True:
        cv2.imshow(UIConstants.WINDOW_NAME, splash)
        key = cv2.waitKey(20) & 0xFF
        # Exit on Esc key, mouse click, or window closure
        if (
            key == 27
            or param["dismissed"]
            or cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) <= 0
        ):
            break

    # Restore the main mouse callback
    cv2.setMouseCallback(UIConstants.WINDOW_NAME,
                         main_callback, callback_param)
    cv2.imshow(UIConstants.WINDOW_NAME, frame)
    logger.info("Returned to game frame after splash screen")