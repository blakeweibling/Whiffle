"""
Submenu rendering and logic for the Whiffle Tracker project.

This module contains functions to render and manage the submenus within the main game menu,
including settings, help, FAQ, about, leaderboard, players, achievements, and zone management.
"""

import cv2
import numpy as np
import logging
from typing import List, Tuple, Callable, Any, Optional

# Import constants, including MenuConstants
from constants import UIConstants, GameConstants, ScoringConstants, MenuConstants
from menu_utils import _draw_button, show_splash_on_click

# Removed incorrect import: from utils import mouse_callback
# Removed incorrect import: from menu import ZONE_SUBMENU_ITEMS

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


# --- Individual Submenu Drawing Functions ---


def _draw_settings_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
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
                game_state.toggle_background_music(),
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
            lambda: setattr(game_state, "debug_mode",
                            not game_state.debug_mode),
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
            (20, y_offset + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            1,
        )

        button_x = menu_frame.shape[1] - toggle_width - 20
        button_y = y_offset
        button_w = toggle_width
        button_h = item_height

        cv2.rectangle(
            menu_frame,
            (button_x, button_y),
            (button_x + button_w, button_y + button_h),
            state_color,
            -1,
        )
        cv2.putText(
            menu_frame,
            state_text,
            (button_x + 10, button_y + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            1,
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
        ((20, back_y, menu_frame.shape[1] - 40,
         item_height), "back_to_main", "Back")
    )

    game_state.menu_height = back_y + item_height + 20


def _draw_game_mode_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
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

    modes = ["classic", "timed", "practice"]
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
            ((20, y_offset, menu_frame.shape[1] -
             40, item_height), action_key, label)
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
        ((20, back_y, menu_frame.shape[1] - 40,
         item_height), "back_to_main", "Back")
    )
    game_state.menu_height = back_y + item_height + 20


def _draw_zone_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
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
            ((20, y_offset, menu_frame.shape[1] -
             40, item_height), action_key, label)
        )
        y_offset += item_height + 5

    game_state.menu_height = y_offset + 20


def _draw_edit_zones_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Edit Zones submenu."""
    cv2.putText(
        menu_frame,
        "Edit Scoring Zones",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    y_offset = 80
    item_height = 30
    button_width = 60
    button_spacing = 5
    list_width = menu_frame.shape[1] - 40 - \
        (button_width * 2 + button_spacing * 2)

    game_state.submenu_items.clear()

    confirm_delete_message = None
    if (
        game_state.editing_zone_mode == "confirm_delete"
        and game_state.editing_zone_index is not None
    ):
        confirm_delete_message = f"Click Delete again for Zone {game_state.editing_zone_index + 1} to confirm?"

    edit_instruction_message = None
    if (
        game_state.editing_zone_mode == "edit_points"
        and game_state.editing_zone_index is not None
    ):
        edit_instruction_message = "Enter points (0-9), Bksp=Delete, Enter=Save"

    top_message = confirm_delete_message or edit_instruction_message
    if top_message:
        cv2.putText(
            menu_frame,
            top_message,
            (20, y_offset - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.YELLOW,
            1,
        )
        y_offset += 15

    if not game_state.scoring_zones:
        cv2.putText(
            menu_frame,
            "No zones defined.",
            (20, y_offset + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            1,
        )
        y_offset += item_height + 5
    else:
        cv2.putText(
            menu_frame,
            "Zone",
            (20, y_offset - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.YELLOW,
            1,
        )
        cv2.putText(
            menu_frame,
            "Actions",
            (20 + list_width + button_spacing, y_offset - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.YELLOW,
            1,
        )

        for i, zone in enumerate(game_state.scoring_zones):
            x, y, w, h, points = zone
            zone_label = f"{i+1}: @({x},{y}) Pts="
            label_color = UIConstants.WHITE
            if (
                game_state.editing_zone_index == i
                and game_state.editing_zone_mode == "edit_points"
            ):
                input_display = (
                    game_state.editing_zone_points_input
                    if game_state.editing_zone_points_input
                    else "___"
                )
                zone_label += f"[ {input_display} ]"
                label_color = UIConstants.GREEN
            else:
                zone_label += str(points)

            cv2.putText(
                menu_frame,
                zone_label[:35],
                (20, y_offset + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_SMALL,
                label_color,
                1,
            )

            edit_x = 20 + list_width + button_spacing
            edit_rect = (edit_x, y_offset, button_width, item_height)
            edit_color = (
                UIConstants.GREEN
                if game_state.editing_zone_index == i
                and game_state.editing_zone_mode == "edit_points"
                else UIConstants.CV2_BLUE
            )
            _draw_button(
                menu_frame,
                edit_x,
                y_offset,
                button_width,
                item_height,
                "Edit",
                edit_color,
                UIConstants.FONT_SCALE_SMALL,
            )
            game_state.submenu_items.append(
                (edit_rect, f"edit_zone_{i}", f"Edit Zone {i+1} Points")
            )

            delete_x = edit_x + button_width + button_spacing
            delete_rect = (delete_x, y_offset, button_width, item_height)
            delete_color = (
                UIConstants.RED
                if game_state.editing_zone_index == i
                and game_state.editing_zone_mode == "confirm_delete"
                else UIConstants.CV2_BLUE
            )
            _draw_button(
                menu_frame,
                delete_x,
                y_offset,
                button_width,
                item_height,
                "Delete",
                delete_color,
                UIConstants.FONT_SCALE_SMALL,
            )
            game_state.submenu_items.append(
                (delete_rect, f"delete_zone_{i}", f"Delete Zone {i+1}")
            )

            y_offset += item_height + 5

    back_y = y_offset + 10
    item_height = 35
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
            "back_to_manage_zones",
            "Back",
        )
    )
    game_state.menu_height = back_y + item_height + 20


def _draw_leaderboard_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Leaderboard submenu."""
    cv2.putText(
        menu_frame,
        "Leaderboard",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    y_offset = 80
    item_height = 25
    game_state.submenu_items.clear()

    cv2.putText(
        menu_frame,
        f"Mode: {game_state.game_mode.capitalize()}",
        (20, y_offset - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.YELLOW,
        1,
    )

    scores, is_online = ([], False)
    if hasattr(game_state, "leaderboard") and game_state.leaderboard:
        scores, is_online = game_state.leaderboard.get_top_scores(
            limit=10, mode=game_state.game_mode
        )
    else:
        logger.warning(
            "game_state.leaderboard not found in _draw_leaderboard_submenu")

    status_text = "Online" if is_online else "Local (Offline)"
    status_color = UIConstants.GREEN if is_online else UIConstants.YELLOW
    cv2.putText(
        menu_frame,
        status_text,
        (menu_frame.shape[1] - 150, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_SMALL,
        status_color,
        1,
    )

    if not scores:
        cv2.putText(
            menu_frame,
            "No scores available.",
            (20, y_offset + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            1,
        )
        y_offset += item_height + 5
    else:
        cv2.putText(
            menu_frame,
            f"{'Rank':<5} {'Name':<15} {'Score':<6}",
            (20, y_offset),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.YELLOW,
            1,
        )
        y_offset += 5
        for i, score_entry in enumerate(scores):
            rank = i + 1
            name = score_entry.get("player_name", "N/A")[:15]
            score = score_entry.get("score", 0)
            entry_text = f"{rank:<5} {name:<15} {score:<6}"
            cv2.putText(
                menu_frame,
                entry_text,
                (20, y_offset + item_height),
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_SMALL,
                UIConstants.WHITE,
                1,
            )
            y_offset += item_height + 2

    back_y = y_offset + 10
    item_height = 35
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
        ((20, back_y, menu_frame.shape[1] - 40,
         item_height), "back_to_main", "Back")
    )
    game_state.menu_height = back_y + item_height + 20


# <<< Modified: Added Player Name Editing UI >>>
def _draw_players_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Players submenu."""
    cv2.putText(
        menu_frame,
        "Manage Players",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    y_offset = 80
    item_height = 35
    button_width = 80  # Width for Edit/Select buttons
    button_spacing = 10
    # Calculate width available for name display
    name_width = menu_frame.shape[1] - 40 - \
        (button_width * 2 + button_spacing * 2)

    game_state.submenu_items.clear()

    # Instructions for editing name
    if (
        game_state.editing_player_mode == "edit_name"
        and game_state.editing_player_index is not None
    ):
        instruction_text = "Enter Name (A-Z, 0-9), Bksp, Enter=Save, ESC=Cancel"
        cv2.putText(
            menu_frame,
            instruction_text,
            (20, y_offset - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.YELLOW,
            1,
        )
        y_offset += 15

    # cv2.putText(menu_frame, "Select Player:", (20, y_offset - 5), cv2.FONT_HERSHEY_SIMPLEX,
    #             UIConstants.FONT_SCALE_MEDIUM, UIConstants.YELLOW, 1)
    # y_offset += 20 # Add space after header

    for i, player in enumerate(game_state.players):
        name_color = UIConstants.WHITE
        # Display current name or editing input
        if (
            game_state.editing_player_index == i
            and game_state.editing_player_mode == "edit_name"
        ):
            # Show input with cursor placeholder
            display_name = f"Edit: [{game_state.editing_player_name_input or ''}_]"
            name_color = UIConstants.GREEN  # Highlight name being edited
        else:
            display_name = f"{i+1}. {player.name}"

        # Draw Player Name (or input field) - ensure it fits
        max_name_len = name_width // 8  # Approx calculation based on font size
        cv2.putText(
            menu_frame,
            display_name[:max_name_len],
            (20, y_offset + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            name_color,
            1,
        )

        # Edit Name Button
        edit_x = 20 + name_width + button_spacing
        edit_rect = (edit_x, y_offset, button_width, item_height)
        # Highlight if this player is being edited
        edit_color = (
            UIConstants.GREEN
            if game_state.editing_player_index == i
            and game_state.editing_player_mode == "edit_name"
            else UIConstants.CV2_BLUE
        )
        _draw_button(
            menu_frame,
            edit_x,
            y_offset,
            button_width,
            item_height,
            "Edit",
            edit_color,
            UIConstants.FONT_SCALE_SMALL,
        )
        game_state.submenu_items.append(
            (edit_rect, f"edit_player_name_{i}", f"Edit P{i+1} Name")
        )

        # Select Button (or indicate current player)
        select_x = edit_x + button_width + button_spacing
        select_rect = (select_x, y_offset, button_width, item_height)
        is_current = i == game_state.current_player_index
        select_color = UIConstants.GREEN if is_current else UIConstants.CV2_BLUE
        select_text = "Current" if is_current else "Select"
        # Disable select button if editing this player's name
        if (
            game_state.editing_player_index == i
            and game_state.editing_player_mode == "edit_name"
        ):
            _draw_button(
                menu_frame,
                select_x,
                y_offset,
                button_width,
                item_height,
                "-",
                UIConstants.GREY_BG,
                UIConstants.FONT_SCALE_SMALL,
            )
            # Don't add click action if disabled
        else:
            _draw_button(
                menu_frame,
                select_x,
                y_offset,
                button_width,
                item_height,
                select_text,
                select_color,
                UIConstants.FONT_SCALE_SMALL,
            )
            if not is_current:  # Only allow clicking select if not current
                game_state.submenu_items.append(
                    (select_rect, f"select_player_{i}", f"Select P{i+1}")
                )

        y_offset += item_height + 5

    # Add Player Button (conditionally enable/disable)
    add_y = y_offset + 5
    add_color = (
        UIConstants.CV2_BLUE if len(
            game_state.players) < 2 else UIConstants.GREY_BG
    )  # Disable if 2 players exist
    _draw_button(
        menu_frame,
        20,
        add_y,
        menu_frame.shape[1] - 40,
        item_height,
        "Add Player",
        add_color,
        UIConstants.FONT_SCALE_MEDIUM,
    )
    if len(game_state.players) < 2:  # Only add action if enabled
        game_state.submenu_items.append(
            (
                (20, add_y, menu_frame.shape[1] - 40, item_height),
                "add_player",
                "Add Player",
            )
        )
    y_offset = add_y + item_height + 5

    # Back Button
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
        ((20, back_y, menu_frame.shape[1] - 40,
         item_height), "back_to_main", "Back")
    )
    game_state.menu_height = back_y + item_height + 20


def _draw_achievements_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Achievements submenu."""
    cv2.putText(
        menu_frame,
        "Achievements",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )
    y_offset = 80
    item_height = 25
    game_state.submenu_items.clear()

    unlocked_count = sum(1 for ach in game_state.achievements if ach.unlocked)
    total_count = len(game_state.achievements)
    status_text = f"Unlocked: {unlocked_count} / {total_count}"
    cv2.putText(
        menu_frame,
        status_text,
        (20, y_offset - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.YELLOW,
        1,
    )

    if not game_state.achievements:
        cv2.putText(
            menu_frame,
            "No achievements defined.",
            (20, y_offset + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            1,
        )
        y_offset += item_height + 5
    else:
        for achievement in game_state.achievements:
            text = f"- {achievement.name}: {achievement.description}"
            color = UIConstants.GREEN if achievement.unlocked else UIConstants.WHITE
            max_len = 55
            if len(text) > max_len:
                break_point = text.rfind(" ", 0, max_len)
                if break_point == -1:
                    break_point = max_len
                line1 = text[:break_point]
                line2 = "  " + text[break_point:].strip()
                cv2.putText(
                    menu_frame,
                    line1,
                    (20, y_offset + item_height),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    UIConstants.FONT_SCALE_SMALL,
                    color,
                    1,
                )
                y_offset += item_height
                cv2.putText(
                    menu_frame,
                    line2,
                    (20, y_offset + item_height),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    UIConstants.FONT_SCALE_SMALL,
                    color,
                    1,
                )
            else:
                cv2.putText(
                    menu_frame,
                    text,
                    (20, y_offset + item_height),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    UIConstants.FONT_SCALE_SMALL,
                    color,
                    1,
                )
            y_offset += item_height + 2

    back_y = y_offset + 10
    item_height = 35
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
        ((20, back_y, menu_frame.shape[1] - 40,
         item_height), "back_to_main", "Back")
    )
    game_state.menu_height = back_y + item_height + 20


def _draw_help_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Help submenu."""
    # ...(help submenu remains the same)...
    cv2.putText(
        menu_frame,
        "Help",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )
    y_offset = 80
    item_height = 20
    game_state.submenu_items.clear()
    help_text = [
        "Controls:",
        "  'm' / Click Menu Btn : Toggle Menu",
        "  's' : Start/Stop drawing zone (while playing)",
        "  'd' : Toggle General Debug Logs",
        "  'b' : Toggle Visual Debug Overlay",
        "  'p' : Pause/Resume Game (while playing)",
        "  'q' / ESC: Quit Game",
        "  BACKSPACE: Go back in menu / Close menu",
        "",
        "Gameplay:",
        "  - Define scoring zones via Menu > Manage Zones.",
        "  - Score points by getting balls into zones.",
        "  - Leftmost zone is the 'Special Hole'.",
        "  - Change modes in Menu > Game Mode.",
        "  - Edit zones in Menu > Manage Zones > Edit Zones.",
        "  - Edit player names in Menu > Players.",
    ]
    for line in help_text:
        cv2.putText(
            menu_frame,
            line,
            (20, y_offset + item_height),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.WHITE,
            1,
        )
        y_offset += item_height
    back_y = y_offset + 10
    item_height = 35
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
        ((20, back_y, menu_frame.shape[1] - 40,
         item_height), "back_to_main", "Back")
    )
    game_state.menu_height = back_y + item_height + 20


def _draw_faq_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the FAQ submenu."""
    # ...(faq submenu remains the same)...
    cv2.putText(
        menu_frame,
        "FAQ",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )
    y_offset = 80
    item_height = 20
    game_state.submenu_items.clear()
    faq_text = [
        "Q: Why aren't balls being detected?",
        "A: Check lighting. Ensure balls are visible.",
        "   Use Debug Overlay ('b') to see tracked balls.",
        "   Check YOLO model confidence if needed.",
        "",
        "Q: How do I define scoring zones accurately?",
        "A: Use 's' key, click and drag. Aim for the center.",
        "   Use Edit Zones menu to delete/modify.",
        "",
        "Q: What is the 'Special Hole'?",
        "A: The leftmost zone, potentially for bonus points",
        "   or specific achievements.",
    ]
    for line in faq_text:
        cv2.putText(
            menu_frame,
            line,
            (20, y_offset + item_height),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.WHITE,
            1,
        )
        y_offset += item_height
    back_y = y_offset + 10
    item_height = 35
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
        ((20, back_y, menu_frame.shape[1] - 40,
         item_height), "back_to_main", "Back")
    )
    game_state.menu_height = back_y + item_height + 20


def _draw_about_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the About submenu."""
    # ...(about submenu remains the same)...
    cv2.putText(
        menu_frame,
        "About",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )
    y_offset = 80
    item_height = 35
    game_state.submenu_items.clear()
    cv2.putText(
        menu_frame,
        "Whiffle Tracker v1.0",
        (20, y_offset),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.WHITE,
        1,
    )
    y_offset += item_height
    cv2.putText(
        menu_frame,
        "Developed using OpenCV & YOLOv8",
        (20, y_offset),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_SMALL,
        UIConstants.WHITE,
        1,
    )
    y_offset += item_height + 10
    splash_y = y_offset
    _draw_button(
        menu_frame,
        20,
        splash_y,
        menu_frame.shape[1] - 40,
        item_height,
        "Show Splash",
        UIConstants.CV2_BLUE,
        UIConstants.FONT_SCALE_MEDIUM,
    )
    game_state.submenu_items.append(
        (
            (20, splash_y, menu_frame.shape[1] - 40, item_height),
            "show_splash",
            "Show Splash",
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
        ((20, back_y, menu_frame.shape[1] - 40,
         item_height), "back_to_main", "Back")
    )
    game_state.menu_height = back_y + item_height + 20


# --- Main Submenu Dispatcher ---


def draw_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """
    Draw the currently active submenu.
    """
    submenu_draw_functions = {
        "settings": _draw_settings_submenu,
        "game_mode": _draw_game_mode_submenu,
        "manage_zones": _draw_zone_submenu,
        "edit_zones": _draw_edit_zones_submenu,
        "leaderboard": _draw_leaderboard_submenu,
        "players": _draw_players_submenu,  # Handles player list and editing UI
        "achievements": _draw_achievements_submenu,
        "help": _draw_help_submenu,
        "faq": _draw_faq_submenu,
        "about": _draw_about_submenu,
    }

    draw_func = submenu_draw_functions.get(game_state.submenu_active)
    if draw_func:
        game_state.menu_height = 400  # Default height, function can override
        draw_func(menu_frame, game_state)
    else:
        if game_state.submenu_active is not None:
            logger.warning(
                f"No draw function found for submenu: {game_state.submenu_active}"
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
                ((20, 80, menu_frame.shape[1] -
                 40, 35), "back_to_main", "Back")
            ]
            game_state.menu_height = 135
