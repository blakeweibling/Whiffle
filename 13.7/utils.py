# utils.py

import logging
import time
from typing import Any

import cv2

# Import from interaction_utils module
from interaction_utils import _get_mouse_event_handlers, EVENT_HANDLERS
from game_types import CurrentGameState
from constants import UIConstants

logger = logging.getLogger(__name__)


# Mouse callback function
def mouse_callback(event: int, x: int, y: int, flags: int, param: Any) -> None:
    """Global mouse event handler for OpenCV window."""
    # First, log the event to help with debugging
    event_names = {
        cv2.EVENT_LBUTTONDOWN: "LEFT_DOWN",
        cv2.EVENT_LBUTTONUP: "LEFT_UP",
        cv2.EVENT_RBUTTONDOWN: "RIGHT_DOWN",
        cv2.EVENT_RBUTTONUP: "RIGHT_UP",
        cv2.EVENT_MOUSEMOVE: "MOVE",
    }
    event_name = event_names.get(event, f"UNKNOWN({event})")

    if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_RBUTTONDOWN]:
        logger.debug(f"OpenCV mouse event: {event_name} at ({x}, {y})")

    # Skip motion events to reduce log noise
    if event == cv2.EVENT_MOUSEMOVE:
        return

    # Convert to Pygame coordinates if needed
    # OpenCV and Pygame use the same coordinate system, but if there's scaling this would be addressed here

    # Extract the game_state from params
    if not param or not hasattr(param, "current_state"):
        logger.error("Invalid param or missing game_state in mouse_callback")
        return

    game_state = param
    current_state = game_state.current_state

    # Direct handling for menu button click in PLAYING state
    if current_state == CurrentGameState.PLAYING and event == cv2.EVENT_LBUTTONDOWN:
        menu_btn_x = UIConstants.MENU_BUTTON_X
        menu_btn_y = UIConstants.MENU_BUTTON_Y
        menu_btn_w = UIConstants.MENU_BUTTON_WIDTH
        menu_btn_h = UIConstants.MENU_BUTTON_HEIGHT

        # Check if click is within menu button
        if (
            menu_btn_x <= x < menu_btn_x + menu_btn_w
            and menu_btn_y <= y < menu_btn_y + menu_btn_h
        ):
            logger.info(f"Menu button clicked via OpenCV handler at ({x}, {y})")
            menu_button_rect = (menu_btn_x, menu_btn_y, menu_btn_w, menu_btn_h)
            game_state.click_feedback_state = (menu_button_rect, time.time())
            game_state.current_state = CurrentGameState.MENU
            game_state.menu_cache = None  # Force menu redraw
            logger.info("Switched to MENU state via OpenCV")
            return

    # If we're showing a heatmap, that takes precedence
    if getattr(game_state, "show_heatmap", False) and event == cv2.EVENT_LBUTTONDOWN:
        logger.info("Heatmap dismissed by mouse click")
        game_state.show_heatmap = False
        return

    # Handle direct menu or modal clicks
    if (
        current_state in [CurrentGameState.MENU, CurrentGameState.CONFIRM_QUIT]
        and event == cv2.EVENT_LBUTTONDOWN
    ):
        from interaction_utils import _process_menu_or_modal_click

        if _process_menu_or_modal_click(x, y, game_state):
            logger.debug("Menu/modal click was handled by _process_menu_or_modal_click")
            return

    # Use the handler dictionary from interaction_utils for other event handling
    try:
        from interaction_utils import _get_mouse_event_handlers

        handlers = _get_mouse_event_handlers()

        # The handlers structure is a dictionary, so we need to:
        # 1. Get the handler dictionary for the current state
        # 2. Get the handler function for the current event
        if current_state in handlers and event in handlers[current_state]:
            handler_fn = handlers[current_state][event]
            result = handler_fn(event, x, y, game_state)
            if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_RBUTTONDOWN]:
                logger.debug(f"Mouse handler result: {result}")
        else:
            logger.debug(
                f"No specific handler for {event_name} event in state {current_state}"
            )

    except Exception as e:
        logger.error(f"Error in mouse handler: {e}")
        import traceback

        logger.error(traceback.format_exc())
