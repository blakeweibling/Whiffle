# submenu_draw_functions.py
"""
Specific submenu drawing functions for the Whiffle Tracker project.

This module contains the drawing logic for leaderboards, player management,
achievements, help, FAQ, and about screens. Includes volume sliders in settings.
"""

import logging
from math import ceil
import time

# <<< ADDED IMPORT >>>
from typing import TYPE_CHECKING

import cv2
import numpy as np

# Import constants
from constants import GameConstants, UIConstants, MenuConstants, ReplayConstants

# Keep GameState import for now, but hints will use strings
# from game_state import GameState # Avoid direct import if causing cycles
# Import types/enums
from game_types import CurrentGameState  # Use the new location

# Import necessary base utilities
# <<< MODIFIED: Pass game_state to _draw_button >>>
from menu_utils import _draw_button

# <<< ADDED FOR TYPE HINTING >>>
if TYPE_CHECKING:
    from game_state import GameState

logger = logging.getLogger(__name__)


# --- Helper to Draw Volume Slider with Mute Toggle ---
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
    current_x = (
        label_x
        + cv2.getTextSize(
            label_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, 1
        )[0][0]
        + UIConstants.TEXT_SAFE_DISTANCE
    )
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
    game_state.submenu_items.append((slider_rect, slider_action, f"Adjust {label}"))
    current_x += slider_width + spacing
    handle_center_x = int(slider_x + current_volume * slider_width)
    handle_x1 = max(slider_x, handle_center_x - handle_width // 2)
    handle_x2 = min(slider_x + slider_width, handle_center_x + handle_width // 2)
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
    text_width = cv2.getTextSize(
        percent_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, 1
    )[0][0]
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
    mute_color = UIConstants.RED if is_on else UIConstants.ACCENT
    _draw_button(
        menu_frame,
        mute_button_x,
        mute_button_y,
        button_width,
        slider_height,
        mute_text,
        mute_color,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_SMALL,
    )
    toggle_rect = (mute_button_x, mute_button_y, button_width, slider_height)
    game_state.submenu_items.append((toggle_rect, toggle_action, f"Toggle {label}"))
    return slider_height + 10


# --- Settings Submenu ---
def _draw_settings_submenu(menu_frame: np.ndarray, game_state: "GameState") -> None:
    """Draw the Settings submenu with volume sliders and other toggles."""
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
    # _draw_volume_slider calls _draw_button internally and passes game_state
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
    track_display_text = (
        "N/A"
        if total_tracks == 0
        else f"Track {current_track_index + 1} / {total_tracks}"
    )
    track_button_x = menu_frame.shape[1] - button_width - 20
    _draw_button(
        menu_frame,
        track_button_x,
        y_offset,
        button_width,
        item_height,
        track_display_text,
        UIConstants.PRIMARY,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_SMALL,
    )
    if total_tracks > 0:
        game_state.submenu_items.append(
            (
                (track_button_x, y_offset, button_width, item_height),
                "cycle_music_track",
                "Cycle Music Track",
            )
        )
    y_offset += item_height + 5

    # Add accessibility toggles
    accessibility_toggles = [
        (
            "Colorblind Mode",
            lambda: getattr(game_state, "colorblind_mode", False),
            "toggle_colorblind_mode",
        ),
    ]

    # Display accessibility toggles
    for label, get_state, action in accessibility_toggles:
        state = get_state()
        label_text = f"{label}:"
        state_text = "ON" if state else "OFF"
        state_color = UIConstants.ACCENT if state else UIConstants.RED
        cv2.putText(
            menu_frame,
            label_text,
            (20, y_offset + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            1,
        )
        toggle_button_width = 80
        button_x = menu_frame.shape[1] - toggle_button_width - 20
        _draw_button(
            menu_frame,
            button_x,
            y_offset,
            toggle_button_width,
            item_height,
            state_text,
            state_color,
            game_state=game_state,
            font_scale=UIConstants.FONT_SCALE_MEDIUM,
        )
        game_state.submenu_items.append(
            ((button_x, y_offset, toggle_button_width, item_height), action, label)
        )
        y_offset += item_height + 5

    debug_toggles = [
        (
            "Visual Debug Overlay",
            lambda: game_state.show_debug_overlay,
            "toggle_debug_overlay",
        ),
        ("General Debug Mode", lambda: game_state.debug_mode, "toggle_debug_mode"),
    ]
    toggle_button_width = 80
    for label, get_state, action in debug_toggles:
        state = get_state()
        label_text = f"{label}:"
        state_text = "ON" if state else "OFF"
        state_color = UIConstants.ACCENT if state else UIConstants.RED
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
            game_state=game_state,
            font_scale=UIConstants.FONT_SCALE_MEDIUM,
        )
        game_state.submenu_items.append(
            ((button_x, y_offset, toggle_button_width, item_height), action, label)
        )
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
        UIConstants.PRIMARY,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_MEDIUM,
    )
    game_state.submenu_items.append(
        (
            (20, back_y, menu_frame.shape[1] - 40, back_button_height),
            "back_to_main",
            "Back",
        )
    )
    game_state.menu_height = back_y + back_button_height + 20


# --- Leaderboard Submenu ---
def _draw_leaderboard_submenu(menu_frame: np.ndarray, game_state: "GameState") -> None:
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
    display_mode = getattr(game_state, "leaderboard_mode", "classic").capitalize()
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
            limit=10, mode=getattr(game_state, "leaderboard_mode", "classic")
        )
    status_text = "Online" if is_online else "Local (Offline)"
    status_color = UIConstants.ACCENT if is_online else UIConstants.YELLOW
    cv2.putText(
        menu_frame,
        status_text,
        (menu_frame.shape[1] - 150, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_SMALL,
        status_color,
        1,
    )
    if not is_online:
        offline_hint = "Scores from local storage. Connect for online."
        cv2.putText(
            menu_frame,
            offline_hint,
            (20, 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (180, 180, 180),
            1,
        )

    if not scores:
        cv2.putText(
            menu_frame,
            "No scores yet for this mode.",
            (20, y_offset + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            1,
        )
        empty_state_hint = (
            "Finish a live-camera game to add a score here."
            if is_online
            else "Your local fallback board is empty. Connect and finish a run to populate it."
        )
        cv2.putText(
            menu_frame,
            empty_state_hint,
            (20, y_offset + 48),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            (200, 200, 200),
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
    num_buttons_per_row = 3
    button_spacing = 10
    total_button_space = menu_frame.shape[1] - 40
    total_spacing = button_spacing * (num_buttons_per_row - 1)
    mode_button_width = (total_button_space - total_spacing) // num_buttons_per_row

    # First row: Classic, Timed, Survival
    classic_x = 20
    timed_x = classic_x + mode_button_width + button_spacing
    survival_x = timed_x + mode_button_width + button_spacing

    # Second row: Fun, Practice, Retro
    fun_x = classic_x
    practice_x = timed_x
    retro_x = survival_x
    second_row_y = mode_button_y + mode_button_height + button_spacing

    # First row buttons
    classic_color = (
        UIConstants.ACCENT
        if getattr(game_state, "leaderboard_mode", "classic") == "classic"
        else UIConstants.PRIMARY
    )
    _draw_button(
        menu_frame,
        classic_x,
        mode_button_y,
        mode_button_width,
        mode_button_height,
        "Classic",
        classic_color,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_SMALL,
    )
    game_state.submenu_items.append(
        (
            (classic_x, mode_button_y, mode_button_width, mode_button_height),
            "leaderboard_classic",
            "Classic Leaderboard",
        )
    )

    timed_color = (
        UIConstants.ACCENT
        if getattr(game_state, "leaderboard_mode", "classic") == "timed"
        else UIConstants.PRIMARY
    )
    _draw_button(
        menu_frame,
        timed_x,
        mode_button_y,
        mode_button_width,
        mode_button_height,
        "Timed",
        timed_color,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_SMALL,
    )
    game_state.submenu_items.append(
        (
            (timed_x, mode_button_y, mode_button_width, mode_button_height),
            "leaderboard_timed",
            "Timed Leaderboard",
        )
    )

    survival_color = (
        UIConstants.ACCENT
        if getattr(game_state, "leaderboard_mode", "classic") == "survival"
        else UIConstants.PRIMARY
    )
    _draw_button(
        menu_frame,
        survival_x,
        mode_button_y,
        mode_button_width,
        mode_button_height,
        "Survival",
        survival_color,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_SMALL,
    )
    game_state.submenu_items.append(
        (
            (survival_x, mode_button_y, mode_button_width, mode_button_height),
            "leaderboard_survival",
            "Survival Leaderboard",
        )
    )

    # Second row buttons
    fun_color = (
        UIConstants.ACCENT
        if getattr(game_state, "leaderboard_mode", "classic") == "fun"
        else UIConstants.PRIMARY
    )
    _draw_button(
        menu_frame,
        fun_x,
        second_row_y,
        mode_button_width,
        mode_button_height,
        "Fun",
        fun_color,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_SMALL,
    )
    game_state.submenu_items.append(
        (
            (fun_x, second_row_y, mode_button_width, mode_button_height),
            "leaderboard_fun",
            "Fun Leaderboard",
        )
    )

    practice_color = (
        UIConstants.ACCENT
        if getattr(game_state, "leaderboard_mode", "classic") == "practice"
        else UIConstants.PRIMARY
    )
    _draw_button(
        menu_frame,
        practice_x,
        second_row_y,
        mode_button_width,
        mode_button_height,
        "Practice",
        practice_color,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_SMALL,
    )
    game_state.submenu_items.append(
        (
            (practice_x, second_row_y, mode_button_width, mode_button_height),
            "leaderboard_practice",
            "Practice Leaderboard",
        )
    )

    retro_color = (
        UIConstants.ACCENT
        if getattr(game_state, "leaderboard_mode", "classic") == "retro"
        else UIConstants.PRIMARY
    )
    _draw_button(
        menu_frame,
        retro_x,
        second_row_y,
        mode_button_width,
        mode_button_height,
        "Retro",
        retro_color,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_SMALL,
    )
    game_state.submenu_items.append(
        (
            (retro_x, second_row_y, mode_button_width, mode_button_height),
            "leaderboard_retro",
            "Retro Leaderboard",
        )
    )

    y_offset = second_row_y + mode_button_height + 5
    back_y = y_offset + 10
    back_button_height = 35
    _draw_button(
        menu_frame,
        20,
        back_y,
        menu_frame.shape[1] - 40,
        back_button_height,
        "Back",
        UIConstants.PRIMARY,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_MEDIUM,
    )
    game_state.submenu_items.append(
        (
            (20, back_y, menu_frame.shape[1] - 40, back_button_height),
            "back_to_main",
            "Back",
        )
    )
    game_state.menu_height = back_y + back_button_height + 20


# --- Players Submenu ---
def _draw_players_submenu(menu_frame: np.ndarray, game_state: "GameState") -> None:
    """Draw the Players management submenu."""
    # Initialize player editing attributes if not present to prevent AttributeError
    if not hasattr(game_state, "editing_player_mode"):
        game_state.editing_player_mode = None
    if not hasattr(game_state, "editing_player_index"):
        game_state.editing_player_index = None
    if not hasattr(game_state, "editing_player_name_input"):
        game_state.editing_player_name_input = None

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
    name_width = (
        menu_frame.shape[1] - 40 - (button_width * 2 + UIConstants.TEXT_SAFE_DISTANCE)
    )
    game_state.submenu_items.clear()
    if (
        game_state.editing_player_mode == "edit_name"
        and game_state.editing_player_index is not None
    ):
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
        if (
            game_state.editing_player_index == i
            and game_state.editing_player_mode == "edit_name"
        ):
            display_name = f"Edit: [{game_state.editing_player_name_input or ''}_]"
            name_color = UIConstants.ACCENT
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
        edit_color = (
            UIConstants.ACCENT
            if game_state.editing_player_index == i
            and game_state.editing_player_mode == "edit_name"
            else UIConstants.PRIMARY
        )
        _draw_button(
            menu_frame,
            edit_x,
            y_offset,
            button_width,
            item_height,
            "Edit",
            edit_color,
            game_state=game_state,
            font_scale=UIConstants.FONT_SCALE_SMALL,
        )
        game_state.submenu_items.append(
            (edit_rect, f"edit_player_name_{i}", f"Edit P{i+1} Name")
        )

        select_x = edit_x + button_width + button_spacing
        select_rect = (select_x, y_offset, button_width, item_height)
        is_current = i == game_state.current_player_index
        select_color = UIConstants.ACCENT if is_current else UIConstants.PRIMARY
        select_text = "Current" if is_current else "Select"
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
                game_state=game_state,
                font_scale=UIConstants.FONT_SCALE_SMALL,
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
                game_state=game_state,
                font_scale=UIConstants.FONT_SCALE_SMALL,
            )
            if not is_current:
                game_state.submenu_items.append(
                    (select_rect, f"select_player_{i}", f"Select P{i+1}")
                )

        y_offset += item_height + 5

    add_y = y_offset + 5
    add_color = (
        UIConstants.PRIMARY if len(game_state.players) < 4 else UIConstants.GREY_BG
    )
    _draw_button(
        menu_frame,
        20,
        add_y,
        menu_frame.shape[1] - 40,
        item_height,
        "Add Player",
        add_color,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_MEDIUM,
    )
    if len(game_state.players) < 4:
        game_state.submenu_items.append(
            (
                (20, add_y, menu_frame.shape[1] - 40, item_height),
                "add_player",
                "Add Player",
            )
        )
    y_offset = add_y + item_height + 5

    back_y = y_offset + 10
    _draw_button(
        menu_frame,
        20,
        back_y,
        menu_frame.shape[1] - 40,
        item_height,
        "Back",
        UIConstants.PRIMARY,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_MEDIUM,
    )
    game_state.submenu_items.append(
        ((20, back_y, menu_frame.shape[1] - 40, item_height), "back_to_main", "Back")
    )
    game_state.menu_height = back_y + item_height + 20


# --- Achievements Submenu (scrollable) ---
ACHIEVEMENTS_MENU_HEIGHT = 500
ACHIEVEMENTS_LIST_TOP = 80
ACHIEVEMENTS_LIST_VISIBLE_HEIGHT = 340  # space for list before back button
ACHIEVEMENTS_BACK_BUTTON_Y = 435
ACHIEVEMENTS_SCROLL_STEP = 50


def _draw_achievements_submenu(menu_frame: np.ndarray, game_state: "GameState") -> None:
    """Draw the Achievements submenu with scrollable list."""
    menu_h, menu_w = menu_frame.shape[:2]
    game_state.submenu_items.clear()

    # Initialize scroll offset when not set
    if not hasattr(game_state, "achievements_scroll_offset"):
        game_state.achievements_scroll_offset = 0

    cv2.putText(
        menu_frame,
        "Achievements",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )
    item_height = 25
    unlocked_count = sum(1 for ach in game_state.achievements if ach.unlocked)
    total_count = len(game_state.achievements)
    status_text = f"Unlocked: {unlocked_count} / {total_count}"
    cv2.putText(
        menu_frame,
        status_text,
        (20, ACHIEVEMENTS_LIST_TOP - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.YELLOW,
        1,
    )

    list_bottom = ACHIEVEMENTS_LIST_TOP + ACHIEVEMENTS_LIST_VISIBLE_HEIGHT

    if not game_state.achievements:
        cv2.putText(
            menu_frame,
            "No achievements defined.",
            (20, ACHIEVEMENTS_LIST_TOP + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            1,
        )
        total_content_height = 30
    else:
        # Compute total content height and draw only visible lines
        total_content_height = 0
        scroll = getattr(game_state, "achievements_scroll_offset", 0)

        for achievement in game_state.achievements:
            layout_suffix = ""
            if achievement.unlocked and getattr(achievement, "unlocked_layout", None):
                layout_suffix = " (Five Star)" if achievement.unlocked_layout == "fivestar" else " (Whiffle)"
            text = f"- {achievement.name}{layout_suffix}: {achievement.description}"
            color = UIConstants.ACCENT if achievement.unlocked else UIConstants.WHITE
            max_len = 55
            if len(text) > max_len:
                break_point = text.rfind(" ", 0, max_len)
                line1 = text[:break_point]
                line2 = "  " + text[break_point:].strip()
            else:
                line1 = text
                line2 = None

            line_height = item_height + (item_height + 2 if line2 else 2)
            content_y_start = total_content_height
            content_y_end = total_content_height + line_height
            total_content_height = content_y_end

            # Only draw if this block is visible in the scroll window
            screen_y1 = ACHIEVEMENTS_LIST_TOP + content_y_start - scroll
            screen_y2 = ACHIEVEMENTS_LIST_TOP + content_y_end - scroll
            if screen_y2 <= ACHIEVEMENTS_LIST_TOP or screen_y1 >= list_bottom:
                continue

            cv2.putText(
                menu_frame,
                line1,
                (20, screen_y1 + item_height),
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_SMALL,
                color,
                1,
            )
            if line2:
                cv2.putText(
                    menu_frame,
                    line2,
                    (20, screen_y1 + item_height + item_height),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    UIConstants.FONT_SCALE_SMALL,
                    color,
                    1,
                )

        max_scroll = max(0, total_content_height - ACHIEVEMENTS_LIST_VISIBLE_HEIGHT)
        game_state.achievements_scroll_offset = max(0, min(scroll, max_scroll))

        # Scroll indicator on the right: thin track + thumb when content overflows
        if max_scroll > 0:
            track_margin = 12
            track_width = 6
            track_x = menu_w - track_margin - track_width
            track_y1 = ACHIEVEMENTS_LIST_TOP
            track_y2 = list_bottom
            track_height = track_y2 - track_y1
            # Track (subtle line)
            cv2.rectangle(
                menu_frame,
                (track_x, track_y1),
                (track_x + track_width, track_y2),
                (80, 80, 80),
                -1,
            )
            # Thumb: height proportional to visible/total, position to scroll offset
            visible_ratio = ACHIEVEMENTS_LIST_VISIBLE_HEIGHT / total_content_height
            thumb_height = max(24, int(track_height * visible_ratio))
            thumb_range = track_height - thumb_height
            thumb_y = track_y1 + int(
                (game_state.achievements_scroll_offset / max_scroll) * thumb_range
            )
            cv2.rectangle(
                menu_frame,
                (track_x, thumb_y),
                (track_x + track_width, thumb_y + thumb_height),
                (140, 140, 140),
                -1,
            )

    # Back button at fixed position
    back_button_height = 35
    _draw_button(
        menu_frame,
        20,
        ACHIEVEMENTS_BACK_BUTTON_Y,
        menu_w - 40,
        back_button_height,
        "Back",
        UIConstants.PRIMARY,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_MEDIUM,
    )
    game_state.submenu_items.append(
        ((20, ACHIEVEMENTS_BACK_BUTTON_Y, menu_w - 40, back_button_height), "back_to_main", "Back")
    )

    game_state.menu_height = ACHIEVEMENTS_MENU_HEIGHT


# --- Help Submenu ---
def _draw_help_submenu(menu_frame: np.ndarray, game_state: "GameState") -> None:
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
        "  's' : Start/Stop drawing zone",
        "  'd' : Toggle Debug Logs",
        "  'b' : Toggle Debug Overlay",
        "  'p' : Pause/Resume Game",
        "  'q' / ESC: Quit Game",
        "  'n' : New game (at Game Over)",
        "  'h' : View heatmap (at Game Over)",
        "  '1'/'2'/'W'/'F' : Playfield selection",
        "  N/ESC/Q : Cancel quit confirmation",
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
        UIConstants.PRIMARY,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_MEDIUM,
    )
    game_state.submenu_items.append(
        ((20, back_y, menu_frame.shape[1] - 40, item_height), "back_to_main", "Back")
    )
    game_state.menu_height = back_y + item_height + 20


# --- FAQ Submenu ---
def _draw_faq_submenu(menu_frame: np.ndarray, game_state: "GameState") -> None:
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
        UIConstants.PRIMARY,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_MEDIUM,
    )
    game_state.submenu_items.append(
        ((20, back_y, menu_frame.shape[1] - 40, item_height), "back_to_main", "Back")
    )
    game_state.menu_height = back_y + item_height + 20


# --- About Submenu ---
def _draw_about_submenu(menu_frame: np.ndarray, game_state: "GameState") -> None:
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
        "Whiffle Tracker v15.6",
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
        UIConstants.PRIMARY,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_MEDIUM,
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
        UIConstants.PRIMARY,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_MEDIUM,
    )
    game_state.submenu_items.append(
        ((20, back_y, menu_frame.shape[1] - 40, item_height), "back_to_main", "Back")
    )
    game_state.menu_height = back_y + item_height + 20


# --- Edit Zones Submenu ---
def _draw_edit_zones_submenu(menu_frame: np.ndarray, game_state: "GameState") -> None:
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
    item_height = 30
    button_width = 45
    button_spacing = 3
    num_buttons = 4
    actions_width = (button_width * num_buttons) + (button_spacing * (num_buttons - 1))
    list_width = menu_frame.shape[1] - 40 - actions_width - button_spacing
    game_state.submenu_items.clear()

    # Move All Zones button (only when zones exist)
    if game_state.scoring_zones:
        move_all_btn_h = 32
        move_all_color = (
            UIConstants.ZONE_EDIT_MOVE_COLOR
            if getattr(game_state, "move_all_zones", False)
            else UIConstants.PRIMARY
        )
        _draw_button(
            menu_frame,
            20,
            y_offset,
            menu_frame.shape[1] - 40,
            move_all_btn_h,
            "Move All Zones",
            move_all_color,
            game_state=game_state,
            font_scale=UIConstants.FONT_SCALE_SMALL,
        )
        game_state.submenu_items.append(
            (
                (20, y_offset, menu_frame.shape[1] - 40, move_all_btn_h),
                "move_all_zones",
                "Move All Zones",
            )
        )
        y_offset += move_all_btn_h + 8

    items_per_page = game_state.edit_zones_items_per_page
    total_zones = len(game_state.scoring_zones)
    total_pages = max(1, ceil(total_zones / items_per_page))
    game_state.edit_zones_current_page = max(
        1, min(game_state.edit_zones_current_page, total_pages)
    )
    current_page = game_state.edit_zones_current_page
    start_index = (current_page - 1) * items_per_page
    end_index = start_index + items_per_page
    zones_to_display = game_state.scoring_zones[start_index:end_index]

    confirm_delete_message = None
    if (
        game_state.editing_zone_mode == "confirm_delete"
        and game_state.editing_zone_index is not None
        and start_index <= game_state.editing_zone_index < end_index
    ):
        confirm_delete_message = (
            f"Click Delete again for Zone {game_state.editing_zone_index+1} to confirm?"
        )
    edit_instruction_message = None
    if (
        game_state.editing_zone_mode == "edit_points"
        and game_state.editing_zone_index is not None
        and start_index <= game_state.editing_zone_index < end_index
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
        for i_display, zone_data in enumerate(zones_to_display):
            original_index = start_index + i_display
            x_z, y_z, w_z, h_z, points = zone_data
            zone_label = f"{original_index+1}: @({x_z},{y_z}) Pts="
            label_color = UIConstants.WHITE
            if (
                game_state.editing_zone_index == original_index
                and game_state.editing_zone_mode == "edit_points"
            ):
                input_display = game_state.editing_zone_points_input or "___"
                zone_label += f"[ {input_display} ]"
                label_color = UIConstants.ACCENT
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
            edit_color = (
                UIConstants.ACCENT
                if game_state.editing_zone_index == original_index
                and game_state.editing_zone_mode == "edit_points"
                else UIConstants.PRIMARY
            )
            _draw_button(
                menu_frame,
                button_x,
                y_offset,
                button_width,
                item_height,
                "Pts",
                edit_color,
                game_state=game_state,
                font_scale=UIConstants.FONT_SCALE_SMALL,
            )
            game_state.submenu_items.append(
                (
                    edit_rect,
                    f"edit_zone_{original_index}",
                    f"Edit Zone {original_index+1} Points",
                )
            )

            button_x += button_width + button_spacing
            move_rect = (button_x, y_offset, button_width, item_height)
            if (
                game_state.current_state == CurrentGameState.ZONE_EDITING
                and game_state.selected_zone_for_edit == original_index
                and game_state.zone_editing_action == "move"
            ):
                move_color = UIConstants.ZONE_EDIT_MOVE_COLOR
            else:
                move_color = UIConstants.PRIMARY
            _draw_button(
                menu_frame,
                button_x,
                y_offset,
                button_width,
                item_height,
                "Move",
                move_color,
                game_state=game_state,
                font_scale=UIConstants.FONT_SCALE_SMALL,
            )
            game_state.submenu_items.append(
                (
                    move_rect,
                    f"move_zone_{original_index}",
                    f"Move Zone {original_index+1}",
                )
            )

            button_x += button_width + button_spacing
            resize_rect = (button_x, y_offset, button_width, item_height)
            if (
                game_state.current_state == CurrentGameState.ZONE_EDITING
                and game_state.selected_zone_for_edit == original_index
                and game_state.zone_editing_action
                and game_state.zone_editing_action.startswith("resize")
            ):
                resize_color = UIConstants.ZONE_EDIT_RESIZE_COLOR
            else:
                resize_color = UIConstants.PRIMARY
            _draw_button(
                menu_frame,
                button_x,
                y_offset,
                button_width,
                item_height,
                "Resize",
                resize_color,
                game_state=game_state,
                font_scale=UIConstants.FONT_SCALE_SMALL,
            )
            game_state.submenu_items.append(
                (
                    resize_rect,
                    f"resize_zone_{original_index}",
                    f"Resize Zone {original_index+1}",
                )
            )

            button_x += button_width + button_spacing
            delete_rect = (button_x, y_offset, button_width, item_height)
            if (
                game_state.editing_zone_index == original_index
                and game_state.editing_zone_mode == "confirm_delete"
            ):
                delete_color = UIConstants.RED
            else:
                delete_color = UIConstants.PRIMARY
            _draw_button(
                menu_frame,
                button_x,
                y_offset,
                button_width,
                item_height,
                "Del",
                delete_color,
                game_state=game_state,
                font_scale=UIConstants.FONT_SCALE_SMALL,
            )
            game_state.submenu_items.append(
                (
                    delete_rect,
                    f"delete_zone_{original_index}",
                    f"Delete Zone {original_index+1}",
                )
            )

            y_offset += item_height + 5

    page_y_start = y_offset + 10
    page_item_height = 35
    page_button_width = 80
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

    prev_button_x = 20
    prev_enabled = current_page > 1
    prev_color = UIConstants.PRIMARY if prev_enabled else UIConstants.GREY_BG
    _draw_button(
        menu_frame,
        prev_button_x,
        page_y_start,
        page_button_width,
        page_item_height,
        "Previous",
        prev_color,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_SMALL,
    )
    if prev_enabled:
        game_state.submenu_items.append(
            (
                (prev_button_x, page_y_start, page_button_width, page_item_height),
                "prev_edit_zone_page",
                "Previous Page",
            )
        )

    next_button_x = menu_frame.shape[1] - page_button_width - 20
    next_enabled = current_page < total_pages
    next_color = UIConstants.PRIMARY if next_enabled else UIConstants.GREY_BG
    _draw_button(
        menu_frame,
        next_button_x,
        page_y_start,
        page_button_width,
        page_item_height,
        "Next",
        next_color,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_SMALL,
    )
    if next_enabled:
        game_state.submenu_items.append(
            (
                (next_button_x, page_y_start, page_button_width, page_item_height),
                "next_edit_zone_page",
                "Next Page",
            )
        )

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
        UIConstants.PRIMARY,
        game_state=game_state,
        font_scale=UIConstants.FONT_SCALE_MEDIUM,
    )
    game_state.submenu_items.append(
        (
            (20, back_y, menu_frame.shape[1] - 40, back_button_height),
            "back_to_manage_zones",
            "Back",
        )
    )
    game_state.menu_height = back_y + back_button_height + 20


def _draw_replays_submenu(menu_frame: np.ndarray, game_state: "GameState") -> None:
    """Draw the Replays submenu for recording and viewing replays."""
    from constants import UIConstants

    # Draw title
    cv2.putText(
        menu_frame,
        "Replay System",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    # Clear submenu items
    game_state.submenu_items.clear()

    # Initialize replay_browser_page if needed
    if not hasattr(game_state, "replay_browser_page"):
        game_state.replay_browser_page = 1

    # Record/Stop Recording toggle button
    recording_active = getattr(game_state, "replay_recording", False)
    record_color = UIConstants.RED if recording_active else UIConstants.PRIMARY
    record_text = "Stop Recording" if recording_active else "Start Recording"
    record_action = "stop_recording" if recording_active else "start_recording"

    _draw_button(
        menu_frame,
        20,
        80,
        menu_frame.shape[1] - 40,
        40,
        record_text,
        record_color,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        ((20, 80, menu_frame.shape[1] - 40, 40), record_action, f"{record_text} replay")
    )

    # View Replays button
    _draw_button(
        menu_frame,
        20,
        140,
        menu_frame.shape[1] - 40,
        40,
        "Browse Replays",
        UIConstants.PRIMARY,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (20, 140, menu_frame.shape[1] - 40, 40),
            "view_replays",
            "Browse and play replays",
        )
    )

    replay_count = 0
    if hasattr(game_state, "replay_manager") and game_state.replay_manager:
        replay_count = len(game_state.replay_manager.get_all_replays())
    replay_summary = (
        f"{replay_count} replay saved"
        if replay_count == 1
        else f"{replay_count} replays saved"
    )
    cv2.putText(
        menu_frame,
        replay_summary,
        (30, 195),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_SMALL,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )
    if replay_count == 0:
        cv2.putText(
            menu_frame,
            "Start a recording now or enable Auto-Record to capture your next game.",
            (30, 212),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (200, 200, 200),
            1,
        )

    # Replay Settings section
    cv2.putText(
        menu_frame,
        "Replay Settings:",
        (30, 210),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    # Auto-record option
    auto_record = getattr(game_state, "auto_record_replays", False)
    auto_record_color = UIConstants.ACCENT if auto_record else UIConstants.PRIMARY
    auto_record_text = "Auto-Record: ON" if auto_record else "Auto-Record: OFF"

    _draw_button(
        menu_frame,
        20,
        240,
        menu_frame.shape[1] - 40,
        35,
        auto_record_text,
        auto_record_color,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (20, 240, menu_frame.shape[1] - 40, 35),
            "toggle_auto_record",
            "Toggle automatic replay recording",
        )
    )

    # Replay Storage Management button
    _draw_button(
        menu_frame,
        20,
        290,
        menu_frame.shape[1] - 40,
        35,
        "Manage Replay Storage",
        UIConstants.PRIMARY,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (20, 290, menu_frame.shape[1] - 40, 35),
            "manage_replay_storage",
            "Manage replay storage settings",
        )
    )

    # Back button
    back_y = menu_frame.shape[0] - 50
    _draw_button(
        menu_frame,
        menu_frame.shape[1] // 2 - 50,
        back_y,
        100,
        30,
        "Back",
        UIConstants.PRIMARY,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (menu_frame.shape[1] // 2 - 50, back_y, 100, 30),
            "back_to_main",
            "Back to main menu",
        )
    )

    # If recording is active, show recording status
    if recording_active:
        # Get recording duration if available
        recording_duration = 0.0
        if hasattr(game_state, "replay_manager") and game_state.replay_manager:
            if getattr(game_state.replay_manager, "current_replay", None):
                start_time = getattr(
                    game_state.replay_manager.current_replay,
                    "creation_time",
                    time.time(),
                )
                recording_duration = time.time() - start_time

        # Show recording status
        status_text = f"Recording: {recording_duration:.1f}s"
        cv2.putText(
            menu_frame,
            status_text,
            (30, 350),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.RED,
            UIConstants.FONT_THICKNESS,
        )

        # Add an indicator dot that blinks
        blink_on = int(time.time() * 2) % 2 == 0  # Blink every 0.5 seconds
        if blink_on:
            cv2.circle(
                menu_frame, (menu_frame.shape[1] - 30, 350), 10, UIConstants.RED, -1
            )

    # Set menu height
    game_state.menu_height = back_y + 50


def _draw_replay_browser_submenu(
    menu_frame: np.ndarray, game_state: "GameState"
) -> None:
    """
    Draw the Replay Browser submenu for viewing and managing replays.
    """
    from constants import UIConstants, ReplayConstants

    if not hasattr(game_state, "replay_browser_page"):
        game_state.replay_browser_page = 1
    if not hasattr(game_state, "selected_replay_id"):
        game_state.selected_replay_id = None
    if not hasattr(game_state, "replay_browser_sort"):
        game_state.replay_browser_sort = "newest"

    replay_list = []
    if hasattr(game_state, "replay_manager") and game_state.replay_manager:
        replay_list = game_state.replay_manager.get_all_replays()

    sort_mode = getattr(game_state, "replay_browser_sort", "newest")
    if sort_mode == "score":
        replay_list = sorted(
            replay_list,
            key=lambda r: (r.get("final_score", 0), r.get("creation_time", 0)),
            reverse=True,
        )
    elif sort_mode == "player":
        replay_list = sorted(
            replay_list,
            key=lambda r: (
                str(r.get("player_name", "")).lower(),
                -int(r.get("creation_time", 0) or 0),
            ),
        )
    elif sort_mode == "mode":
        replay_list = sorted(
            replay_list,
            key=lambda r: (
                str(r.get("game_mode", "")).lower(),
                -int(r.get("creation_time", 0) or 0),
            ),
        )
    else:
        replay_list = sorted(
            replay_list, key=lambda r: r.get("creation_time", 0), reverse=True
        )

    selected_replay = None
    if game_state.selected_replay_id:
        for replay in replay_list:
            if replay.get("id") == game_state.selected_replay_id:
                selected_replay = replay
                break
    if selected_replay is None and replay_list:
        selected_replay = replay_list[0]
        game_state.selected_replay_id = selected_replay.get("id")

    total_pages = max(
        1,
        (len(replay_list) + ReplayConstants.REPLAYS_PER_PAGE - 1)
        // ReplayConstants.REPLAYS_PER_PAGE,
    )
    game_state.replay_browser_page = max(
        1, min(game_state.replay_browser_page, total_pages)
    )

    cv2.putText(
        menu_frame,
        "My Replays",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )
    cv2.putText(
        menu_frame,
        f"{len(replay_list)} saved",
        (30, 62),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_SMALL,
        (210, 210, 210),
        UIConstants.FONT_THICKNESS,
    )
    cv2.putText(
        menu_frame,
        f"Page {game_state.replay_browser_page} of {total_pages}",
        (menu_frame.shape[1] - 150, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_SMALL,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    game_state.submenu_items.clear()

    sort_buttons = [
        ("Newest", "newest"),
        ("High Score", "score"),
        ("Player", "player"),
        ("Mode", "mode"),
    ]
    sort_y = 78
    sort_x = 20
    sort_width = 132
    sort_height = 26
    sort_gap = 8
    for idx, (label, sort_key) in enumerate(sort_buttons):
        button_x = sort_x + idx * (sort_width + sort_gap)
        button_color = (
            UIConstants.ACCENT
            if sort_mode == sort_key
            else UIConstants.PRIMARY
        )
        _draw_button(
            menu_frame,
            button_x,
            sort_y,
            sort_width,
            sort_height,
            label,
            button_color,
            game_state=game_state,
            font_scale=UIConstants.FONT_SCALE_SMALL,
        )
        game_state.submenu_items.append(
            (
                (button_x, sort_y, sort_width, sort_height),
                f"set_replay_sort_{sort_key}",
                f"Sort replays by {label}",
            )
        )

    if not replay_list:
        game_state.selected_replay_id = None
        panel_x, panel_y, panel_w, panel_h = 30, 130, menu_frame.shape[1] - 60, 210
        cv2.rectangle(
            menu_frame,
            (panel_x, panel_y),
            (panel_x + panel_w, panel_y + panel_h),
            UIConstants.GREY_BG,
            -1,
        )
        cv2.rectangle(
            menu_frame,
            (panel_x, panel_y),
            (panel_x + panel_w, panel_y + panel_h),
            UIConstants.WHITE,
            1,
        )
        empty_lines = [
            "No replays saved yet.",
            "Start a recording from the Replay menu or enable Auto-Record",
            "to capture your next game automatically.",
            "Once you have a replay, you can play it back, export highlights, and share it.",
        ]
        for idx, text in enumerate(empty_lines):
            cv2.putText(
                menu_frame,
                text,
                (panel_x + 20, panel_y + 40 + idx * 34),
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_MEDIUM if idx == 0 else UIConstants.FONT_SCALE_SMALL,
                UIConstants.WHITE,
                UIConstants.FONT_THICKNESS if idx == 0 else 1,
            )
        back_y = 370
        _draw_button(
            menu_frame,
            menu_frame.shape[1] // 2 - 50,
            back_y,
            100,
            30,
            "Back",
            UIConstants.PRIMARY,
            game_state=game_state,
        )
        game_state.submenu_items.append(
            (
                (menu_frame.shape[1] // 2 - 50, back_y, 100, 30),
                "back_to_replays",
                "Back to Replays menu",
            )
        )
        game_state.menu_height = 430
        return

    grid_x = 24
    grid_y = 122
    thumb_width = 120
    thumb_height = 68
    cell_height = 102
    spacing_x = 16
    spacing_y = 12
    cols = 2
    details_x = 310
    details_y = 122
    details_w = menu_frame.shape[1] - details_x - 20
    details_h = 348
    start_idx = (game_state.replay_browser_page - 1) * ReplayConstants.REPLAYS_PER_PAGE
    end_idx = min(start_idx + ReplayConstants.REPLAYS_PER_PAGE, len(replay_list))

    for i in range(start_idx, end_idx):
        replay = replay_list[i]
        grid_idx = i - start_idx
        row = grid_idx // cols
        col = grid_idx % cols
        x = grid_x + col * (thumb_width + spacing_x)
        y = grid_y + row * (cell_height + spacing_y)
        is_selected = replay.get("id") == game_state.selected_replay_id
        border_color = UIConstants.ACCENT if is_selected else UIConstants.WHITE
        cv2.rectangle(
            menu_frame,
            (x, y),
            (x + thumb_width, y + thumb_height),
            border_color,
            2 if is_selected else 1,
        )

        if game_state.replay_manager:
            thumbnail = game_state.replay_manager.get_replay_thumbnail(replay.get("id"))
            if thumbnail is not None:
                try:
                    if thumbnail.shape[0] != thumb_height or thumbnail.shape[1] != thumb_width:
                        thumbnail = cv2.resize(thumbnail, (thumb_width, thumb_height))
                    if thumbnail.dtype != menu_frame.dtype:
                        thumbnail = thumbnail.astype(menu_frame.dtype)
                    menu_frame[y : y + thumb_height, x : x + thumb_width] = thumbnail
                except Exception as e:
                    logger.error(f"Error displaying thumbnail: {e}")

        title = replay.get("title", "Unknown Replay")
        cv2.putText(
            menu_frame,
            title[:18],
            (x, y + thumb_height + 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )
        cv2.putText(
            menu_frame,
            f"{replay.get('final_score', 0)} pts",
            (x, y + thumb_height + 36),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.YELLOW,
            UIConstants.FONT_THICKNESS,
        )
        date_str = time.strftime(
            "%m/%d %H:%M", time.localtime(replay.get("creation_time", 0))
        )
        cv2.putText(
            menu_frame,
            date_str,
            (x, y + thumb_height + 56),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            (200, 200, 200),
            UIConstants.FONT_THICKNESS,
        )
        game_state.submenu_items.append(
            (
                (x, y, thumb_width, cell_height),
                f"select_replay_{replay.get('id')}",
                f"Select replay {title}",
            )
        )

    cv2.rectangle(
        menu_frame,
        (details_x, details_y),
        (details_x + details_w, details_y + details_h),
        UIConstants.GREY_BG,
        -1,
    )
    cv2.rectangle(
        menu_frame,
        (details_x, details_y),
        (details_x + details_w, details_y + details_h),
        UIConstants.WHITE,
        1,
    )
    cv2.putText(
        menu_frame,
        "Replay Details",
        (details_x + 15, details_y + 26),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    if selected_replay:
        details_lines = [
            f"Title: {selected_replay.get('title', 'Unknown Replay')[:22]}",
            f"Player: {selected_replay.get('player_name', 'Unknown')}",
            f"Mode: {str(selected_replay.get('game_mode', 'classic')).capitalize()}",
            f"Score: {selected_replay.get('final_score', 0)}",
            f"Duration: {selected_replay.get('duration', 0):.1f}s",
            "Created: "
            + time.strftime(
                "%Y-%m-%d %H:%M",
                time.localtime(selected_replay.get("creation_time", 0)),
            ),
            f"Highlights: {selected_replay.get('highlight_count', 0)}",
            "Thumbnail: "
            + ("Available" if selected_replay.get("has_thumbnail", False) else "Not saved"),
        ]
        for idx, line in enumerate(details_lines):
            cv2.putText(
                menu_frame,
                line,
                (details_x + 15, details_y + 62 + idx * 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_SMALL,
                UIConstants.WHITE,
                UIConstants.FONT_THICKNESS,
            )
        footer_lines = [
            "Select a replay on the left to change focus.",
            "Play opens the viewer. Share opens export/upload actions.",
            "Delete requires a second confirmation click.",
        ]
        for idx, line in enumerate(footer_lines):
            cv2.putText(
                menu_frame,
                line,
                (details_x + 15, details_y + 308 + idx * 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (200, 200, 200),
                1,
            )

    pager_y = 484
    if total_pages > 1:
        button_width = 100
        button_height = 30
        prev_x = 25
        next_x = prev_x + button_width + 15
        if game_state.replay_browser_page > 1:
            _draw_button(
                menu_frame,
                prev_x,
                pager_y,
                button_width,
                button_height,
                "Previous",
                UIConstants.PRIMARY,
                game_state=game_state,
            )
            game_state.submenu_items.append(
                ((prev_x, pager_y, button_width, button_height), "prev_replay_page", "Previous page")
            )
        if game_state.replay_browser_page < total_pages:
            _draw_button(
                menu_frame,
                next_x,
                pager_y,
                button_width,
                button_height,
                "Next",
                UIConstants.PRIMARY,
                game_state=game_state,
            )
            game_state.submenu_items.append(
                ((next_x, pager_y, button_width, button_height), "next_replay_page", "Next page")
            )

    action_y = 528
    if selected_replay:
        selected_replay_id = selected_replay.get("id")
        button_width = 132
        button_height = 30
        button_spacing = 10
        buttons = [
            ("Play Replay", UIConstants.PRIMARY, f"play_replay_{selected_replay_id}", "Play selected replay"),
            ("Share", UIConstants.PRIMARY, f"share_replay_{selected_replay_id}", "Share selected replay"),
            ("Highlights", UIConstants.PRIMARY, f"highlights_replay_{selected_replay_id}", "View highlights"),
            ("Delete", UIConstants.RED, f"delete_replay_{selected_replay_id}", "Delete selected replay"),
        ]
        for idx, (label, color, action, help_text) in enumerate(buttons):
            button_x = 20 + idx * (button_width + button_spacing)
            _draw_button(
                menu_frame,
                button_x,
                action_y,
                button_width,
                button_height,
                label,
                color,
                game_state=game_state,
            )
            game_state.submenu_items.append(
                ((button_x, action_y, button_width, button_height), action, help_text)
            )

    back_y = 573
    _draw_button(
        menu_frame,
        menu_frame.shape[1] // 2 - 50,
        back_y,
        100,
        30,
        "Back",
        UIConstants.PRIMARY,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (menu_frame.shape[1] // 2 - 50, back_y, 100, 30),
            "back_to_replays",
            "Back to Replays menu",
        )
    )
    game_state.menu_height = 625


def _draw_replay_playback_submenu(
    menu_frame: np.ndarray, game_state: "GameState"
) -> None:
    """Draw the Replay Playback submenu for controlling replay playback."""
    from constants import UIConstants, ReplayConstants
    import time

    # Initialize if needed
    if not hasattr(game_state, "replay_playback"):
        game_state.replay_playback = {
            "playing": False,
            "current_frame_idx": 0,
            "playback_speed": ReplayConstants.DEFAULT_PLAYBACK_SPEED,
            "current_replay_id": None,
            "current_replay": None,
            "last_update_time": time.time(),
            "timeline_dragging": False,
            "last_keyframe_image": None,
        }

    # Draw title
    cv2.putText(
        menu_frame,
        "Replay Playback",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    # Clear submenu items
    game_state.submenu_items.clear()

    # Get the current replay
    replay = None
    if game_state.replay_playback and game_state.replay_playback.get("current_replay"):
        replay = game_state.replay_playback["current_replay"]

    if not replay:
        # No replay loaded
        cv2.putText(
            menu_frame,
            "No replay loaded.",
            (30, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.RED,
            UIConstants.FONT_THICKNESS,
        )
        cv2.putText(
            menu_frame,
            "Go back to Replay Browser and choose a saved replay to preview.",
            (30, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )

        # Back button
        back_y = menu_frame.shape[0] - 50
        _draw_button(
            menu_frame,
            menu_frame.shape[1] // 2 - 50,
            back_y,
            100,
            30,
            "Back",
            UIConstants.PRIMARY,
            game_state=game_state,
        )
        game_state.submenu_items.append(
            (
                (menu_frame.shape[1] // 2 - 50, back_y, 100, 30),
                "back_to_view_replays",
                "Back to Replay Browser",
            )
        )
        return

    # Display replay information
    cv2.putText(
        menu_frame,
        replay.title,
        (30, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    cv2.putText(
        menu_frame,
        f"Player: {replay.player_name} | Mode: {replay.game_mode} | Score: {replay.final_score}",
        (30, 110),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_SMALL,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    # Display current keyframe if available
    preview_y = 140
    preview_height = menu_frame.shape[0] // 2 - preview_y
    preview_width = int(preview_height * 16 / 9)  # Maintain 16:9 aspect ratio
    preview_x = (menu_frame.shape[1] - preview_width) // 2

    # Draw frame box background
    cv2.rectangle(
        menu_frame,
        (preview_x, preview_y),
        (preview_x + preview_width, preview_y + preview_height),
        UIConstants.GREY_BG,
        -1,
    )

    # Try to get current keyframe
    current_frame_idx = game_state.replay_playback.get("current_frame_idx", 0)
    current_keyframe = None

    if len(replay.frames) > current_frame_idx:
        # Calculate nearest keyframe
        nearest_keyframe_idx = (
            current_frame_idx // ReplayConstants.KEYFRAME_INTERVAL
        ) * ReplayConstants.KEYFRAME_INTERVAL

        # Try to get keyframe image
        try:
            # Use cached keyframe if we have it
            if (
                game_state.replay_playback.get("last_keyframe_image") is not None
                and game_state.replay_playback.get("last_keyframe_idx")
                == nearest_keyframe_idx
            ):
                current_keyframe = game_state.replay_playback.get("last_keyframe_image")
            else:
                # Get new keyframe image
                current_keyframe = replay.get_keyframe_image(nearest_keyframe_idx)
                if current_keyframe is not None:
                    # Cache it for next time
                    game_state.replay_playback["last_keyframe_image"] = current_keyframe
                    game_state.replay_playback["last_keyframe_idx"] = (
                        nearest_keyframe_idx
                    )
        except Exception as e:
            logger.error(f"Error getting keyframe: {e}")

    # Draw current keyframe or placeholder
    if current_keyframe is not None:
        # Resize keyframe to fit the preview area
        resized_keyframe = cv2.resize(current_keyframe, (preview_width, preview_height))

        # Place keyframe in preview area
        menu_frame[
            preview_y : preview_y + preview_height,
            preview_x : preview_x + preview_width,
        ] = resized_keyframe
    else:
        # Draw placeholder text
        cv2.putText(
            menu_frame,
            "No keyframe available",
            (preview_x + 20, preview_y + preview_height // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )

    # Draw timeline scrubber below the preview
    timeline_y = preview_y + preview_height + 20
    timeline_width = preview_width
    timeline_x = preview_x
    timeline_height = ReplayConstants.TIMELINE_HEIGHT

    # Draw timeline background
    cv2.rectangle(
        menu_frame,
        (timeline_x, timeline_y),
        (timeline_x + timeline_width, timeline_y + timeline_height),
        UIConstants.SLIDER_BG,
        -1,
    )

    # Calculate handle position based on current frame
    handle_pos = 0
    if len(replay.frames) > 0:
        handle_pos = int(
            (current_frame_idx / (len(replay.frames) - 1))
            * (timeline_width - ReplayConstants.TIMELINE_HANDLE_WIDTH)
        )

    # Draw timeline handle
    handle_x = timeline_x + handle_pos
    cv2.rectangle(
        menu_frame,
        (handle_x, timeline_y),
        (
            handle_x + ReplayConstants.TIMELINE_HANDLE_WIDTH,
            timeline_y + timeline_height,
        ),
        UIConstants.SLIDER_HANDLE,
        -1,
    )

    # Add timeline to submenu items for interaction
    game_state.submenu_items.append(
        (
            (timeline_x, timeline_y, timeline_width, timeline_height),
            "replay_timeline",
            "Timeline Scrubber",
        )
    )

    # Draw playback controls
    controls_y = timeline_y + timeline_height + 30
    button_width = 40
    button_height = 40
    button_spacing = 10
    total_buttons_width = 5 * button_width + 4 * button_spacing
    start_x = (menu_frame.shape[1] - total_buttons_width) // 2

    # "Rewind" button
    rewind_x = start_x
    _draw_button(
        menu_frame,
        rewind_x,
        controls_y,
        button_width,
        button_height,
        "<<",
        UIConstants.PRIMARY,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        ((rewind_x, controls_y, button_width, button_height), "replay_rewind", "Rewind")
    )

    # "Prev Frame" button
    prev_x = rewind_x + button_width + button_spacing
    _draw_button(
        menu_frame,
        prev_x,
        controls_y,
        button_width,
        button_height,
        "<",
        UIConstants.PRIMARY,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (prev_x, controls_y, button_width, button_height),
            "replay_prev_frame",
            "Previous Frame",
        )
    )

    # "Play/Pause" button
    play_x = prev_x + button_width + button_spacing
    _draw_button(
        menu_frame,
        play_x,
        controls_y,
        button_width,
        button_height,
        ">" if not game_state.replay_playback["playing"] else "||",
        UIConstants.PRIMARY,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (play_x, controls_y, button_width, button_height),
            "replay_toggle_play",
            "Play/Pause",
        )
    )

    # "Next Frame" button
    next_x = play_x + button_width + button_spacing
    _draw_button(
        menu_frame,
        next_x,
        controls_y,
        button_width,
        button_height,
        ">",
        UIConstants.PRIMARY,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (next_x, controls_y, button_width, button_height),
            "replay_next_frame",
            "Next Frame",
        )
    )

    # "Fast Forward" button
    ffwd_x = next_x + button_width + button_spacing
    _draw_button(
        menu_frame,
        ffwd_x,
        controls_y,
        button_width,
        button_height,
        ">>",
        UIConstants.PRIMARY,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (ffwd_x, controls_y, button_width, button_height),
            "replay_ffwd",
            "Fast Forward",
        )
    )

    # Draw playback speed control
    speed_y = controls_y + button_height + 30
    speed_label = f"Speed: {game_state.replay_playback['playback_speed']:.2f}x"
    label_size = cv2.getTextSize(
        speed_label,
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_SMALL,
        UIConstants.FONT_THICKNESS,
    )[0]

    cv2.putText(
        menu_frame,
        speed_label,
        (menu_frame.shape[1] // 2 - label_size[0] // 2, speed_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_SMALL,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    # Speed control buttons
    speed_button_width = 40
    speed_button_height = 30

    # "Slower" button
    slower_x = menu_frame.shape[1] // 2 - 30 - speed_button_width
    _draw_button(
        menu_frame,
        slower_x,
        speed_y + 10,
        speed_button_width,
        speed_button_height,
        "-",
        UIConstants.PRIMARY,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (slower_x, speed_y + 10, speed_button_width, speed_button_height),
            "replay_slower",
            "Decrease speed",
        )
    )

    # "Faster" button
    faster_x = menu_frame.shape[1] // 2 + 30
    _draw_button(
        menu_frame,
        faster_x,
        speed_y + 10,
        speed_button_width,
        speed_button_height,
        "+",
        UIConstants.PRIMARY,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (faster_x, speed_y + 10, speed_button_width, speed_button_height),
            "replay_faster",
            "Increase speed",
        )
    )

    # Draw current frame info
    frame_y = speed_y + speed_button_height + 30
    if len(replay.frames) > 0 and game_state.replay_playback["current_frame_idx"] < len(
        replay.frames
    ):
        current_frame = replay.frames[game_state.replay_playback["current_frame_idx"]]

        # Show frame count and timestamp
        cv2.putText(
            menu_frame,
            f"Frame: {current_frame_idx + 1} / {len(replay.frames)}",
            (30, frame_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )

        relative_time = 0
        if len(replay.frames) > 0:
            relative_time = current_frame.timestamp - replay.frames[0].timestamp

        cv2.putText(
            menu_frame,
            f"Time: {relative_time:.1f}s / {replay.duration:.1f}s",
            (menu_frame.shape[1] - 200, frame_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )

        # Show score
        cv2.putText(
            menu_frame,
            f"Score: {current_frame.score}",
            (30, frame_y + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )

        # Show timer if available
        if current_frame.game_timer is not None:
            cv2.putText(
                menu_frame,
                f"Timer: {current_frame.game_timer:.1f}s",
                (menu_frame.shape[1] - 200, frame_y + 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_SMALL,
                UIConstants.WHITE,
                UIConstants.FONT_THICKNESS,
            )

    # Add buttons for additional actions at the bottom of the menu
    action_buttons_y = frame_y + 60
    buttons_per_row = 2
    button_width = 180
    button_height = 35
    button_margin = 20

    # Share button
    share_x = menu_frame.shape[1] // 2 - button_width - button_margin // 2
    _draw_button(
        menu_frame,
        share_x,
        action_buttons_y,
        button_width,
        button_height,
        "Share Replay",
        UIConstants.PRIMARY,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (share_x, action_buttons_y, button_width, button_height),
            f"open_share_menu_{game_state.replay_playback.get('current_replay_id', '')}",
            "Open share options",
        )
    )

    # Export as video button
    export_x = menu_frame.shape[1] // 2 + button_margin // 2
    _draw_button(
        menu_frame,
        export_x,
        action_buttons_y,
        button_width,
        button_height,
        "Export as Video",
        UIConstants.PRIMARY,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (export_x, action_buttons_y, button_width, button_height),
            f"export_video_{game_state.replay_playback.get('current_replay_id', '')}",
            "Export as video file",
        )
    )

    # "Close" button
    close_y = action_buttons_y + button_height + 20
    _draw_button(
        menu_frame,
        menu_frame.shape[1] // 2 - 50,
        close_y,
        100,
        30,
        "Close",
        UIConstants.RED,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (menu_frame.shape[1] // 2 - 50, close_y, 100, 30),
            "close_replay_playback",
            "Close replay playback",
        )
    )

    # Set menu height
    game_state.menu_height = close_y + 50


def _draw_replay_share_submenu(menu_frame: np.ndarray, game_state: "GameState") -> None:
    """Draw the Replay Share submenu for sharing replays."""
    from constants import UIConstants, ReplayConstants

    # Draw title
    cv2.putText(
        menu_frame,
        "Share Replay",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    # Clear submenu items
    game_state.submenu_items.clear()

    # Initialize sharing state if needed
    if not hasattr(game_state, "replay_sharing"):
        game_state.replay_sharing = {
            "selected_format": ReplayConstants.DEFAULT_EXPORT_FORMAT,
            "selected_platform": "Local",
            "export_progress": 0.0,
            "export_status": "",
            "last_export_path": None,
        }

    # Get the selected replay info
    replay_info = None
    if hasattr(game_state, "replay_manager") and game_state.replay_manager:
        if hasattr(game_state, "selected_replay_id") and game_state.selected_replay_id:
            for replay in game_state.replay_manager.get_all_replays():
                if replay.get("id") == game_state.selected_replay_id:
                    replay_info = replay
                    break

    if replay_info:
        # Show replay details
        cv2.putText(
            menu_frame,
            replay_info.get("title", "Unknown"),
            (30, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )

        cv2.putText(
            menu_frame,
            f"Player: {replay_info.get('player_name', 'Unknown')} | Score: {replay_info.get('final_score', 0)}",
            (30, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )

        # Draw format options
        format_y = 150
        cv2.putText(
            menu_frame,
            "Export Format:",
            (30, format_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )

        # Format selection buttons
        format_buttons_y = format_y + 30
        format_button_width = 80
        format_button_height = 30
        format_button_spacing = 20

        for i, format_type in enumerate(ReplayConstants.EXPORT_FORMATS):
            is_selected = game_state.replay_sharing["selected_format"] == format_type
            button_color = UIConstants.ACCENT if is_selected else UIConstants.PRIMARY

            button_x = 30 + i * (format_button_width + format_button_spacing)
            _draw_button(
                menu_frame,
                button_x,
                format_buttons_y,
                format_button_width,
                format_button_height,
                format_type,
                button_color,
                game_state=game_state,
            )
            game_state.submenu_items.append(
                (
                    (
                        button_x,
                        format_buttons_y,
                        format_button_width,
                        format_button_height,
                    ),
                    f"select_format_{format_type}",
                    f"Set export format to {format_type}",
                )
            )

        # Draw sharing platform options
        platform_y = format_buttons_y + format_button_height + 40
        cv2.putText(
            menu_frame,
            "Share to Platform:",
            (30, platform_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )

        # Platform buttons - 2 rows of 2 if needed
        platform_buttons_y = platform_y + 30
        platform_button_width = 120
        platform_button_height = 30
        platform_button_spacing = 20
        platform_buttons_per_row = 2
        platform_row_spacing = 40

        for i, platform in enumerate(ReplayConstants.SHARING_PLATFORMS):
            row = i // platform_buttons_per_row
            col = i % platform_buttons_per_row

            is_selected = game_state.replay_sharing["selected_platform"] == platform
            button_color = UIConstants.ACCENT if is_selected else UIConstants.PRIMARY

            button_x = 30 + col * (platform_button_width + platform_button_spacing)
            button_y = platform_buttons_y + row * platform_row_spacing

            _draw_button(
                menu_frame,
                button_x,
                button_y,
                platform_button_width,
                platform_button_height,
                platform,
                button_color,
                game_state=game_state,
            )
            game_state.submenu_items.append(
                (
                    (button_x, button_y, platform_button_width, platform_button_height),
                    f"select_platform_{platform}",
                    f"Set sharing platform to {platform}",
                )
            )

        # Calculate the position for action buttons based on number of platform rows
        num_platform_rows = (
            len(ReplayConstants.SHARING_PLATFORMS) + platform_buttons_per_row - 1
        ) // platform_buttons_per_row
        action_y = platform_buttons_y + (num_platform_rows * platform_row_spacing) + 40

        # Show export status if available
        if game_state.replay_sharing.get("export_status"):
            status_text = game_state.replay_sharing["export_status"]
            cv2.putText(
                menu_frame,
                status_text,
                (30, action_y - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_SMALL,
                UIConstants.ACCENT,
                UIConstants.FONT_THICKNESS,
            )

            # Draw progress bar if exporting
            if game_state.replay_sharing.get("export_progress", 0) > 0:
                progress_width = menu_frame.shape[1] - 60
                progress_height = 10
                progress_x = 30
                progress_y = action_y - 10

                # Background
                cv2.rectangle(
                    menu_frame,
                    (progress_x, progress_y),
                    (progress_x + progress_width, progress_y + progress_height),
                    UIConstants.GREY_BG,
                    -1,
                )

                # Progress fill
                fill_width = int(
                    progress_width * game_state.replay_sharing["export_progress"]
                )
                cv2.rectangle(
                    menu_frame,
                    (progress_x, progress_y),
                    (progress_x + fill_width, progress_y + progress_height),
                    UIConstants.ACCENT,
                    -1,
                )

                # Update action_y to account for progress bar
                action_y += 20

        # Action buttons
        action_button_width = (
            180  # Increased from 160 to accommodate "Export Full Video" text
        )
        action_button_height = 35
        action_button_spacing = 30

        # Generate Full Video button
        generate_x = (
            menu_frame.shape[1] // 2 - action_button_width - action_button_spacing // 2
        )
        _draw_button(
            menu_frame,
            generate_x,
            action_y,
            action_button_width,
            action_button_height,
            "Export Full Video",
            UIConstants.PRIMARY,
            game_state=game_state,
        )
        game_state.submenu_items.append(
            (
                (generate_x, action_y, action_button_width, action_button_height),
                f"generate_video_{game_state.selected_replay_id}",
                "Generate and export full video from replay",
            )
        )

        # Share button
        share_x = menu_frame.shape[1] // 2 + action_button_spacing // 2
        share_text = f"Share to {game_state.replay_sharing['selected_platform']}"
        _draw_button(
            menu_frame,
            share_x,
            action_y,
            action_button_width,
            action_button_height,
            share_text,
            UIConstants.PRIMARY,
            game_state=game_state,
        )
        game_state.submenu_items.append(
            (
                (share_x, action_y, action_button_width, action_button_height),
                f"share_to_{game_state.replay_sharing['selected_platform']}_{game_state.selected_replay_id}",
                f"Share replay to {game_state.replay_sharing['selected_platform']}",
            )
        )

        # Highlight options
        highlight_y = action_y + action_button_height + 40

        if replay_info.get("highlight_count", 0) > 0:
            cv2.putText(
                menu_frame,
                "Share Highlights:",
                (30, highlight_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_MEDIUM,
                UIConstants.WHITE,
                UIConstants.FONT_THICKNESS,
            )

            highlight_y += 30

            # Try to get actual highlight descriptions
            highlights = []
            try:
                if game_state.replay_manager:
                    replay_obj = game_state.replay_manager.load_replay(
                        game_state.selected_replay_id
                    )
                    if replay_obj and replay_obj.highlight_segments:
                        highlights = replay_obj.highlight_segments
            except Exception as e:
                logger.error(f"Error loading highlights: {e}")

            for i, highlight in enumerate(
                highlights[:3]
            ):  # Limit to 3 highlights to save space
                if len(highlight) >= 3:
                    _, _, description = highlight

                    # Highlight export button
                    _draw_button(
                        menu_frame,
                        30,
                        highlight_y,
                        menu_frame.shape[1] // 2 - 40,
                        action_button_height,
                        f"#{i+1}: {description}",
                        UIConstants.PRIMARY,
                        game_state=game_state,
                    )
                    game_state.submenu_items.append(
                        (
                            (
                                30,
                                highlight_y,
                                menu_frame.shape[1] // 2 - 40,
                                action_button_height,
                            ),
                            f"export_highlight_{game_state.selected_replay_id}_{i}",
                            f"Export highlight {i+1}",
                        )
                    )

                    # Highlight share button
                    _draw_button(
                        menu_frame,
                        menu_frame.shape[1] // 2 + 10,
                        highlight_y,
                        menu_frame.shape[1] // 2 - 40,
                        action_button_height,
                        f"Share #{i+1}",
                        UIConstants.PRIMARY,
                        game_state=game_state,
                    )
                    game_state.submenu_items.append(
                        (
                            (
                                menu_frame.shape[1] // 2 + 10,
                                highlight_y,
                                menu_frame.shape[1] // 2 - 40,
                                action_button_height,
                            ),
                            f"share_highlight_{game_state.selected_replay_id}_{i}_{game_state.replay_sharing['selected_platform']}",
                            f"Share highlight {i+1} to {game_state.replay_sharing['selected_platform']}",
                        )
                    )

                    highlight_y += action_button_height + 10
        else:
            cv2.putText(
                menu_frame,
                "No highlights available for this replay.",
                (30, highlight_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_SMALL,
                UIConstants.WHITE,
                UIConstants.FONT_THICKNESS,
            )
            cv2.putText(
                menu_frame,
                "Scoring events automatically create highlights while recording.",
                (30, highlight_y + 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (200, 200, 200),
                1,
            )
            highlight_y += 30

    else:
        # No replay selected
        cv2.putText(
            menu_frame,
            "No replay selected.",
            (30, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.RED,
            UIConstants.FONT_THICKNESS,
        )
        cv2.putText(
            menu_frame,
            "Choose one from Replay Browser to export video, share, or open highlights.",
            (30, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )
        highlight_y = 120  # Set a default value if not previously defined

    # Back button - ensure it's positioned below the highlight area with some padding
    back_y = highlight_y + 40  # Increased spacing to avoid overlap
    _draw_button(
        menu_frame,
        menu_frame.shape[1] // 2 - 50,
        back_y,
        100,
        30,
        "Back",
        UIConstants.PRIMARY,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (menu_frame.shape[1] // 2 - 50, back_y, 100, 30),
            "back_to_view_replays",
            "Back to Replay Browser",
        )
    )

    # Set menu height
    game_state.menu_height = back_y + 50


def _draw_manage_replay_storage_submenu(
    menu_frame: np.ndarray, game_state: "GameState"
) -> None:
    """Draw the Manage Replay Storage submenu with usage info and bulk-delete."""
    import os

    # Title
    cv2.putText(
        menu_frame,
        "Replay Storage",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    # Gather stats
    replay_count = 0
    total_bytes = 0
    if hasattr(game_state, "replay_manager") and game_state.replay_manager:
        replays = game_state.replay_manager.get_all_replays()
        replay_count = len(replays)
        for r in replays:
            fp = r.get("file_path", "")
            if fp and os.path.exists(fp):
                try:
                    total_bytes += os.path.getsize(fp)
                except OSError:
                    pass

    if total_bytes < 1024:
        size_str = f"{total_bytes} B"
    elif total_bytes < 1024 * 1024:
        size_str = f"{total_bytes / 1024:.1f} KB"
    else:
        size_str = f"{total_bytes / (1024 * 1024):.1f} MB"

    cv2.putText(
        menu_frame,
        f"Replays: {replay_count}   Total size: {size_str}",
        (30, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.WHITE,
        1,
    )

    # Browse Replays button
    _draw_button(
        menu_frame,
        20,
        110,
        menu_frame.shape[1] - 40,
        35,
        "Browse Replays",
        UIConstants.PRIMARY,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (20, 110, menu_frame.shape[1] - 40, 35),
            "view_replays",
            "Open the replay browser",
        )
    )

    # Delete All Replays button
    btn_color = UIConstants.RED if replay_count > 0 else (100, 100, 100)
    _draw_button(
        menu_frame,
        20,
        160,
        menu_frame.shape[1] - 40,
        35,
        "Delete All Replays",
        btn_color,
        game_state=game_state,
    )
    if replay_count > 0:
        game_state.submenu_items.append(
            (
                (20, 160, menu_frame.shape[1] - 40, 35),
                "delete_all_replays",
                "Delete every saved replay",
            )
        )

    # Back button
    back_y = 220
    _draw_button(
        menu_frame,
        menu_frame.shape[1] // 2 - 50,
        back_y,
        100,
        30,
        "Back",
        UIConstants.PRIMARY,
        game_state=game_state,
    )
    game_state.submenu_items.append(
        (
            (menu_frame.shape[1] // 2 - 50, back_y, 100, 30),
            "back_to_replays",
            "Back to replays menu",
        )
    )

    game_state.menu_height = back_y + 50
