# utils.py

import logging
import time
from typing import Any

import cv2

# Import from interaction_utils module
from interaction_utils import EVENT_HANDLERS
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

    if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_RBUTTONDOWN, cv2.EVENT_LBUTTONUP]:
        logger.debug(f"OpenCV mouse event: {event_name} at ({x}, {y})")

    # Extract the game_state from params
    if not param or not hasattr(param, "current_state"):
        logger.error("Invalid param or missing game_state in mouse_callback")
        return

    game_state = param
    current_state = game_state.current_state

    # Debug zone editing state with more detail
    if current_state == CurrentGameState.ZONE_EDITING:
        if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP]:
            logger.info(
                f"Zone Editing: {event_name} at ({x}, {y}), zone_editing_action={getattr(game_state, 'zone_editing_action', None)}, selected_zone={getattr(game_state, 'selected_zone_for_edit', None)}"
            )

        # Handle all zone editing events
        from interaction_utils import _process_zone_editing_event

        if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP, cv2.EVENT_MOUSEMOVE]:
            if _process_zone_editing_event(event, x, y, game_state):
                logger.debug(
                    f"Zone editing event {event_name} handled in mouse_callback"
                )
                return

    # Handle drag/resize if drawing is active (different from zone editing)
    if (
        getattr(game_state, "drawing", False)
        and current_state == CurrentGameState.PLAYING
    ):
        from interaction_utils import _process_drawing_event

        _process_drawing_event(event, x, y, game_state)
        logger.debug(f"Drawing event {event_name} handled in mouse_callback")
        return

    # Skip remaining motion events to reduce log noise
    if event == cv2.EVENT_MOUSEMOVE:
        return

    # Special debug for resolution button click in PLAYING state
    if current_state == CurrentGameState.PLAYING and event == cv2.EVENT_LBUTTONDOWN:
        # Debug resolution button
        res_button_rect = (
            UIConstants.RESOLUTION_BUTTON_X,
            UIConstants.RESOLUTION_BUTTON_Y,
            UIConstants.RESOLUTION_BUTTON_WIDTH,
            UIConstants.RESOLUTION_BUTTON_HEIGHT,
        )
        res_x, res_y, res_w, res_h = res_button_rect

        # Check if the click is on the resolution button
        if res_x <= x < res_x + res_w and res_y <= y < res_y + res_h:
            logger.warning(
                f"CRITICAL DEBUG: Resolution button clicked in mouse_callback at ({x}, {y})"
            )

            # Try direct resolution toggle for debugging
            try:
                if hasattr(game_state, "set_resolution") and hasattr(
                    game_state, "current_resolution_key"
                ):
                    from constants import ResolutionConstants

                    available_resolutions = list(ResolutionConstants.RESOLUTIONS.keys())
                    current_index = available_resolutions.index(
                        game_state.current_resolution_key
                    )
                    new_index = (current_index + 1) % len(available_resolutions)
                    new_resolution = available_resolutions[new_index]

                    logger.warning(
                        f"CRITICAL DEBUG: Attempting direct resolution toggle to {new_resolution}"
                    )
                    game_state.set_resolution(new_resolution)
                    game_state.menu_cache = None

                    # Add visual feedback
                    from game_state_helpers import show_notification

                    show_notification(
                        game_state,
                        f"Resolution changed to {new_resolution} (direct)",
                        duration=3.0,
                    )
                    logger.warning(
                        f"CRITICAL DEBUG: Direct resolution change attempt complete"
                    )
                    return  # Skip normal processing
            except Exception as e:
                logger.error(f"CRITICAL DEBUG: Direct resolution toggle error: {e}")

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
        handlers = EVENT_HANDLERS

        # The handlers structure is a dictionary, so we need to:
        # 1. Get the handler dictionary for the current state
        # 2. Get the handler function for the current event
        if current_state in handlers and event in handlers[current_state]:
            handler_fn = handlers[current_state][event]
            result = handler_fn(event, x, y, game_state)
            if event in [
                cv2.EVENT_LBUTTONDOWN,
                cv2.EVENT_RBUTTONDOWN,
                cv2.EVENT_LBUTTONUP,
            ]:
                logger.debug(f"Mouse handler result: {result}")
        else:
            logger.debug(
                f"No specific handler for {event_name} event in state {current_state}"
            )

    except Exception as e:
        logger.error(f"Error in mouse handler: {e}")
        import traceback

        logger.error(traceback.format_exc())
