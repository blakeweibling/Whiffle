# ui.py

import logging
import time
from typing import TYPE_CHECKING, Tuple, Dict, Any, Optional

import cv2
import numpy as np

# Local project imports
from constants import UIConstants #
from game_types import CurrentGameState #
from menu import draw_menu, draw_menu_window #

try:
    from menu_utils import _draw_button #
except ImportError:
    logger.error("Failed to import _draw_button from menu_utils. Button drawing will fail.") #
    def _draw_button(*args, **kwargs): pass

from scoring import draw_scoring_zones #
from ui_elements import _draw_debug_overlay #
# [MODIFY] Import _draw_player_name_input from ui_screens if it moved
# from ui_screens import _draw_game_over_screen, display_modal_splash, _draw_player_name_input
from ui_screens import _draw_game_over_screen, display_modal_splash, _draw_player_name_input

try:
    from ui_utils import _draw_text_with_background #
except ImportError:
    logger.error("Failed to import _draw_text_with_background from ui_utils. Text drawing will fail.") #
    def _draw_text_with_background(*args, **kwargs): pass

# Imports for Stats Display
try: from stats_calculator import calculate_session_stats #
except ImportError: logger.error("Failed to import calculate_session_stats. Stats display will be unavailable."); calculate_session_stats = None #
try: from data_logger import SessionData #
except ImportError: SessionData = Any #

# Type hint for GameState
if TYPE_CHECKING:
    from game_state import GameState

logger = logging.getLogger(__name__)


# --- Player Name Input Drawing ---
# [MODIFY] Ensure this function also uses current dimensions for positioning if needed
def _draw_player_name_input(frame: np.ndarray, game_state: "GameState"):
    """Draws the pop-up screen for initial player name input."""
    # Get current dimensions
    current_width, current_height = game_state.get_current_resolution_dimensions()

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (current_width, current_height), UIConstants.BLACK, -1) # Use current dims
    alpha = 0.7
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    popup_width, popup_height = 700, 200 # Keep fixed size for popup? Or scale? Scaling example:
    # popup_width = int(0.36 * current_width) # ~700/1920
    # popup_height = int(0.18 * current_height) # ~200/1080

    popup_x = (current_width - popup_width) // 2 # Center based on current width
    popup_y = (current_height - popup_height) // 2 # Center based on current height

    # Draw popup background and border
    cv2.rectangle(frame, (popup_x, popup_y), (popup_x + popup_width, popup_y + popup_height), UIConstants.GREY_BG, -1,) #
    cv2.rectangle(frame, (popup_x, popup_y), (popup_x + popup_width, popup_y + popup_height), UIConstants.WHITE, 1,) #

    # Position text elements relative to popup_x, popup_y
    prompt_text = "Enter Player Name:"
    prompt_pos = (popup_x + 20, popup_y + 40)
    cv2.putText(frame, prompt_text, prompt_pos, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, UIConstants.FONT_THICKNESS, cv2.LINE_AA,) #

    input_bg_x, input_bg_y = popup_x + 20, popup_y + 70
    input_bg_w, input_bg_h = popup_width - 40, 40
    cv2.rectangle(frame, (input_bg_x, input_bg_y), (input_bg_x + input_bg_w, input_bg_y + input_bg_h), (50, 50, 50), -1,) #

    show_cursor = int(time.time() * 2) % 2 == 0
    cursor = "_" if show_cursor else " "
    current_input = getattr(game_state, "current_player_name_input", "") #
    display_name = current_input + cursor
    name_pos = (input_bg_x + 10, input_bg_y + 30)
    cv2.putText(frame, display_name, name_pos, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.YELLOW, UIConstants.FONT_THICKNESS + 1, cv2.LINE_AA,) #

    instructions_text = "Enter=Confirm, Esc=Default ('Player 1'), Backspace=Delete"
    instr_pos = (popup_x + 20, popup_y + popup_height - 30)
    cv2.putText(frame, instructions_text, instr_pos, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, UIConstants.WHITE, UIConstants.FONT_THICKNESS, cv2.LINE_AA,) #


# --- Helper: Draw Zone Editing Handles ---
# (Unchanged, uses absolute coords passed to it)
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
# [MODIFY] Ensure this function uses current dimensions for panel positioning
def _draw_stats_display(frame: np.ndarray, game_state: "GameState"):
    """Draws the current session stats in a panel, using LIVE score/duration."""
    if not calculate_session_stats: return #
    if not hasattr(game_state, "data_logger") or not game_state.data_logger: logger.debug("No data logger for stats display."); return #
    current_session = game_state.data_logger.get_current_session_data() #
    if not current_session: logger.debug("No active session data for stats display."); return #

    try: stats = calculate_session_stats(current_session) #
    except Exception as e: logger.error(f"Error calculating session stats: {e}"); return #
    if not stats: return #

    # Override with LIVE data for display
    live_score = getattr(game_state, "score", 0) #
    stats["total_score"] = live_score
    live_duration_seconds = time.time() - current_session.start_time #
    stats["duration_seconds"] = live_duration_seconds
    live_duration_min = live_duration_seconds / 60.0 if live_duration_seconds > 0 else 0 #
    stats["score_rate_per_min"] = ((live_score / live_duration_min) if live_duration_min > 0 else 0) #

    # Get current dimensions for panel positioning
    current_width, current_height = game_state.get_current_resolution_dimensions()

    # Panel Positioning and Drawing (Uses Menu position as anchor - ensure menu pos is valid)
    menu_x, menu_y = getattr(game_state, "menu_pos", (0, 0)) #
    menu_w = getattr(game_state, "menu_width", 600) # Should this also scale? Maybe fixed pixel width is ok.
    stats_content_height = 230 # Fixed height for content
    button_height = 35 # Fixed button height
    panel_padding_bottom = 15 # Fixed padding
    total_content_height = stats_content_height + button_height + panel_padding_bottom #
    panel_width = 350 # Fixed panel width
    panel_height = max(total_content_height + 40, getattr(game_state, "menu_height", 450)) # Anchor height to menu height or content
    padding = 20 # Fixed padding

    # Attempt to position right of menu, fallback to below or center
    panel_x = menu_x + menu_w + padding
    panel_y = menu_y
    if panel_x + panel_width > current_width - padding: # Check against current_width
        panel_x = menu_x - panel_width - padding
    if panel_x < padding: # If still overlapping or off-screen left
        panel_x = (current_width - panel_width) // 2 # Center horizontally
        panel_y = menu_y + getattr(game_state, "menu_height", 450) + padding # Place below menu
        panel_height = total_content_height + 40 # Recalculate height if placed below
    # Clamp final position within screen bounds
    panel_x = max(padding, min(panel_x, current_width - panel_width - padding)) # Use current_width
    panel_y = max(padding, min(panel_y, current_height - panel_height - padding)) # Use current_height

    # Draw Panel Background & Border
    bg_color = UIConstants.GREY_BG #
    alpha = 0.85 #
    try:
        x1, y1 = panel_x, panel_y
        x2, y2 = panel_x + panel_width, panel_y + panel_height
        # Clamp ROI to frame dimensions
        y1_c, y2_c = max(0, y1), min(current_height, y2) # Use current_height
        x1_c, x2_c = max(0, x1), min(current_width, x2) # Use current_width
        if y1_c >= y2_c or x1_c >= x2_c: raise ValueError("Invalid panel dimensions after clamping.") #
        roi = frame[y1_c:y2_c, x1_c:x2_c]
        overlay = np.full(roi.shape, bg_color, dtype=np.uint8)
        cv2.addWeighted(overlay, alpha, roi, 1.0 - alpha, 0, roi) #
        cv2.rectangle(frame, (x1, y1), (x2, y2), UIConstants.WHITE, 1) # Draw border at original calculated position
    except Exception as e:
        logger.error(f"Error drawing stats panel background or border: {e}")
        return # Don't draw text if background failed

    # Draw Stats Text (Positioned relative to panel_x, panel_y)
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

    # Draw Title
    cv2.putText(frame, "Current Session Stats", (panel_x + text_x_offset, panel_y + 25), font, small_scale * 1.1, title_color, 1, cv2.LINE_AA,) #

    # Draw Duration
    duration = stats.get("duration_seconds", 0) #
    duration_str = time.strftime("%M:%S", time.gmtime(duration)) #
    cv2.putText(frame, f"Duration:", (panel_x + text_x_offset, current_y), font, small_scale, text_color, 1, cv2.LINE_AA,) #
    cv2.putText(frame, f"{duration_str}", (panel_x + 150, current_y), font, small_scale, value_color, 1, cv2.LINE_AA,) #
    current_y += line_height

    # Draw Score
    score = stats.get("total_score", 0) #
    cv2.putText(frame, f"Score:", (panel_x + text_x_offset, current_y), font, small_scale, text_color, 1, cv2.LINE_AA,) #
    cv2.putText(frame, f"{score}", (panel_x + 150, current_y), font, small_scale, value_color, 1, cv2.LINE_AA,) #
    current_y += line_height

    # Draw Score Rate
    rate = stats.get("score_rate_per_min", 0) #
    cv2.putText(frame, f"Score Rate:", (panel_x + text_x_offset, current_y), font, small_scale, text_color, 1, cv2.LINE_AA,) #
    cv2.putText(frame, f"{rate:.1f} pts/min", (panel_x + 150, current_y), font, small_scale, value_color, 1, cv2.LINE_AA,) #
    current_y += line_height + 5

    # Draw Points by Ball Type
    cv2.putText(frame, f"Points by Ball Type:", (panel_x + text_x_offset, current_y), font, small_scale, text_color, 1, cv2.LINE_AA,) #
    current_y += line_height
    ball_pts = stats.get("points_by_ball_type", {}) #
    type_order = ["white", "red", "half"] #
    for ball_type in type_order: #
        pts = ball_pts.get(ball_type, 0)
        cv2.putText(frame, f"  - {ball_type.capitalize()}:", (panel_x + text_x_offset, current_y), font, small_scale, text_color, 1, cv2.LINE_AA,) #
        cv2.putText(frame, f"{pts}", (panel_x + 150, current_y), font, small_scale, value_color, 1, cv2.LINE_AA,) #
        current_y += line_height
    current_y += 5

    # Draw Top Scoring Zones
    cv2.putText(frame, f"Top Scoring Zones:", (panel_x + text_x_offset, current_y), font, small_scale, text_color, 1, cv2.LINE_AA,) #
    current_y += line_height
    top_zones = stats.get("top_3_zones", []) #
    if not top_zones:
        cv2.putText(frame, "  (No scores yet)", (panel_x + text_x_offset, current_y), font, small_scale, text_color, 1, cv2.LINE_AA,) #
        current_y += line_height
    else:
        for i, (zone_id, zone_points) in enumerate(top_zones): #
            cv2.putText(frame, f"  {i+1}. Zone {zone_id + 1}:", (panel_x + text_x_offset, current_y), font, small_scale, text_color, 1, cv2.LINE_AA,) #
            cv2.putText(frame, f"{zone_points} pts", (panel_x + 150, current_y), font, small_scale, value_color, 1, cv2.LINE_AA,) #
            current_y += line_height

    # Draw Show Heatmap Button (Positioned relative to panel bottom)
    button_y_pos = panel_y + panel_height - button_height - panel_padding_bottom #
    button_x_pos = panel_x + text_x_offset #
    heatmap_button_width = panel_width - (2 * text_x_offset) #
    _draw_button(frame=frame, x=button_x_pos, y=button_y_pos, w=heatmap_button_width, h=button_height, text="Show Heatmap", color=UIConstants.CV2_BLUE, game_state=game_state, font_scale=UIConstants.FONT_SCALE_MEDIUM,) #


# --- Main UI Drawing Function ---
def draw_ui(frame: np.ndarray, game_state: "GameState") -> None:
    """Draw the user interface elements on the frame, handling different game states."""

    # [ADD] Get current dimensions for positioning calculations
    current_width, current_height = game_state.get_current_resolution_dimensions()

    # State: Getting Player Name
    if game_state.current_state == CurrentGameState.GETTING_PLAYER_NAME: #
        # Pass current dimensions if needed, or ensure it uses game_state internally
        _draw_player_name_input(frame, game_state)
        if getattr(game_state, "debug_mode", False): #
            fps = getattr(game_state, "fps", 0) #
            state_text = str(game_state.current_state).split(".")[-1] #
            debug_text = f"FPS:{fps:.1f}|State:{state_text}"
            # Position debug text bottom-left using current_height
            _draw_text_with_background(frame, debug_text, (10, current_height - 10), UIConstants.FONT_SCALE_SMALL, UIConstants.YELLOW, UIConstants.BLACK, alpha=0.7,) #
        return

    # --- Draw common elements ---
    if game_state.current_state not in [CurrentGameState.GAME_OVER]: #
        try: player_name = game_state.get_current_player().name #
        except Exception: player_name = "Error" #
        score_text = f"Player: {player_name} Score: {game_state.score}" #
        # Position score text top-left using relative padding
        score_pos_x = int(0.01 * current_width)
        score_pos_y = int(0.04 * current_height)
        _draw_text_with_background(frame, score_text, (score_pos_x, score_pos_y), UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, UIConstants.GREY_BG, thickness=UIConstants.FONT_THICKNESS,) #

        high_score_text = f"High Score: {game_state.high_score}" #
        (tw, th), _ = cv2.getTextSize(high_score_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.FONT_THICKNESS,) #
        # Position high score top-right using relative padding
        high_score_pos_x = current_width - tw - int(0.01 * current_width)
        high_score_pos_y = score_pos_y # Align vertically
        _draw_text_with_background(frame, high_score_text, (high_score_pos_x, high_score_pos_y), UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, UIConstants.GREY_BG, thickness=UIConstants.FONT_THICKNESS,) #

        mode_text = f"Mode: {game_state.game_mode.capitalize()}" #
        # Position mode below score
        mode_pos_y = score_pos_y + int(0.05 * current_height) # ~5% height below score_pos_y
        _draw_text_with_background(frame, mode_text, (score_pos_x, mode_pos_y), UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, UIConstants.GREY_BG, thickness=UIConstants.FONT_THICKNESS,) #

        # Timer positioning (centered horizontally, aligned with score vertically)
        if (game_state.game_mode in ["timed", "survival"] and game_state.game_timer is not None and game_state.current_state not in [CurrentGameState.GAME_OVER]): #
            timer_text = f"Time: {int(max(0, game_state.game_timer))}" #
            time_color = (UIConstants.RED if game_state.game_timer <= 10 else UIConstants.WHITE) #
            (tw_t, th_t), _ = cv2.getTextSize(timer_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.FONT_THICKNESS,) #
            timer_x = (current_width - tw_t) // 2 # Use current_width for centering
            timer_y = score_pos_y # Align vertically with score
            _draw_text_with_background(frame, timer_text, (timer_x, timer_y), UIConstants.FONT_SCALE_MEDIUM, time_color, UIConstants.BLACK, thickness=UIConstants.FONT_THICKNESS, alpha=0.7,) #

    # --- State-Specific Drawing ---

    # State: Playing
    if game_state.current_state == CurrentGameState.PLAYING: #
        # Draw zones (assuming draw_scoring_zones handles scaling internally or uses absolute coords)
        draw_scoring_zones(frame, game_state.scoring_zones, game_state.special_hole) #

        # Draw temporary zone if drawing (needs to use absolute coords during draw)
        if game_state.drawing and game_state.temp_zone: #
            x1, y1, w, h = game_state.temp_zone
            cv2.rectangle(frame, (x1, y1), (x1 + w, y1 + h), UIConstants.YELLOW, 2) #
            # Drawing points text positioning needs current dimensions
            show_cursor = int(time.time() * 2) % 2 == 0 #
            cursor = "_" if show_cursor else " " #
            points_display_str = game_state.drawing_points_input or "..." #
            points_text = f"{points_display_str}{cursor} pts" #
            (ptw, pth), _ = cv2.getTextSize(points_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, 1) #
            text_x, text_y = x1 + w + 5, y1 + h - 5
            # Adjust based on current_width/height if needed
            if text_x + ptw > current_width: text_x = x1 + w - ptw - 5 #
            if text_y < pth: text_y = y1 + pth + 5 #
            if text_y > current_height - 5: text_y = y1 + h - pth - 5 #
            _draw_text_with_background(frame, points_text, (text_x, text_y), UIConstants.FONT_SCALE_SMALL, UIConstants.YELLOW, UIConstants.BLACK, thickness=1, alpha=0.7,) #

        # Draw Menu button and NEW Resolution button if not drawing zone
        if not game_state.drawing:
            draw_menu(frame, game_state) # Draws the 'Menu' button

            # --- [ADD] Draw Resolution Button ---
            res_button_rect = (
                UIConstants.RESOLUTION_BUTTON_X,
                UIConstants.RESOLUTION_BUTTON_Y,
                UIConstants.RESOLUTION_BUTTON_WIDTH,
                UIConstants.RESOLUTION_BUTTON_HEIGHT
            )
            res_button_text = game_state.current_resolution_key # Dynamic text

            _draw_button(
                frame,
                res_button_rect[0],
                res_button_rect[1],
                res_button_rect[2],
                res_button_rect[3],
                res_button_text,
                UIConstants.CV2_BLUE, # Or another color
                game_state=game_state, # Pass game_state for click feedback
                font_scale=UIConstants.FONT_SCALE_SMALL # Adjust size if needed
            )
            # --- [END ADD] ---


    # State: Paused
    elif game_state.current_state == CurrentGameState.PAUSED: #
        pause_text = "PAUSED"
        (tw_p, th_p), _ = cv2.getTextSize(pause_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_XLARGE, 3) #
        # Center based on current dimensions
        pause_x = (current_width - tw_p) // 2
        pause_y = current_height // 2
        _draw_text_with_background(frame, pause_text, (pause_x, pause_y), UIConstants.FONT_SCALE_XLARGE, UIConstants.YELLOW, UIConstants.BLACK, thickness=3,) #
        # Draw zones and stats display
        draw_scoring_zones(frame, game_state.scoring_zones, game_state.special_hole) #
        _draw_stats_display(frame, game_state) # Ensure stats display positions correctly

    # State: Menu
    elif game_state.current_state == CurrentGameState.MENU: #
        overlay = frame.copy()
        # Use current dimensions for overlay
        cv2.rectangle(overlay, (0, 0), (current_width, current_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        # Ensure draw_menu_window uses current dimensions if needed for positioning/sizing
        draw_menu_window(frame, game_state) #
        _draw_stats_display(frame, game_state) #

    # State: Zone Editing (Interactive Move/Resize)
    elif game_state.current_state == CurrentGameState.ZONE_EDITING: #
        draw_scoring_zones(frame, game_state.scoring_zones, game_state.special_hole) #
        if (game_state.selected_zone_for_edit is not None and 0 <= game_state.selected_zone_for_edit < len(game_state.scoring_zones)): #
            zone_to_edit = game_state.scoring_zones[game_state.selected_zone_for_edit] #
            zx, zy, zw, zh, _ = zone_to_edit
            cv2.rectangle(frame, (zx, zy), (zx + zw, zy + zh), UIConstants.ZONE_EDIT_SELECTED_COLOR, 3,) #
            _draw_zone_edit_handles(frame, (zx, zy, zw, zh)) #
        else:
             # Safety check: Revert state if invalid index(logic unchanged)
             logger.warning("In ZONE_EDITING state but selected_zone_for_edit is invalid. Reverting state.") #
             try: prev_state = getattr(game_state, "previous_state", None); game_state.current_state = (prev_state if prev_state else CurrentGameState.MENU); game_state.previous_state = None #
             except AttributeError: game_state.current_state = CurrentGameState.MENU #
             game_state.selected_zone_for_edit = None; game_state.zone_editing_action = None; game_state.drag_start_pos = None; game_state.original_zone_on_drag_start = None #

    # State: Game Over
    elif game_state.current_state == CurrentGameState.GAME_OVER: #
        # Ensure _draw_game_over_screen positions buttons based on current dimensions
        _draw_game_over_screen(frame, game_state) #

    # State: Confirm Quit
    elif game_state.current_state == CurrentGameState.CONFIRM_QUIT: #
        overlay = frame.copy()
        # Use current dimensions for overlay
        cv2.rectangle(overlay, (0, 0), (current_width, current_height), UIConstants.BLACK, -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
        # Center dialog based on current dimensions
        dialog_width, dialog_height = 400, 150 # Fixed dialog size
        dialog_x = (current_width - dialog_width) // 2
        dialog_y = (current_height - dialog_height) // 2
        # Draw dialog box and elements relative to dialog_x, dialog_y (logic unchanged)
        cv2.rectangle(frame, (dialog_x, dialog_y), (dialog_x + dialog_width, dialog_y + dialog_height), UIConstants.GREY_BG, -1,) #
        cv2.rectangle(frame, (dialog_x, dialog_y), (dialog_x + dialog_width, dialog_y + dialog_height), UIConstants.WHITE, 2,) #
        confirm_text = "Quit Game?"
        font_scale, thickness = UIConstants.FONT_SCALE_LARGE, 2 #
        (tw, th), _ = cv2.getTextSize(confirm_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness) #
        text_x, text_y = dialog_x + (dialog_width - tw) // 2, dialog_y + th + 20 #
        cv2.putText(frame, confirm_text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, UIConstants.WHITE, thickness, cv2.LINE_AA,) #
        button_width, button_height, button_spacing = 100, 40, 40 #
        total_button_width = button_width * 2 + button_spacing #
        button_start_x = dialog_x + (dialog_width - total_button_width) // 2 #
        button_y = dialog_y + dialog_height - button_height - 20 #
        yes_button_x = button_start_x #
        no_button_x = button_start_x + button_width + button_spacing #
        yes_rect = (yes_button_x, button_y, button_width, button_height) #
        _draw_button(frame, yes_button_x, button_y, button_width, button_height, "Yes (Y)", UIConstants.GREEN, game_state=game_state, font_scale=UIConstants.FONT_SCALE_MEDIUM,) #
        no_rect = (no_button_x, button_y, button_width, button_height) #
        _draw_button(frame, no_button_x, button_y, button_width, button_height, "No (N)", UIConstants.RED, game_state=game_state, font_scale=UIConstants.FONT_SCALE_MEDIUM,) #
        game_state.submenu_items = [(yes_rect, "confirm_quit_yes", "Confirm Quit"), (no_rect, "confirm_quit_no", "Cancel Quit"),] #
        game_state.menu_pos = (0, 0); game_state.menu_width = current_width; game_state.menu_height = current_height # Update effective menu size for click handling

    # --- Draw Effects ---
    # (Unchanged, assuming effects draw at absolute coordinates within the frame)
    if game_state.game_mode in ["fun", "retro"]:
        if hasattr(game_state, "active_explosions") and isinstance(game_state.active_explosions, list):
            for explosion in list(game_state.active_explosions):
                try:
                    if hasattr(explosion, "is_active") and explosion.is_active() and hasattr(explosion, "draw"): explosion.draw(frame) #
                except Exception as e: logger.error(f"Error drawing explosion: {e}") #

    # --- Draw Notifications & Achievement Popups ---
    # [MODIFY] Position notifications relative to current_height
    if game_state.current_state != CurrentGameState.GETTING_PLAYER_NAME: #
        notification_drawn = False
        ny_not = current_height - 30 # Bottom padding
        if game_state.notification_text and game_state.notification_timer > 0: #
            color = game_state.notification_color #
            (tw_not, th_not), _ = cv2.getTextSize(game_state.notification_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.FONT_THICKNESS,) #
            # Center horizontally based on current_width
            nx_not = (current_width - tw_not) // 2
            _draw_text_with_background(frame, game_state.notification_text, (nx_not, ny_not), UIConstants.FONT_SCALE_MEDIUM, color, UIConstants.BLACK, thickness=UIConstants.FONT_THICKNESS, alpha=0.7,) #
            notification_drawn = True

        if (game_state.achievement_notification and game_state.achievement_notification_timer > 0): #
            ach_text = game_state.achievement_notification #
            (tw_ach, th_ach), _ = cv2.getTextSize(ach_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.FONT_THICKNESS,) #
            ach_y_offset = 80 # Fixed offset from bottom? Or relative? Let's try relative from bottom.
            ny_ach = current_height - int(0.1 * current_height) # ~10% from bottom
            # Adjust if overlapping with regular notification
            if notification_drawn and ny_ach > ny_not - th_ach - 10: ny_ach = ny_not - th_ach - 10 #
            # Center horizontally based on current_width
            nx_ach = (current_width - tw_ach) // 2
            _draw_text_with_background(frame, ach_text, (nx_ach, ny_ach), UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.BLACK, thickness=UIConstants.FONT_THICKNESS, alpha=0.7,) #

    # --- Draw Visual Debug Overlay ---
    # (Unchanged, assuming _draw_debug_overlay works with absolute coordinates within the frame)
    if (game_state.current_state != CurrentGameState.GETTING_PLAYER_NAME and hasattr(game_state, "show_debug_overlay") and game_state.show_debug_overlay): #
        _draw_debug_overlay(frame, game_state) #

    # --- Draw General Debug Text ---
    # [MODIFY] Position debug text relative to current_height
    if game_state.current_state != CurrentGameState.GETTING_PLAYER_NAME and getattr(game_state, "debug_mode", False): #
        fps = getattr(game_state, "fps", 0) #
        state_text = str(game_state.current_state).split(".")[-1] #
        overlay_status = ("ON" if getattr(game_state, "show_debug_overlay", False) else "OFF") #
        tracked_count = len(getattr(game_state, "tracked_balls", [])) #
        drawing_active_text = ("Draw:ON" if getattr(game_state, "drawing", False) else "Draw:OFF") #
        edit_info = "" #
        if game_state.current_state == CurrentGameState.ZONE_EDITING: edit_info = f" | EditZone:{game_state.selected_zone_for_edit} Act:{game_state.zone_editing_action or '...'}" #
        elif game_state.current_state == CurrentGameState.CONFIRM_QUIT: prev_state_name = str(getattr(game_state, "previous_state_before_quit_confirm","N/A")).split(".")[-1]; edit_info = f" | PrevState:{prev_state_name}" #
        debug_text_parts = [f"FPS:{fps:.1f}", f"State:{state_text}", f"{drawing_active_text}", f"Overlay(b):{overlay_status}", f"Tracked:{tracked_count}",] #
        if edit_info: debug_text_parts.append(edit_info) #
        # Add resolution info to debug text
        debug_text_parts.append(f"Res:{game_state.current_resolution_key}")
        debug_text = " | ".join(debug_text_parts) #
        # Position bottom-left using current_height
        debug_y_pos = current_height - 10
        _draw_text_with_background(frame, debug_text, (10, debug_y_pos), UIConstants.FONT_SCALE_SMALL, UIConstants.YELLOW, UIConstants.BLACK, alpha=0.7,) #