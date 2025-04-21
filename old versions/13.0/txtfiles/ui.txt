# ui.py

import logging
import time
# <<< ADDED IMPORT >>>
from typing import TYPE_CHECKING, Tuple

import cv2
import numpy as np

# Local project imports
from constants import UIConstants
# Import GameState class and CurrentGameState enum from NEW location
# <<< MODIFIED: Avoid direct GameState import if causing cycles, use TYPE_CHECKING >>>
# from game_state import GameState
from game_types import CurrentGameState
from menu import draw_menu, draw_menu_window
# <<< MODIFIED: Pass game_state to _draw_button >>>
from menu_utils import _draw_button
from scoring import draw_scoring_zones
# Import draw_balls here if it's not already being called elsewhere before draw_ui
# from ui_elements import draw_balls
from ui_elements import _draw_debug_overlay
# Import functions from the split files
from ui_screens import _draw_game_over_screen
# Import helper function from ui_utils
from ui_utils import _draw_text_with_background

# <<< ADDED FOR TYPE HINTING >>>
if TYPE_CHECKING:
    from game_state import GameState

logger = logging.getLogger(__name__)


# --- Player Name Input Drawing (Unchanged) ---
def _draw_player_name_input(frame: np.ndarray, game_state: "GameState"):
    """Draws the pop-up screen for initial player name input."""
    overlay = frame.copy()
    cv2.rectangle(
        overlay, (0, 0), (frame.shape[1], frame.shape[0]), UIConstants.BLACK, -1
    )
    alpha = 0.7
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    popup_width, popup_height = 700, 200
    popup_x = (frame.shape[1] - popup_width) // 2
    popup_y = (frame.shape[0] - popup_height) // 2
    cv2.rectangle(
        frame,
        (popup_x, popup_y),
        (popup_x + popup_width, popup_y + popup_height),
        UIConstants.GREY_BG,
        -1,
    )
    cv2.rectangle(
        frame,
        (popup_x, popup_y),
        (popup_x + popup_width, popup_y + popup_height),
        UIConstants.WHITE,
        1,
    )
    prompt_text = "Enter Player Name:"
    prompt_pos = (popup_x + 20, popup_y + 40)
    cv2.putText(
        frame,
        prompt_text,
        prompt_pos,
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
        cv2.LINE_AA,
    )
    input_bg_x, input_bg_y = popup_x + 20, popup_y + 70
    input_bg_w, input_bg_h = popup_width - 40, 40
    cv2.rectangle(
        frame,
        (input_bg_x, input_bg_y),
        (input_bg_x + input_bg_w, input_bg_y + input_bg_h),
        (50, 50, 50),
        -1,
    )
    show_cursor = int(time.time() * 2) % 2 == 0
    cursor = "_" if show_cursor else " "
    display_name = game_state.current_player_name_input + cursor
    name_pos = (input_bg_x + 10, input_bg_y + 30)
    cv2.putText(
        frame,
        display_name,
        name_pos,
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_LARGE,
        UIConstants.YELLOW,
        UIConstants.FONT_THICKNESS + 1,
        cv2.LINE_AA,
    )
    instructions_text = "Enter=Confirm, Esc=Default ('Player 1'), Backspace=Delete"
    instr_pos = (popup_x + 20, popup_y + popup_height - 30)
    cv2.putText(
        frame,
        instructions_text,
        instr_pos,
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_SMALL,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
        cv2.LINE_AA,
    )


# --- Helper: Draw Zone Editing Handles ---
def _draw_zone_edit_handles(frame: np.ndarray, zone_rect: Tuple[int, int, int, int]):
    """Draws resize handles on the corners of a zone."""
    zx, zy, zw, zh = zone_rect
    handle_size = UIConstants.ZONE_EDIT_HANDLE_SIZE
    handle_color = UIConstants.ZONE_EDIT_HANDLE_COLOR
    half_handle = handle_size // 2
    corners = [(zx, zy), (zx + zw, zy), (zx, zy + zh), (zx + zw, zy + zh)]
    for cx, cy in corners:
        pt1 = (cx - half_handle, cy - half_handle)
        pt2 = (cx + half_handle, cy + half_handle)
        cv2.rectangle(frame, pt1, pt2, handle_color, -1)


# --- Main UI Drawing Function ---
def draw_ui(frame: np.ndarray, game_state: "GameState") -> None:
    """Draw the user interface elements on the frame, handling different game states."""

    # State: Getting Player Name
    if game_state.current_state == CurrentGameState.GETTING_PLAYER_NAME:
        _draw_player_name_input(frame, game_state)
        if game_state.debug_mode:
            fps = game_state.fps if hasattr(game_state, "fps") else 0
            state_text = str(game_state.current_state).split(".")[-1]
            debug_text = f"FPS:{fps:.1f}|State:{state_text}"
            _draw_text_with_background(
                frame,
                debug_text,
                (10, UIConstants.WINDOW_HEIGHT - 10),
                UIConstants.FONT_SCALE_SMALL,
                UIConstants.YELLOW,
                UIConstants.BLACK,
                alpha=0.7,
            )
        return

    # --- Draw common elements (Score, High Score, Mode, Timer) ---
    if game_state.current_state not in [
        CurrentGameState.GAME_OVER
    ]:  # Show score etc even during CONFIRM_QUIT
        try:
            player_name = game_state.get_current_player().name
        except Exception:
            player_name = "Error"
        score_text = f"Player: {player_name} Score: {game_state.score}"
        _draw_text_with_background(
            frame,
            score_text,
            (10, 30),
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            UIConstants.GREY_BG,
            thickness=UIConstants.FONT_THICKNESS,
        )
        high_score_text = f"High Score: {game_state.high_score}"
        (tw, th), _ = cv2.getTextSize(
            high_score_text,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.FONT_THICKNESS,
        )
        high_score_x = UIConstants.WINDOW_WIDTH - tw - 10 - 3
        _draw_text_with_background(
            frame,
            high_score_text,
            (high_score_x, 30),
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            UIConstants.GREY_BG,
            thickness=UIConstants.FONT_THICKNESS,
        )
        mode_text = f"Mode: {game_state.game_mode.capitalize()}"
        _draw_text_with_background(
            frame,
            mode_text,
            (10, 60),
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            UIConstants.GREY_BG,
            thickness=UIConstants.FONT_THICKNESS,
        )
        if (
            game_state.game_mode in ["timed", "survival"]
            and game_state.game_timer is not None
            and game_state.current_state
            in [
                CurrentGameState.PLAYING,
                CurrentGameState.PAUSED,
                CurrentGameState.ZONE_EDITING,
                CurrentGameState.CONFIRM_QUIT,
            ]
        ):
            timer_text = f"Time: {int(max(0, game_state.game_timer))}"
            time_color = (
                UIConstants.RED if game_state.game_timer <= 10 else UIConstants.WHITE
            )
            (tw_t, th_t), _ = cv2.getTextSize(
                timer_text,
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_MEDIUM,
                UIConstants.FONT_THICKNESS,
            )
            timer_x = (UIConstants.WINDOW_WIDTH - tw_t) // 2
            timer_y = 30
            _draw_text_with_background(
                frame,
                timer_text,
                (timer_x, timer_y),
                UIConstants.FONT_SCALE_MEDIUM,
                time_color,
                UIConstants.BLACK,
                thickness=UIConstants.FONT_THICKNESS,
                alpha=0.7,
            )

    # --- State-Specific Drawing ---

    # State: Playing
    if game_state.current_state == CurrentGameState.PLAYING:
        draw_scoring_zones(
            frame, game_state.scoring_zones, game_state.special_hole
        )  # Pass game_state
        if game_state.drawing and game_state.temp_zone:
            x1, y1, w, h = game_state.temp_zone
            cv2.rectangle(frame, (x1, y1), (x1 + w, y1 + h), UIConstants.YELLOW, 2)
            show_cursor = int(time.time() * 2) % 2 == 0
            cursor = "_" if show_cursor else " "
            points_display_str = game_state.drawing_points_input or "..."
            points_text = f"{points_display_str}{cursor} pts"
            (ptw, pth), _ = cv2.getTextSize(
                points_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, 1
            )
            text_x, text_y = x1 + w + 5, y1 + h - 5
            if text_x + ptw > frame.shape[1]:
                text_x = x1 + w - ptw - 5
            if text_y < pth:
                text_y = y1 + pth + 5
            if text_y > frame.shape[0] - 5:
                text_y = y1 + h - pth - 5
            _draw_text_with_background(
                frame,
                points_text,
                (text_x, text_y),
                UIConstants.FONT_SCALE_SMALL,
                UIConstants.YELLOW,
                UIConstants.BLACK,
                thickness=1,
                alpha=0.7,
            )
        if not game_state.drawing:
            # Pass game_state to draw_menu (which passes it to _draw_button)
            draw_menu(frame, game_state)

    # State: Paused
    elif game_state.current_state == CurrentGameState.PAUSED:
        pause_text = "PAUSED"
        (tw_p, th_p), _ = cv2.getTextSize(
            pause_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_XLARGE, 3
        )
        pause_x = (UIConstants.WINDOW_WIDTH - tw_p) // 2
        pause_y = UIConstants.WINDOW_HEIGHT // 2
        _draw_text_with_background(
            frame,
            pause_text,
            (pause_x, pause_y),
            UIConstants.FONT_SCALE_XLARGE,
            UIConstants.YELLOW,
            UIConstants.BLACK,
            thickness=3,
        )
        # Pass game_state to draw_scoring_zones
        draw_scoring_zones(
            frame, game_state.scoring_zones, game_state.special_hole, game_state
        )

    # State: Menu
    elif game_state.current_state == CurrentGameState.MENU:
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], frame.shape[0]), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        # Pass game_state to draw_menu_window (which passes it down)
        draw_menu_window(frame, game_state)

    # State: Zone Editing (Interactive Move/Resize)
    elif game_state.current_state == CurrentGameState.ZONE_EDITING:
        # Pass game_state to draw_scoring_zones
        draw_scoring_zones(
            frame, game_state.scoring_zones, game_state.special_hole, game_state
        )
        if (
            game_state.selected_zone_for_edit is not None
            and 0 <= game_state.selected_zone_for_edit < len(game_state.scoring_zones)
        ):
            zone_to_edit = game_state.scoring_zones[game_state.selected_zone_for_edit]
            zx, zy, zw, zh, _ = zone_to_edit
            cv2.rectangle(
                frame,
                (zx, zy),
                (zx + zw, zy + zh),
                UIConstants.ZONE_EDIT_SELECTED_COLOR,
                3,
            )
            _draw_zone_edit_handles(frame, (zx, zy, zw, zh))
        else:
            logger.warning(
                "In ZONE_EDITING state but selected_zone_for_edit is invalid."
            )
            try:
                game_state.current_state = (
                    game_state.previous_state or CurrentGameState.MENU
                )
            except Exception:
                game_state.current_state = CurrentGameState.MENU
            game_state.selected_zone_for_edit = None
            game_state.zone_editing_action = None
            game_state.drag_start_pos = None
            game_state.original_zone_on_drag_start = None

    # State: Game Over
    elif game_state.current_state == CurrentGameState.GAME_OVER:
        # Pass game_state to _draw_game_over_screen (which passes it to _draw_button)
        _draw_game_over_screen(frame, game_state)

    # State: Confirm Quit
    elif game_state.current_state == CurrentGameState.CONFIRM_QUIT:
        overlay = frame.copy()
        cv2.rectangle(
            overlay, (0, 0), (frame.shape[1], frame.shape[0]), UIConstants.BLACK, -1
        )
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
        dialog_width, dialog_height = 400, 150
        dialog_x = (UIConstants.WINDOW_WIDTH - dialog_width) // 2
        dialog_y = (UIConstants.WINDOW_HEIGHT - dialog_height) // 2
        cv2.rectangle(
            frame,
            (dialog_x, dialog_y),
            (dialog_x + dialog_width, dialog_y + dialog_height),
            UIConstants.GREY_BG,
            -1,
        )
        cv2.rectangle(
            frame,
            (dialog_x, dialog_y),
            (dialog_x + dialog_width, dialog_y + dialog_height),
            UIConstants.WHITE,
            2,
        )
        confirm_text = "Quit Game?"
        font_scale, thickness = UIConstants.FONT_SCALE_LARGE, 2
        (tw, th), _ = cv2.getTextSize(
            confirm_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        text_x, text_y = dialog_x + (dialog_width - tw) // 2, dialog_y + th + 20
        cv2.putText(
            frame,
            confirm_text,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            UIConstants.WHITE,
            thickness,
            cv2.LINE_AA,
        )
        button_width, button_height, button_spacing = 100, 40, 40
        total_button_width = button_width * 2 + button_spacing
        button_start_x = dialog_x + (dialog_width - total_button_width) // 2
        button_y = dialog_y + dialog_height - button_height - 20
        yes_button_x = button_start_x
        no_button_x = button_start_x + button_width + button_spacing
        yes_rect = (yes_button_x, button_y, button_width, button_height)
        _draw_button(
            frame,
            yes_button_x,
            button_y,
            button_width,
            button_height,
            "Yes (Y)",
            UIConstants.GREEN,
            # <<< ADDED game_state >>>
            game_state=game_state,
            font_scale=UIConstants.FONT_SCALE_MEDIUM,
        )
        no_rect = (no_button_x, button_y, button_width, button_height)
        _draw_button(
            frame,
            no_button_x,
            button_y,
            button_width,
            button_height,
            "No (N)",
            UIConstants.RED,
            # <<< ADDED game_state >>>
            game_state=game_state,
            font_scale=UIConstants.FONT_SCALE_MEDIUM,
        )
        # Store absolute button rectangles and actions
        game_state.submenu_items = [
            (yes_rect, "confirm_quit_yes", "Confirm Quit"),
            (no_rect, "confirm_quit_no", "Cancel Quit"),
        ]
        game_state.menu_pos = (0, 0)
        game_state.menu_width = frame.shape[1]
        game_state.menu_height = frame.shape[0]

    # --- Draw Effects ---
    if game_state.game_mode in ["fun", "retro"]:
        if hasattr(game_state, "active_explosions") and isinstance(
            game_state.active_explosions, list
        ):
            for explosion in list(game_state.active_explosions):
                try:
                    if explosion.is_active():
                        explosion.draw(frame)
                except Exception as e:
                    logger.error(f"Error drawing explosion: {e}")

    # --- Draw Notifications & Achievement Popups ---
    if game_state.current_state != CurrentGameState.GETTING_PLAYER_NAME:
        notification_drawn = False
        if game_state.notification_text and game_state.notification_timer > 0:
            color = game_state.notification_color
            (tw_not, th_not), _ = cv2.getTextSize(
                game_state.notification_text,
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_MEDIUM,
                UIConstants.FONT_THICKNESS,
            )
            nx_not = (UIConstants.WINDOW_WIDTH - tw_not) // 2
            ny_not = UIConstants.WINDOW_HEIGHT - 30
            _draw_text_with_background(
                frame,
                game_state.notification_text,
                (nx_not, ny_not),
                UIConstants.FONT_SCALE_MEDIUM,
                color,
                UIConstants.BLACK,
                thickness=UIConstants.FONT_THICKNESS,
                alpha=0.7,
            )
            notification_drawn = True
        if (
            game_state.achievement_notification
            and game_state.achievement_notification_timer > 0
        ):
            ach_text = game_state.achievement_notification
            (tw_ach, th_ach), _ = cv2.getTextSize(
                ach_text,
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_LARGE,
                UIConstants.FONT_THICKNESS,
            )
            ach_y_offset = 80
            nx_ach = (UIConstants.WINDOW_WIDTH - tw_ach) // 2
            ny_ach = UIConstants.WINDOW_HEIGHT - ach_y_offset
            if notification_drawn and ny_ach > ny_not - th_ach - 10:
                ny_ach = ny_not - th_ach - 10
            _draw_text_with_background(
                frame,
                ach_text,
                (nx_ach, ny_ach),
                UIConstants.FONT_SCALE_LARGE,
                UIConstants.GREEN,
                UIConstants.BLACK,
                thickness=UIConstants.FONT_THICKNESS,
                alpha=0.7,
            )

    # --- Draw Visual Debug Overlay ---
    if (
        game_state.current_state != CurrentGameState.GETTING_PLAYER_NAME
        and hasattr(game_state, "show_debug_overlay")
        and game_state.show_debug_overlay
    ):
        _draw_debug_overlay(frame, game_state)

    # --- Draw General Debug Text ---
    if (
        game_state.current_state != CurrentGameState.GETTING_PLAYER_NAME
        and game_state.debug_mode
    ):
        fps = game_state.fps if hasattr(game_state, "fps") else 0
        state_text = str(game_state.current_state).split(".")[-1]
        overlay_status = (
            "ON" if getattr(game_state, "show_debug_overlay", False) else "OFF"
        )
        tracked_count = len(getattr(game_state, "tracked_balls", []))
        drawing_active_text = (
            "Draw:ON" if getattr(game_state, "drawing", False) else "Draw:OFF"
        )
        edit_info = ""
        if game_state.current_state == CurrentGameState.ZONE_EDITING:
            edit_info = f" | EditZone:{game_state.selected_zone_for_edit} Act:{game_state.zone_editing_action or '...'}"
        elif game_state.current_state == CurrentGameState.CONFIRM_QUIT:
            prev_state_name = str(
                getattr(game_state, "previous_state_before_quit_confirm", "N/A")
            ).split(".")[-1]
            edit_info = f" | PrevState:{prev_state_name}"
        debug_text = f"FPS:{fps:.1f} | State:{state_text} | {drawing_active_text} | Overlay(b):{overlay_status} | Tracked:{tracked_count}{edit_info}"
        _draw_text_with_background(
            frame,
            debug_text,
            (10, UIConstants.WINDOW_HEIGHT - 10),
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.YELLOW,
            UIConstants.BLACK,
            alpha=0.7,
        )

    # <<< ADDED: Also need to update draw_scoring_zones call >>>
    # Find where draw_scoring_zones is called and ensure game_state is passed
    # (Already addressed within the PLAYING and PAUSED state logic above)
