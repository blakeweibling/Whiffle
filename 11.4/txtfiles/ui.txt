# ui.py
"""
UI rendering functions for the Whiffle Tracker project.
Manages drawing of UI elements, handling different game states.
"""

import cv2
import numpy as np
import logging
import os
import time  # Import time for cursor blinking effect
from typing import Tuple, Optional

# Local project imports
from constants import UIConstants, GameConstants
from scoring import draw_scoring_zones
from menu import draw_menu, draw_menu_window
from game_state import GameState, CurrentGameState

# Import functions from the split files
# Assume necessary functions like _draw_game_over_screen are imported
from ui_screens import _draw_game_over_screen

# Assume necessary functions like _draw_debug_overlay are imported
from ui_elements import _draw_debug_overlay, draw_balls

# Import the moved helper function
from ui_utils import _draw_text_with_background

logger = logging.getLogger(__name__)


# --- NEW: Function to draw the initial player name input screen ---
def _draw_player_name_input(frame: np.ndarray, game_state: GameState):
    """Draws the pop-up screen for initial player name input."""
    overlay = frame.copy()
    cv2.rectangle(
        overlay, (0, 0), (frame.shape[1], frame.shape[0]), UIConstants.BLACK, -1
    )
    alpha = 0.7  # Dimming factor
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    # Pop-up box dimensions
    popup_width = 500
    popup_height = 200
    popup_x = (frame.shape[1] - popup_width) // 2
    popup_y = (frame.shape[0] - popup_height) // 2

    # Draw the pop-up box background
    cv2.rectangle(
        frame,
        (popup_x, popup_y),
        (popup_x + popup_width, popup_y + popup_height),
        UIConstants.GREY_BG,
        -1,
    )
    # Draw border
    cv2.rectangle(
        frame,
        (popup_x, popup_y),
        (popup_x + popup_width, popup_y + popup_height),
        UIConstants.WHITE,
        1,
    )

    # Prompt text
    prompt_text = "Hi! Please input your name for scorekeeping!"
    prompt_pos = (popup_x + 20, popup_y + 40)
    cv2.putText(
        frame,
        prompt_text,
        prompt_pos,
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )

    # Input field background (optional, subtle)
    input_bg_x = popup_x + 20
    input_bg_y = popup_y + 70
    input_bg_w = popup_width - 40
    input_bg_h = 40
    cv2.rectangle(
        frame,
        (input_bg_x, input_bg_y),
        (input_bg_x + input_bg_w, input_bg_y + input_bg_h),
        (50, 50, 50),
        -1,
    )

    # Display the entered name with a blinking cursor
    cursor = "_" if int(time.time() * 2) % 2 == 0 else " "  # Simple blink effect
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
    )

    # Instructions text
    instructions_text = "Enter to confirm, Esc to use default ('Player 1')"
    instr_pos = (popup_x + 20, popup_y + popup_height - 30)
    cv2.putText(
        frame,
        instructions_text,
        instr_pos,
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_SMALL,
        UIConstants.WHITE,
        UIConstants.FONT_THICKNESS,
    )


def draw_ui(
    frame: np.ndarray, game_state: GameState
) -> None:  # Use GameState type hint
    """
    Draw the user interface elements on the frame, handling different game states.
    """

    # --- Handle GETTING_PLAYER_NAME state first ---
    if game_state.current_state == CurrentGameState.GETTING_PLAYER_NAME:
        _draw_player_name_input(frame, game_state)
        # Optionally draw debug info on top if needed
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
        return  # Don't draw other game UI elements in this state

    # --- Draw elements common to PLAYING and MENU states ---
    if game_state.current_state != CurrentGameState.GAME_OVER:
        # Use helper function for text with background
        player_name = game_state.get_current_player().name
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
        # Calculate X position for High Score to align right (approx)
        (tw, th), _ = cv2.getTextSize(
            high_score_text,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.FONT_THICKNESS,
        )
        high_score_x = (
            UIConstants.WINDOW_WIDTH - tw - 10 - 3
        )  # Adjust 10 for space, 3 for padding
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

        # --- Draw Timer Text ---
        if (
            game_state.game_mode == "timed"
            and game_state.game_timer is not None
            # Draw timer even if paused, but maybe not in menu? Check state:
            and game_state.current_state
            in [CurrentGameState.PLAYING, CurrentGameState.PAUSED]
        ):
            # Format as integer seconds remaining
            timer_text = f"Time: {int(game_state.game_timer)}"
            # Change color if <= 10 seconds left
            time_color = (
                UIConstants.RED
                if game_state.game_timer <= 10
                else UIConstants.WHITE  # Use white normally
            )
            # Calculate position (centered at top)
            (tw_t, th_t), _ = cv2.getTextSize(
                timer_text,
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_MEDIUM,
                UIConstants.FONT_THICKNESS,
            )
            timer_x = (UIConstants.WINDOW_WIDTH - tw_t) // 2  # Center timer text
            timer_y = 30  # Align vertically with Score/High Score

            _draw_text_with_background(
                frame,
                timer_text,
                (timer_x, timer_y),
                UIConstants.FONT_SCALE_MEDIUM,
                time_color,
                UIConstants.BLACK,  # Use black background for contrast
                thickness=UIConstants.FONT_THICKNESS,
                alpha=0.7,  # Semi-transparent background
            )
        # --- End Timer Drawing ---

        if game_state.current_state == CurrentGameState.PLAYING:
            # Draw balls only if not drawing zones (optional enhancement)
            if not game_state.drawing:
                draw_balls(frame, game_state)  # Draw balls and trails
            # Draw scoring zones
            draw_scoring_zones(frame, game_state.scoring_zones, game_state.special_hole)
            # Draw temporary zone being drawn
            if game_state.drawing and game_state.temp_zone:
                x1, y1, w, h = game_state.temp_zone
                cv2.rectangle(frame, (x1, y1), (x1 + w, y1 + h), UIConstants.YELLOW, 2)
            # Draw menu button
            draw_menu(frame, game_state)  # Assumes draw_menu draws the button itself

            # Draw achievement notification
            if game_state.achievement_notification:
                notif_text = game_state.achievement_notification
                (tw_ach, th_ach), _ = cv2.getTextSize(
                    notif_text,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    UIConstants.FONT_SCALE_LARGE,
                    UIConstants.FONT_THICKNESS,
                )
                nx_ach, ny_ach = (
                    UIConstants.WINDOW_WIDTH - tw_ach
                ) // 2, UIConstants.WINDOW_HEIGHT - 50
                _draw_text_with_background(
                    frame,
                    notif_text,
                    (nx_ach, ny_ach),
                    UIConstants.FONT_SCALE_LARGE,
                    UIConstants.GREEN,
                    UIConstants.BLACK,
                    thickness=UIConstants.FONT_THICKNESS,
                    alpha=0.7,
                )

        elif game_state.current_state == CurrentGameState.PAUSED:
            # Draw elements specific to PAUSED state if any (e.g., PAUSED text)
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
                3,
            )
            # Also draw zones while paused
            draw_scoring_zones(frame, game_state.scoring_zones, game_state.special_hole)
            # Optionally draw balls while paused
            draw_balls(frame, game_state)

        elif game_state.current_state == CurrentGameState.MENU:
            # Draw elements specific to MENU state
            # Draw balls and zones dimly in background?
            overlay = frame.copy()
            draw_scoring_zones(
                overlay, game_state.scoring_zones, game_state.special_hole
            )
            draw_balls(overlay, game_state)  # Draw balls dimmed
            cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)  # Blend with main frame

            # Calculate menu position and draw menu window
            mx, my = (frame.shape[1] - game_state.menu_width) // 2, (
                frame.shape[0] - game_state.menu_height
            ) // 2
            game_state.menu_pos = (mx, my)
            draw_menu_window(
                frame, game_state
            )  # Assumes draw_menu_window draws the full menu

        # Draw general notifications (like zone added/deleted, errors)
        if game_state.notification_text and game_state.notification_timer > 0:
            color = game_state.notification_color
            (tw_not, th_not), _ = cv2.getTextSize(
                game_state.notification_text,
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_MEDIUM,
                UIConstants.FONT_THICKNESS,
            )
            nx_not, ny_not = (
                UIConstants.WINDOW_WIDTH - tw_not
            ) // 2, UIConstants.WINDOW_HEIGHT - 20
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

    # --- Draw elements specific to GAME_OVER state ---
    elif game_state.current_state == CurrentGameState.GAME_OVER:
        _draw_game_over_screen(frame, game_state)  # From ui_screens.py

    # --- Draw Visual Debug Overlay (if enabled) ---
    # Skip during GETTING_PLAYER_NAME unless explicitly desired
    if (
        game_state.current_state != CurrentGameState.GETTING_PLAYER_NAME
        and hasattr(game_state, "show_debug_overlay")
        and game_state.show_debug_overlay
    ):
        _draw_debug_overlay(frame, game_state)  # From ui_elements.py

    # --- Draw elements always on top (except over name input) ---
    if (
        game_state.current_state != CurrentGameState.GETTING_PLAYER_NAME
        and game_state.debug_mode
    ):
        fps = game_state.fps if hasattr(game_state, "fps") else 0
        state_text = str(game_state.current_state).split(".")[-1]
        overlay_status = (
            "ON" if getattr(game_state, "show_debug_overlay", False) else "OFF"
        )
        # Check if tracked_balls exists before accessing its length
        tracked_count = (
            len(game_state.tracked_balls) if hasattr(game_state, "tracked_balls") else 0
        )
        debug_text = f"FPS:{fps:.1f}|State:{state_text}|Overlay(b):{overlay_status}|Tracked:{tracked_count}"
        # Use helper for debug text background
        _draw_text_with_background(
            frame,
            debug_text,
            (10, UIConstants.WINDOW_HEIGHT - 10),
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.YELLOW,
            UIConstants.BLACK,
            alpha=0.7,
        )
