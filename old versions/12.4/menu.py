# menu.py
"""
Menu rendering functions for the Whiffle Tracker project.

This module provides functions to manage the main game menu, including rendering
the menu button and overlaying the menu on the game window.
Zone management functions have been moved to game_state_helpers.py.
"""

import cv2
import numpy as np
import logging
# Removed: import json
# Removed: import os
from typing import List, Tuple, Any

# Import constants, including MenuConstants
from constants import UIConstants, GameConstants, ScoringConstants, MenuConstants
from menu_utils import _draw_button

# Import submenu functions here to avoid circular imports within _draw_menu_content
from submenus import draw_submenu

# Import GameState class and CurrentGameState enum from NEW location
from game_state import GameState # Keep import for GameState class
from game_types import CurrentGameState # Import Enum from new location

# Removed imports from game_state_helpers/utils

# Set up logging
logger = logging.getLogger(__name__)


# --- REMOVED Zone Management Functions ---
# --- REMOVED reset_game function ---


def draw_menu(frame: np.ndarray, game_state: GameState) -> None:
    """Draw the menu button on the frame."""
    # (Code unchanged)
    if game_state.current_state == CurrentGameState.PLAYING and not game_state.drawing:
        _draw_button(frame, UIConstants.MENU_BUTTON_X, UIConstants.MENU_BUTTON_Y, UIConstants.MENU_BUTTON_WIDTH, UIConstants.MENU_BUTTON_HEIGHT, "Menu", UIConstants.CV2_BLUE)


def _draw_menu_content(menu_frame: np.ndarray, game_state: GameState) -> None:
    """Draw the actual content of the menu or submenu onto the menu_frame."""
    # (Code unchanged)
    if game_state.submenu_active:
        draw_submenu(menu_frame, game_state)
    else:
        cv2.putText(menu_frame,"Main Menu",(30, 40),cv2.FONT_HERSHEY_SIMPLEX,UIConstants.FONT_SCALE_LARGE,UIConstants.WHITE,UIConstants.FONT_THICKNESS)
        game_state.submenu_items.clear()
        y_offset = 80; item_height = 35
        for label, action_key in MenuConstants.MAIN_MENU_ITEMS:
            item_rect = (20, y_offset, game_state.menu_width - 40, item_height)
            _draw_button(menu_frame, item_rect[0], item_rect[1], item_rect[2], item_rect[3], label, UIConstants.CV2_BLUE, font_scale=UIConstants.FONT_SCALE_MEDIUM)
            game_state.submenu_items.append((item_rect, action_key, label))
            y_offset += item_height + 5


def draw_menu_window(frame: np.ndarray, game_state: GameState) -> None:
    """Draw the menu as an overlay, using caching."""
    if game_state.current_state != CurrentGameState.MENU: return

    # --- Start CORRECTED Height Calculation ---
    default_height = 450
    menu_height_to_use = default_height # Fallback default

    if game_state.submenu_active is None: # Explicitly check for Main Menu
        # Calculate height based on MAIN_MENU_ITEMS
        header_height = 80 # Approx space for title
        item_height_with_padding = 35 + 5 # Height of button + padding
        num_main_items = len(MenuConstants.MAIN_MENU_ITEMS)
        footer_padding = 20 # Extra space at the bottom
        estimated_height = header_height + (num_main_items * item_height_with_padding) + footer_padding
        menu_height_to_use = max(300, estimated_height) # Ensure minimum height
        logger.debug(f"Calculated main menu height: {menu_height_to_use} based on {num_main_items} items.")
    elif hasattr(game_state, "menu_height") and game_state.menu_height > 100:
        # Use height set by the specific submenu drawing function if available
        menu_height_to_use = game_state.menu_height
        logger.debug(f"Using submenu defined height: {menu_height_to_use}")
    else:
        # Fallback if submenu doesn't set height (should ideally not happen)
        logger.warning(f"Submenu '{game_state.submenu_active}' did not set menu_height. Using default: {default_height}")
        menu_height_to_use = default_height
    # --- End CORRECTED Height Calculation ---

    game_state.menu_width = getattr(game_state, 'menu_width', 600); # Keep width consistent
    if game_state.menu_width <= 0: game_state.menu_width = 600

    # --- Cache Key Generation (minor update for clarity) ---
    current_item_actions = tuple(item[1] if len(item) > 1 else None for item in getattr(game_state, 'submenu_items', []))
    cache_key_parts = [
        game_state.submenu_active, current_item_actions,
        getattr(game_state, 'editing_zone_index', None), getattr(game_state, 'editing_zone_mode', None), getattr(game_state, 'editing_zone_points_input', None),
        getattr(game_state, 'editing_player_index', None), getattr(game_state, 'editing_player_mode', None), getattr(game_state, 'editing_player_name_input', None),
        getattr(game_state, 'current_player_index', 0),
        # Add parts relevant to specific submenus for redraw triggers
        getattr(game_state, 'edit_zones_current_page', 1) if game_state.submenu_active == "edit_zones" else None,
        getattr(game_state, 'current_sound_volume', 0.0) if game_state.submenu_active == "settings" else None,
        getattr(game_state, 'current_music_volume', 0.0) if game_state.submenu_active == "settings" else None,
        getattr(game_state, 'game_sounds_on', True) if game_state.submenu_active == "settings" else None,
        getattr(game_state, 'background_music_on', True) if game_state.submenu_active == "settings" else None,
        # Add leaderboard mode if it affects display
        getattr(game_state, 'leaderboard_mode', 'classic') if game_state.submenu_active == "leaderboard" else None,
    ]
    cache_key = tuple(filter(lambda x: x is not None, cache_key_parts)) # Use only non-None parts

    # --- Cache Check & Redraw ---
    menu_frame = None
    cache_valid = (
        hasattr(game_state, "menu_cache") and game_state.menu_cache is not None and
        hasattr(game_state, "menu_cache_key") and game_state.menu_cache_key == cache_key and
        game_state.menu_cache.shape[0] == menu_height_to_use and # Check against calculated height
        game_state.menu_cache.shape[1] == game_state.menu_width
    )

    if cache_valid:
        menu_frame = game_state.menu_cache
    else:
        logger.debug(f"Redrawing menu. Cache key mismatch or dimensions changed. New HxW: {menu_height_to_use}x{game_state.menu_width}")
        menu_frame = np.zeros((menu_height_to_use, game_state.menu_width, 3), dtype=np.uint8)
        game_state.menu_height = menu_height_to_use # Store the height actually used for drawing
        _draw_menu_content(menu_frame, game_state) # Draw content

        # Draw close button before caching
        try:
            pad=UIConstants.MENU_CLOSE_BUTTON_PADDING; size=UIConstants.MENU_CLOSE_BUTTON_SIZE; btn_x1=game_state.menu_width-pad-size; btn_y1=pad; btn_x2=game_state.menu_width-pad; btn_y2=pad+size; line_pad=size//4
            cv2.line(menu_frame, (btn_x1+line_pad, btn_y1+line_pad), (btn_x2-line_pad, btn_y2-line_pad), UIConstants.MENU_CLOSE_BUTTON_COLOR, UIConstants.MENU_CLOSE_BUTTON_THICKNESS, cv2.LINE_AA)
            cv2.line(menu_frame, (btn_x1+line_pad, btn_y2-line_pad), (btn_x2-line_pad, btn_y1+line_pad), UIConstants.MENU_CLOSE_BUTTON_COLOR, UIConstants.MENU_CLOSE_BUTTON_THICKNESS, cv2.LINE_AA)
        except Exception as e: logger.error(f"Error drawing menu close button: {e}")

        game_state.menu_cache = menu_frame
        game_state.menu_cache_key = cache_key

    # --- Blending menu onto main frame ---
    # (Code unchanged)
    start_x = (frame.shape[1] - game_state.menu_width) // 2; start_y = (frame.shape[0] - game_state.menu_height) // 2
    game_state.menu_pos = (start_x, start_y); x1, y1 = game_state.menu_pos
    menu_h_actual, menu_w_actual = menu_frame.shape[:2]; x2, y2 = x1 + menu_w_actual, y1 + menu_h_actual
    x1c, y1c = max(0, x1), max(0, y1); x2c, y2c = min(frame.shape[1], x2), min(frame.shape[0], y2)
    roi_h, roi_w = y2c - y1c, x2c - x1c
    menu_start_y, menu_start_x = max(0, -y1), max(0, -x1); menu_end_y, menu_end_x = menu_start_y + roi_h, menu_start_x + roi_w

    if roi_h > 0 and roi_w > 0 and menu_end_y <= menu_h_actual and menu_end_x <= menu_w_actual:
        try:
            roi = frame[y1c:y2c, x1c:x2c]; menu_frame_slice = menu_frame[menu_start_y:menu_end_y, menu_start_x:menu_end_x]
            if roi.shape == menu_frame_slice.shape:
                alpha = 0.85; cv2.addWeighted(menu_frame_slice, alpha, roi, 1.0 - alpha, 0, roi)
                cv2.rectangle(frame, (x1c, y1c), (x2c, y2c), UIConstants.WHITE, 2)
            else: logger.warning("ROI/menu slice shape mismatch"); cv2.rectangle(frame, (x1c, y1c), (x2c, y2c), (50,50,50), -1)
        except Exception as e: logger.exception(f"Error blending menu: {e}"); cv2.rectangle(frame, (x1c, y1c), (x2c, y2c), (50,0,0), -1)