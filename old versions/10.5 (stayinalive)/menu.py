"""
Menu rendering and utility functions for the Whiffle Tracker project.

This module provides functions to manage the main game menu, including rendering the menu button,
overlaying the menu on the game window, and handling game state utilities like resetting the game
and managing scoring zones.
"""

import cv2
import numpy as np
import logging
import json
import os
from typing import List, Tuple, Any

# Import constants, including the new MenuConstants
from constants import UIConstants, GameConstants, ScoringConstants, MenuConstants
from menu_utils import _draw_button # Import from menu_utils.py
# Import submenu functions here to avoid circular imports within _draw_menu_content
from submenus import (
    draw_submenu # This is the main dispatcher
)
# Import GameState directly for type hinting if needed, but avoid direct use that causes cycles
from game_state import GameState, CurrentGameState # Import state enum

# Set up logging
logger = logging.getLogger(__name__)

# --- Menu Item Definitions Moved to constants.MenuConstants ---

def reset_game(game_state: GameState) -> None: # Added GameState type hint
    """
    Reset the game state fully.
    """ # [source: 83]
    game_state.score = 0 # [source: 84]
    # Don't clear zones on reset by default
    game_state.tracked_balls.clear() # [source: 84]
    game_state.scored_balls.clear() # [source: 84]
    game_state.scored_positions.clear() # [source: 84]
    game_state.next_ball_id = 0 # [source: 84]
    game_state.submenu_active = None # [source: 84]
    game_state.submenu_items = [] # [source: 84]
    game_state.game_timer = None # [source: 84]
    game_state.ball_trails.clear() # [source: 84]
    game_state.ball_states.clear() # [source: 84]
    game_state.previous_ball_states.clear() # [source: 84]
    game_state.achievement_notification = None # [source: 84]
    game_state.achievement_notification_timer = 0.0 # [source: 84]
    game_state.balls_in_zone.clear() # [source: 84]
    game_state.ball_scored_zones.clear() # [source: 84]
    game_state.ball_positions_history.clear() # [source: 84]
    game_state.ball_zone_history.clear() # [source: 84]
    game_state.scored_cooldown.clear() # [source: 84]
    game_state.win_condition_met = False # [source: 85]
    game_state.editing_zone_index = None # Reset zone editing state # [source: 85]
    game_state.editing_zone_mode = None # [source: 85]
    game_state.editing_zone_points = None # [source: 85]

    if game_state.players and 0 <= game_state.current_player_index < len(game_state.players): # [source: 85]
        game_state.players[game_state.current_player_index].reset_score() # [source: 85]
    else: # [source: 85]
         logger.warning("Player index out of bounds or no players during reset.") # [source: 85]

    if game_state.game_mode == "timed": # [source: 85]
         game_state.game_timer = GameConstants.TIMED_MODE_DURATION # [source: 85]

    # Reload initial state (zones and high score for current mode)
    # Ensure _load_initial_state exists and is appropriate to call here
    if hasattr(game_state, '_load_initial_state') and callable(game_state._load_initial_state): # [source: 86]
        game_state._load_initial_state() # [source: 86]
    else: # [source: 86]
        logger.warning("Cannot reload initial state during reset, _load_initial_state not found.") # [source: 86]


    logger.info("Game state reset.") # [source: 86]


def save_zones(game_state: GameState) -> None: # Added GameState type hint
    """Save the current scoring zones to a JSON file."""
    try:
        with open(GameConstants.ZONES_FILE, 'w') as f: # [source: 87]
             json.dump(game_state.scoring_zones, f, indent=4) # [source: 87]
        logger.info(f"Scoring zones saved to {GameConstants.ZONES_FILE}") # [source: 87]
        game_state.show_notification("Zones Saved") # [source: 87]
    except IOError as e: # [source: 87]
        logger.error(f"Error saving scoring zones: {e}") # [source: 87]
        game_state.show_notification("Error Saving Zones", is_error=True) # [source: 87]


def load_zones(game_state: GameState) -> None: # Added GameState type hint
    """Load scoring zones from a JSON file."""
    if os.path.exists(GameConstants.ZONES_FILE): # [source: 87]
        try: # [source: 88]
            # Check if file is empty before trying to load
            if os.path.getsize(GameConstants.ZONES_FILE) == 0: # [source: 88]
                logger.warning(f"{GameConstants.ZONES_FILE} is empty. Clearing zones.") # [source: 89]
                game_state.scoring_zones = [] # [source: 89]
                game_state.special_hole = None # [source: 89]
                return # Exit early # [source: 89]

            with open(GameConstants.ZONES_FILE, 'r') as f: # [source: 89]
                loaded_data = json.load(f) # [source: 90]
            # Basic validation
            if isinstance(loaded_data, list) and all(isinstance(z, list) and len(z) == 5 for z in loaded_data): # [source: 90]
                 game_state.scoring_zones = [(int(z[0]), int(z[1]), int(z[2]), int(z[3]), int(z[4])) for z in loaded_data] # [source: 90]
                 logger.info(f"Scoring zones loaded from {GameConstants.ZONES_FILE}") # [source: 90]
                 game_state.show_notification("Zones Loaded") # [source: 91]
                 from game_state_utils import set_special_hole # Local import to avoid cycles # [source: 91]
                 game_state.special_hole = set_special_hole(game_state.scoring_zones) # [source: 91]
            else: # [source: 91]
                 logger.error("Invalid format in zones file. Expected list of [x, y, w, h, points].") # [source: 91]
                 game_state.show_notification("Invalid Zone File Format", is_error=True) # [source: 92]
                 game_state.scoring_zones = [] # Clear zones if file is invalid # [source: 92]
                 game_state.special_hole = None # [source: 92]

        except (IOError, json.JSONDecodeError) as e: # [source: 92]
            logger.error(f"Error loading scoring zones: {e}") # [source: 92]
            game_state.show_notification("Error Loading Zones", is_error=True) # [source: 93]
            game_state.scoring_zones = [] # Clear zones on error # [source: 93]
            game_state.special_hole = None # [source: 93]
    else: # [source: 93]
        logger.warning(f"Scoring zones file '{GameConstants.ZONES_FILE}' not found.") # [source: 93]
        # game_state.show_notification("Zone File Not Found", is_error=True) # Maybe too noisy?
        game_state.scoring_zones = [] # Ensure zones are clear if file doesn't exist # [source: 94]
        game_state.special_hole = None # [source: 94]


def clear_zones(game_state: GameState) -> None: # Added GameState type hint
    """Clear all scoring zones."""
    game_state.scoring_zones.clear() # [source: 94]
    game_state.special_hole = None # Clear special hole too # [source: 94]
    # Clear the cache and file as well
    if hasattr(game_state, 'scoring_zones_cache'): game_state.scoring_zones_cache = [] # If using cache # [source: 94]
    if os.path.exists(GameConstants.ZONES_FILE): # [source: 94]
        try: os.remove(GameConstants.ZONES_FILE) # [source: 95]
        except OSError as e: logger.error(f"Failed to remove zones file: {e}") # [source: 95]

    logger.info("All scoring zones cleared.") # [source: 95]
    game_state.show_notification("All Zones Cleared") # [source: 95]

def flush_scoring_zones(game_state: GameState) -> None: # Added GameState type hint
     """ Writes current scoring zones to disk (used by clean_exit). """
     logger.debug("Flushing scoring zones (calling save_zones)...") # [source: 95]
     save_zones(game_state) # Just call save_zones # [source: 95]


def draw_menu(frame: np.ndarray, game_state: GameState) -> None: # Added GameState type hint
    """Draw the menu button on the frame."""
    # Draw only if in playing state
    if game_state.current_state == CurrentGameState.PLAYING: # [source: 96]
        # --- Color Changed Here ---
        _draw_button(frame, UIConstants.MENU_BUTTON_X, UIConstants.MENU_BUTTON_Y,
                     UIConstants.MENU_BUTTON_WIDTH, UIConstants.MENU_BUTTON_HEIGHT,
                     "Menu", UIConstants.CV2_BLUE) # Changed from YELLOW to CV2_BLUE # [source: 561]

# --- Menu Window Drawing ---

def _draw_menu_content(menu_frame: np.ndarray, game_state: GameState) -> None: # Added GameState type hint
    """Draw the actual content of the menu or submenu onto the menu_frame."""
    if game_state.submenu_active: # [source: 96]
        # Call the main dispatcher function from submenus.py
        draw_submenu(menu_frame, game_state) # [source: 97]
    else: # [source: 97]
        # Draw the main menu
        cv2.putText(menu_frame, "Main Menu", (30, 40), cv2.FONT_HERSHEY_SIMPLEX,
                    UIConstants.FONT_SCALE_LARGE, UIConstants.WHITE, UIConstants.FONT_THICKNESS) # [source: 97]

        game_state.submenu_items.clear() # Clear before drawing # [source: 97]
        y_offset = 80 # [source: 97]
        item_height = 35 # [source: 97]

        # Use MAIN_MENU_ITEMS from MenuConstants
        for label, action_key in MenuConstants.MAIN_MENU_ITEMS: # [source: 98]
            item_rect = (20, y_offset, game_state.menu_width - 40, item_height) # [source: 98]
            _draw_button(menu_frame, item_rect[0], item_rect[1], item_rect[2], item_rect[3],
                         label, UIConstants.CV2_BLUE, font_scale=UIConstants.FONT_SCALE_MEDIUM) # [source: 98]
            game_state.submenu_items.append((item_rect, action_key, label)) # [source: 98]
            y_offset += item_height + 5 # [source: 99]

# --- Using Robust Caching Logic ---
def draw_menu_window(frame: np.ndarray, game_state: GameState) -> None: # Added GameState type hint
    """
    Draw the menu as an overlay within the main game window, using caching to reduce redraws.
    """ # [source: 99]
    # This function should only be called when game_state.current_state is MENU
    if game_state.current_state != CurrentGameState.MENU: # [source: 100]
        return # [source: 100]

    # Dynamic menu sizing based on content (Main Menu vs Submenu)
    game_state.menu_width = 400 # Fixed width for now # [source: 100]
    if not game_state.submenu_active: # [source: 100]
         # Calculate height based on main menu items
         game_state.menu_height = 60 + len(MenuConstants.MAIN_MENU_ITEMS) * 40 + 20 # [source: 100]
    else: # [source: 101]
         # Submenus determine their height within their draw functions,
         # Use a default/max height if the specific submenu doesn't set it
         if not hasattr(game_state, 'menu_height') or game_state.menu_height < 100: # Ensure a minimum height # [source: 101]
             game_state.menu_height = 450 # Default/Max Submenu height # [source: 101]

    # Check cache validity using submenu state and item actions as key
    current_item_actions = tuple(item[1] for item in game_state.submenu_items) # Use actions as part of key # [source: 102]
    cache_key = (game_state.submenu_active, current_item_actions) # [source: 102]
    menu_frame = None # [source: 102]

    if hasattr(game_state, 'menu_cache') and game_state.menu_cache is not None and game_state.menu_cache_key == cache_key: # [source: 102]
        # Use cached frame if key matches and cache exists
        menu_frame = game_state.menu_cache # [source: 102]
        if game_state.debug_mode: logger.debug("Using cached menu frame.") # [source: 102]
        # Ensure game_state dimensions match cache if using cache
        if game_state.menu_height != menu_frame.shape[0] or game_state.menu_width != menu_frame.shape[1]: # [source: 103]
             logger.warning("Menu cache dimensions mismatch with game_state. Forcing redraw.") # [source: 104]
             menu_frame = None # Invalidate # [source: 104]
             game_state.menu_cache = None # [source: 104]
    else: # [source: 104]
         if game_state.debug_mode: logger.debug("Cache invalid or missing. Redrawing menu content.") # [source: 104]

    if menu_frame is None: # Need to redraw # [source: 104]
        # Ensure height is positive and reasonable
        menu_height_to_use = max(100, game_state.menu_height) # [source: 104]
        menu_frame = np.zeros((menu_height_to_use, game_state.menu_width, 3), dtype=np.uint8) # [source: 105]
        game_state.menu_height = menu_height_to_use # Update game state with actual used height # [source: 105]

        # Draw the content (main menu or submenu)
        _draw_menu_content(menu_frame, game_state) # [source: 105]

        # Update cache ONLY if drawing was successful
        if menu_frame is not None: # [source: 105]
            game_state.menu_cache = menu_frame # [source: 105]
            game_state.menu_cache_key = cache_key # [source: 106]
        else: # [source: 106]
             logger.error("Failed to create menu_frame during redraw.") # [source: 106]
             return # Cannot proceed if menu frame creation failed # [source: 106]

    # --- Overlay Logic ---
    # Calculate position (center)
    start_x = (frame.shape[1] - game_state.menu_width) // 2 # [source: 106]
    start_y = (frame.shape[0] - game_state.menu_height) // 2 # [source: 106]
    # Update game_state.menu_pos *before* using it for clicks in utils.py
    game_state.menu_pos = (start_x, start_y) # [source: 107]

    # Blend the menu frame onto the main frame
    x1, y1 = game_state.menu_pos # [source: 107]
    # Use the *actual* dimensions of the menu_frame for slicing and blending
    menu_h, menu_w = menu_frame.shape[0], menu_frame.shape[1] # [source: 107]
    x2, y2 = x1 + menu_w, y1 + menu_h # [source: 107]

    # Clip coordinates to frame boundaries
    x1c, y1c = max(0, x1), max(0, y1) # [source: 107]
    x2c, y2c = min(frame.shape[1], x2), min(frame.shape[0], y2) # [source: 107]

    # Calculate dimensions of the clipped ROI and the corresponding slice of menu_frame
    roi_h, roi_w = y2c - y1c, x2c - x1c # [source: 108]
    menu_start_y, menu_start_x = max(0, -y1), max(0, -x1) # Offset if menu starts off-screen # [source: 108]
    menu_end_y, menu_end_x = menu_start_y + roi_h, menu_start_x + roi_w # [source: 108]

    if roi_h > 0 and roi_w > 0 and menu_end_y <= menu_h and menu_end_x <= menu_w: # [source: 108]
        try: # [source: 108]
            roi = frame[y1c:y2c, x1c:x2c] # [source: 108]
            menu_frame_slice = menu_frame[menu_start_y:menu_end_y, menu_start_x:menu_end_x] # [source: 109]

            if roi.shape == menu_frame_slice.shape: # [source: 109]
                alpha = 0.85 # Opacity # [source: 109]
                cv2.addWeighted(menu_frame_slice, alpha, roi, 1.0 - alpha, 0, roi) # [source: 109]
            else: # [source: 109]
                logger.warning(f"ROI shape {roi.shape} mismatch with menu slice {menu_frame_slice.shape}. Drawing fallback.") # [source: 110]
                cv2.rectangle(frame, (x1c, y1c), (x2c, y2c), (50, 50, 50), -1) # Fallback # [source: 110]
        except Exception as e: # [source: 110]
            logger.exception(f"Error blending menu: {e}. ROI shape: {roi.shape if 'roi' in locals() else 'N/A'}") # [source: 110]
            # Draw fallback rectangle on error
            cv2.rectangle(frame, (x1c, y1c), (x2c, y2c), (50, 0, 0), -1) # [source: 110]
    elif roi_h <= 0 or roi_w <= 0: # [source: 111]
         logger.debug("Menu overlay ROI has zero or negative size, skipping overlay.") # [source: 111]
    else: # [source: 111]
         logger.warning("Menu slice calculation resulted in out-of-bounds indices, skipping overlay.") # [source: 111]