# ui.py

import logging
import time
from typing import TYPE_CHECKING, Tuple, Dict, Any, Optional, Hashable

import cv2
import numpy as np

# Local project imports
from constants import UIConstants
from game_types import CurrentGameState
from menu import draw_menu, draw_menu_window

# Avoid circular import with game_input
import game_input  # Import game_input module for initialization functions

try:
    from menu_utils import _draw_button
except ImportError:
    # [FIXED] Correctly formatted fallback
    logger = logging.getLogger(__name__)
    logger.error(
        "Failed to import _draw_button from menu_utils. Button drawing will fail."
    )

    def _draw_button(*args, **kwargs):
        pass


from scoring import draw_scoring_zones
from ui_elements import _draw_debug_overlay

# [MODIFY] Import _draw_player_name_input from ui_screens
from ui_screens import (
    _draw_game_over_screen,
    _draw_player_name_input,
)

try:
    from ui_utils import _draw_text_with_background
except ImportError:
    # [FIXED] Correctly formatted fallback
    logger = logging.getLogger(__name__)
    logger.error(
        "Failed to import _draw_text_with_background from ui_utils. Text drawing will fail."
    )

    def _draw_text_with_background(*args, **kwargs):
        pass


# Imports for Stats Display
try:
    from stats_calculator import calculate_session_stats
except ImportError:
    logger.error("Failed import calculate_session_stats")
    calculate_session_stats = None
try:
    from data_logger import SessionData
except ImportError:
    SessionData = Any

# Type hint for GameState
if TYPE_CHECKING:
    from game_state import GameState

logger = logging.getLogger(__name__)

# UI Caching system - improve performance by caching render operations
ui_text_cache: Dict[Hashable, np.ndarray] = {}
ui_element_cache: Dict[Hashable, np.ndarray] = {}
MAX_CACHE_ENTRIES = 50


def _get_cached_text(
    text: str,
    font_scale: float,
    color: Tuple[int, int, int],
    bg_color: Tuple[int, int, int],
    thickness: int = 1,
    alpha: float = 0.7,
) -> Optional[Tuple[np.ndarray, Tuple[int, int]]]:
    """Get cached text image if available."""
    cache_key = (text, font_scale, tuple(color), tuple(bg_color), thickness, alpha)
    if cache_key in ui_text_cache:
        return ui_text_cache[cache_key]
    return None


def _cache_text(
    text: str,
    font_scale: float,
    color: Tuple[int, int, int],
    bg_color: Tuple[int, int, int],
    thickness: int,
    alpha: float,
    text_img: np.ndarray,
    text_size: Tuple[int, int],
) -> None:
    """Cache a rendered text image."""
    # Clean up cache if too large
    if len(ui_text_cache) >= MAX_CACHE_ENTRIES:
        # Remove random entry to keep cache size under control
        keys = list(ui_text_cache.keys())
        if keys:
            del ui_text_cache[keys[0]]

    cache_key = (text, font_scale, tuple(color), tuple(bg_color), thickness, alpha)
    ui_text_cache[cache_key] = (text_img.copy(), text_size)


def _optimized_draw_text(
    frame: np.ndarray,
    text: str,
    position: Tuple[int, int],
    font_scale: float,
    color: Tuple[int, int, int],
    bg_color: Tuple[int, int, int],
    thickness: int = 1,
    alpha: float = 0.7,
) -> None:
    """Optimized version of _draw_text_with_background that uses caching."""
    x, y = position

    # Try to get from cache
    cached_result = _get_cached_text(
        text, font_scale, color, bg_color, thickness, alpha
    )

    if cached_result:
        text_img, (text_w, text_h) = cached_result

        # Ensure within frame bounds
        if x >= 0 and y >= 0 and x + text_w < frame.shape[1] and y < frame.shape[0]:
            # Get ROI from frame
            y_start = max(0, y - text_h)
            y_end = min(frame.shape[0], y + 10)
            x_start = max(0, x)
            x_end = min(frame.shape[1], x + text_w)

            # Only copy if dimensions match and are valid
            if text_img.shape[0] == (y_end - y_start) and text_img.shape[1] == (
                x_end - x_start
            ):
                frame[y_start:y_end, x_start:x_end] = text_img
                return

    # If cache miss or bounds issue, do regular draw and cache the result
    try:
        # Get text size
        (text_w, text_h), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )

        # Calculate background coordinates
        bg_x0 = x
        bg_y0 = y - text_h - baseline
        bg_x1 = x + text_w
        bg_y1 = y + baseline

        # Create a separate canvas for the text
        text_canvas = np.zeros((text_h + 2 * baseline, text_w, 3), dtype=np.uint8)

        # Draw background
        cv2.rectangle(
            text_canvas, (0, 0), (text_w, text_h + 2 * baseline), bg_color, -1
        )

        # Draw text
        cv2.putText(
            text_canvas,
            text,
            (0, text_h),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            color,
            thickness,
            cv2.LINE_AA,
        )

        # Cache for future use
        _cache_text(
            text,
            font_scale,
            color,
            bg_color,
            thickness,
            alpha,
            text_canvas,
            (text_w, text_h),
        )

        # Place on frame
        if (
            bg_x0 >= 0
            and bg_y0 >= 0
            and bg_x1 < frame.shape[1]
            and bg_y1 < frame.shape[0]
        ):
            # Get ROI from frame
            roi = frame[bg_y0:bg_y1, bg_x0:bg_x1]

            # Apply text canvas to ROI
            if roi.shape[:2] == text_canvas.shape[:2]:
                cv2.addWeighted(text_canvas, alpha, roi, 1 - alpha, 0, roi)
            else:
                # Fallback to original method if dimensions don't match
                _draw_text_with_background(
                    frame, text, position, font_scale, color, bg_color, thickness, alpha
                )

    except Exception as e:
        logger.error(f"Error in optimized text drawing: {e}")
        # Fallback to original method
        _draw_text_with_background(
            frame, text, position, font_scale, color, bg_color, thickness, alpha
        )


# --- Helper: Draw Zone Editing Handles ---
# (Function unchanged)
def _draw_zone_edit_handles(frame: np.ndarray, zone_rect: Tuple[int, int, int, int]):
    zx, zy, zw, zh = zone_rect
    handle_size = UIConstants.ZONE_EDIT_HANDLE_SIZE
    handle_color = UIConstants.ZONE_EDIT_HANDLE_COLOR
    half_handle = handle_size // 2
    corners = [(zx, zy), (zx + zw, zy), (zx, zy + zh), (zx + zw, zy + zh)]
    for cx, cy in corners:
        pt1 = (cx - half_handle, cy - half_handle)
        pt2 = (cx + half_handle, cy + half_handle)
        cv2.rectangle(frame, pt1, pt2, handle_color, -1)


# --- Helper Function to Draw Stats Display ---
# (Function unchanged from previous correction)
def _draw_stats_display(frame: np.ndarray, game_state: "GameState") -> None:
    """Draw the statistics display overlay."""
    if not calculate_session_stats:
        logger.error("Stats calculator not available")
        return

    if not hasattr(game_state, "data_logger") or not game_state.data_logger:
        logger.debug("No data logger for stats display.")
        return

    current_session = game_state.data_logger.get_current_session_data()
    if not current_session:
        logger.debug("No active session data for stats display.")
        return

    try:
        stats = calculate_session_stats(current_session)
        if not stats:
            return

        # Update live stats
        live_score = getattr(game_state, "score", 0)
        stats["total_score"] = live_score
        live_duration_seconds = game_state.get_duration()
        stats["duration_seconds"] = live_duration_seconds
        live_duration_min = (
            live_duration_seconds / 60.0 if live_duration_seconds > 0 else 0
        )
        stats["score_rate_per_min"] = (
            (live_score / live_duration_min) if live_duration_min > 0 else 0
        )

        # Panel dimensions and positioning
        current_width, current_height = game_state.get_current_resolution_dimensions()
        menu_x, menu_y = getattr(game_state, "menu_pos", (0, 0))
        menu_w = getattr(game_state, "menu_width", 600)
        stats_content_height = 230
        button_height = 35
        panel_padding_bottom = 15
        total_content_height = (
            stats_content_height + button_height + panel_padding_bottom
        )
        panel_width = 350
        panel_height = max(
            total_content_height + 40, getattr(game_state, "menu_height", 450)
        )
        padding = 20

        # Position panel next to menu
        panel_x = menu_x + menu_w + padding
        panel_y = menu_y

        # Adjust if panel would go off screen
        if panel_x + panel_width > current_width - padding:
            panel_x = menu_x - panel_width - padding
        if panel_x < padding:
            panel_x = (current_width - panel_width) // 2
            panel_y = menu_y + getattr(game_state, "menu_height", 450) + padding
            panel_height = total_content_height + 40

        # Ensure panel stays within screen bounds
        panel_x = max(padding, min(panel_x, current_width - panel_width - padding))
        panel_y = max(padding, min(panel_y, current_height - panel_height - padding))

        # Draw semi-transparent background
        bg_color = UIConstants.GREY_BG
        alpha = 0.85
        try:
            x1, y1 = panel_x, panel_y
            x2, y2 = panel_x + panel_width, panel_y + panel_height
            y1_c, y2_c = max(0, y1), min(current_height, y2)
            x1_c, x2_c = max(0, x1), min(current_width, x2)
            if y1_c >= y2_c or x1_c >= x2_c:
                raise ValueError("Invalid panel dimensions after clamping.")
            roi = frame[y1_c:y2_c, x1_c:x2_c]
            overlay = np.full(roi.shape, bg_color, dtype=np.uint8)
            cv2.addWeighted(overlay, alpha, roi, 1.0 - alpha, 0, roi)
            cv2.rectangle(frame, (x1, y1), (x2, y2), UIConstants.WHITE, 1)
        except Exception as e:
            logger.error(f"Error drawing stats panel background or border: {e}")
            return

        # Text settings
        text_x_offset = 15
        text_y_offset = 40
        line_height = 25
        current_y = panel_y + text_y_offset
        font = cv2.FONT_HERSHEY_SIMPLEX
        small_scale = UIConstants.FONT_SCALE_SMALL
        medium_scale = UIConstants.FONT_SCALE_MEDIUM
        text_color = UIConstants.WHITE
        value_color = UIConstants.YELLOW
        title_color = UIConstants.YELLOW

        # Draw title
        cv2.putText(
            frame,
            "Session Stats",
            (panel_x + text_x_offset, panel_y + 25),
            font,
            small_scale * 1.1,
            title_color,
            1,
            cv2.LINE_AA,
        )

        # Draw duration
        duration = stats.get("duration_seconds", 0)
        duration_str = f"{int(duration // 60):02d}:{int(duration % 60):02d}"
        cv2.putText(
            frame,
            "Duration:",
            (panel_x + text_x_offset, current_y),
            font,
            small_scale,
            text_color,
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            duration_str,
            (panel_x + 150, current_y),
            font,
            small_scale,
            value_color,
            1,
            cv2.LINE_AA,
        )
        current_y += line_height

        # Draw score
        score = stats.get("total_score", 0)
        cv2.putText(
            frame,
            "Score:",
            (panel_x + text_x_offset, current_y),
            font,
            small_scale,
            text_color,
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            f"{score}",
            (panel_x + 150, current_y),
            font,
            small_scale,
            value_color,
            1,
            cv2.LINE_AA,
        )
        current_y += line_height

        # Draw score rate
        rate = stats.get("score_rate_per_min", 0)
        cv2.putText(
            frame,
            "Score Rate:",
            (panel_x + text_x_offset, current_y),
            font,
            small_scale,
            text_color,
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            f"{rate:.1f} pts/min",
            (panel_x + 150, current_y),
            font,
            small_scale,
            value_color,
            1,
            cv2.LINE_AA,
        )
        current_y += line_height + 5

        # Draw points by ball type
        cv2.putText(
            frame,
            "Points by Ball Type:",
            (panel_x + text_x_offset, current_y),
            font,
            small_scale,
            text_color,
            1,
            cv2.LINE_AA,
        )
        current_y += line_height

        ball_pts = stats.get("points_by_ball_type", {})
        type_order = ["white", "red", "half"]
        for ball_type in type_order:
            pts = ball_pts.get(ball_type, 0)
            cv2.putText(
                frame,
                f"  - {ball_type.capitalize()}:",
                (panel_x + text_x_offset, current_y),
                font,
                small_scale,
                text_color,
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                f"{pts}",
                (panel_x + 150, current_y),
                font,
                small_scale,
                value_color,
                1,
                cv2.LINE_AA,
            )
            current_y += line_height

        # Draw top scoring zones
        current_y += 5
        cv2.putText(
            frame,
            "Top Scoring Zones:",
            (panel_x + text_x_offset, current_y),
            font,
            small_scale,
            text_color,
            1,
            cv2.LINE_AA,
        )
        current_y += line_height

        top_zones = stats.get("top_3_zones", [])
        if not top_zones:
            cv2.putText(
                frame,
                "  (No scores yet)",
                (panel_x + text_x_offset, current_y),
                font,
                small_scale,
                text_color,
                1,
                cv2.LINE_AA,
            )
            current_y += line_height
        else:
            for i, (zone_id, zone_points) in enumerate(top_zones):
                cv2.putText(
                    frame,
                    f"  {i+1}. Zone {zone_id + 1}:",
                    (panel_x + text_x_offset, current_y),
                    font,
                    small_scale,
                    text_color,
                    1,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    frame,
                    f"{zone_points} pts",
                    (panel_x + 150, current_y),
                    font,
                    small_scale,
                    value_color,
                    1,
                    cv2.LINE_AA,
                )
                current_y += line_height

        # Draw heatmap button
        button_y_pos = panel_y + panel_height - button_height - panel_padding_bottom
        button_x_pos = panel_x + text_x_offset
        heatmap_button_width = panel_width - (2 * text_x_offset)
        _draw_button(
            frame=frame,
            x=button_x_pos,
            y=button_y_pos,
            w=heatmap_button_width,
            h=button_height,
            text="Show Heatmap",
            color=UIConstants.CV2_BLUE,
            game_state=game_state,
            font_scale=UIConstants.FONT_SCALE_MEDIUM,
        )

    except Exception as e:
        logger.error(f"Error drawing stats display: {e}")


# --- Main UI Drawing Function ---
def draw_ui(frame: np.ndarray, game_state: "GameState") -> None:
    current_width, current_height = game_state.get_current_resolution_dimensions()
    if game_state.current_state == CurrentGameState.GETTING_PLAYER_NAME:
        # Initialize cursor position if not done yet
        if not hasattr(game_state, "player_name_cursor_pos"):
            if hasattr(game_input, "init_player_name_input"):
                game_input.init_player_name_input(game_state)
            else:
                # Fallback initialization if import failed
                game_state.player_name_cursor_pos = len(
                    getattr(game_state, "current_player_name_input", "")
                )

        _draw_player_name_input(frame, game_state)

        if getattr(game_state, "debug_mode", False):
            fps = getattr(game_state, "fps", 0)
            state_text = str(game_state.current_state).split(".")[-1]
            debug_text = f"FPS:{fps:.1f}|State:{state_text}"
            _optimized_draw_text(
                frame,
                debug_text,
                (10, current_height - 10),
                UIConstants.FONT_SCALE_SMALL,
                UIConstants.YELLOW,
                UIConstants.BLACK,
                alpha=0.7,
            )
        return
    if game_state.current_state not in [CurrentGameState.GAME_OVER]:
        try:
            player_name = game_state.get_current_player().name
        except Exception:
            player_name = "Error"
        score_text = f"Player: {player_name} Score: {game_state.score}"
        score_pos_x = int(0.01 * current_width)
        score_pos_y = int(0.04 * current_height)
        _optimized_draw_text(
            frame,
            score_text,
            (score_pos_x, score_pos_y),
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
        high_score_pos_x = current_width - tw - int(0.01 * current_width)
        high_score_pos_y = score_pos_y
        _optimized_draw_text(
            frame,
            high_score_text,
            (high_score_pos_x, high_score_pos_y),
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            UIConstants.GREY_BG,
            thickness=UIConstants.FONT_THICKNESS,
        )
        mode_text = f"Mode: {game_state.game_mode.capitalize()}"
        mode_pos_x = score_pos_x
        mode_pos_y = current_height - int(0.03 * current_height)
        _optimized_draw_text(
            frame,
            mode_text,
            (mode_pos_x, mode_pos_y),
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.WHITE,
            UIConstants.GREY_BG,
            thickness=UIConstants.FONT_THICKNESS,
        )
        if (
            game_state.game_mode in ["timed", "survival"]
            and game_state.game_timer is not None
            and game_state.current_state not in [CurrentGameState.GAME_OVER]
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
            timer_x = (current_width - tw_t) // 2
            timer_y = score_pos_y
            _optimized_draw_text(
                frame,
                timer_text,
                (timer_x, timer_y),
                UIConstants.FONT_SCALE_MEDIUM,
                time_color,
                UIConstants.BLACK,
                thickness=UIConstants.FONT_THICKNESS,
                alpha=0.7,
            )
    if game_state.current_state == CurrentGameState.PLAYING:
        draw_scoring_zones(frame, game_state.scoring_zones, game_state.special_hole)
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
            if text_x + ptw > current_width:
                text_x = x1 + w - ptw - 5
            if text_y < pth:
                text_y = y1 + pth + 5
            if text_y > current_height - 5:
                text_y = y1 + h - pth - 5
            _optimized_draw_text(
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
            draw_menu(frame, game_state)
            res_button_rect = (
                UIConstants.RESOLUTION_BUTTON_X,
                UIConstants.RESOLUTION_BUTTON_Y,
                UIConstants.RESOLUTION_BUTTON_WIDTH,
                UIConstants.RESOLUTION_BUTTON_HEIGHT,
            )
            res_button_text = game_state.current_resolution_key
            _draw_button(
                frame,
                res_button_rect[0],
                res_button_rect[1],
                res_button_rect[2],
                res_button_rect[3],
                res_button_text,
                UIConstants.CV2_BLUE,
                game_state=game_state,
                font_scale=UIConstants.FONT_SCALE_SMALL,
            )
    elif game_state.current_state == CurrentGameState.PAUSED:
        pause_text = "PAUSED"
        (tw_p, th_p), _ = cv2.getTextSize(
            pause_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_XLARGE, 3
        )
        pause_x = (current_width - tw_p) // 2
        pause_y = current_height // 2
        _optimized_draw_text(
            frame,
            pause_text,
            (pause_x, pause_y),
            UIConstants.FONT_SCALE_XLARGE,
            UIConstants.YELLOW,
            UIConstants.BLACK,
            thickness=3,
        )
        draw_scoring_zones(frame, game_state.scoring_zones, game_state.special_hole)
        _draw_stats_display(frame, game_state)
    elif game_state.current_state == CurrentGameState.MENU:
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (current_width, current_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        draw_menu_window(frame, game_state)
        _draw_stats_display(frame, game_state)
    elif game_state.current_state == CurrentGameState.ZONE_EDITING:
        draw_scoring_zones(frame, game_state.scoring_zones, game_state.special_hole)
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
        # --- [FIX 5th time] Correctly formatted else/try/except block ---
        else:
            logger.warning(
                "In ZONE_EDITING state but selected_zone_for_edit is invalid. Reverting state."
            )
            try:
                # Get previous state (e.g., MENU)
                prev_state = getattr(game_state, "previous_state", None)
                # Set current state, defaulting to MENU if previous wasn't set
                game_state.current_state = (
                    prev_state if prev_state else CurrentGameState.MENU
                )
                # Clear the previous state marker
                game_state.previous_state = None
            except AttributeError:
                # Fallback if 'previous_state' doesn't exist or error occurs
                game_state.current_state = CurrentGameState.MENU

            # Reset editing variables cleanly on separate lines
            game_state.selected_zone_for_edit = None
            game_state.zone_editing_action = None
            game_state.drag_start_pos = None
            game_state.original_zone_on_drag_start = None
            game_state.menu_cache = None  # Invalidate menu cache if returning to menu
        # --- [END FIX] ---
    elif game_state.current_state == CurrentGameState.GAME_OVER:
        _draw_game_over_screen(frame, game_state)
    elif game_state.current_state == CurrentGameState.CONFIRM_QUIT:
        overlay = frame.copy()
        cv2.rectangle(
            overlay, (0, 0), (current_width, current_height), UIConstants.BLACK, -1
        )
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
        dialog_width, dialog_height = 400, 150
        dialog_x = (current_width - dialog_width) // 2
        dialog_y = (current_height - dialog_height) // 2
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
            game_state=game_state,
            font_scale=UIConstants.FONT_SCALE_MEDIUM,
        )
        game_state.submenu_items = [
            (yes_rect, "confirm_quit_yes", "Confirm Quit"),
            (no_rect, "confirm_quit_no", "Cancel Quit"),
        ]
        game_state.menu_pos = (0, 0)
        game_state.menu_width = current_width
        game_state.menu_height = current_height
    if game_state.game_mode in ["fun", "retro"]:
        if hasattr(game_state, "active_explosions") and isinstance(
            game_state.active_explosions, list
        ):
            for explosion in list(game_state.active_explosions):
                try:
                    if (
                        hasattr(explosion, "is_active")
                        and explosion.is_active()
                        and hasattr(explosion, "draw")
                    ):
                        explosion.draw(frame)
                except Exception as e:
                    logger.error(f"Error drawing explosion: {e}")
    if game_state.current_state != CurrentGameState.GETTING_PLAYER_NAME:
        notification_drawn = False
        ny_not = current_height - 30
        if game_state.notification_text and game_state.notification_timer > 0:
            color = game_state.notification_color
            (tw_not, th_not), _ = cv2.getTextSize(
                game_state.notification_text,
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_MEDIUM,
                UIConstants.FONT_THICKNESS,
            )
            nx_not = (current_width - tw_not) // 2
            _optimized_draw_text(
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
            initial_ny_ach = current_height - int(0.1 * current_height)
            final_ny_ach = initial_ny_ach
            if notification_drawn and initial_ny_ach > ny_not - th_ach - 10:
                final_ny_ach = ny_not - th_ach - 10
            nx_ach = (current_width - tw_ach) // 2
            _optimized_draw_text(
                frame,
                ach_text,
                (nx_ach, final_ny_ach),
                UIConstants.FONT_SCALE_LARGE,
                UIConstants.GREEN,
                UIConstants.BLACK,
                thickness=UIConstants.FONT_THICKNESS,
                alpha=0.7,
            )
    if (
        game_state.current_state != CurrentGameState.GETTING_PLAYER_NAME
        and hasattr(game_state, "show_debug_overlay")
        and game_state.show_debug_overlay
    ):
        _draw_debug_overlay(frame, game_state)
    if game_state.current_state != CurrentGameState.GETTING_PLAYER_NAME and getattr(
        game_state, "debug_mode", False
    ):
        fps = getattr(game_state, "fps", 0)
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
        debug_text_parts = [
            f"FPS:{fps:.1f}",
            f"State:{state_text}",
            f"{drawing_active_text}",
            f"Overlay(b):{overlay_status}",
            f"Tracked:{tracked_count}",
            f"Res:{game_state.current_resolution_key}",
        ]
        if edit_info:
            debug_text_parts.append(edit_info)
        debug_text = " | ".join(debug_text_parts)
        _optimized_draw_text(
            frame,
            debug_text,
            (10, current_height - 10),
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.YELLOW,
            UIConstants.BLACK,
            alpha=0.7,
        )


# Clear UI caches to free memory
def clear_ui_caches() -> None:
    """Clear the UI caches."""
    global ui_text_cache, ui_element_cache
    ui_text_cache.clear()
    ui_element_cache.clear()
    logger.debug("UI caches cleared")
