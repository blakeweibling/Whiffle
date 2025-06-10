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

    # Extract the game_state from params
    if not param or not hasattr(param, "current_state"):
        logger.error("Invalid param or missing game_state in mouse_callback")
        return

    game_state = param
    current_state = game_state.current_state

    # Check for drawing mode which needs to handle all mouse events
    drawing_mode = current_state == CurrentGameState.PLAYING and getattr(
        game_state, "drawing", False
    )

    # Skip motion events to reduce log noise, except for zone editing and drawing
    if event == cv2.EVENT_MOUSEMOVE and not (
        current_state == CurrentGameState.ZONE_EDITING or drawing_mode
    ):
        # Handle hover for menu items
        if current_state == CurrentGameState.MENU:
            # Store previous hover state to detect changes
            previous_hover = getattr(game_state, "hover_feedback_state", None)

            # Reset hover state
            game_state.hover_feedback_state = None

            # Get menu position for coordinate adjustment
            menu_x, menu_y = getattr(game_state, "menu_pos", (0, 0))

            # Calculate mouse position relative to menu
            relative_x = x - menu_x
            relative_y = y - menu_y

            # Check if mouse is within menu bounds
            menu_width = getattr(game_state, "menu_width", 600)
            menu_height = getattr(game_state, "menu_height", 450)

            if 0 <= relative_x < menu_width and 0 <= relative_y < menu_height:
                # Check if hovering over any menu item
                if hasattr(game_state, "submenu_items") and game_state.submenu_items:
                    for item_rect, action_key, label in game_state.submenu_items:
                        if isinstance(item_rect, tuple) and len(item_rect) == 4:
                            rect_x, rect_y, rect_w, rect_h = item_rect
                            if (
                                rect_x <= relative_x < rect_x + rect_w
                                and rect_y <= relative_y < rect_y + rect_h
                            ):
                                # Found a menu item being hovered
                                game_state.hover_feedback_state = item_rect
                                if previous_hover != item_rect:
                                    logger.debug(f"Hovering over menu item: {label}")
                                break

            # Force menu redraw if hover state changed
            if previous_hover != game_state.hover_feedback_state:
                game_state.menu_cache = None  # Force menu redraw

            # No need to log hover events further
            return

    # Make sure we don't skip button up events for zone editing and drawing
    if event == cv2.EVENT_LBUTTONUP and (
        current_state == CurrentGameState.ZONE_EDITING or drawing_mode
    ):
        # Process this event through the handler system below
        pass

    # Convert to Pygame coordinates if needed
    # OpenCV and Pygame use the same coordinate system, but if there's scaling this would be addressed here

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

    # Direct handling for drawing mode events
    if drawing_mode:
        from interaction_utils import _process_drawing_event

        _process_drawing_event(event, x, y, game_state)
        # Drawing events are important, log them
        if event == cv2.EVENT_LBUTTONDOWN:
            logger.debug(f"Drawing started at ({x}, {y})")
        elif event == cv2.EVENT_LBUTTONUP:
            logger.debug(f"Drawing finished at ({x}, {y})")
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
