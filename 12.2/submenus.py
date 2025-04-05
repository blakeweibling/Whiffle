import submenu_draw_functions
import os
import cv2
import numpy as np
import logging
from typing import List, Tuple, Callable, Any, Optional
from math import ceil

# Import constants, including MenuConstants
from constants import UIConstants, GameConstants, ScoringConstants, MenuConstants
from menu_utils import _draw_button, show_splash_on_click

# Import the drawing functions from the new file
# Note: _draw_settings_submenu is now intended to be used FROM submenu_draw_functions
from submenu_draw_functions import (
    _draw_leaderboard_submenu,
    _draw_players_submenu,
    _draw_achievements_submenu,
    _draw_help_submenu,
    _draw_faq_submenu,
    _draw_about_submenu,
    _draw_edit_zones_submenu,
    _draw_settings_submenu, # Ensure this is imported if not already
)

# Import GameState for type hinting if needed, but avoid direct use that causes cycles
from game_state import GameState  # Assuming GameState is the type hint

logger = logging.getLogger(__name__)


# --- REMOVED Redundant/Incorrect Local _draw_settings_submenu Definition ---
# The local definition that used lambdas has been removed.


# --- UPDATED: Added "survival" mode to list ---
def _draw_game_mode_submenu(menu_frame: np.ndarray, game_state: GameState) -> None:
    """Draw the Game Mode selection submenu."""
    cv2.putText(
        menu_frame,
        "Select Game Mode",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    # Add "survival" mode to the list
    modes = ["classic", "timed", "fun", "practice", "survival"] # Added survival
    y_offset = 80
    item_height = 35
    game_state.submenu_items.clear()

    for mode in modes:
        label = mode.capitalize()
        # Highlight the currently active mode
        color = (
            UIConstants.GREEN if game_state.game_mode == mode else UIConstants.CV2_BLUE
        )
        action_key = f"set_mode_{mode}"

        _draw_button(
            menu_frame,
            20,
            y_offset,
            menu_frame.shape[1] - 40,
            item_height,
            label,
            color,
            UIConstants.FONT_SCALE_MEDIUM,
        )
        game_state.submenu_items.append(
            (
                (20, y_offset, menu_frame.shape[1] - 40, item_height),
                action_key,
                label,
            )
        )
        y_offset += item_height + 5

    back_y = y_offset + 10
    _draw_button(
        menu_frame,
        20,
        back_y,
        menu_frame.shape[1] - 40,
        item_height,
        "Back",
        UIConstants.CV2_BLUE,
        UIConstants.FONT_SCALE_MEDIUM,
    )
    game_state.submenu_items.append(
        (
            (20, back_y, menu_frame.shape[1] - 40, item_height),
            "back_to_main",
            "Back",
        )
    )
    game_state.menu_height = back_y + item_height + 20
# --- END UPDATE ---


def _draw_zone_submenu(menu_frame: np.ndarray, game_state: GameState) -> None:
    """Draw the Manage Zones submenu."""
    cv2.putText(
        menu_frame,
        "Manage Zones",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    y_offset = 80
    item_height = 35
    game_state.submenu_items.clear()

    for label, action_key in MenuConstants.ZONE_SUBMENU_ITEMS:
        _draw_button(
            menu_frame,
            20,
            y_offset,
            menu_frame.shape[1] - 40,
            item_height,
            label,
            UIConstants.CV2_BLUE,
            UIConstants.FONT_SCALE_MEDIUM,
        )
        game_state.submenu_items.append(
            (
                (20, y_offset, menu_frame.shape[1] - 40, item_height),
                action_key,
                label,
            )
        )
        y_offset += item_height + 5

    game_state.menu_height = (
        y_offset + 20
    )  # Adjust height based on fixed number of items


# --- Main Submenu Dispatcher ---

# --- UPDATED: Point to the imported _draw_settings_submenu ---
# Define the mapping dictionary
submenu_draw_functions_map = {
    "settings": _draw_settings_submenu, # Use the CORRECT imported function
    "game_mode": _draw_game_mode_submenu,
    "manage_zones": _draw_zone_submenu,
    "edit_zones": _draw_edit_zones_submenu, # Assumes this is also imported correctly
    "leaderboard": _draw_leaderboard_submenu, # Assumes this is also imported correctly
    "players": _draw_players_submenu, # Assumes this is also imported correctly
    "achievements": _draw_achievements_submenu, # Assumes this is also imported correctly
    "help": _draw_help_submenu, # Assumes this is also imported correctly
    "faq": _draw_faq_submenu, # Assumes this is also imported correctly
    "about": _draw_about_submenu, # Assumes this is also imported correctly
}
# --- END UPDATE ---

def draw_submenu(menu_frame: np.ndarray, game_state: GameState) -> None:
    """
    Draw the currently active submenu.
    """
    # Use the updated mapping dictionary
    draw_func = submenu_draw_functions_map.get(game_state.submenu_active)

    if draw_func:
        # Default height, the specific draw function should override this if needed
        game_state.menu_height = 450
        game_state.submenu_items.clear()  # Clear items before drawing
        draw_func(menu_frame, game_state)
    else:
        # Handle case where submenu_active might be invalid or None unexpectedly
        if game_state.submenu_active is not None:
            logger.warning(
                f"No draw function found for submenu: {game_state.submenu_active}. Drawing error message."
            )
            cv2.putText(
                menu_frame,
                f"Error: Unknown Submenu '{game_state.submenu_active}'",
                (30, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_MEDIUM,
                UIConstants.RED,
                UIConstants.FONT_THICKNESS,
            )
            # Provide a Back button as a fallback
            _draw_button(
                menu_frame,
                20,
                80,
                menu_frame.shape[1] - 40,
                35,
                "Back",
                UIConstants.CV2_BLUE,
                UIConstants.FONT_SCALE_MEDIUM,
            )
            game_state.submenu_items = [
                ((20, 80, menu_frame.shape[1] - 40, 35), "back_to_main", "Back")
            ]
            game_state.menu_height = (
                135  # Minimal height for error message and back button
            )
        else:
            # This case should ideally be handled before calling draw_submenu,
            # but log it if it occurs.
            logger.error(
                "draw_submenu called with game_state.submenu_active being None."
            )