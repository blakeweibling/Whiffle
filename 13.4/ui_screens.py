# ui_screens.py
import logging
import os
import time
from typing import TYPE_CHECKING, Any, Callable, Optional

import cv2
import numpy as np

# Import clean_exit from the new cleanup file
from cleanup_utils import clean_exit

# Local project imports
from constants import GameConstants, UIConstants, ResolutionConstants
from game_state_helpers import show_notification # Import show_notification

# Import Enum from new location
from game_types import CurrentGameState

# Use _draw_button from menu_utils
try:
    from menu_utils import _draw_button
except ImportError:
    logger.error("Failed to import _draw_button from menu_utils. Button drawing will fail.")
    # Ensure def is on a new, indented line
    def _draw_button(*args, **kwargs):
        pass # Indented under except


# Imports for Heatmap
try: from heatmap_utils import generate_heatmap
except ImportError: logger.error("Failed import generate_heatmap"); generate_heatmap = None
try: from data_logger import SessionData
except ImportError: SessionData = Any

# Import _draw_text_with_background
try:
    from ui_utils import _draw_text_with_background
except ImportError:
    logger.error("Failed to import _draw_text_with_background from ui_utils. Text drawing will fail.")
    # Ensure def is on a new, indented line
    def _draw_text_with_background(*args, **kwargs):
        pass # Indented under except


# Type hint for GameState using string literal
if TYPE_CHECKING:
    from game_state import GameState

logger = logging.getLogger(__name__)

# Cache for game over splash image
game_over_splash_cache = None


# --- Game Over Screen Drawing ---
def _draw_game_over_screen(frame: np.ndarray, game_state: "GameState") -> None:
    """Draws the game over screen and its interactive buttons."""
    global game_over_splash_cache
    current_width, current_height = game_state.get_current_resolution_dimensions()

    # Splash image handling (no changes needed here)
    if isinstance(game_over_splash_cache, np.ndarray):
         if (game_over_splash_cache.shape[1] != current_width or game_over_splash_cache.shape[0] != current_height):
              logger.warning("Game over cache dimensions mismatch. Resizing.")
              try: game_over_splash_cache = cv2.resize(game_over_splash_cache, (current_width, current_height))
              except Exception as e: logger.error(f"Failed resize game over cache: {e}"); game_over_splash_cache = "fallback"
    if game_over_splash_cache is None:
        splash_path = GameConstants.GAME_OVER_SPLASH_FILE
        if os.path.exists(splash_path):
            try:
                splash = cv2.imread(splash_path)
                if splash is not None and splash.size > 0: game_over_splash_cache = cv2.resize(splash, (current_width, current_height))
                else: logger.error(f"Loaded game_over.png empty."); game_over_splash_cache = "fallback"
            except Exception as e: logger.error(f"Error loading/resizing game_over.png: {e}"); game_over_splash_cache = "fallback"
        else: logger.warning(f"Game over splash file not found: {splash_path}"); game_over_splash_cache = "fallback"

    # Draw background (splash or fallback text)
    if isinstance(game_over_splash_cache, np.ndarray): frame[:, :] = game_over_splash_cache.copy()
    else:
        cv2.rectangle(frame, (0, 0), (current_width, current_height), (0, 0, 0), -1)
        win_condition = getattr(game_state, "win_condition_met", False)
        title_text = "You Win!" if win_condition else "Game Over!"
        title_color = UIConstants.GREEN if win_condition else UIConstants.RED
        (tw, th), _ = cv2.getTextSize(title_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_XLARGE, UIConstants.FONT_THICKNESS + 1,)
        title_x = (current_width - tw) // 2
        title_y = current_height // 3
        cv2.putText(frame, title_text, (title_x, title_y), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_XLARGE, title_color, UIConstants.FONT_THICKNESS + 1,)
        score = getattr(game_state, "score", 0)
        display_score = score * 2 if getattr(game_state, "special_hole_hit_this_session", False) else score
        doubled_indicator = " (x2 Bonus!)" if getattr(game_state, "special_hole_hit_this_session", False) else ""
        score_text = f"Final Score: {display_score}{doubled_indicator}"
        (sw, sh), _ = cv2.getTextSize(score_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.FONT_THICKNESS,); score_x = (current_width - sw) // 2
        score_y = title_y + th + 30
        cv2.putText(frame, score_text, (score_x, score_y), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.WHITE, UIConstants.FONT_THICKNESS,)

    # Draw buttons
    button_width, button_height, button_spacing = (200, 50, 60,)
    button_y = current_height - int(0.1 * current_height) - button_height
    total_button_width = button_width * 2 + button_spacing
    start_x = (current_width - total_button_width) // 2
    new_game_x = start_x
    new_game_rect = (new_game_x, button_y, button_width, button_height)
    _draw_button(frame, new_game_x, button_y, button_width, button_height, "New Game (N)", UIConstants.CV2_BLUE, game_state=game_state,)

    leaderboard_x = new_game_x + button_width + button_spacing
    leaderboard_rect = (leaderboard_x, button_y, button_width, button_height)
    _draw_button(frame, leaderboard_x, button_y, button_width, button_height, "Leaderboard (L)", UIConstants.CV2_BLUE, game_state=game_state,)

    # Store rects for direct click checking in mouse_callback
    if hasattr(game_state, "game_over_buttons"):
         game_state.game_over_buttons = {
             "new_game": new_game_rect,
             "leaderboard": leaderboard_rect
         }
    else:
         logger.warning("game_state missing 'game_over_buttons' attribute.")

# --- Modal Dismissal Callback ---
# (Unchanged)
def _modal_mouse_callback(event: int, x: int, y: int, flags: int, param: dict):
    if event == cv2.EVENT_LBUTTONDOWN: param["clicked"] = True


# --- Modal Splash Screen ---
# (Modified to fix SyntaxError)
def display_modal_splash(
    game_state: "GameState",
    main_mouse_callback: Callable,
    main_callback_param: Any,
) -> None:
    logger.info("Displaying modal splash screen...")
    splash_path = GameConstants.SPLASH_SCREEN_FILE
    splash_image = None
    target_width, target_height = game_state.get_current_resolution_dimensions()
    try:
        if os.path.exists(splash_path):
             splash = cv2.imread(splash_path)
             if splash is not None and splash.size > 0:
                  splash_image = cv2.resize(splash, (target_width, target_height), interpolation=cv2.INTER_AREA,)
             else:
                  logger.error(f"Loaded splash image '{splash_path}' is empty or invalid.")
                  splash_image = None # Ensure it's None if loading failed
        else:
             logger.warning(f"Splash file not found: {splash_path}")
             splash_image = None # Ensure it's None if file doesn't exist

        if splash_image is None: logger.error(f"Failed load/resize splash '{splash_path}'.")
    except Exception as e:
        logger.error(f"Error processing splash '{splash_path}': {e}")
        splash_image = None # Ensure it's None on error

    display_frame = np.zeros((target_height, target_width, 3), dtype=np.uint8)
    display_frame[:, :] = UIConstants.BLACK

    # --- START FIX: Corrected if/else block ---
    if splash_image is not None:
        display_frame = splash_image.copy()
        message = "Click or press any key to continue..."
        text_color = UIConstants.YELLOW
    else:
        # This block now correctly follows the 'if splash_image is not None:'
        message = "Splash Image Unavailable. Click or press any key..."
        text_color = UIConstants.RED
        cv2.putText(display_frame, "Error: Splash Not Found", (50, target_height // 2), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.RED, 2,)
    # --- END FIX ---

    (tw, th), _ = cv2.getTextSize(message, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.FONT_THICKNESS,)
    cv2.putText(display_frame, message, ((target_width - tw) // 2, target_height - 50), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, text_color, UIConstants.FONT_THICKNESS,)

    dismiss_flag = {"clicked": False}
    cv2.setMouseCallback(UIConstants.WINDOW_NAME, _modal_mouse_callback, dismiss_flag)
    while True:
        try:
            if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1: logger.warning("Modal splash window closed."); break
            cv2.imshow(UIConstants.WINDOW_NAME, display_frame)
            key = cv2.waitKey(30)
            if key != -1 or dismiss_flag["clicked"]: logger.info("Dismissing modal splash."); break
        except cv2.error as e: logger.error(f"OpenCV error during modal splash loop: {e}"); break
        except Exception as e: logger.exception(f"Unexpected error during modal splash loop: {e}"); break
    try: cv2.setMouseCallback(UIConstants.WINDOW_NAME, main_mouse_callback, main_callback_param); logger.info("Restored main mouse callback.")
    except Exception as e: logger.exception(f"Error restoring mouse callback: {e}")


# --- Display Heatmap Modally ---
# (Unchanged from previous correction)
def display_heatmap_modal(game_state: "GameState",
                          main_mouse_callback: Callable,
                          main_callback_param: Any) -> None:
    logger.info("Attempting to display heatmap modal...")
    if not generate_heatmap: logger.error("generate_heatmap unavailable."); show_notification(game_state, "Error: Heatmap unavailable", is_error=True, duration=3.0); return
    if not hasattr(game_state, "data_logger") or not game_state.data_logger: logger.warning("No data logger for heatmap."); show_notification(game_state, "No session data for heatmap", is_error=True, duration=3.0); return
    current_session = game_state.data_logger.get_current_session_data()
    if not current_session: logger.warning("No active session data for heatmap."); show_notification(game_state, "No active session data for heatmap", is_error=True, duration=3.0); return
    current_width, current_height = game_state.get_current_resolution_dimensions()
    try: heatmap_image = generate_heatmap(current_session, width=current_width, height=current_height,)
    except Exception as e: logger.exception(f"Error generating heatmap: {e}"); show_notification(game_state, "Error generating heatmap", is_error=True, duration=3.0); return
    if heatmap_image is None: logger.info("Heatmap generation returned None."); show_notification(game_state, "No position data for heatmap", duration=3.0); return
    dismiss_flag = {"clicked": False}
    cv2.setMouseCallback(UIConstants.WINDOW_NAME, _modal_mouse_callback, dismiss_flag)
    if hasattr(game_state, "show_heatmap"): game_state.show_heatmap = True
    logger.info("Entering heatmap display loop...")
    while True:
        try:
            if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1: logger.warning("Heatmap display window closed."); break
            background_frame = None; cap = getattr(game_state, "cap", None)
            static_frame = getattr(game_state, "static_frame", None)
            if (getattr(game_state, "camera_available", False) and cap and cap.isOpened()):
                ret, frame_read = cap.read()
                if ret and frame_read is not None: background_frame = cv2.resize(frame_read, (current_width, current_height))
                else: logger.error("Failed camera frame during heatmap.")
            elif static_frame is not None:
                 if static_frame.shape[1] != current_width or static_frame.shape[0] != current_height: background_frame = cv2.resize(static_frame, (current_width, current_height))
                 else: background_frame = static_frame.copy()
            if background_frame is None: background_frame = np.zeros((current_height, current_width, 3), dtype=np.uint8,)
            heatmap_alpha = 0.2
            blended_frame = cv2.addWeighted(heatmap_image, heatmap_alpha, background_frame, 1.0 - heatmap_alpha, 0); display_frame = blended_frame
            message = "Heatmap View - Click or press ESC/Any Key to Close"
            text_color = UIConstants.WHITE; bg_color = UIConstants.BLACK
            (tw, th), _ = cv2.getTextSize(message, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.FONT_THICKNESS,)
            text_pos = ((current_width - tw) // 2, current_height - 30,)
            try: _draw_text_with_background(display_frame, message, text_pos, UIConstants.FONT_SCALE_MEDIUM, text_color, bg_color, thickness=UIConstants.FONT_THICKNESS, alpha=0.7,)
            except Exception as e: logger.exception(f"Error drawing text on heatmap overlay: {e}"); cv2.putText(display_frame, message, text_pos, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, text_color, UIConstants.FONT_THICKNESS,)
            cv2.imshow(UIConstants.WINDOW_NAME, display_frame)
            key = cv2.waitKey(30)
            if key == 27 or key != -1 or dismiss_flag["clicked"]: logger.info("Dismissing heatmap display."); break
        except cv2.error as e: logger.error(f"OpenCV error during heatmap display loop: {e}"); break
        except Exception as e: logger.exception(f"Unexpected error during heatmap display loop: {e}"); break
    try: cv2.setMouseCallback(UIConstants.WINDOW_NAME, main_mouse_callback, main_callback_param); logger.info("Restored main mouse callback.")
    except Exception as e: logger.exception(f"Error restoring mouse callback: {e}")
    if hasattr(game_state, "show_heatmap"): game_state.show_heatmap = False


# --- Initial Splash Screen ---
# (Unchanged from previous correction)
def show_splash_screen(supabase_url: str,
                       supabase_key: str) -> Optional["GameState"]:
    logger.info("Showing splash screen...")
    splash_path = GameConstants.SPLASH_SCREEN_FILE
    splash = cv2.imread(splash_path)
    initial_width = ResolutionConstants.RESOLUTIONS[ResolutionConstants.DEFAULT_RESOLUTION][0]
    initial_height = ResolutionConstants.RESOLUTIONS[ResolutionConstants.DEFAULT_RESOLUTION][1]
    window_created = False
    try: cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL); cv2.resizeWindow(UIConstants.WINDOW_NAME, initial_width, initial_height); window_created = True
    except cv2.error as e: logger.error(f"Failed create/resize window: {e}"); return None

    if splash is None:
        logger.error(f"Failed load {splash_path}.")
        splash = np.zeros((initial_height, initial_width, 3), dtype=np.uint8)
        error_text = f"Error: {os.path.basename(splash_path)} not found!"
        (tw_err, th_err), _ = cv2.getTextSize(error_text, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
        text_x = (initial_width - tw_err) // 2
        text_y = initial_height // 2
        cv2.putText(splash, error_text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 1, UIConstants.RED, 2,)
        cv2.imshow(UIConstants.WINDOW_NAME, splash)
        cv2.waitKey(3000)
        try: cv2.destroyWindow(UIConstants.WINDOW_NAME)
        except: pass
        return None
    try:
        splash = cv2.resize(splash, (initial_width, initial_height))
    except cv2.error as e:
        logger.error(f"Failed resize splash: {e}.")
        splash = np.zeros((initial_height, initial_width, 3), dtype=np.uint8)
        cv2.putText(splash, "Error resizing splash", (50, initial_height // 2), cv2.FONT_HERSHEY_SIMPLEX, 1, UIConstants.RED, 2,)
        cv2.imshow(UIConstants.WINDOW_NAME, splash)
        cv2.waitKey(3000)
        try: cv2.destroyWindow(UIConstants.WINDOW_NAME)
        except: pass
        return None

    cv2.putText(splash, "Loading...", (50, initial_height - 50), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.YELLOW, UIConstants.FONT_THICKNESS,)
    cv2.imshow(UIConstants.WINDOW_NAME, splash); cv2.waitKey(1)
    game_state: Optional["GameState"] = None; first_frame: Optional[np.ndarray] = None
    from game_state import GameState
    try:
        logger.info("Initializing GameState...")
        game_state = GameState(supabase_url, supabase_key)
        current_width, current_height = game_state.get_current_resolution_dimensions()
        if not game_state.camera_available:
            if game_state.static_frame is None: raise RuntimeError("No Camera or Static Frame source available.")
            if game_state.static_frame.shape[1] != current_width or game_state.static_frame.shape[0] != current_height: first_frame = cv2.resize(game_state.static_frame, (current_width, current_height))
            else: first_frame = game_state.static_frame.copy()
        else:
            if game_state.cap is None or not game_state.cap.isOpened(): raise RuntimeError("Camera requested but not available.")
            ret, frame_read = game_state.cap.read()
            if not ret or frame_read is None: raise RuntimeError("Failed initial camera frame capture.")
            if frame_read.shape[1] != current_width or frame_read.shape[0] != current_height: first_frame = cv2.resize(frame_read, (current_width, current_height))
            else: first_frame = frame_read
    except Exception as e:
        logger.exception(f"Critical error during GameState init or first frame capture: {e}"); cv2.putText(splash, f"Initialization Error", (50, initial_height // 2 - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, UIConstants.RED, 1,); cv2.imshow(UIConstants.WINDOW_NAME, splash); cv2.waitKey(5000)
        cap = getattr(game_state, "cap", None) if game_state else None
        music = getattr(game_state, "background_music", None) if game_state else None; music_on = getattr(game_state, "background_music_on", False) if game_state else False
        clean_exit(cap, music, music_on, game_state); return None
    if first_frame is None: logger.error("First frame None after init."); clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state,); return None
    start_time = time.time(); logger.info("Starting splash fade loop.")
    splash_for_fade = cv2.resize(splash, (first_frame.shape[1], first_frame.shape[0]))
    while (time.time() - start_time < GameConstants.SPLASH_DURATION + GameConstants.FADE_DURATION):
        try:
            if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1: logger.warning("Splash window closed."); clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state,); return None
        except cv2.error: logger.warning("Window check failed."); clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state,); return None
        elapsed = time.time() - start_time; display_frame = np.zeros_like(first_frame)
        try:
            if elapsed < GameConstants.SPLASH_DURATION: display_frame = splash_for_fade.copy(); cv2.putText(display_frame, "Ready...", (50, first_frame.shape[0] - 50), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.YELLOW, UIConstants.FONT_THICKNESS,)
            elif elapsed < GameConstants.SPLASH_DURATION + GameConstants.FADE_DURATION: fade_duration = GameConstants.FADE_DURATION; alpha = (max(0.0, 1.0 - (elapsed - GameConstants.SPLASH_DURATION) / fade_duration,) if fade_duration > 0 else 0.0); display_frame = cv2.addWeighted(splash_for_fade, alpha, first_frame, 1.0 - alpha, 0)
            else: display_frame = first_frame.copy()
            cv2.imshow(UIConstants.WINDOW_NAME, display_frame)
        except cv2.error as e:
            logger.error(f"OpenCV error during splash fade display: {e}")
            try:
                cv2.imshow(UIConstants.WINDOW_NAME, first_frame)
            except:
                pass
        except Exception as e:
            logger.exception(f"Unexpected error during splash fade loop: {e}")
            try:
                cv2.imshow(UIConstants.WINDOW_NAME, first_frame)
            except:
                pass
        key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY) & 0xFF
        if key == ord("q") or key == 27: logger.info("Splash skipped."); clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state,); return None
    logger.info("Initial splash screen finished.")
    try:
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 1: cv2.imshow(UIConstants.WINDOW_NAME, first_frame); cv2.waitKey(1)
    except cv2.error: logger.warning("Could not display final frame after splash.")
    return game_state

# --- Add _draw_player_name_input function ---
# (Copied from ui.py correction)
def _draw_player_name_input(frame: np.ndarray, game_state: "GameState"):
    """Draws the pop-up screen for initial player name input."""
    current_width, current_height = game_state.get_current_resolution_dimensions()
    overlay = frame.copy(); cv2.rectangle(overlay, (0, 0), (current_width, current_height), UIConstants.BLACK, -1); alpha = 0.7; cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    popup_width, popup_height = 700, 200 # Fixed size popup
    popup_x = (current_width - popup_width) // 2
    popup_y = (current_height - popup_height) // 2
    cv2.rectangle(frame, (popup_x, popup_y), (popup_x + popup_width, popup_y + popup_height), UIConstants.GREY_BG, -1,)
    cv2.rectangle(frame, (popup_x, popup_y), (popup_x + popup_width, popup_y + popup_height), UIConstants.WHITE, 1,)
    prompt_text = "Enter Player Name:"; prompt_pos = (popup_x + 20, popup_y + 40)
    cv2.putText(frame, prompt_text, prompt_pos, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, UIConstants.FONT_THICKNESS, cv2.LINE_AA,)
    input_bg_x, input_bg_y = popup_x + 20, popup_y + 70; input_bg_w, input_bg_h = popup_width - 40, 40
    cv2.rectangle(frame, (input_bg_x, input_bg_y), (input_bg_x + input_bg_w, input_bg_y + input_bg_h), (50, 50, 50), -1,)
    show_cursor = int(time.time() * 2) % 2 == 0; cursor = "_" if show_cursor else " "; current_input = getattr(game_state, "current_player_name_input", ""); display_name = current_input + cursor
    name_pos = (input_bg_x + 10, input_bg_y + 30); cv2.putText(frame, display_name, name_pos, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.YELLOW, UIConstants.FONT_THICKNESS + 1, cv2.LINE_AA,)
    instructions_text = "Enter=Confirm, Esc=Default ('Player 1'), Backspace=Delete"; instr_pos = (popup_x + 20, popup_y + popup_height - 30)
    cv2.putText(frame, instructions_text, instr_pos, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, UIConstants.WHITE, UIConstants.FONT_THICKNESS, cv2.LINE_AA,)