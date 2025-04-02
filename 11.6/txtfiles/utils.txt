# utils.py

import cv2
import logging
from typing import Any

# Main game state and constants needed for top-level logic
from game_state import GameState, CurrentGameState
from constants import UIConstants

# Import the processing functions from the helper files
from utils_zone_helpers import _process_zone_editing_event, _process_drawing_event
from utils_ui_interactions import _process_menu_or_gameover_click, _reset_all_editing_states

logger = logging.getLogger(__name__)

# --- MOUSE CALLBACK ---
def mouse_callback(event: int, x: int, y: int, flags: int, param: Any) -> None: # [cite: 136]
    """Handle mouse events for the main application window."""
    game_state: GameState = param # Type hint for clarity [cite: 136]
    if game_state is None: # [cite: 137]
        logger.warning("Mouse callback received None for game_state param.") # [cite: 137]
        return # [cite: 137]

    click_handled = False # [cite: 137]

    # --- Priority 1: Interactive Zone Editing (if in ZONE_EDITING state) ---
    if ( # [cite: 137]
        game_state.current_state == CurrentGameState.ZONE_EDITING # [cite: 137]
        and event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONUP] # [cite: 137]
    ):
        logger.debug(f"Mouse event {event} received during ZONE_EDITING.") # [cite: 137]
        click_handled = _process_zone_editing_event(event, x, y, game_state) # [cite: 138]
        # Prevent other actions if a drag/click was handled within zone editing
        if click_handled and event != cv2.EVENT_MOUSEMOVE: # [cite: 138]
             return # Don't check other handlers if LBUTTONDOWN/UP was handled here [cite: 138]

    # --- Priority 2: Drawing New Zones (if PLAYING and drawing is active) ---
    elif ( # [cite: 138]
        not click_handled # Check if not handled above [cite: 138]
        and game_state.current_state == CurrentGameState.PLAYING # [cite: 139]
        and getattr(game_state, 'drawing', False) # [cite: 139]
        and event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONUP] # [cite: 139]
    ):
        logger.debug(f"Mouse event {event} received while drawing is active.") # [cite: 139]
        _process_drawing_event(event, x, y, game_state) # [cite: 139]
        if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP]: # [cite: 139]
            click_handled = True # [cite: 139]

    # --- Priority 3: Clicks within MENU or GAME_OVER states ---
    elif ( # [cite: 140]
        not click_handled # [cite: 140]
        and game_state.current_state in [CurrentGameState.MENU, CurrentGameState.GAME_OVER] # [cite: 140]
        and event == cv2.EVENT_LBUTTONDOWN # [cite: 140]
    ):
        logger.debug(f"LBUTTONDOWN in {game_state.current_state}, checking menu items...") # [cite: 140]
        click_handled = _process_menu_or_gameover_click(x, y, game_state) # [cite: 140]

    # --- Priority 4: Menu Button Click (if PLAYING and NOT drawing) ---
    elif ( # [cite: 140]
        not click_handled # [cite: 141]
        and game_state.current_state == CurrentGameState.PLAYING # [cite: 141]
        and not getattr(game_state, 'drawing', False) # Ensure not drawing [cite: 141]
        and event == cv2.EVENT_LBUTTONDOWN # [cite: 141]
    ):
        if ( # [cite: 141]
            UIConstants.MENU_BUTTON_X # [cite: 141]
            <= x # [cite: 141]
            <= UIConstants.MENU_BUTTON_X + UIConstants.MENU_BUTTON_WIDTH # [cite: 141]
            and UIConstants.MENU_BUTTON_Y # [cite: 142]
            <= y # [cite: 142]
            <= UIConstants.MENU_BUTTON_Y + UIConstants.MENU_BUTTON_HEIGHT # [cite: 142]
        ):
            logger.info("Menu toggled ON via button click.") # [cite: 142]
            game_state.current_state = CurrentGameState.MENU # [cite: 142]
            # Reset menu/editing states when opening menu
            game_state.submenu_active = None # [cite: 143]
            _reset_all_editing_states(game_state) # Use the helper from ui_interactions [cite: 143]
            # Crucially, reset interactive zone editing state if menu opened
            game_state.selected_zone_for_edit = None # [cite: 144]
            game_state.zone_editing_action = None # [cite: 144]
            game_state.drag_start_pos = None # [cite: 144]
            game_state.original_zone_on_drag_start = None # [cite: 144]
            # Reset page number when opening menu
            game_state.edit_zones_page = 0 # [cite: 144]

            game_state.menu_cache = None # Invalidate cache [cite: 145]
            click_handled = True # [cite: 145]

    # --- Log Unhandled Clicks ---
    if not click_handled and event == cv2.EVENT_LBUTTONDOWN: # [cite: 145]
         # Ignore clicks during some states
         if game_state.current_state not in [ # [cite: 145]
             CurrentGameState.GETTING_PLAYER_NAME, # [cite: 145]
             CurrentGameState.ZONE_EDITING # Clicks outside zone already handled/ignored in helper [cite: 146]
             ]:
              logger.debug( # [cite: 146]
                   f"Unhandled click at ({x},{y}) in state {game_state.current_state}" # [cite: 146]
              )