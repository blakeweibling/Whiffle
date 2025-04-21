# utils.py

import logging
from typing import Any

import cv2

# Import from interaction_utils module
from interaction_utils import EVENT_HANDLERS

logger = logging.getLogger(__name__)


# Mouse callback function
def mouse_callback(event: int, x: int, y: int, flags: int, param: Any) -> None:
    """Global mouse event handler that delegates to the appropriate function
    based on game state.
    """
    try:
        # Add debug logging for mouse clicks
        if event == cv2.EVENT_LBUTTONDOWN:
            logger.debug(f"Mouse click detected at coordinates: ({x}, {y})")

        game_state = param
        if game_state is None:
            logger.warning("Mouse callback received None game_state.")
            return

        current_state = getattr(game_state, "current_state", None)
        if current_state is None:
            logger.warning(
                "game_state has no current_state attribute in mouse callback."
            )
            return

        # Get the appropriate event handlers for the current state
        state_handlers = EVENT_HANDLERS.get(current_state, {})

        # Get the handler for this specific event
        handler = state_handlers.get(event)

        # Call the handler if one exists
        if handler:
            handler(event, x, y, game_state)
            return

    except Exception as e:
        logger.exception(f"Error in mouse_callback: {e}")
