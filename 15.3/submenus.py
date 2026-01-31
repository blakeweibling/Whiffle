# submenus.py
import logging
import cv2
import numpy as np

# Import constants, including MenuConstants
from constants import MenuConstants, UIConstants

# Import GameState for type hinting if needed, but avoid direct use that causes cycles
from game_state import GameState

# <<< MODIFIED: Pass game_state to _draw_button >>>
from menu_utils import _draw_button

# Import the drawing functions from the new file
from submenu_draw_functions import (
    _draw_about_submenu,
    _draw_achievements_submenu,
    _draw_edit_zones_submenu,
    _draw_faq_submenu,
    _draw_help_submenu,
    _draw_leaderboard_submenu,
    _draw_players_submenu,
    _draw_settings_submenu,
    _draw_replays_submenu,
    _draw_replay_browser_submenu,
    _draw_replay_playback_submenu,
    _draw_replay_share_submenu,
)

logger = logging.getLogger(__name__)


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

    modes = ["classic", "timed", "fun", "practice", "survival", "retro", "versus"]
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
            # <<< ADDED game_state parameter >>>
            game_state=game_state,
            font_scale=UIConstants.FONT_SCALE_MEDIUM,
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
        # <<< ADDED game_state parameter >>>
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_MEDIUM,
    )
    game_state.submenu_items.append(
        (
            (20, back_y, menu_frame.shape[1] - 40, item_height),
            "back_to_main",
            "Back",
        )
    )
    game_state.menu_height = back_y + item_height + 20


def _draw_layout_submenu(menu_frame: np.ndarray, game_state: GameState) -> None:
    """Draw the Layout selection submenu."""
    cv2.putText(
        menu_frame,
        "Select Layout",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    layouts = ["whiffle", "fivestar"]
    y_offset = 80
    item_height = 35
    game_state.submenu_items.clear()

    for layout in layouts:
        # Display name: capitalize and format nicely
        if layout == "fivestar":
            label = "Five star"
        else:
            label = layout.capitalize()
        
        # Get current playfield type
        current_playfield = getattr(game_state, "playfield_type", "whiffle")
        is_current = (
            (layout == "fivestar" and current_playfield == "fivestar") or
            (layout == "whiffle" and current_playfield == "whiffle")
        )
        
        # Use green for currently selected layout, normal color for others
        color = UIConstants.GREEN if is_current else UIConstants.CV2_BLUE
        action_key = f"set_layout_{layout}"

        _draw_button(
            menu_frame,
            20,
            y_offset,
            menu_frame.shape[1] - 40,
            item_height,
            label,
            color,
            game_state=game_state,
            font_scale=UIConstants.FONT_SCALE_MEDIUM,
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
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_MEDIUM,
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
            # <<< ADDED game_state parameter >>>
            game_state=game_state,
            font_scale=UIConstants.FONT_SCALE_MEDIUM,
        )
        game_state.submenu_items.append(
            (
                (20, y_offset, menu_frame.shape[1] - 40, item_height),
                action_key,
                label,
            )
        )
        y_offset += item_height + 5

    game_state.menu_height = y_offset + 20


# --- Main Submenu Dispatcher ---

submenu_draw_functions_map = {
    "settings": _draw_settings_submenu,
    "game_mode": _draw_game_mode_submenu,
    "layout": _draw_layout_submenu,
    "manage_zones": _draw_zone_submenu,
    "edit_zones": _draw_edit_zones_submenu,
    "leaderboard": _draw_leaderboard_submenu,
    "players": _draw_players_submenu,
    "achievements": _draw_achievements_submenu,
    "help": _draw_help_submenu,
    "faq": _draw_faq_submenu,
    "about": _draw_about_submenu,
    "replays": _draw_replays_submenu,
    "view_replays": _draw_replay_browser_submenu,
    "replay_playback": _draw_replay_playback_submenu,
    "replay_share": _draw_replay_share_submenu,
}


def draw_submenu(menu_frame: np.ndarray, game_state: GameState) -> None:
    """
    Draw the currently active submenu.
    """
    draw_func = submenu_draw_functions_map.get(game_state.submenu_active)

    if draw_func:
        game_state.menu_height = 450  # Default height
        game_state.submenu_items.clear()
        # The specific draw_func (e.g., _draw_settings_submenu) is responsible
        # for calling _draw_button with game_state. We will update those functions next.
        draw_func(menu_frame, game_state)
    else:
        if game_state.submenu_active is not None:
            logger.warning(
                f"No draw function found for submenu: {game_state.submenu_active}."
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
            # Fallback Back button
            _draw_button(
                menu_frame,
                20,
                80,
                menu_frame.shape[1] - 40,
                35,
                "Back",
                UIConstants.CV2_BLUE,
                # <<< ADDED game_state parameter >>>
                game_state=game_state,
                font_scale=UIConstants.FONT_SCALE_MEDIUM,
            )
            game_state.submenu_items = [
                ((20, 80, menu_frame.shape[1] - 40, 35), "back_to_main", "Back")
            ]
            game_state.menu_height = 135
        else:
            logger.error(
                "draw_submenu called with game_state.submenu_active being None."
            )
