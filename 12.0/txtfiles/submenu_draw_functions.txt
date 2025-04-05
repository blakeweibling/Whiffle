# submenu_draw_functions.py
"""
Specific submenu drawing functions for the Whiffle Tracker project.

This module contains the drawing logic for leaderboards, player management,
achievements, help, FAQ, and about screens.
"""

import cv2
import numpy as np
import logging
from typing import Any
from math import ceil  # Add ceil import

# Import constants and utilities needed by these functions
# Ensure ScoringConstants and CurrentGameState are imported if needed by updated functions
from constants import UIConstants, MenuConstants, ScoringConstants
from menu_utils import _draw_button
from game_state import CurrentGameState  # Import needed for state checking

logger = logging.getLogger(__name__)

# --- Specific Submenu Drawing Functions ---


# (Keep original functions from the file for leaderboard, players, achievements, etc.)
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
        logger.warning("game_state.leaderboard not found in _draw_leaderboard_submenu")

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
    item_height = 35  # Reset item height
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
    name_width = menu_frame.shape[1] - 40 - (button_width * 2 + button_spacing * 2)

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

    for i, player in enumerate(game_state.players):
        name_color = UIConstants.WHITE
        # Display current name or editing input
        if (
            game_state.editing_player_index == i
            and game_state.editing_player_mode == "edit_name"
        ):
            # Show input with cursor placeholder
            display_name = f"Edit: [{game_state.editing_player_name_input or ''}_]"
            # Highlight name being edited
            name_color = UIConstants.GREEN
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
            # Only allow clicking select if not current
            if not is_current:
                game_state.submenu_items.append(
                    (select_rect, f"select_player_{i}", f"Select P{i+1}")
                )

        y_offset += item_height + 5

    # Add Player Button (conditionally enable/disable)
    add_y = y_offset + 5
    add_color = (
        UIConstants.CV2_BLUE if len(game_state.players) < 2 else UIConstants.GREY_BG
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
        (
            (20, back_y, menu_frame.shape[1] - 40, item_height),
            "back_to_main",
            "Back",
        )
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
    item_height = 35  # Reset item height
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


def _draw_help_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Help submenu."""
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
        "  - Edit zones via Menu > Manage Zones > Edit Zones.",
        "      - Use Pts/Move/Resize/Del buttons.",
        "      - When Move/Resize active, click zone/handle in main window.",
        "      - Press ESC to cancel Move/Resize.",
        "  - Score points by getting balls into zones.",
        "  - Leftmost zone is the 'Special Hole'.",
        "  - Change modes in Menu > Game Mode.",
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
    item_height = 35  # Reset item height
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


def _draw_faq_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the FAQ submenu."""
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
        "A: Check lighting.",
        "   Use Debug Overlay ('b') to see tracked balls.",
        "   Check YOLO model confidence if needed.",
        "",
        "Q: How do I define scoring zones accurately?",
        "A: Use 's' key, click and drag.",
        "   Use Edit Zones menu to delete/modify points.",
        "   Use Move/Resize buttons for interactive edit.",
        "",
        "Q: What is the 'Special Hole'?",
        "A: The leftmost zone, potentially for bonus points",
        "   or specific achievements.",
        "",
        "Q: Why is the Edit Zones list cut off?",
        "A: Pagination has been added. Use Prev/Next buttons.",  # ADDED
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
    item_height = 35  # Reset item height
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


def _draw_about_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the About submenu."""
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
        "Whiffle Tracker v11.5",  # Updated version maybe?
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
    # Assuming show_splash_on_click handles the action or import it if needed
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
        (
            (20, back_y, menu_frame.shape[1] - 40, item_height),
            "back_to_main",
            "Back",
        )
    )
    game_state.menu_height = back_y + item_height + 20


# --- MODIFIED Edit Zones Submenu ---
def _draw_edit_zones_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Edit Zones submenu with pagination and Move/Resize options."""
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
    item_height = 30  # Make items smaller to fit more buttons
    button_width = 45  # Reduced from 55 to fit all buttons
    button_spacing = 3  # Reduced from 5
    num_buttons = 4  # Number of action buttons per zone (Pts, Move, Resize, Del)
    actions_width = (button_width * num_buttons) + (button_spacing * (num_buttons - 1))
    list_width = menu_frame.shape[1] - 40 - actions_width - button_spacing

    game_state.submenu_items.clear()

    # --- Pagination Calculations ---
    items_per_page = game_state.edit_zones_items_per_page
    total_zones = len(game_state.scoring_zones)
    total_pages = max(1, ceil(total_zones / items_per_page))
    # Ensure current page is valid
    game_state.edit_zones_current_page = max(
        1, min(game_state.edit_zones_current_page, total_pages)
    )
    current_page = game_state.edit_zones_current_page

    start_index = (current_page - 1) * items_per_page
    end_index = start_index + items_per_page
    zones_to_display = game_state.scoring_zones[start_index:end_index]
    # --- End Pagination Calculations ---

    confirm_delete_message = None
    if (
        game_state.editing_zone_mode == "confirm_delete"
        and game_state.editing_zone_index is not None
    ):
        # Adjust index check for pagination
        if start_index <= game_state.editing_zone_index < end_index:
            confirm_delete_message = f"Click Delete again for Zone {game_state.editing_zone_index + 1} to confirm?"

    edit_instruction_message = None
    if (
        game_state.editing_zone_mode == "edit_points"
        and game_state.editing_zone_index is not None
    ):
        # Adjust index check for pagination
        if start_index <= game_state.editing_zone_index < end_index:
            edit_instruction_message = "Enter points (0-9), Bksp=Delete, Enter=Save"

    # Combine messages or show priority message
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
        # Column Headers
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

        # --- Iterate over zones_to_display (paginated list) ---
        for i_display, zone_data in enumerate(zones_to_display):
            # Calculate the original index
            original_index = start_index + i_display
            x_z, y_z, w_z, h_z, points = (
                zone_data  # Use zone_data from the paginated list
            )
            zone_label = f"{original_index+1}: @({x_z},{y_z}) Pts="  # Use original index for label
            label_color = UIConstants.WHITE

            # Highlight if editing points for this zone
            if (
                game_state.editing_zone_index == original_index  # Check original index
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

            # Highlight if this zone is selected for interactive edit
            if (
                game_state.selected_zone_for_edit == original_index
            ):  # Check original index
                label_color = UIConstants.ZONE_EDIT_SELECTED_COLOR  # Yellow highlight

            # Draw Zone Label
            cv2.putText(
                menu_frame,
                zone_label[:45],  # Truncate if too long
                (20, y_offset + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_SMALL,
                label_color,
                1,
            )

            # --- Action Buttons (use original_index in action strings) ---
            button_x = 20 + list_width + button_spacing

            # Edit Points Button ("Pts")
            edit_rect = (button_x, y_offset, button_width, item_height)
            edit_color = (
                UIConstants.GREEN
                if game_state.editing_zone_index
                == original_index  # Check original index
                and game_state.editing_zone_mode == "edit_points"
                else UIConstants.CV2_BLUE
            )
            _draw_button(
                menu_frame,
                button_x,
                y_offset,
                button_width,
                item_height,
                "Pts",
                edit_color,
                UIConstants.FONT_SCALE_SMALL,
            )
            game_state.submenu_items.append(
                (
                    edit_rect,
                    f"edit_zone_{original_index}",
                    f"Edit Zone {original_index+1} Points",
                )
            )
            button_x += button_width + button_spacing

            # Move Button
            move_rect = (button_x, y_offset, button_width, item_height)
            is_moving_this_zone = (
                game_state.current_state == CurrentGameState.ZONE_EDITING
                and game_state.selected_zone_for_edit
                == original_index  # Check original index
                and game_state.zone_editing_action == "move"
            )
            move_color = (
                UIConstants.ZONE_EDIT_MOVE_COLOR
                if is_moving_this_zone
                else UIConstants.CV2_BLUE
            )
            _draw_button(
                menu_frame,
                button_x,
                y_offset,
                button_width,
                item_height,
                "Move",
                move_color,
                UIConstants.FONT_SCALE_SMALL,
            )
            game_state.submenu_items.append(
                (
                    move_rect,
                    f"move_zone_{original_index}",
                    f"Move Zone {original_index+1}",
                )
            )
            button_x += button_width + button_spacing

            # Resize Button
            resize_rect = (button_x, y_offset, button_width, item_height)
            is_resizing_this_zone = (
                game_state.current_state == CurrentGameState.ZONE_EDITING
                and game_state.selected_zone_for_edit
                == original_index  # Check original index
                and game_state.zone_editing_action
                and game_state.zone_editing_action.startswith("resize")
            )
            resize_color = (
                UIConstants.ZONE_EDIT_RESIZE_COLOR
                if is_resizing_this_zone
                else UIConstants.CV2_BLUE
            )
            _draw_button(
                menu_frame,
                button_x,
                y_offset,
                button_width,
                item_height,
                "Resize",
                resize_color,
                UIConstants.FONT_SCALE_SMALL,
            )
            game_state.submenu_items.append(
                (
                    resize_rect,
                    f"resize_zone_{original_index}",
                    f"Resize Zone {original_index+1}",
                )
            )
            button_x += button_width + button_spacing

            # Delete Button ("Del")
            delete_rect = (button_x, y_offset, button_width, item_height)
            delete_color = (
                UIConstants.RED
                if game_state.editing_zone_index
                == original_index  # Check original index
                and game_state.editing_zone_mode == "confirm_delete"
                else UIConstants.CV2_BLUE
            )
            _draw_button(
                menu_frame,
                button_x,
                y_offset,
                button_width,
                item_height,
                "Del",
                delete_color,
                UIConstants.FONT_SCALE_SMALL,
            )
            game_state.submenu_items.append(
                (
                    delete_rect,
                    f"delete_zone_{original_index}",
                    f"Delete Zone {original_index+1}",
                )
            )

            y_offset += item_height + 5

    # --- Draw Pagination Controls ---
    page_y_start = y_offset + 10
    page_item_height = 35
    page_button_width = 80

    # Page Number Text
    page_text = f"Page {current_page} / {total_pages}"
    (tw, th), _ = cv2.getTextSize(
        page_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, 1
    )
    page_text_x = (menu_frame.shape[1] - tw) // 2
    cv2.putText(
        menu_frame,
        page_text,
        (page_text_x, page_y_start + 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_SMALL,
        UIConstants.WHITE,
        1,
    )

    # Previous Button
    prev_button_x = 20
    prev_enabled = current_page > 1
    prev_color = UIConstants.CV2_BLUE if prev_enabled else UIConstants.GREY_BG
    _draw_button(
        menu_frame,
        prev_button_x,
        page_y_start,
        page_button_width,
        page_item_height,
        "Previous",
        prev_color,
        UIConstants.FONT_SCALE_SMALL,
    )
    if prev_enabled:
        game_state.submenu_items.append(
            (
                (prev_button_x, page_y_start, page_button_width, page_item_height),
                "prev_edit_zone_page",
                "Previous Page",
            )
        )

    # Next Button
    next_button_x = menu_frame.shape[1] - page_button_width - 20
    next_enabled = current_page < total_pages
    next_color = UIConstants.CV2_BLUE if next_enabled else UIConstants.GREY_BG
    _draw_button(
        menu_frame,
        next_button_x,
        page_y_start,
        page_button_width,
        page_item_height,
        "Next",
        next_color,
        UIConstants.FONT_SCALE_SMALL,
    )
    if next_enabled:
        game_state.submenu_items.append(
            (
                (next_button_x, page_y_start, page_button_width, page_item_height),
                "next_edit_zone_page",
                "Next Page",
            )
        )

    y_offset = (
        page_y_start + page_item_height + 5
    )  # Update y_offset after page controls
    # --- End Pagination Controls ---

    # Back Button (adjust position)
    back_y = y_offset + 10
    back_button_height = 35  # Keep Back button height consistent
    _draw_button(
        menu_frame,
        20,
        back_y,
        menu_frame.shape[1] - 40,
        back_button_height,
        "Back",
        UIConstants.CV2_BLUE,
        UIConstants.FONT_SCALE_MEDIUM,
    )
    game_state.submenu_items.append(
        (
            (20, back_y, menu_frame.shape[1] - 40, back_button_height),
            "back_to_manage_zones",
            "Back",
        )
    )
    game_state.menu_height = (
        back_y + back_button_height + 20
    )  # Adjust height based on content
