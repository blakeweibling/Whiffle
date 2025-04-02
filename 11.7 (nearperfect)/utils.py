# utils.py

import cv2
import logging
from typing import Any

# Main game state and constants needed for top-level logic
from game_state import GameState, CurrentGameState
from game_constants import UIConstants

# Import the processing functions from the helper files
from utils_zone_helpers import _process_zone_editing_event, _process_drawing_event
from utils_ui_interactions import _process_menu_or_gameover_click, _reset_all_editing_states

logger = logging.getLogger(__name__)

# --- MOUSE CALLBACK ---
def mouse_callback(event: int, x: int, y: int, flags: int, param: Any) -> None:
    """Handle mouse events for the main application window."""
    game_state: GameState = param # Type hint for clarity
    if game_state is None:
        logger.warning("Mouse callback received None for game_state param.")
        return

    click_handled = False # Flag to track if an event was consumed

    # --- RELOCATED DRAG LOGIC STARTS HERE ---

    # --- Menu Drag Move / End (Check these first based on event type) ---
    if event == cv2.EVENT_MOUSEMOVE:
        if game_state.is_dragging_menu and game_state.menu_drag_offset:
            menu_w = getattr(game_state, 'menu_width', UIConstants.MENU_WIDTH)
            menu_h = getattr(game_state, 'menu_height', UIConstants.MENU_HEIGHT)
            new_menu_x = x - game_state.menu_drag_offset[0]
            new_menu_y = y - game_state.menu_drag_offset[1]

            # Clamp position to screen bounds
            max_x = UIConstants.WINDOW_WIDTH - menu_w
            max_y = UIConstants.WINDOW_HEIGHT - menu_h
            new_menu_x = max(0, min(new_menu_x, max_x))
            new_menu_y = max(0, min(new_menu_y, max_y))

            # --- MODIFICATION: Always update position and invalidate cache during drag ---
            game_state.menu_pos = (new_menu_x, new_menu_y)
            game_state.menu_cache = None # Ensure cache is invalidated to force redraw
            # logger.debug(f"Menu dragging to: {game_state.menu_pos}") # Optional debug
            # --- END MODIFICATION ---

            # MOUSEMOVE during drag doesn't consume the "handled" flag for button events
            # click_handled = True # Keep this commented out

    elif event == cv2.EVENT_LBUTTONUP:
        if game_state.is_dragging_menu:
            game_state.is_dragging_menu = False
            game_state.menu_drag_offset = None
            logger.info("Stopped dragging menu.")
            # Mark as handled to prevent accidental button clicks on release
            click_handled = True

    # --- Menu Background Drag Start (Check only if LBUTTONDOWN wasn't handled by Drag End) ---
    elif not click_handled and event == cv2.EVENT_LBUTTONDOWN: # Prioritize Drag Start if LBUTTONUP wasn't handled
        if game_state.current_state == CurrentGameState.MENU:
            logger.info(">>> LBUTTONDOWN in MENU state - Checking Drag Start <<<")
            # Ensure menu attributes are valid
            menu_w = getattr(game_state, 'menu_width', UIConstants.MENU_WIDTH)
            menu_h = getattr(game_state, 'menu_height', UIConstants.MENU_HEIGHT)
            if hasattr(game_state, 'menu_pos') and menu_w > 0 and menu_h > 0:
                menu_x, menu_y = game_state.menu_pos
                is_within_menu = (menu_x <= x < menu_x + menu_w and menu_y <= y < menu_y + menu_h)
                logger.info(f"Drag Start Check: is_within_menu={is_within_menu}")

                # Start dragging ONLY if click is within bounds
                if is_within_menu:
                     # Check if click is NOT on a menu item before initiating drag
                     is_on_item = False
                     if hasattr(game_state, "submenu_items") and isinstance(game_state.submenu_items, list):
                         relative_x = x - menu_x
                         relative_y = y - menu_y
                         for item_rect, _, _ in game_state.submenu_items:
                             if isinstance(item_rect, tuple) and len(item_rect) == 4:
                                 item_x_rel, item_y_rel, item_w, item_h = item_rect
                                 # Use relative coordinates for item check
                                 if item_x_rel <= relative_x <= item_x_rel + item_w and item_y_rel <= relative_y <= item_y_rel + item_h:
                                     is_on_item = True
                                     logger.debug(f"Click at relative ({relative_x},{relative_y}) is on item: {item_rect}")
                                     break

                     if not is_on_item:
                        game_state.is_dragging_menu = True
                        game_state.menu_drag_offset = (x - menu_x, y - menu_y)
                        logger.info(f"Started dragging menu from offset: {game_state.menu_drag_offset}")
                        click_handled = True # Consume this click event
                     else:
                        logger.debug("Click was on a menu item, drag not initiated.")
            else:
                logger.debug("Menu drag start check skipped: Menu attributes invalid or missing.")

    # --- RELOCATED DRAG LOGIC ENDS HERE ---


    # --- Event Handling Order (Original logic resumes here, checked only if click_handled is False) ---
    # 1. Zone Editing (Highest Priority AFTER Dragging)
    # 2. Drawing New Zones
    # 3. Menu Item / Game Over Button Clicks
    # 4. Menu Button Click (to open menu)

    # --- Priority 1: Interactive Zone Editing ---
    if (
        not click_handled # Check if not handled by drag logic
        and game_state.current_state == CurrentGameState.ZONE_EDITING
        and event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONUP] # Only check relevant events
    ):
        logger.debug(f"Mouse event {event} received during ZONE_EDITING.")
        click_handled = _process_zone_editing_event(event, x, y, game_state)
        # Prevent other actions if a drag/click was handled within zone editing
        if click_handled and event != cv2.EVENT_MOUSEMOVE:
             return # Don't check other handlers if LBUTTONDOWN/UP was handled here

    # --- Priority 2: Drawing New Zones ---
    elif (
        not click_handled # Check if not handled above
        and game_state.current_state == CurrentGameState.PLAYING
        and getattr(game_state, 'drawing', False)
        and event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONUP]
    ):
        logger.debug(f"Mouse event {event} received while drawing is active.")
        _process_drawing_event(event, x, y, game_state)
        if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP]:
            click_handled = True

    # --- Priority 3: Menu Item / Game Over Button Clicks ---
    elif (
        not click_handled
        and game_state.current_state in [CurrentGameState.MENU, CurrentGameState.GAME_OVER]
        and event == cv2.EVENT_LBUTTONDOWN
    ):
        logger.debug(f"LBUTTONDOWN in {game_state.current_state}, checking menu items...")
        # Check if click is within menu bounds before processing item clicks
        if game_state.current_state == CurrentGameState.MENU:
            if hasattr(game_state, 'menu_pos'):
                 menu_x, menu_y = game_state.menu_pos
                 menu_w, menu_h = getattr(game_state, 'menu_width', 0), getattr(game_state, 'menu_height', 0)
                 if (menu_x <= x < menu_x + menu_w and menu_y <= y < menu_y + menu_h):
                      click_handled = _process_menu_or_gameover_click(x, y, game_state) # Pass window coords
                 else:
                      logger.debug("Click outside menu bounds, not checking menu items.")
            else:
                 logger.warning("menu_pos missing, cannot check menu item clicks accurately.")
        elif game_state.current_state == CurrentGameState.GAME_OVER:
             # Game over screen might cover the whole window, so process directly
             click_handled = _process_menu_or_gameover_click(x, y, game_state)


    # --- Priority 4: Menu Button Click (to open menu) ---
    elif (
        not click_handled
        and game_state.current_state == CurrentGameState.PLAYING
        and not getattr(game_state, 'drawing', False) # Ensure not drawing
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
            _reset_all_editing_states(game_state)
            game_state.selected_zone_for_edit = None
            game_state.zone_editing_action = None
            game_state.drag_start_pos = None
            game_state.original_zone_on_drag_start = None
            game_state.edit_zones_page = 0

            # Calculate initial centered menu position
            initial_menu_w = UIConstants.MENU_WIDTH
            initial_menu_h = UIConstants.MENU_HEIGHT
            current_menu_w = getattr(game_state, 'menu_width', initial_menu_w)
            current_menu_h = getattr(game_state, 'menu_height', initial_menu_h)
            if current_menu_w <=0: current_menu_w = initial_menu_w
            if current_menu_h <=0: current_menu_h = initial_menu_h

            start_x = (UIConstants.WINDOW_WIDTH - current_menu_w) // 2
            start_y = (UIConstants.WINDOW_HEIGHT - current_menu_h) // 2
            game_state.menu_pos = (start_x, start_y)
            logger.info(f"Set initial menu position to: {game_state.menu_pos}")

            game_state.menu_cache = None # Invalidate cache
            click_handled = True


    # --- Log Unhandled Clicks ---
    if not click_handled and event == cv2.EVENT_LBUTTONDOWN:
         if game_state.current_state not in [
             CurrentGameState.GETTING_PLAYER_NAME,
             CurrentGameState.ZONE_EDITING
             ]:
              logger.debug(
                  f"Unhandled click at ({x},{y}) in state {game_state.current_state}"
              )