"""
Specific submenu drawing functions for the Whiffle Tracker project.

This module contains the drawing logic for leaderboards, player management,
achievements, help, FAQ, and about screens.
"""

import cv2
import numpy as np
import logging
from typing import Any

# Import constants and utilities needed by these functions
from constants import UIConstants, MenuConstants  # Adjusted imports
from menu_utils import _draw_button  # Adjusted imports

logger = logging.getLogger(__name__)

# --- Specific Submenu Drawing Functions ---


def _draw_leaderboard_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Leaderboard submenu."""  # [cite: 40]
    cv2.putText(
        menu_frame,
        "Leaderboard",  # [cite: 41]
        (30, 40),  # [cite: 41]
        cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 41]
        UIConstants.FONT_SCALE_LARGE,  # [cite: 41]
        UIConstants.WHITE,  # [cite: 41]
        UIConstants.FONT_THICKNESS,  # [cite: 41]
    )

    y_offset = 80  # [cite: 41]
    item_height = 25  # [cite: 41]
    game_state.submenu_items.clear()  # [cite: 41]

    cv2.putText(
        menu_frame,
        f"Mode: {game_state.game_mode.capitalize()}",  # [cite: 41]
        (20, y_offset - 20),  # [cite: 41]
        cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 42]
        UIConstants.FONT_SCALE_MEDIUM,  # [cite: 42]
        UIConstants.YELLOW,  # [cite: 42]
        1,  # [cite: 42]
    )

    scores, is_online = ([], False)  # [cite: 42]
    # [cite: 42]
    if hasattr(game_state, "leaderboard") and game_state.leaderboard:
        scores, is_online = game_state.leaderboard.get_top_scores(
            limit=10, mode=game_state.game_mode  # [cite: 42]
        )
    else:  # [cite: 42]
        logger.warning(
            "game_state.leaderboard not found in _draw_leaderboard_submenu"
        )  # [cite: 43]

    status_text = "Online" if is_online else "Local (Offline)"  # [cite: 43]
    # [cite: 43]
    status_color = UIConstants.GREEN if is_online else UIConstants.YELLOW
    cv2.putText(
        menu_frame,
        status_text,  # [cite: 43]
        (menu_frame.shape[1] - 150, 40),  # [cite: 43]
        cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 43]
        UIConstants.FONT_SCALE_SMALL,  # [cite: 43]
        status_color,  # [cite: 43]
        1,  # [cite: 43]
    )

    if not scores:  # [cite: 44]
        cv2.putText(
            menu_frame,
            "No scores available.",  # [cite: 44]
            (20, y_offset + 20),  # [cite: 44]
            cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 44]
            UIConstants.FONT_SCALE_MEDIUM,  # [cite: 44]
            UIConstants.WHITE,  # [cite: 44]
            1,  # [cite: 45]
        )
        y_offset += item_height + 5  # [cite: 45]
    else:  # [cite: 45]
        cv2.putText(
            menu_frame,
            f"{'Rank':<5} {'Name':<15} {'Score':<6}",  # [cite: 45]
            (20, y_offset),  # [cite: 45]
            cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 45]
            UIConstants.FONT_SCALE_SMALL,  # [cite: 45]
            UIConstants.YELLOW,  # [cite: 46]
            1,  # [cite: 46]
        )
        y_offset += 5  # [cite: 46]
        for i, score_entry in enumerate(scores):  # [cite: 46]
            rank = i + 1  # [cite: 46]
            name = score_entry.get("player_name", "N/A")[:15]  # [cite: 46]
            score = score_entry.get("score", 0)  # [cite: 46]
            entry_text = f"{rank:<5} {name:<15} {score:<6}"  # [cite: 47]
            cv2.putText(
                menu_frame,
                entry_text,  # [cite: 47]
                (20, y_offset + item_height),  # [cite: 47]
                cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 47]
                UIConstants.FONT_SCALE_SMALL,  # [cite: 48]
                UIConstants.WHITE,  # [cite: 48]
                1,  # [cite: 48]
            )
            y_offset += item_height + 2  # [cite: 48]

    back_y = y_offset + 10  # [cite: 48]
    item_height = 35  # [cite: 48] # Reset item height
    _draw_button(
        menu_frame,
        20,  # [cite: 49]
        back_y,  # [cite: 49]
        menu_frame.shape[1] - 40,  # [cite: 49]
        item_height,  # [cite: 49]
        "Back",  # [cite: 49]
        UIConstants.CV2_BLUE,  # [cite: 49]
        UIConstants.FONT_SCALE_MEDIUM,  # [cite: 49]
    )
    game_state.submenu_items.append(
        (
            (20, back_y, menu_frame.shape[1] - 40, item_height),  # [cite: 49]
            "back_to_main",
            "Back",
        )  # [cite: 49]
    )
    game_state.menu_height = back_y + item_height + 20  # [cite: 49]


# <<< Modified: Added Player Name Editing UI >>> # [cite: 49]
def _draw_players_submenu(
    menu_frame: np.ndarray, game_state: Any
) -> None:  # [cite: 50]
    """Draw the Players submenu."""  # [cite: 50]
    cv2.putText(
        menu_frame,
        "Manage Players",  # [cite: 50]
        (30, 40),  # [cite: 50]
        cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 50]
        UIConstants.FONT_SCALE_LARGE,  # [cite: 50]
        UIConstants.WHITE,  # [cite: 50]
        UIConstants.FONT_THICKNESS,  # [cite: 50]
    )

    y_offset = 80  # [cite: 50]
    item_height = 35  # [cite: 50]
    button_width = 80  # Width for Edit/Select buttons # [cite: 51]
    button_spacing = 10  # [cite: 51]
    # Calculate width available for name display # [cite: 51]
    name_width = (
        menu_frame.shape[1] - 40 - (button_width * 2 + button_spacing * 2)
    )  # [cite: 51]

    game_state.submenu_items.clear()  # [cite: 51]

    # Instructions for editing name # [cite: 51]
    if (
        game_state.editing_player_mode == "edit_name"  # [cite: 51]
        and game_state.editing_player_index is not None  # [cite: 51]
    ):
        instruction_text = (
            "Enter Name (A-Z, 0-9), Bksp, Enter=Save, ESC=Cancel"  # [cite: 52]
        )
        cv2.putText(
            menu_frame,
            instruction_text,  # [cite: 52]
            (20, y_offset - 5),  # [cite: 52]
            cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 52]
            UIConstants.FONT_SCALE_SMALL,  # [cite: 52]
            UIConstants.YELLOW,  # [cite: 52]
            1,  # [cite: 53]
        )
        y_offset += 15  # [cite: 53]

    for i, player in enumerate(game_state.players):  # [cite: 53]
        name_color = UIConstants.WHITE  # [cite: 53]
        # Display current name or editing input # [cite: 53]
        if (  # [cite: 54]
            game_state.editing_player_index == i  # [cite: 54]
            and game_state.editing_player_mode == "edit_name"  # [cite: 54]
        ):
            # Show input with cursor placeholder # [cite: 54]
            display_name = (
                # [cite: 54]
                f"Edit: [{game_state.editing_player_name_input or ''}_]"
            )
            # Highlight name being edited # [cite: 54]
            name_color = UIConstants.GREEN
        else:  # [cite: 55]
            display_name = f"{i+1}. {player.name}"  # [cite: 56]

        # Draw Player Name (or input field) - ensure it fits # [cite: 56]
        max_name_len = (
            name_width // 8
        )  # Approx calculation based on font size # [cite: 56]
        cv2.putText(
            menu_frame,
            display_name[:max_name_len],  # [cite: 56]
            (20, y_offset + 25),  # [cite: 56]
            cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 56]
            UIConstants.FONT_SCALE_MEDIUM,  # [cite: 57]
            name_color,  # [cite: 57]
            1,  # [cite: 57]
        )

        # Edit Name Button # [cite: 57]
        edit_x = 20 + name_width + button_spacing  # [cite: 57]
        edit_rect = (edit_x, y_offset, button_width, item_height)  # [cite: 57]
        # Highlight if this player is being edited # [cite: 57]
        edit_color = (  # [cite: 58]
            UIConstants.GREEN  # [cite: 58]
            if game_state.editing_player_index == i  # [cite: 58]
            and game_state.editing_player_mode == "edit_name"  # [cite: 58]
            else UIConstants.CV2_BLUE  # [cite: 58]
        )
        _draw_button(
            menu_frame,
            edit_x,  # [cite: 58]
            y_offset,  # [cite: 59]
            button_width,  # [cite: 59]
            item_height,  # [cite: 59]
            "Edit",  # [cite: 59]
            edit_color,  # [cite: 59]
            UIConstants.FONT_SCALE_SMALL,  # [cite: 59]
        )
        game_state.submenu_items.append(
            (edit_rect, f"edit_player_name_{i}", f"Edit P{i+1} Name")  # [cite: 60]
        )

        # Select Button (or indicate current player) # [cite: 60]
        select_x = edit_x + button_width + button_spacing  # [cite: 60]
        select_rect = (select_x, y_offset, button_width, item_height)  # [cite: 60]
        is_current = i == game_state.current_player_index  # [cite: 60]
        select_color = (
            UIConstants.GREEN if is_current else UIConstants.CV2_BLUE
        )  # [cite: 60]
        select_text = "Current" if is_current else "Select"  # [cite: 60]
        # Disable select button if editing this player's name # [cite: 61]
        if (
            game_state.editing_player_index == i  # [cite: 61]
            and game_state.editing_player_mode == "edit_name"  # [cite: 61]
        ):
            _draw_button(
                menu_frame,
                select_x,  # [cite: 61]
                y_offset,  # [cite: 62]
                button_width,  # [cite: 62]
                item_height,  # [cite: 62]
                "-",  # [cite: 62]
                UIConstants.GREY_BG,  # [cite: 62]
                UIConstants.FONT_SCALE_SMALL,  # [cite: 62]
            )  # [cite: 63]
            # Don't add click action if disabled # [cite: 63]
        else:  # [cite: 63]
            _draw_button(
                menu_frame,
                select_x,  # [cite: 63]
                y_offset,  # [cite: 63]
                button_width,  # [cite: 64]
                item_height,  # [cite: 64]
                select_text,  # [cite: 64]
                select_color,  # [cite: 64]
                UIConstants.FONT_SCALE_SMALL,  # [cite: 64]
            )
            # Only allow clicking select if not current # [cite: 65]
            if not is_current:
                game_state.submenu_items.append(
                    # [cite: 65]
                    (select_rect, f"select_player_{i}", f"Select P{i+1}")
                )

        y_offset += item_height + 5  # [cite: 65]

    # Add Player Button (conditionally enable/disable) # [cite: 65]
    add_y = y_offset + 5  # [cite: 65]
    add_color = (
        UIConstants.CV2_BLUE
        if len(game_state.players) < 2  # [cite: 66]
        else UIConstants.GREY_BG  # [cite: 66]
    )  # Disable if 2 players exist # [cite: 66]
    _draw_button(
        menu_frame,
        20,  # [cite: 66]
        add_y,  # [cite: 66]
        menu_frame.shape[1] - 40,  # [cite: 66]
        item_height,  # [cite: 66]
        "Add Player",  # [cite: 66]
        add_color,  # [cite: 66]
        UIConstants.FONT_SCALE_MEDIUM,  # [cite: 67]
    )
    if len(game_state.players) < 2:  # Only add action if enabled # [cite: 67]
        game_state.submenu_items.append(
            (
                (20, add_y, menu_frame.shape[1] - 40, item_height),  # [cite: 67]
                "add_player",  # [cite: 67]
                "Add Player",  # [cite: 67]
            )  # [cite: 68]
        )
    y_offset = add_y + item_height + 5  # [cite: 68]

    # Back Button # [cite: 68]
    back_y = y_offset + 10  # [cite: 68]
    _draw_button(
        menu_frame,
        20,  # [cite: 68]
        back_y,  # [cite: 68]
        menu_frame.shape[1] - 40,  # [cite: 68]
        item_height,  # [cite: 68]
        "Back",  # [cite: 68]
        UIConstants.CV2_BLUE,  # [cite: 69]
        UIConstants.FONT_SCALE_MEDIUM,  # [cite: 69]
    )
    game_state.submenu_items.append(
        (
            (20, back_y, menu_frame.shape[1] - 40, item_height),  # [cite: 69]
            "back_to_main",
            "Back",
        )  # [cite: 69]
    )
    game_state.menu_height = back_y + item_height + 20  # [cite: 69]


def _draw_achievements_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Achievements submenu."""  # [cite: 69]
    cv2.putText(
        menu_frame,
        "Achievements",  # [cite: 69]
        (30, 40),  # [cite: 69]
        cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 70]
        UIConstants.FONT_SCALE_LARGE,  # [cite: 70]
        UIConstants.WHITE,  # [cite: 70]
        UIConstants.FONT_THICKNESS,  # [cite: 70]
    )
    y_offset = 80  # [cite: 70]
    item_height = 25  # [cite: 70]
    game_state.submenu_items.clear()  # [cite: 70]

    unlocked_count = sum(
        1 for ach in game_state.achievements if ach.unlocked
    )  # [cite: 70]
    total_count = len(game_state.achievements)  # [cite: 70]
    status_text = f"Unlocked: {unlocked_count} / {total_count}"  # [cite: 70]
    cv2.putText(
        menu_frame,
        status_text,  # [cite: 70]
        (20, y_offset - 20),  # [cite: 71]
        cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 71]
        UIConstants.FONT_SCALE_MEDIUM,  # [cite: 71]
        UIConstants.YELLOW,  # [cite: 71]
        1,  # [cite: 71]
    )

    if not game_state.achievements:  # [cite: 71]
        cv2.putText(
            menu_frame,
            "No achievements defined.",  # [cite: 71]
            (20, y_offset + 20),  # [cite: 71]
            cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 72]
            UIConstants.FONT_SCALE_MEDIUM,  # [cite: 72]
            UIConstants.WHITE,  # [cite: 72]
            1,  # [cite: 72]
        )
        y_offset += item_height + 5  # [cite: 72]
    else:  # [cite: 72]
        for achievement in game_state.achievements:  # [cite: 72]
            # [cite: 72]
            text = f"- {achievement.name}: {achievement.description}"
            color = (
                UIConstants.GREEN if achievement.unlocked else UIConstants.WHITE
            )  # [cite: 73]
            max_len = 55  # [cite: 73]
            if len(text) > max_len:  # [cite: 73]
                break_point = text.rfind(" ", 0, max_len)  # [cite: 73]
                if break_point == -1:  # [cite: 73]
                    break_point = max_len  # [cite: 74]
                line1 = text[:break_point]  # [cite: 74]
                line2 = "  " + text[break_point:].strip()  # [cite: 74]
                cv2.putText(
                    menu_frame,
                    line1,  # [cite: 75]
                    (20, y_offset + item_height),  # [cite: 75]
                    cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 75]
                    UIConstants.FONT_SCALE_SMALL,  # [cite: 75]
                    color,  # [cite: 75]
                    1,  # [cite: 76]
                )
                y_offset += item_height  # [cite: 76]
                cv2.putText(
                    menu_frame,
                    line2,  # [cite: 76]
                    (20, y_offset + item_height),  # [cite: 77]
                    cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 77]
                    UIConstants.FONT_SCALE_SMALL,  # [cite: 77]
                    color,  # [cite: 77]
                    1,  # [cite: 77]
                )  # [cite: 78]
            else:  # [cite: 78]
                cv2.putText(
                    menu_frame,
                    text,  # [cite: 78]
                    (20, y_offset + item_height),  # [cite: 79]
                    cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 79]
                    UIConstants.FONT_SCALE_SMALL,  # [cite: 79]
                    color,  # [cite: 79]
                    1,  # [cite: 79]
                )  # [cite: 80]
            y_offset += item_height + 2  # [cite: 80]

    back_y = y_offset + 10  # [cite: 80]
    item_height = 35  # [cite: 80] # Reset item height
    _draw_button(
        menu_frame,
        20,  # [cite: 80]
        back_y,  # [cite: 80]
        menu_frame.shape[1] - 40,  # [cite: 80]
        item_height,  # [cite: 80]
        "Back",  # [cite: 80]
        UIConstants.CV2_BLUE,  # [cite: 80]
        UIConstants.FONT_SCALE_MEDIUM,  # [cite: 81]
    )
    game_state.submenu_items.append(
        (
            (20, back_y, menu_frame.shape[1] - 40, item_height),  # [cite: 81]
            "back_to_main",
            "Back",
        )  # [cite: 81]
    )
    game_state.menu_height = back_y + item_height + 20  # [cite: 81]


def _draw_help_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Help submenu."""  # [cite: 81]
    cv2.putText(
        menu_frame,
        "Help",  # [cite: 81]
        (30, 40),  # [cite: 81]
        cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 82]
        UIConstants.FONT_SCALE_LARGE,  # [cite: 82]
        UIConstants.WHITE,  # [cite: 82]
        UIConstants.FONT_THICKNESS,  # [cite: 82]
    )
    y_offset = 80  # [cite: 82]
    item_height = 20  # [cite: 82]
    game_state.submenu_items.clear()  # [cite: 82]
    help_text = [
        "Controls:",  # [cite: 82]
        "  'm' / Click Menu Btn : Toggle Menu",  # [cite: 82]
        "  's' : Start/Stop drawing zone (while playing)",  # [cite: 82]
        "  'd' : Toggle General Debug Logs",  # [cite: 83]
        "  'b' : Toggle Visual Debug Overlay",  # [cite: 83]
        "  'p' : Pause/Resume Game (while playing)",  # [cite: 83]
        "  'q' / ESC: Quit Game",  # [cite: 83]
        "  BACKSPACE: Go back in menu / Close menu",  # [cite: 83]
        "",  # [cite: 83]
        "Gameplay:",  # [cite: 83]
        "  - Define scoring zones via Menu > Manage Zones.",  # [cite: 84]
        "  - Score points by getting balls into zones.",  # [cite: 84]
        "  - Leftmost zone is the 'Special Hole'.",  # [cite: 84]
        "  - Change modes in Menu > Game Mode.",  # [cite: 84]
        "  - Edit zones in Menu > Manage Zones > Edit Zones.",  # [cite: 84]
        "  - Edit player names in Menu > Players.",  # [cite: 84]
    ]
    for line in help_text:  # [cite: 85]
        cv2.putText(
            menu_frame,
            line,  # [cite: 85]
            (20, y_offset + item_height),  # [cite: 85]
            cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 85]
            UIConstants.FONT_SCALE_SMALL,  # [cite: 85]
            UIConstants.WHITE,  # [cite: 85]
            1,  # [cite: 86]
        )
        y_offset += item_height  # [cite: 86]
    back_y = y_offset + 10  # [cite: 86]
    item_height = 35  # [cite: 86] # Reset item height
    _draw_button(
        menu_frame,
        20,  # [cite: 86]
        back_y,  # [cite: 86]
        menu_frame.shape[1] - 40,  # [cite: 86]
        item_height,  # [cite: 86]
        "Back",  # [cite: 86]
        UIConstants.CV2_BLUE,  # [cite: 86]
        UIConstants.FONT_SCALE_MEDIUM,  # [cite: 87]
    )
    game_state.submenu_items.append(
        (
            (20, back_y, menu_frame.shape[1] - 40, item_height),  # [cite: 87]
            "back_to_main",
            "Back",
        )  # [cite: 87]
    )
    game_state.menu_height = back_y + item_height + 20  # [cite: 87]


def _draw_faq_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the FAQ submenu."""  # [cite: 87]
    cv2.putText(
        menu_frame,
        "FAQ",  # [cite: 87]
        (30, 40),  # [cite: 87]
        cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 88]
        UIConstants.FONT_SCALE_LARGE,  # [cite: 88]
        UIConstants.WHITE,  # [cite: 88]
        UIConstants.FONT_THICKNESS,  # [cite: 88]
    )
    y_offset = 80  # [cite: 88]
    item_height = 20  # [cite: 88]
    game_state.submenu_items.clear()  # [cite: 88]
    faq_text = [
        "Q: Why aren't balls being detected?",  # [cite: 88]
        "A: Check lighting.",  # [cite: 89]
        "   Use Debug Overlay ('b') to see tracked balls.",  # [cite: 89]
        "   Check YOLO model confidence if needed.",  # [cite: 89]
        "",  # [cite: 89]
        "Q: How do I define scoring zones accurately?",  # [cite: 89]
        "A: Use 's' key, click and drag.",  # [cite: 89]
        "   Use Edit Zones menu to delete/modify.",  # [cite: 90]
        "",  # [cite: 90]
        "Q: What is the 'Special Hole'?",  # [cite: 90]
        "A: The leftmost zone, potentially for bonus points",  # [cite: 90]
        "   or specific achievements.",  # [cite: 90]
    ]
    for line in faq_text:  # [cite: 90]
        cv2.putText(
            menu_frame,
            line,  # [cite: 91]
            (20, y_offset + item_height),  # [cite: 91]
            cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 91]
            UIConstants.FONT_SCALE_SMALL,  # [cite: 91]
            UIConstants.WHITE,  # [cite: 91]
            1,  # [cite: 91]
        )
        y_offset += item_height  # [cite: 91]
    back_y = y_offset + 10  # [cite: 92]
    item_height = 35  # [cite: 92] # Reset item height
    _draw_button(
        menu_frame,
        20,  # [cite: 92]
        back_y,  # [cite: 92]
        menu_frame.shape[1] - 40,  # [cite: 92]
        item_height,  # [cite: 92]
        "Back",  # [cite: 92]
        UIConstants.CV2_BLUE,  # [cite: 92]
        UIConstants.FONT_SCALE_MEDIUM,  # [cite: 92]
    )
    game_state.submenu_items.append(
        (
            (20, back_y, menu_frame.shape[1] - 40, item_height),  # [cite: 92]
            "back_to_main",
            "Back",
        )  # [cite: 93]
    )
    game_state.menu_height = back_y + item_height + 20  # [cite: 93]


def _draw_about_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the About submenu."""  # [cite: 93]
    cv2.putText(
        menu_frame,
        "About",  # [cite: 93]
        (30, 40),  # [cite: 93]
        cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 93]
        UIConstants.FONT_SCALE_LARGE,  # [cite: 93]
        UIConstants.WHITE,  # [cite: 93]
        UIConstants.FONT_THICKNESS,  # [cite: 94]
    )
    y_offset = 80  # [cite: 94]
    item_height = 35  # [cite: 94]
    game_state.submenu_items.clear()  # [cite: 94]
    cv2.putText(
        menu_frame,
        "Whiffle Tracker v11.3",  # [cite: 94]
        (20, y_offset),  # [cite: 94]
        cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 94]
        UIConstants.FONT_SCALE_MEDIUM,  # [cite: 94]
        UIConstants.WHITE,  # [cite: 94]
        1,  # [cite: 94]
    )
    y_offset += item_height  # [cite: 94]
    cv2.putText(  # [cite: 95]
        menu_frame,
        "Developed using OpenCV & YOLOv8",  # [cite: 95]
        (20, y_offset),  # [cite: 95]
        cv2.FONT_HERSHEY_SIMPLEX,  # [cite: 95]
        UIConstants.FONT_SCALE_SMALL,  # [cite: 95]
        UIConstants.WHITE,  # [cite: 95]
        1,  # [cite: 95]
    )
    y_offset += item_height + 10  # [cite: 95]
    splash_y = y_offset  # [cite: 95]
    _draw_button(
        menu_frame,
        20,  # [cite: 96]
        splash_y,  # [cite: 96]
        menu_frame.shape[1] - 40,  # [cite: 96]
        item_height,  # [cite: 96]
        "Show Splash",  # [cite: 96]
        UIConstants.CV2_BLUE,  # [cite: 96]
        UIConstants.FONT_SCALE_MEDIUM,  # [cite: 96]
    )
    # Assuming show_splash_on_click handles the action or import it if needed
    game_state.submenu_items.append(
        (
            (20, splash_y, menu_frame.shape[1] - 40, item_height),  # [cite: 96]
            "show_splash",  # [cite: 96]
            "Show Splash",  # [cite: 97]
        )
    )
    y_offset += item_height + 5  # [cite: 97]
    back_y = y_offset + 10  # [cite: 97]
    _draw_button(
        menu_frame,
        20,  # [cite: 97]
        back_y,  # [cite: 97]
        menu_frame.shape[1] - 40,  # [cite: 97]
        item_height,  # [cite: 97]
        "Back",  # [cite: 97]
        UIConstants.CV2_BLUE,  # [cite: 97]
        UIConstants.FONT_SCALE_MEDIUM,  # [cite: 98]
    )
    game_state.submenu_items.append(
        (
            (20, back_y, menu_frame.shape[1] - 40, item_height),  # [cite: 98]
            "back_to_main",
            "Back",
        )  # [cite: 98]
    )
    game_state.menu_height = back_y + item_height + 20  # [cite: 98]
