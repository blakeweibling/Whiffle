# utils.py

import cv2
import logging
from typing import Any, Tuple, Optional

# Import necessary constants and types
from constants import UIConstants
from game_state import GameState, CurrentGameState

# Import the helper functions moved to the other file
from utils_mouse_logic import (
    _process_zone_editing_event,
    _process_drawing_event,
    _process_menu_or_gameover_click,
)

logger = logging.getLogger(__name__)


# --- Helper: Find which handle/area of a zone is clicked ---
def _get_zone_click_location(
    x: int, y: int, zone_rect: Tuple[int, int, int, int]
) -> Optional[str]:
    """Determine if a click is on a corner, edge, or inside a zone."""
    zx, zy, zw, zh = zone_rect
    handle_size = UIConstants.ZONE_EDIT_HANDLE_SIZE
    half_handle = handle_size // 2

    # Check corners first (priority)
    if abs(x - zx) < half_handle and abs(y - zy) < half_handle:
        return "resize_tl"
    if abs(x - (zx + zw)) < half_handle and abs(y - zy) < half_handle:
        return "resize_tr"
    if abs(x - zx) < half_handle and abs(y - (zy + zh)) < half_handle:
        return "resize_bl"
    if abs(x - (zx + zw)) < half_handle and abs(y - (zy + zh)) < half_handle:
        return "resize_br"

    # Check if inside
    if zx < x < zx + zw and zy < y < zy + zh:
        return "move"

    return None


# --- MAIN MOUSE CALLBACK ---
def mouse_callback(event: int, x: int, y: int, flags: int, param: Any) -> None:
    """Handle mouse events for the main application window."""
    game_state: GameState = param # Type hint for clarity
    if game_state is None:
        logger.warning("Mouse callback received None for game_state param.")
        return

    click_handled = False

    # --- Priority 1: Interactive Zone Editing (if in ZONE_EDITING state) ---
    if game_state.current_state == CurrentGameState.ZONE_EDITING and event in [
        cv2.EVENT_LBUTTONDOWN,
        cv2.EVENT_MOUSEMOVE,
        cv2.EVENT_LBUTTONUP,
    ]:
        logger.debug(f"Mouse event {event} received during ZONE_EDITING.")
        # Call helper from the other file
        click_handled = _process_zone_editing_event(event, x, y, game_state, _get_zone_click_location)
        # Prevent other actions if a drag/click was handled within zone editing
        if click_handled and event != cv2.EVENT_MOUSEMOVE:
            return # Don't check other handlers if LBUTTONDOWN/UP was handled here

    # --- Priority 2: Drawing New Zones (if PLAYING and drawing is active) ---
    elif (
        not click_handled # Check if not handled above
        and game_state.current_state == CurrentGameState.PLAYING
        and getattr(game_state, "drawing", False)
        and event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONUP]
    ):
        logger.debug(f"Mouse event {event} received while drawing is active.")
        # Call helper from the other file
        _process_drawing_event(event, x, y, game_state)
        if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP]:
            click_handled = True

    # --- Priority 3: Clicks within MENU or GAME_OVER states ---
    elif (
        not click_handled
        and game_state.current_state
        in [CurrentGameState.MENU, CurrentGameState.GAME_OVER]
        and event == cv2.EVENT_LBUTTONDOWN
    ):
        logger.debug(
            f"LBUTTONDOWN in {game_state.current_state}, checking menu items..."
        )
        # Call helper from the other file
        # Pass the main mouse_callback itself for potential recursive calls like splash screen
        click_handled = _process_menu_or_gameover_click(x, y, game_state, mouse_callback)


    # --- Priority 4: Menu Button Click (if PLAYING and NOT drawing) ---
    elif (
        not click_handled
        and game_state.current_state == CurrentGameState.PLAYING
        and not getattr(game_state, "drawing", False) # Ensure not drawing
        and event == cv2.EVENT_LBUTTONDOWN
    ):
        if (
            UIConstants.MENU_BUTTON_X
            <= x
            <= UIConstants.MENU_BUTTON_X + UIConstants.MENU_BUTTON_WIDTH
            and UIConstants.MENU_BUTTON_Y
            <= y
            <= UIConstants.MENU_BUTTON_Y + UIConstants.MENU_BUTTON_HEIGHT
        ):
            logger.info("Menu toggled ON via button click.")
            game_state.current_state = CurrentGameState.MENU
            # Reset menu/editing states when opening menu
            game_state.submenu_active = None
            game_state.editing_zone_index = None
            game_state.editing_zone_mode = None
            game_state.editing_zone_points_input = None
            game_state.editing_player_index = None
            game_state.editing_player_mode = None
            game_state.editing_player_name_input = None
            # Crucially, reset interactive zone editing state if menu opened
            game_state.selected_zone_for_edit = None
            game_state.zone_editing_action = None
            game_state.drag_start_pos = None
            game_state.original_zone_on_drag_start = None

            game_state.menu_cache = None # Invalidate cache
            click_handled = True

    # --- Log Unhandled Clicks ---
    if not click_handled and event == cv2.EVENT_LBUTTONDOWN:
         # Ignore clicks during some states
         if game_state.current_state not in [
            CurrentGameState.GETTING_PLAYER_NAME,
            CurrentGameState.ZONE_EDITING, # Clicks handled by _process_zone_editing_event
         ]:
            logger.debug(
                f"Unhandled click at ({x},{y}) in state {game_state.current_state}"
            )