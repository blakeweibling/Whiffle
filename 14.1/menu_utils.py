# menu_utils.py
"""
Utility functions for menu rendering in the Whiffle Tracker project.

This module contains shared functions used by both menu.py and submenus.py to avoid circular imports.
"""

import logging
import time  # Added import

# <<< ADDED IMPORT >>>
from typing import TYPE_CHECKING, Any, Callable, Tuple

import cv2
import numpy as np

# Import constants
from constants import UIConstants

# <<< ADDED FOR TYPE HINTING >>>
if TYPE_CHECKING:
    from game_state import GameState

# Set up logging
logger = logging.getLogger(__name__)


# --- UPDATED: Added hover functionality to _draw_button ---
def _draw_button(
    frame: cv2.typing.MatLike,
    x: int,
    y: int,
    w: int,
    h: int,
    text: str,
    color: Tuple[int, int, int],
    # <<< ADDED game_state PARAMETER >>>
    game_state: "GameState",  # Use string literal for type hint
    font_scale: float = UIConstants.FONT_SCALE_MEDIUM,
    font_thickness: int = 2,
    text_color: Tuple[int, int, int] = UIConstants.WHITE,
    shadow_offset: int = 3,
    shadow_color: Tuple[int, int, int] = UIConstants.BLACK,
    # <<< ADDED click_color PARAMETER (Optional) >>>
    click_color: Tuple[int, int, int] = UIConstants.YELLOW,  # Color when clicked
    # <<< ADDED hover_color PARAMETER (Optional) >>>
    hover_color: Tuple[int, int, int] = UIConstants.LIGHT_BLUE,  # Color when hovered
) -> None:
    """
    Draws a button with centered text, specified color, and a drop shadow.
    Highlights the button if its rectangle matches game_state.click_feedback_state
    and the click timestamp is within the feedback duration.
    Also highlights when mouse is hovering over it if game_state.hover_feedback_state is set.
    If colorblind mode is enabled, uses colorblind-friendly alternative colors.
    """
    try:
        # Check if colorblind mode is enabled and adjust colors if needed
        colorblind_mode = getattr(game_state, "colorblind_mode", False)
        if colorblind_mode:
            # Replace standard colors with colorblind-friendly alternatives
            if color == UIConstants.CV2_BLUE:
                color = UIConstants.CB_BLUE
            elif color == UIConstants.LIGHT_BLUE:
                color = UIConstants.CB_LIGHT_BLUE
            elif color == UIConstants.GREEN:
                color = UIConstants.CB_SELECT
            elif color == UIConstants.RED:
                color = UIConstants.CB_HIGHLIGHT
            
            # Also replace highlight colors
            if hover_color == UIConstants.LIGHT_BLUE:
                hover_color = UIConstants.CB_LIGHT_BLUE
            if click_color == UIConstants.YELLOW:
                click_color = UIConstants.CB_HIGHLIGHT

        # <<< MODIFIED LOGIC to check for click state, hover state, and duration >>>
        button_rect = (x, y, w, h)
        is_clicked = False
        is_hovered = False

        # Check if button is being clicked
        if (
            hasattr(game_state, "click_feedback_state")
            and game_state.click_feedback_state
        ):
            stored_rect, click_time = game_state.click_feedback_state
            # Check if the rectangle matches AND the time is within the duration
            if (
                stored_rect == button_rect
                and (time.time() - click_time) < UIConstants.CLICK_FEEDBACK_DURATION
            ):
                is_clicked = True

        # Check if button is being hovered
        if (
            hasattr(game_state, "hover_feedback_state")
            and game_state.hover_feedback_state
        ):
            hovered_rect = game_state.hover_feedback_state
            if hovered_rect == button_rect:
                is_hovered = True

        # Determine color - click state has precedence over hover state
        if is_clicked:
            current_color = click_color
        elif is_hovered:
            current_color = hover_color
        else:
            current_color = color
        # <<< END MODIFIED LOGIC >>>

        # Draw Drop Shadow
        shadow_x = x + shadow_offset
        shadow_y = y + shadow_offset
        shadow_x2 = min(frame.shape[1], shadow_x + w)
        shadow_y2 = min(frame.shape[0], shadow_y + h)
        shadow_x = max(0, shadow_x)
        shadow_y = max(0, shadow_y)
        if shadow_x < shadow_x2 and shadow_y < shadow_y2:
            cv2.rectangle(
                frame, (shadow_x, shadow_y), (shadow_x2, shadow_y2), shadow_color, -1
            )

        # Draw the main button rectangle (using current_color)
        cv2.rectangle(
            frame, (x, y), (x + w, y + h), current_color, -1
        )  # <<< USE current_color >>>

        # Center Text
        (text_width, text_height), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness
        )
        text_x = x + (w - text_width) // 2
        text_y = y + (h + text_height) // 2

        # Draw the text
        cv2.putText(
            frame,
            text,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            text_color,
            font_thickness,
            cv2.LINE_AA,
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
    frame: np.ndarray,
    game_state: "GameState",
    main_callback: Callable,
    callback_param: Any,
) -> None:
    """
    Display splash screen until a keypress, mouse click, or window closure.
    """
    splash = cv2.imread("assets/splash.png")
    if splash is None:
        logger.error(
            "Failed to load assets/splash.png for About menu, skipping splash screen"
        )
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
    splash = cv2.resize(splash, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))

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
    cv2.setMouseCallback(UIConstants.WINDOW_NAME, _mouse_callback_splash, param)

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
    cv2.setMouseCallback(UIConstants.WINDOW_NAME, main_callback, callback_param)
    cv2.imshow(UIConstants.WINDOW_NAME, frame)
    logger.info("Returned to game frame after splash screen")
