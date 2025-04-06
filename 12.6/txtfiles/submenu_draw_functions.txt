# submenu_draw_functions.py
"""
Specific submenu drawing functions for the Whiffle Tracker project.

This module contains the drawing logic for leaderboards, player management,
achievements, help, FAQ, and about screens. Includes volume sliders in settings.
"""

import logging
from math import ceil

import cv2
import numpy as np

# Import constants
from constants import (GameConstants, UIConstants)
# Keep GameState import for now, but hints will use strings
from game_state import GameState
# Import types/enums
from game_types import CurrentGameState  # Use the new location
# Import necessary base utilities
from menu_utils import _draw_button

logger = logging.getLogger(__name__)


# --- Helper to Draw Volume Slider with Mute Toggle ---
# Use string literal 'GameState' for type hint
def _draw_volume_slider(
    menu_frame: np.ndarray,
    y_pos: int,
    label: str,
    current_volume: float,
    is_on: bool,
    toggle_action: str,
    slider_action: str,
    game_state: "GameState",
) -> int:
    """Draws a label, a volume slider, percentage text, and a mute toggle button."""
    # (Code unchanged)
    slider_width = UIConstants.SLIDER_WIDTH
    slider_height = UIConstants.SLIDER_HEIGHT
    handle_width = UIConstants.SLIDER_HANDLE_WIDTH
    button_width = 60
    spacing = 15
    label_text = f"{label}:"
    label_x = 20
    label_y = y_pos + slider_height // 2 + 5
    cv2.putText(
        menu_frame,
        label_text,
        (label_x, label_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.WHITE,
        1,
        cv2.LINE_AA,
    )
    current_x = (label_x +
                 cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX,
                                 UIConstants.FONT_SCALE_MEDIUM, 1)[0][0] +
                 spacing)
    slider_x = current_x
    slider_y = y_pos
    cv2.rectangle(
        menu_frame,
        (slider_x, slider_y),
        (slider_x + slider_width, slider_y + slider_height),
        UIConstants.SLIDER_BG,
        -1,
    )
    slider_rect = (slider_x, slider_y, slider_width, slider_height)
    game_state.submenu_items.append(
        (slider_rect, slider_action, f"Adjust {label}"))
    current_x += slider_width + spacing
    handle_center_x = int(slider_x + current_volume * slider_width)
    handle_x1 = max(slider_x, handle_center_x - handle_width // 2)
    handle_x2 = min(slider_x + slider_width,
                    handle_center_x + handle_width // 2)
    handle_x1 = min(handle_x1, slider_x + slider_width - handle_width // 4)
    handle_x2 = max(handle_x2, slider_x + handle_width // 4)
    cv2.rectangle(
        menu_frame,
        (handle_x1, slider_y),
        (handle_x2, slider_y + slider_height),
        UIConstants.SLIDER_HANDLE,
        -1,
    )
    percent_text = f"{int(current_volume * 100)}%"
    text_width = cv2.getTextSize(percent_text, cv2.FONT_HERSHEY_SIMPLEX,
                                 UIConstants.FONT_SCALE_SMALL, 1)[0][0]
    text_x = current_x
    text_y = y_pos + slider_height // 2 + 5
    cv2.putText(
        menu_frame,
        percent_text,
        (text_x, text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_SMALL,
        UIConstants.WHITE,
        1,
        cv2.LINE_AA,
    )
    current_x += text_width + spacing
    mute_button_x = current_x
    mute_button_y = y_pos
    mute_text = "Mute" if is_on else "Unmute"
    mute_color = UIConstants.RED if is_on else UIConstants.GREEN
    _draw_button(
        menu_frame,
        mute_button_x,
        mute_button_y,
        button_width,
        slider_height,
        mute_text,
        mute_color,
        UIConstants.FONT_SCALE_SMALL,
    )
    toggle_rect = (mute_button_x, mute_button_y, button_width, slider_height)
    game_state.submenu_items.append(
        (toggle_rect, toggle_action, f"Toggle {label}"))
    return slider_height + 10


# --- Settings Submenu ---
# Use string literal 'GameState' for type hint
def _draw_settings_submenu(menu_frame: np.ndarray,
                           game_state: "GameState") -> None:
    """Draw the Settings submenu with volume sliders and other toggles."""
    # (Code unchanged)
    cv2.putText(
        menu_frame,
        "Settings",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )
    y_offset = 80
    game_state.submenu_items.clear()
    y_offset += _draw_volume_slider(
        menu_frame,
        y_offset,
        "Sound Effects",
        game_state.current_sound_volume,
        game_state.game_sounds_on,
        "toggle_game_sounds",
        "adjust_sound_volume",
        game_state,
    )
    y_offset += _draw_volume_slider(
        menu_frame,
        y_offset,
        "Background Music",
        game_state.current_music_volume,
        game_state.background_music_on,
        "toggle_background_music",
        "adjust_music_volume",
        game_state,
    )
    button_width = 150
    item_height = 35
    track_label_text = "Music Track:"
    cv2.putText(
        menu_frame,
        track_label_text,
        (20, y_offset + 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.WHITE,
        1,
    )
    current_track_index = game_state.selected_music_track_index
    total_tracks = len(GameConstants.BACKGROUND_MUSIC_TRACKS)
    track_display_text = ("N/A" if total_tracks == 0 else
                          f"Track {current_track_index + 1} / {total_tracks}")
    track_button_x = menu_frame.shape[1] - button_width - 20
    _draw_button(
        menu_frame,
        track_button_x,
        y_offset,
        button_width,
        item_height,
        track_display_text,
        UIConstants.CV2_BLUE,
        UIConstants.FONT_SCALE_SMALL,
    )
    if total_tracks > 0:
        game_state.submenu_items.append((
            (track_button_x, y_offset, button_width, item_height),
            "cycle_music_track",
            "Cycle Music Track",
        ))
    y_offset += item_height + 5
    debug_toggles = [
        (
            "Visual Debug Overlay",
            lambda: game_state.show_debug_overlay,
            "toggle_debug_overlay",
        ),
        ("General Debug Mode", lambda: game_state.debug_mode,
         "toggle_debug_mode"),
    ]
    toggle_button_width = 80
    for label, get_state, action in debug_toggles:
        state = get_state()
        label_text = f"{label}:"
        state_text = "ON" if state else "OFF"
        state_color = UIConstants.GREEN if state else UIConstants.RED
        cv2.putText(
            menu_frame,
            label_text,
            (20, y_offset + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            1,
        )
        button_x = menu_frame.shape[1] - toggle_button_width - 20
        _draw_button(
            menu_frame,
            button_x,
            y_offset,
            toggle_button_width,
            item_height,
            state_text,
            state_color,
            UIConstants.FONT_SCALE_MEDIUM,
        )
        game_state.submenu_items.append(
            ((button_x, y_offset, toggle_button_width, item_height), action,
             label))
        y_offset += item_height + 5
    back_y = y_offset + 10
    back_button_height = 35
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
    game_state.submenu_items.append((
        (20, back_y, menu_frame.shape[1] - 40, back_button_height),
        "back_to_main",
        "Back",
    ))
    game_state.menu_height = back_y + back_button_height + 20


# --- Leaderboard Submenu ---
# Use string literal 'GameState' for type hint
def _draw_leaderboard_submenu(menu_frame: np.ndarray,
                              game_state: "GameState") -> None:
    """Draw the Leaderboard submenu."""
    # (Code unchanged)
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
    display_mode = game_state.leaderboard_mode.capitalize()
    cv2.putText(
        menu_frame,
        f"Mode: {display_mode}",
        (20, y_offset - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.YELLOW,
        1,
    )
    scores, is_online = ([], False)
    if hasattr(game_state, "leaderboard") and game_state.leaderboard:
        scores, is_online = game_state.leaderboard.get_top_scores(
            limit=10, mode=game_state.leaderboard_mode)
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
    mode_button_y = y_offset + 10
    mode_button_height = 30
    num_buttons = 3
    button_spacing = 10
    total_button_space = menu_frame.shape[1] - 40
    total_spacing = button_spacing * (num_buttons - 1)
    mode_button_width = (total_button_space - total_spacing) // num_buttons
    classic_x = 20
    timed_x = classic_x + mode_button_width + button_spacing
    survival_x = timed_x + mode_button_width + button_spacing
    classic_color = (UIConstants.GREEN if game_state.leaderboard_mode
                     == "classic" else UIConstants.CV2_BLUE)
    _draw_button(
        menu_frame,
        classic_x,
        mode_button_y,
        mode_button_width,
        mode_button_height,
        "Classic",
        classic_color,
        UIConstants.FONT_SCALE_SMALL,
    )
    game_state.submenu_items.append((
        (classic_x, mode_button_y, mode_button_width, mode_button_height),
        "leaderboard_classic",
        "Classic Leaderboard",
    ))
    timed_color = (UIConstants.GREEN if game_state.leaderboard_mode == "timed"
                   else UIConstants.CV2_BLUE)
    _draw_button(
        menu_frame,
        timed_x,
        mode_button_y,
        mode_button_width,
        mode_button_height,
        "Timed",
        timed_color,
        UIConstants.FONT_SCALE_SMALL,
    )
    game_state.submenu_items.append((
        (timed_x, mode_button_y, mode_button_width, mode_button_height),
        "leaderboard_timed",
        "Timed Leaderboard",
    ))
    survival_color = (UIConstants.GREEN if game_state.leaderboard_mode
                      == "survival" else UIConstants.CV2_BLUE)
    _draw_button(
        menu_frame,
        survival_x,
        mode_button_y,
        mode_button_width,
        mode_button_height,
        "Survival",
        survival_color,
        UIConstants.FONT_SCALE_SMALL,
    )
    game_state.submenu_items.append((
        (survival_x, mode_button_y, mode_button_width, mode_button_height),
        "leaderboard_survival",
        "Survival Leaderboard",
    ))
    y_offset = mode_button_y + mode_button_height + 5
    back_y = y_offset + 10
    back_button_height = 35
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
    game_state.submenu_items.append((
        (20, back_y, menu_frame.shape[1] - 40, back_button_height),
        "back_to_main",
        "Back",
    ))
    game_state.menu_height = back_y + back_button_height + 20


# --- Players Submenu ---
# Use string literal 'GameState' for type hint
def _draw_players_submenu(menu_frame: np.ndarray,
                          game_state: "GameState") -> None:
    """Draw the Players submenu."""
    # (Code unchanged)
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
    button_width = 80
    button_spacing = 10
    name_width = menu_frame.shape[1] - 40 - \
        (button_width * 2 + button_spacing * 2)
    game_state.submenu_items.clear()
    if (game_state.editing_player_mode == "edit_name"
            and game_state.editing_player_index is not None):
        cv2.putText(
            menu_frame,
            "Enter Name (A-Z, 0-9), Bksp, Enter=Save, ESC=Cancel",
            (20, y_offset - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.YELLOW,
            1,
        )
        y_offset += 15
    for i, player in enumerate(game_state.players):
        name_color = UIConstants.WHITE
        display_name = f"{i+1}. {player.name}"
        if (game_state.editing_player_index == i
                and game_state.editing_player_mode == "edit_name"):
            display_name = f"Edit: [{game_state.editing_player_name_input or ''}_]"
            name_color = UIConstants.GREEN
        max_name_len = name_width // 8
        cv2.putText(
            menu_frame,
            display_name[:max_name_len],
            (20, y_offset + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            name_color,
            1,
        )
        edit_x = 20 + name_width + button_spacing
        edit_rect = (edit_x, y_offset, button_width, item_height)
        edit_color = (UIConstants.GREEN if game_state.editing_player_index == i
                      and game_state.editing_player_mode == "edit_name" else
                      UIConstants.CV2_BLUE)
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
            (edit_rect, f"edit_player_name_{i}", f"Edit P{i+1} Name"))
        select_x = edit_x + button_width + button_spacing
        select_rect = (select_x, y_offset, button_width, item_height)
        is_current = i == game_state.current_player_index
        select_color = UIConstants.GREEN if is_current else UIConstants.CV2_BLUE
        select_text = "Current" if is_current else "Select"
        if (game_state.editing_player_index == i
                and game_state.editing_player_mode == "edit_name"):
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
        if not is_current:
            game_state.submenu_items.append(
                (select_rect, f"select_player_{i}", f"Select P{i+1}"))
        y_offset += item_height + 5
    add_y = y_offset + 5
    add_color = (UIConstants.CV2_BLUE
                 if len(game_state.players) < 2 else UIConstants.GREY_BG)
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
    if len(game_state.players) < 2:
        game_state.submenu_items.append((
            (20, add_y, menu_frame.shape[1] - 40, item_height),
            "add_player",
            "Add Player",
        ))
    y_offset = add_y + item_height + 5
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
    game_state.submenu_items.append(((20, back_y, menu_frame.shape[1] - 40,
                                      item_height), "back_to_main", "Back"))
    game_state.menu_height = back_y + item_height + 20


# --- Achievements Submenu ---
# Use string literal 'GameState' for type hint
def _draw_achievements_submenu(menu_frame: np.ndarray,
                               game_state: "GameState") -> None:
    """Draw the Achievements submenu."""
    # (Code unchanged)
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
                line1 = text[:break_point]
                line2 = "  " + text[break_point:].strip()
            else:
                line1 = text
                line2 = None
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
            if line2:
                cv2.putText(
                    menu_frame,
                    line2,
                    (20, y_offset + item_height),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    UIConstants.FONT_SCALE_SMALL,
                    color,
                    1,
                )
                y_offset += item_height + 2  # Extra spacing if wrapped
            else:
                y_offset += 2  # Normal spacing
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
    game_state.submenu_items.append(((20, back_y, menu_frame.shape[1] - 40,
                                      item_height), "back_to_main", "Back"))
    game_state.menu_height = back_y + item_height + 20


# --- Help Submenu ---
# Use string literal 'GameState' for type hint
def _draw_help_submenu(menu_frame: np.ndarray,
                       game_state: "GameState") -> None:
    """Draw the Help submenu."""
    # (Code unchanged)
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
        "  's' : Start/Stop drawing zone",
        "  'd' : Toggle Debug Logs",
        "  'b' : Toggle Debug Overlay",
        "  'p' : Pause/Resume Game",
        "  'q' / ESC: Quit Game",
        "  BACKSPACE: Go back in menu",
        "",
        "Gameplay:",
        "  - Define/Edit zones via Menu > Manage Zones.",
        "  - Score points by getting balls into zones.",
        "  - Leftmost zone is 'Special Hole'.",
        "  - Change modes in Menu > Game Mode.",
        "  - Edit names in Menu > Players.",
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
    game_state.submenu_items.append(((20, back_y, menu_frame.shape[1] - 40,
                                      item_height), "back_to_main", "Back"))
    game_state.menu_height = back_y + item_height + 20


# --- FAQ Submenu ---
# Use string literal 'GameState' for type hint
def _draw_faq_submenu(menu_frame: np.ndarray, game_state: "GameState") -> None:
    """Draw the FAQ submenu."""
    # (Code unchanged)
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
        "Q: Why aren't balls detected?",
        "A: Check lighting. Use Debug Overlay ('b').",
        "",
        "Q: How do I define zones accurately?",
        "A: Use 's' key, drag. Edit in Menu > Manage Zones.",
        "",
        "Q: What's the 'Special Hole'?",
        "A: Leftmost zone, may give bonus points.",
        "",
        "Q: Why is Edit Zones list cut off?",
        "A: Use Prev/Next buttons for pagination.",
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
    game_state.submenu_items.append(((20, back_y, menu_frame.shape[1] - 40,
                                      item_height), "back_to_main", "Back"))
    game_state.menu_height = back_y + item_height + 20


# --- About Submenu ---
# Use string literal 'GameState' for type hint
def _draw_about_submenu(menu_frame: np.ndarray,
                        game_state: "GameState") -> None:
    """Draw the About submenu."""
    # (Code unchanged)
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
        "Whiffle Tracker v12.X",
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
    game_state.submenu_items.append((
        (20, splash_y, menu_frame.shape[1] - 40, item_height),
        "show_splash",
        "Show Splash",
    ))
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
    game_state.submenu_items.append(((20, back_y, menu_frame.shape[1] - 40,
                                      item_height), "back_to_main", "Back"))
    game_state.menu_height = back_y + item_height + 20


# --- Edit Zones Submenu ---
# Use string literal 'GameState' for type hint
def _draw_edit_zones_submenu(menu_frame: np.ndarray,
                             game_state: "GameState") -> None:
    """Draw the Edit Zones submenu with pagination and Move/Resize options."""
    # (Code unchanged, uses CurrentGameState imported correctly now)
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
    button_width = 45
    button_spacing = 3
    num_buttons = 4
    actions_width = (button_width * num_buttons) + \
        (button_spacing * (num_buttons - 1))
    list_width = menu_frame.shape[1] - 40 - actions_width - button_spacing
    game_state.submenu_items.clear()
    items_per_page = game_state.edit_zones_items_per_page
    total_zones = len(game_state.scoring_zones)
    total_pages = max(1, ceil(total_zones / items_per_page))
    game_state.edit_zones_current_page = max(
        1, min(game_state.edit_zones_current_page, total_pages))
    current_page = game_state.edit_zones_current_page
    start_index = (current_page - 1) * items_per_page
    end_index = start_index + items_per_page
    zones_to_display = game_state.scoring_zones[start_index:end_index]
    confirm_delete_message = None
    if (game_state.editing_zone_mode == "confirm_delete"
            and game_state.editing_zone_index is not None
            and start_index <= game_state.editing_zone_index < end_index):
        confirm_delete_message = (
            f"Click Delete again for Zone {game_state.editing_zone_index+1} to confirm?"
        )
    edit_instruction_message = None
    if (game_state.editing_zone_mode == "edit_points"
            and game_state.editing_zone_index is not None
            and start_index <= game_state.editing_zone_index < end_index):
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
        for i_display, zone_data in enumerate(zones_to_display):
            original_index = start_index + i_display
            x_z, y_z, w_z, h_z, points = zone_data
            zone_label = f"{original_index+1}: @({x_z},{y_z}) Pts="
            label_color = UIConstants.WHITE
            if (game_state.editing_zone_index == original_index
                    and game_state.editing_zone_mode == "edit_points"):
                input_display = game_state.editing_zone_points_input or "___"
                zone_label += f"[ {input_display} ]"
                label_color = UIConstants.GREEN
            else:
                zone_label += str(points)
            if game_state.selected_zone_for_edit == original_index:
                label_color = UIConstants.ZONE_EDIT_SELECTED_COLOR
            cv2.putText(
                menu_frame,
                zone_label[:45],
                (20, y_offset + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_SMALL,
                label_color,
                1,
            )
            button_x = 20 + list_width + button_spacing
            edit_rect = (button_x, y_offset, button_width, item_height)
            edit_color = (UIConstants.GREEN
                          if game_state.editing_zone_index == original_index
                          and game_state.editing_zone_mode == "edit_points"
                          else UIConstants.CV2_BLUE)
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
            game_state.submenu_items.append((
                edit_rect,
                f"edit_zone_{original_index}",
                f"Edit Zone {original_index+1} Points",
            ))
            button_x += button_width + button_spacing
            move_rect = (button_x, y_offset, button_width, item_height)
            is_moving_this_zone = (
                game_state.current_state == CurrentGameState.ZONE_EDITING
                and game_state.selected_zone_for_edit == original_index
                and game_state.zone_editing_action == "move")
            move_color = (UIConstants.ZONE_EDIT_MOVE_COLOR
                          if is_moving_this_zone else UIConstants.CV2_BLUE)
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
            game_state.submenu_items.append((
                move_rect,
                f"move_zone_{original_index}",
                f"Move Zone {original_index+1}",
            ))
            button_x += button_width + button_spacing
            resize_rect = (button_x, y_offset, button_width, item_height)
            is_resizing_this_zone = (
                game_state.current_state == CurrentGameState.ZONE_EDITING
                and game_state.selected_zone_for_edit == original_index
                and game_state.zone_editing_action
                and game_state.zone_editing_action.startswith("resize"))
            resize_color = (UIConstants.ZONE_EDIT_RESIZE_COLOR
                            if is_resizing_this_zone else UIConstants.CV2_BLUE)
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
            game_state.submenu_items.append((
                resize_rect,
                f"resize_zone_{original_index}",
                f"Resize Zone {original_index+1}",
            ))
            button_x += button_width + button_spacing
            delete_rect = (button_x, y_offset, button_width, item_height)
            delete_color = (UIConstants.RED
                            if game_state.editing_zone_index == original_index
                            and game_state.editing_zone_mode
                            == "confirm_delete" else UIConstants.CV2_BLUE)
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
            game_state.submenu_items.append((
                delete_rect,
                f"delete_zone_{original_index}",
                f"Delete Zone {original_index+1}",
            ))
            y_offset += item_height + 5
    page_y_start = y_offset + 10
    page_item_height = 35
    page_button_width = 80
    page_text = f"Page {current_page} / {total_pages}"
    (tw, th), _ = cv2.getTextSize(page_text, cv2.FONT_HERSHEY_SIMPLEX,
                                  UIConstants.FONT_SCALE_SMALL, 1)
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
        game_state.submenu_items.append((
            (prev_button_x, page_y_start, page_button_width, page_item_height),
            "prev_edit_zone_page",
            "Previous Page",
        ))
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
        game_state.submenu_items.append((
            (next_button_x, page_y_start, page_button_width, page_item_height),
            "next_edit_zone_page",
            "Next Page",
        ))
    y_offset = page_y_start + page_item_height + 5
    back_y = y_offset + 10
    back_button_height = 35
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
    game_state.submenu_items.append((
        (20, back_y, menu_frame.shape[1] - 40, back_button_height),
        "back_to_manage_zones",
        "Back",
    ))
    game_state.menu_height = back_y + back_button_height + 20
