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

from constants import UIConstants  # Updated to class-based import
from menu_utils import _draw_button  # Import from menu_utils.py

# Set up logging
logger = logging.getLogger(__name__)

def reset_game(game_state: Any) -> None:
    """
    Reset the game state fully.
    """
    game_state.score = 0
    game_state.scoring_zones.clear()
    game_state.tracked_balls.clear()
    game_state.scored_balls.clear()
    game_state.scored_positions.clear()
    game_state.potential_small_balls_white.clear()
    game_state.potential_small_balls_red.clear()
    game_state.next_ball_id = 0
    game_state.menu_active = False
    game_state.submenu_active = None
    game_state.submenu_items = []
    game_state.game_timer = None
    game_state.ball_trails.clear()
    game_state.ball_states.clear()
    game_state.previous_ball_states.clear()
    # Note: high_score and time_limit not reset to preserve game settings
    if game_state.debug_mode:
        logger.infome.info("Game reset: All state variables cleared, menu closed")

def save_zones(scoring_zones: List[Tuple[int, int, int, int, int]]) -> bool:
    """
    Save scoring zones to a JSON file.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        with open(UIConstants.SCORING_ZONES_FILE, "w", encoding='utf-8') as f:
            json.dump(scoring_zones, f)
        logger.info(f"Scoring zones saved to {UIConstants.SCORING_ZONES_FILE}")
        return True
    except (IOError, PermissionError) as e:
        logger.error(f"Failed to save scoring zones to {UIConstants.SCORING_ZONES_FILE}: {e}")
        return False

def load_zones(scoring_zones: List[Tuple[int, int, int, int, int]]) -> List[Tuple[int, int, int, int, int]]:
    """
    Load scoring zones from a JSON file if it exists.

    Returns:
        Updated list of scoring zones.
    """
    if os.path.exists(UIConstants.SCORING_ZONES_FILE):
        if os.path.getsize(UIConstants.SCORING_ZONES_FILE) == 0:
            logger.warning(f"{UIConstants.SCORING_ZONES_FILE} is empty, treating as if it doesn't exist")
            return scoring_zones
        try:
            with open(UIConstants.SCORING_ZONES_FILE, "r", encoding='utf-8') as f:
                loaded_zones = json.load(f)
                scoring_zones.extend(loaded_zones)
            logger.info(f"Scoring zones loaded from {UIConstants.SCORING_ZONES_FILE}")
        except (json.JSONDecodeError, IOError, PermissionError) as e:
            logger.error(f"Failed to load scoring zones: {e}")
    else:
        logger.info(f"{UIConstants.SCORING_ZONES_FILE} does not exist, starting with empty zones")
    return scoring_zones

def clear_zones(scoring_zones: List[Tuple[int, int, int, int, int]]) -> List[Tuple[int, int, int, int, int]]:
    """
    Clear saved scoring zones and reset the current zones.

    Returns:
        Empty list of scoring zones.
    """
    scoring_zones.clear()
    if os.path.exists(UIConstants.SCORING_ZONES_FILE):
        try:
            os.remove(UIConstants.SCORING_ZONES_FILE)
            logger.info(f"Scoring zones file {UIConstants.SCORING_ZONES_FILE} removed")
        except (IOError, PermissionError) as e:
            logger.error(f"Failed to remove {UIConstants.SCORING_ZONES_FILE}: {e}")
    logger.info("Scoring zones cleared")
    return scoring_zones

def draw_menu(frame: np.ndarray, game_state: Any) -> None:
    """
    Draw the menu button on the main game window.
    """
    _draw_button(frame, UIConstants.MENU_BUTTON_X, UIConstants.MENU_BUTTON_Y,
                 UIConstants.MENU_BUTTON_WIDTH, UIConstants.MENU_BUTTON_HEIGHT,
                 "Click for Menu", UIConstants.CV2_BLUE)  # Updated to use CV2_BLUE

def _create_menu_base(game_state: Any) -> np.ndarray:
    """Create the static base of the menu frame."""
    menu_frame = np.zeros((game_state.menu_height, game_state.menu_width, 3), dtype=np.uint8)
    menu_frame[:] = (50, 50, 50)  # Dark gray background
    overlay = np.ones_like(menu_frame, dtype=np.uint8) * 255
    alpha = 0.8
    menu_frame = cv2.addWeighted(menu_frame, alpha, overlay, 1 - alpha, 0)
    _draw_button(menu_frame, 0, 0, game_state.menu_width, 30, "Menu", UIConstants.CV2_BLUE, UIConstants.FONT_SCALE_MEDIUM)  # Updated
    _draw_button(menu_frame, game_state.menu_width - 30, 0, 30, 30, "X", UIConstants.RED, UIConstants.FONT_SCALE_MEDIUM)  # Updated
    for mx, my, mw, mh, label, _ in game_state.menu_items:
        _draw_button(menu_frame, mx, my - 110, mw, mh, label, UIConstants.CV2_BLUE)  # Updated
    return menu_frame

def _draw_menu_content(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the dynamic content of the menu based on the active submenu."""
    # Import submenu functions here to avoid circular imports
    from submenus import (
        _draw_settings_submenu,
        _draw_help_submenu,
        _draw_faq_submenu,
        _draw_about_submenu,
        _draw_leaderboard_submenu,
        _draw_players_submenu,
        _draw_achievements_submenu
    )
    if game_state.submenu_active == "Settings":
        _draw_settings_submenu(menu_frame, game_state)
    elif game_state.submenu_active == "Help":
        _draw_help_submenu(menu_frame)
    elif game_state.submenu_active == "FAQ":
        _draw_faq_submenu(menu_frame)
    elif game_state.submenu_active == "About":
        _draw_about_submenu(menu_frame, game_state)
    elif game_state.submenu_active == "Leaderboard":
        _draw_leaderboard_submenu(menu_frame, game_state)
    elif game_state.submenu_active == "Players":
        _draw_players_submenu(menu_frame, game_state)
    elif game_state.submenu_active == "Achievements":
        _draw_achievements_submenu(menu_frame, game_state)
    elif game_state.submenu_active:
        for smx, smy, smw, smh, label, _ in game_state.submenu_items:
            _draw_button(menu_frame, smx, smy, smw, smh, label, UIConstants.CV2_BLUE)  # Updated

def _overlay_menu(frame: np.ndarray, menu_frame: np.ndarray, game_state: Any) -> None:
    """Overlay the menu onto the main frame."""
    x1, y1 = game_state.menu_pos_x, game_state.menu_pos_y
    x2, y2 = x1 + game_state.menu_width, y1 + game_state.menu_height
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(frame.shape[1], x2)
    y2 = min(frame.shape[0], y2)
    menu_h, menu_w = y2 - y1, x2 - x1
    if menu_h > 0 and menu_w > 0:
        roi = frame[y1:y2, x1:x2]
        menu_frame_resized = menu_frame[:menu_h, :menu_w]
        alpha = 0.8
        beta = 1.0 - alpha
        cv2.addWeighted(menu_frame_resized, alpha, roi, beta, 0, roi)

def draw_menu_window(frame: np.ndarray, game_state: Any) -> None:
    """
    Draw the menu as an overlay within the main game window.
    """
    if game_state.debug_mode:
        logger.debug(f"draw_menu_window: menu_active={game_state.menu_active}, "
                     f"submenu_active={game_state.submenu_active}, len(submenu_items)={len(game_state.submenu_items)}")
    if not game_state.menu_active:
        return
    menu_frame = _create_menu_base(game_state)
    _draw_menu_content(menu_frame, game_state)
    _overlay_menu(frame, menu_frame, game_state)