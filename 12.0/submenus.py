# submenus.py
"""
Submenu rendering and logic for the Whiffle Tracker project.

This module contains functions to render and manage the core submenus
and dispatch drawing to specific submenu functions.
"""

import cv2
import numpy as np
import logging
from typing import List, Tuple, Callable, Any, Optional
from math import ceil

# Import constants, including MenuConstants
from constants import UIConstants, GameConstants, ScoringConstants, MenuConstants
from menu_utils import _draw_button, show_splash_on_click

# Import the drawing functions from the new file
from submenu_draw_functions import (
    _draw_leaderboard_submenu,
    _draw_players_submenu,
    _draw_achievements_submenu,
    _draw_help_submenu,
    _draw_faq_submenu,
    _draw_about_submenu,
    _draw_edit_zones_submenu,
)

# Import GameState for type hinting if needed, but avoid direct use that causes cycles
from game_state import GameState # Assuming GameState is the type hint

logger = logging.getLogger(__name__)


# --- Helper for Toggle Items ---
class ToggleItem:
    """Represents a toggleable menu item with state and action."""

    def __init__(
        self, label: str, get_state: Callable[[], bool], action: Callable[[], None]
    ):
        self.label = label
        self.get_state = get_state
        self.action = action


# --- Core Submenu Drawing Functions ---


def _draw_settings_submenu(menu_frame: np.ndarray, game_state: GameState) -> None:
    """Draw the Settings submenu with toggle items."""
    cv2.putText(
        menu_frame,
        "Settings",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    settings_items = [
        ToggleItem(
            "Game Sounds",
            lambda: game_state.game_sounds_on,
            lambda: setattr(
                game_state, "game_sounds_on", not game_state.game_sounds_on
            ),
        ),
        ToggleItem(
            "Background Music",
            lambda: game_state.background_music_on,
            lambda: [
                setattr(
                    game_state,
                    "background_music_on",
                    not game_state.background_music_on,
                ),
                game_state.toggle_background_music(), # Call the method to play/stop
            ],
        ),
        ToggleItem(
            "Visual Debug Overlay",
            lambda: game_state.show_debug_overlay,
            lambda: setattr(
                game_state, "show_debug_overlay", not game_state.show_debug_overlay
            ),
        ),
        ToggleItem(
            "General Debug Mode",
            lambda: game_state.debug_mode,
            lambda: setattr(game_state, "debug_mode", not game_state.debug_mode),
        ),
    ]

    y_offset = 80
    item_height = 35
    toggle_width = 80

    game_state.submenu_items.clear()

    for item in settings_items:
        state = item.get_state()
        label_text = f"{item.label}:"
        state_text = "ON" if state else "OFF"
        state_color = UIConstants.GREEN if state else UIConstants.RED

        cv2.putText(
            menu_frame,
            label_text,
            (20, y_offset + 20), # Adjusted y for vertical centering
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            1,
        )

        button_x = menu_frame.shape[1] - toggle_width - 20
        button_y = y_offset
        button_w = toggle_width
        button_h = item_height

        # Draw the toggle button
        cv2.rectangle(
            menu_frame,
            (button_x, button_y),
            (button_x + button_w, button_y + button_h),
            state_color,
            -1,
        )
        # Center the ON/OFF text within the button
        (text_width, text_height), _ = cv2.getTextSize(state_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, 1)
        text_x = button_x + (button_w - text_width) // 2
        text_y = button_y + (button_h + text_height) // 2 # Adjusted for vertical centering

        cv2.putText(
            menu_frame,
            state_text,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            1,
            cv2.LINE_AA
        )

        game_state.submenu_items.append(
            ((button_x, button_y, button_w, button_h), item.action, item.label)
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

    # Dynamically adjust menu height based on content
    game_state.menu_height = back_y + item_height + 20


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

    # Add "fun" mode to the list
    modes = ["classic", "timed", "fun", "practice"]
    y_offset = 80
    item_height = 35
    game_state.submenu_items.clear()

    for mode in modes:
        label = mode.capitalize()
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

    game_state.menu_height = y_offset + 20 # Adjust height based on fixed number of items


# --- Main Submenu Dispatcher ---


def draw_submenu(menu_frame: np.ndarray, game_state: GameState) -> None:
    """
    Draw the currently active submenu.
    """
    submenu_draw_functions = {
        "settings": _draw_settings_submenu,
        "game_mode": _draw_game_mode_submenu,
        "manage_zones": _draw_zone_submenu,
        "edit_zones": _draw_edit_zones_submenu,
        "leaderboard": _draw_leaderboard_submenu,
        "players": _draw_players_submenu,
        "achievements": _draw_achievements_submenu,
        "help": _draw_help_submenu,
        "faq": _draw_faq_submenu,
        "about": _draw_about_submenu,
    }

    draw_func = submenu_draw_functions.get(game_state.submenu_active)
    if draw_func:
        # Default height, the specific draw function should override this if needed
        game_state.menu_height = 450
        game_state.submenu_items.clear() # Clear items before drawing
        draw_func(menu_frame, game_state)
    else:
        # Handle case where submenu_active might be invalid or None unexpectedly
        if game_state.submenu_active is not None:
             logger.warning(f"No draw function found for submenu: {game_state.submenu_active}. Drawing error message.")
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
             _draw_button(menu_frame, 20, 80, menu_frame.shape[1] - 40, 35, "Back", UIConstants.CV2_BLUE, UIConstants.FONT_SCALE_MEDIUM)
             game_state.submenu_items = [((20, 80, menu_frame.shape[1] - 40, 35), "back_to_main", "Back")]
             game_state.menu_height = 135 # Minimal height for error message and back button
        else:
             # This case should ideally be handled before calling draw_submenu,
             # but log it if it occurs.
             logger.error("draw_submenu called with game_state.submenu_active being None.")