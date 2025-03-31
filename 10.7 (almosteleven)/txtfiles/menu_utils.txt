"""
Utility functions for menu rendering in the Whiffle Tracker project.

This module contains shared functions used by both menu.py and submenus.py to avoid circular imports.
"""

import cv2
import logging
import numpy as np
from typing import Tuple, Any, Callable

from constants import UIConstants

# Set up logging
logger = logging.getLogger(__name__)

def _draw_button(
    frame: np.ndarray,
    x: int,
    y: int,
    width: int,
    height: int,
    label: str,
    color: Tuple[int, int, int],
    font_scale: float = UIConstants.FONT_SCALE_SMALL
) -> None:
    """
    Draw a button with a label on the frame.
    """
    cv2.rectangle(frame, (x, y), (x + width, y + height), color, -1)
    cv2.putText(frame, label, (x + 5, y + 20),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, UIConstants.WHITE, 1)

def _mouse_callback_splash(event: int, x: int, y: int, flags: int, param: dict) -> None:
    """Handle mouse events for dismissing the splash screen."""
    if event == cv2.EVENT_LBUTTONDOWN:
        param['dismissed'] = True
        logger.info("Splash screen dismissed via mouse click")

def show_splash_on_click(frame: np.ndarray, game_state: Any, main_callback: Callable, callback_param: Any) -> None:
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
        logger.error("Failed to load splash.png for About menu, skipping splash screen")
        cv2.putText(frame, "Splash unavailable", (50, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.RED, UIConstants.FONT_THICKNESS)
        cv2.imshow(UIConstants.WINDOW_NAME, frame)
        cv2.waitKey(1000)  # Show error briefly
        return
    splash = cv2.resize(splash, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))

    # Add instructions to the splash screen
    cv2.putText(splash, "Click or press Esc to continue", (50, UIConstants.WINDOW_HEIGHT - 50),
                cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.YELLOW, UIConstants.FONT_THICKNESS)

    # Set up mouse callback to detect clicks
    param = {'dismissed': False}
    cv2.setMouseCallback(UIConstants.WINDOW_NAME, _mouse_callback_splash, param)

    while True:
        cv2.imshow(UIConstants.WINDOW_NAME, splash)
        key = cv2.waitKey(20) & 0xFF
        # Exit on Esc key, mouse click, or window closure
        if key == 27 or param['dismissed'] or cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) <= 0:
            break

    # Restore the main mouse callback
    cv2.setMouseCallback(UIConstants.WINDOW_NAME, main_callback, callback_param)
    cv2.imshow(UIConstants.WINDOW_NAME, frame)
    logger.info("Returned to game frame after splash screen")