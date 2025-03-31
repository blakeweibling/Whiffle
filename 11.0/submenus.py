"""
Submenu rendering and logic for the Whiffle Tracker project.

This module contains functions to render and manage the core submenus 
and dispatch drawing to specific submenu functions.
"""

import cv2
import numpy as np
import logging
from typing import List, Tuple, Callable, Any, Optional

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
)


logger = logging.getLogger(__name__)


# --- Helper for Toggle Items ---
class ToggleItem:
    """Represents a toggleable menu item with state and action."""

    def __init__(
        self, label: str, get_state: Callable[[], bool], action: Callable[[], None]
    ): #
        self.label = label #
        self.get_state = get_state #
        self.action = action #


# --- Core Submenu Drawing Functions ---


def _draw_settings_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Settings submenu with toggle items.""" #
    cv2.putText(
        menu_frame,
        "Settings",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX, #
        UIConstants.FONT_SCALE_LARGE, #
        UIConstants.WHITE, #
        UIConstants.FONT_THICKNESS, #
    )

    settings_items = [
        ToggleItem(
            "Game Sounds", #
            lambda: game_state.game_sounds_on, #
            lambda: setattr(
                game_state, "game_sounds_on", not game_state.game_sounds_on #
            ),
        ),
        ToggleItem(
            "Background Music", #
            lambda: game_state.background_music_on, #
            lambda: [
                setattr(
                    game_state, #
                    "background_music_on", #
                    not game_state.background_music_on, #
                ),
                game_state.toggle_background_music(), #
            ],
        ), #
        ToggleItem(
            "Visual Debug Overlay", #
            lambda: game_state.show_debug_overlay, #
            lambda: setattr(
                game_state, "show_debug_overlay", not game_state.show_debug_overlay #
            ),
        ),
        ToggleItem(
            "General Debug Mode", #
            lambda: game_state.debug_mode, #
            lambda: setattr(game_state, "debug_mode", #
                            not game_state.debug_mode), #
        ),
    ]

    y_offset = 80 #
    item_height = 35 #
    toggle_width = 80 #

    game_state.submenu_items.clear() #

    for item in settings_items: #
        state = item.get_state() #
        label_text = f"{item.label}:" #
        state_text = "ON" if state else "OFF" #
        state_color = UIConstants.GREEN if state else UIConstants.RED #

        cv2.putText(
            menu_frame,
            label_text,
            (20, y_offset + 20), #
            cv2.FONT_HERSHEY_SIMPLEX, #
            UIConstants.FONT_SCALE_MEDIUM, #
            UIConstants.WHITE, #
            1, #
        )

        button_x = menu_frame.shape[1] - toggle_width - 20 #
        button_y = y_offset #
        button_w = toggle_width #
        button_h = item_height #

        cv2.rectangle(
            menu_frame,
            (button_x, button_y), #
            (button_x + button_w, button_y + button_h), #
            state_color, #
            -1, #
        )
        cv2.putText(
            menu_frame, #
            state_text, #
            (button_x + 10, button_y + 20), #
            cv2.FONT_HERSHEY_SIMPLEX, #
            UIConstants.FONT_SCALE_MEDIUM, #
            UIConstants.WHITE, #
            1, #
        )

        game_state.submenu_items.append(
            ((button_x, button_y, button_w, button_h), item.action, item.label) #
        )
        y_offset += item_height + 5 #

    back_y = y_offset + 10 #
    _draw_button(
        menu_frame,
        20, #
        back_y, #
        menu_frame.shape[1] - 40, #
        item_height, #
        "Back", #
        UIConstants.CV2_BLUE, #
        UIConstants.FONT_SCALE_MEDIUM, #
    )
    game_state.submenu_items.append(
        ((20, back_y, menu_frame.shape[1] - 40, #
         item_height), "back_to_main", "Back") #
    )

    game_state.menu_height = back_y + item_height + 20 #


def _draw_game_mode_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Game Mode selection submenu.""" #
    cv2.putText(
        menu_frame,
        "Select Game Mode",
        (30, 40), #
        cv2.FONT_HERSHEY_SIMPLEX, #
        UIConstants.FONT_SCALE_LARGE, #
        UIConstants.WHITE, #
        UIConstants.FONT_THICKNESS, #
    )

    modes = ["classic", "timed", "practice"] #
    y_offset = 80 #
    item_height = 35 #
    game_state.submenu_items.clear() #

    for mode in modes: #
        label = mode.capitalize() #
        color = (
            UIConstants.GREEN if game_state.game_mode == mode else UIConstants.CV2_BLUE #
        )
        action_key = f"set_mode_{mode}" #

        _draw_button(
            menu_frame,
            20, #
            y_offset, #
            menu_frame.shape[1] - 40, #
            item_height, #
            label, #
            color, #
            UIConstants.FONT_SCALE_MEDIUM, #
        )
        game_state.submenu_items.append(
            ((20, y_offset, menu_frame.shape[1] - #
             40, item_height), action_key, label) #
        )
        y_offset += item_height + 5 #

    back_y = y_offset + 10 #
    _draw_button(
        menu_frame,
        20, #
        back_y, #
        menu_frame.shape[1] - 40, #
        item_height, #
        "Back", #
        UIConstants.CV2_BLUE, #
        UIConstants.FONT_SCALE_MEDIUM, #
    )
    game_state.submenu_items.append(
        ((20, back_y, menu_frame.shape[1] - 40, #
         item_height), "back_to_main", "Back") #
    )
    game_state.menu_height = back_y + item_height + 20 #


def _draw_zone_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Manage Zones submenu.""" #
    cv2.putText(
        menu_frame,
        "Manage Zones", #
        (30, 40), #
        cv2.FONT_HERSHEY_SIMPLEX, #
        UIConstants.FONT_SCALE_LARGE, #
        UIConstants.WHITE, #
        UIConstants.FONT_THICKNESS, #
    )

    y_offset = 80 #
    item_height = 35 #
    game_state.submenu_items.clear() #

    # Assuming ZONE_SUBMENU_ITEMS is correctly imported via MenuConstants
    for label, action_key in MenuConstants.ZONE_SUBMENU_ITEMS: #
        _draw_button(
            menu_frame,
            20, #
            y_offset, #
            menu_frame.shape[1] - 40, #
            item_height, #
            label, #
            UIConstants.CV2_BLUE, #
            UIConstants.FONT_SCALE_MEDIUM, #
        )
        game_state.submenu_items.append(
            ((20, y_offset, menu_frame.shape[1] - #
             40, item_height), action_key, label) #
        )
        y_offset += item_height + 5 #

    # NOTE: Removed Back button logic here as ZONE_SUBMENU_ITEMS likely contains 'Back'
    game_state.menu_height = y_offset + 20 #


def _draw_edit_zones_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Edit Zones submenu.""" #
    cv2.putText(
        menu_frame,
        "Edit Scoring Zones", #
        (30, 40), #
        cv2.FONT_HERSHEY_SIMPLEX, #
        UIConstants.FONT_SCALE_LARGE, #
        UIConstants.WHITE, #
        UIConstants.FONT_THICKNESS, #
    )

    y_offset = 80 #
    item_height = 30 #
    button_width = 60 #
    button_spacing = 5 #
    list_width = menu_frame.shape[1] - 40 - \
        (button_width * 2 + button_spacing * 2) #

    game_state.submenu_items.clear() #

    confirm_delete_message = None #
    if (
        game_state.editing_zone_mode == "confirm_delete" #
        and game_state.editing_zone_index is not None #
    ):
        confirm_delete_message = f"Click Delete again for Zone {game_state.editing_zone_index + 1} to confirm?" #
    edit_instruction_message = None #
    if (
        game_state.editing_zone_mode == "edit_points" #
        and game_state.editing_zone_index is not None #
    ):
        edit_instruction_message = "Enter points (0-9), Bksp=Delete, Enter=Save" #

    top_message = confirm_delete_message or edit_instruction_message #
    if top_message: #
        cv2.putText(
            menu_frame,
            top_message,
            (20, y_offset - 5), #
            cv2.FONT_HERSHEY_SIMPLEX, #
            UIConstants.FONT_SCALE_SMALL, #
            UIConstants.YELLOW, #
            1, #
        )
        y_offset += 15 #

    if not game_state.scoring_zones: #
        cv2.putText(
            menu_frame,
            "No zones defined.", #
            (20, y_offset + 20), #
            cv2.FONT_HERSHEY_SIMPLEX, #
            UIConstants.FONT_SCALE_MEDIUM, #
            UIConstants.WHITE, #
            1, #
        )
        y_offset += item_height + 5 #
    else: #
        cv2.putText(
            menu_frame,
            "Zone", #
            (20, y_offset - 5), #
            cv2.FONT_HERSHEY_SIMPLEX, #
            UIConstants.FONT_SCALE_SMALL, #
            UIConstants.YELLOW, #
            1, #
        ) #
        cv2.putText(
            menu_frame,
            "Actions", #
            (20 + list_width + button_spacing, y_offset - 5), #
            cv2.FONT_HERSHEY_SIMPLEX, #
            UIConstants.FONT_SCALE_SMALL, #
            UIConstants.YELLOW, #
            1, #
        )

        for i, zone in enumerate(game_state.scoring_zones): #
            x, y, w, h, points = zone #
            zone_label = f"{i+1}: @({x},{y}) Pts=" #
            label_color = UIConstants.WHITE #
            if (
                game_state.editing_zone_index == i #
                and game_state.editing_zone_mode == "edit_points" #
            ):
                input_display = (
                    game_state.editing_zone_points_input #
                    if game_state.editing_zone_points_input #
                    else "___" #
                )
                zone_label += f"[ {input_display} ]" #
                label_color = UIConstants.GREEN #
            else:
                zone_label += str(points) #

            cv2.putText( #
                menu_frame,
                zone_label[:35], #
                (20, y_offset + 20), #
                cv2.FONT_HERSHEY_SIMPLEX, #
                UIConstants.FONT_SCALE_SMALL, #
                label_color, #
                1, #
            )

            edit_x = 20 + list_width + button_spacing #
            edit_rect = (edit_x, y_offset, button_width, item_height) #
            edit_color = (
                UIConstants.GREEN #
                if game_state.editing_zone_index == i #
                and game_state.editing_zone_mode == "edit_points" #
                else UIConstants.CV2_BLUE #
            )
            _draw_button(
                menu_frame,
                edit_x, #
                y_offset, #
                button_width, #
                item_height, #
                "Edit", #
                edit_color, #
                UIConstants.FONT_SCALE_SMALL, #
            )
            game_state.submenu_items.append(
                (edit_rect, f"edit_zone_{i}", f"Edit Zone {i+1} Points") #
            )

            delete_x = edit_x + button_width + button_spacing #
            delete_rect = (delete_x, y_offset, button_width, item_height) #
            delete_color = ( #
                UIConstants.RED #
                if game_state.editing_zone_index == i #
                and game_state.editing_zone_mode == "confirm_delete" #
                else UIConstants.CV2_BLUE #
            )
            _draw_button( #
                menu_frame,
                delete_x, #
                y_offset, #
                button_width, #
                item_height, #
                "Delete", #
                delete_color, #
                UIConstants.FONT_SCALE_SMALL, #
            )
            game_state.submenu_items.append(
                (delete_rect, f"delete_zone_{i}", f"Delete Zone {i+1}") #
            )

            y_offset += item_height + 5 #

    back_y = y_offset + 10 #
    item_height = 35 # # Reset item height for Back button
    _draw_button(
        menu_frame,
        20, #
        back_y, #
        menu_frame.shape[1] - 40, #
        item_height, #
        "Back", #
        UIConstants.CV2_BLUE, #
        UIConstants.FONT_SCALE_MEDIUM, #
    )
    game_state.submenu_items.append( #
        (
            (20, back_y, menu_frame.shape[1] - 40, item_height), #
            "back_to_manage_zones", #
            "Back", #
        )
    )
    game_state.menu_height = back_y + item_height + 20 #


# --- Main Submenu Dispatcher ---


def draw_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """
    Draw the currently active submenu.
    """ #
    submenu_draw_functions = {
        "settings": _draw_settings_submenu, #
        "game_mode": _draw_game_mode_submenu, #
        "manage_zones": _draw_zone_submenu, #
        "edit_zones": _draw_edit_zones_submenu, #
        "leaderboard": _draw_leaderboard_submenu, #
        "players": _draw_players_submenu,  # Handles player list and editing UI #
        "achievements": _draw_achievements_submenu, #
        "help": _draw_help_submenu, #
        "faq": _draw_faq_submenu, #
        "about": _draw_about_submenu, #
    }

    draw_func = submenu_draw_functions.get(game_state.submenu_active) #
    if draw_func: #
        game_state.menu_height = 400  # Default height, function can override #
        draw_func(menu_frame, game_state) #
    else: #
        if game_state.submenu_active is not None: #
            logger.warning(
                f"No draw function found for submenu: {game_state.submenu_active}" #
            ) #
            cv2.putText(
                menu_frame,
                f"Error: Unknown Submenu '{game_state.submenu_active}'", #
                (30, 40), #
                cv2.FONT_HERSHEY_SIMPLEX, #
                UIConstants.FONT_SCALE_MEDIUM, #
                UIConstants.RED, #
                UIConstants.FONT_THICKNESS, #
            )
            _draw_button(
                menu_frame,
                20, #
                80, #
                menu_frame.shape[1] - 40, #
                35, #
                "Back", #
                UIConstants.CV2_BLUE, #
                UIConstants.FONT_SCALE_MEDIUM, #
            ) #
            game_state.submenu_items = [
                ((20, 80, menu_frame.shape[1] - #
                 40, 35), "back_to_main", "Back") #
            ]
            game_state.menu_height = 135 #