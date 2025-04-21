"""
UI rendering functions for the Whiffle Tracker project.
Manages drawing of UI elements, balls, splash screen, game over screen, and debug overlay.
"""

import cv2
import numpy as np
import logging
import time
import os # Added for checking game_over.png path
from typing import List, Tuple, Any, Optional

# Added numpy import
import numpy as np
from constants import UIConstants, GameConstants # Added GameConstants
from scoring import draw_scoring_zones
from menu import draw_menu, draw_menu_window # draw_menu_window is used
from menu_utils import _draw_button, show_splash_on_click # Import _draw_button
from utils import clean_exit
# Import both GameState and CurrentGameState
from game_state import GameState, CurrentGameState # Added GameState import

logger = logging.getLogger(__name__)

# Constants for ball visualization (Updated for Feature 1)
BALL_COLORS = {
    "white": UIConstants.WHITE, # Use constants
    "red": UIConstants.RED,     # Use constants
    "half": (255, 0, 255)       # Magenta for half red/half white (Keep or add to UIConstants)
}
BALL_RADIUS_FACTOR = 1.0 # Adjust if detected radius needs scaling for visualization
TRAIL_LENGTH = GameConstants.BALL_TRAIL_LENGTH # Use constant
TRAIL_THICKNESS = 2 # Thickness of the trail lines
TRAIL_BASE_COLOR = (100, 100, 100) # Base color for trails (Gray)
TRAIL_FADE = True # Whether to fade the trail

# Cache for game over splash image
game_over_splash_cache = None
# <<< Added cache for menu splash image >>>
menu_splash_cache = None


# Helper Function: Draw text with background
def _draw_text_with_background(
    frame: np.ndarray,
    text: str,
    pos: Tuple[int, int],
    font_scale: float,
    text_color: Tuple[int, int, int],
    bg_color: Tuple[int, int, int],
    thickness: int = 1,
    padding: int = 3,
    font: int = cv2.FONT_HERSHEY_SIMPLEX,
    alpha: float = 0.6 # Opacity for background
    ) -> None:
    """Draws text with a semi-transparent background rectangle."""
    (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = pos
    # Rectangle coordinates (top-left and bottom-right)
    rect_x1 = x - padding
    rect_y1 = y - text_height - padding - baseline // 2 # Adjust y based on baseline
    rect_x2 = x + text_width + padding
    rect_y2 = y + padding - baseline // 2

    # Ensure coordinates are within frame bounds
    rect_x1 = max(0, rect_x1)
    rect_y1 = max(0, rect_y1)
    rect_x2 = min(frame.shape[1], rect_x2)
    rect_y2 = min(frame.shape[0], rect_y2)

    # Extract ROI and create overlay
    if rect_x1 < rect_x2 and rect_y1 < rect_y2: # Check if rectangle has valid size
        sub_img = frame[rect_y1:rect_y2, rect_x1:rect_x2]
        # Ensure sub_img is not empty before proceeding
        if sub_img.size == 0:
            logger.warning(f"Empty sub_img for text background at {pos}. Text: '{text}'")
            # Just draw text without background if ROI is invalid
            text_y_pos = y - baseline // 2
            cv2.putText(frame, text, (x, text_y_pos), font, font_scale, text_color, thickness, cv2.LINE_AA)
            return

        bg_rect = np.zeros(sub_img.shape, dtype=np.uint8)
        bg_rect[:] = bg_color

        # Blend background
        try:
             res = cv2.addWeighted(sub_img, 1.0 - alpha, bg_rect, alpha, 0)
             frame[rect_y1:rect_y2, rect_x1:rect_x2] = res
        except cv2.error as e:
             logger.error(f"CV2 error in addWeighted for text '{text}': {e}. ROI shape: {sub_img.shape}, BG shape: {bg_rect.shape}")
             # Fallback: Draw solid background or just text? Draw just text for now.
             pass # Text will be drawn below

        # Draw text on top
        text_y_pos = y - baseline // 2 # Adjust text Y position based on baseline
        cv2.putText(frame, text, (x, text_y_pos), font, font_scale, text_color, thickness, cv2.LINE_AA)


def draw_balls(frame: np.ndarray, game_state: GameState) -> None:
    """
    Draw tracked balls and their trails on the frame (disabled).
    Args:
        frame (np.ndarray): The frame to draw on.
        game_state (GameState): The current game state containing tracked balls and trails.
    """
    # Clean up trails for balls no longer tracked, but don't draw anything
    if hasattr(game_state, 'ball_trails') and game_state.ball_trails:
        for ball_id, trail in list(game_state.ball_trails.items()):
            # Check if the ball ID still exists in tracked_balls
            if not any(hasattr(b, '__len__') and len(b) > 3 and b[3] == ball_id for b in game_state.tracked_balls):
                if ball_id in game_state.ball_trails:
                    del game_state.ball_trails[ball_id]
                continue  # Skip drawing trail for untracked ball

    # Ball and trail drawing is disabled; no rendering occurs
    logger.debug("Ball drawing effects are disabled.")


# Feature 3 (Revised): Draw Game Over Screen with Image
def _draw_game_over_screen(frame: np.ndarray, game_state: GameState) -> None: # Use GameState type hint
    """Draws the Game Over screen using game_over.png and adds buttons."""
    global game_over_splash_cache
    if game_over_splash_cache is None:
        splash_path = GameConstants.GAME_OVER_SPLASH_FILE
        if os.path.exists(splash_path):
            try:
                splash = cv2.imread(splash_path)
                if splash is not None:
                    splash_resized = cv2.resize(splash, (frame.shape[1], frame.shape[0]))
                    game_over_splash_cache = splash_resized
                    logger.info(f"Loaded and cached '{splash_path}'")
                else:
                    logger.error(f"Failed to load '{splash_path}'. Using fallback.")
                    game_over_splash_cache = "fallback"
            except Exception as e:
                logger.error(f"Error loading or resizing '{splash_path}': {e}. Using fallback.")
                game_over_splash_cache = "fallback"
        else:
            logger.warning(f"'{splash_path}' not found. Using fallback.")
            game_over_splash_cache = "fallback"

    if game_over_splash_cache is not None and game_over_splash_cache != "fallback":
        frame[:, :] = game_over_splash_cache
    else: # Fallback drawing
        cv2.rectangle(frame, (0, 0), (frame.shape[1], frame.shape[0]), (0, 0, 0), -1)
        title_text = "You Win!" if game_state.win_condition_met else "Game Over!"
        title_color = UIConstants.GREEN if game_state.win_condition_met else UIConstants.RED
        (text_width, text_height), _ = cv2.getTextSize(title_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_XLARGE, UIConstants.FONT_THICKNESS + 1)
        title_x = (frame.shape[1] - text_width) // 2; title_y = frame.shape[0] // 3
        cv2.putText(frame, title_text, (title_x, title_y), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_XLARGE, title_color, UIConstants.FONT_THICKNESS + 1)
        score_text = f"Final Score: {game_state.score}"
        (score_width, score_height), _ = cv2.getTextSize(score_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.FONT_THICKNESS)
        score_x = (frame.shape[1] - score_width) // 2; score_y = title_y + text_height + 30
        cv2.putText(frame, score_text, (score_x, score_y), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.WHITE, UIConstants.FONT_THICKNESS)

    # Draw Buttons (Common)
    button_width, button_height, button_y, button_spacing = 200, 50, frame.shape[0] - 90, 60
    total_button_width = button_width * 2 + button_spacing
    start_x = (frame.shape[1] - total_button_width) // 2
    new_game_x = start_x
    new_game_rect = (new_game_x, button_y, button_width, button_height)
    _draw_button(frame, new_game_x, button_y, button_width, button_height, "New Game", UIConstants.GREEN, font_scale=UIConstants.FONT_SCALE_MEDIUM)
    action_new_game = "new_game_from_gameover"
    leaderboard_x = new_game_x + button_width + button_spacing
    leaderboard_rect = (leaderboard_x, button_y, button_width, button_height)
    _draw_button(frame, leaderboard_x, button_y, button_width, button_height, "Leaderboard", UIConstants.YELLOW, font_scale=UIConstants.FONT_SCALE_MEDIUM)
    action_leaderboard = "show_leaderboard_from_gameover"
    game_state.submenu_items = [(new_game_rect, action_new_game, "New Game"), (leaderboard_rect, action_leaderboard, "Leaderboard")]
    game_state.menu_pos, game_state.menu_width, game_state.menu_height = (0, 0), frame.shape[1], frame.shape[0]


# Feature 5: Draw Visual Debug Overlay
def _draw_debug_overlay(frame: np.ndarray, game_state: GameState) -> None: # Use GameState type hint
    """Draws debugging information directly onto the frame."""
    if hasattr(game_state, 'tracked_balls'):
        for ball in game_state.tracked_balls:
            try:
                x, y, radius, ball_id, age, ball_type = ball
                center_x, center_y, int_radius = int(x), int(y), int(radius)
                pt1 = (center_x - int_radius, center_y - int_radius)
                pt2 = (center_x + int_radius, center_y + int_radius)
                cv2.rectangle(frame, pt1, pt2, UIConstants.YELLOW, 1) # Bounding box
                label = f"ID:{ball_id} T:{ball_type}"
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, 1)
                text_x, text_y = pt1[0], pt1[1] - 5 # Position text above box
                # Draw background for text
                cv2.rectangle(frame, (text_x, text_y - h - 2), (text_x + w, text_y + 2), (0,0,0), -1) # Text bg
                cv2.putText(frame, label, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, UIConstants.YELLOW, 1)
            except (IndexError, ValueError, TypeError): # Catch potential unpacking errors
                 logger.warning(f"Malformed ball data for debug overlay: {ball}")
            except Exception as e: logger.error(f"Error drawing debug overlay for ball {ball}: {e}")

def draw_ui(frame: np.ndarray, game_state: GameState) -> None: # Use GameState type hint
    """
    Draw the user interface elements on the frame, handling different game states.
    """
    # --- Handle SHOWING_SPLASH state first ---
    if game_state.current_state == CurrentGameState.SHOWING_SPLASH:
        global menu_splash_cache
        if menu_splash_cache is None: # Load splash on demand
            splash_path = GameConstants.SPLASH_SCREEN_FILE
            if os.path.exists(splash_path):
                try:
                    splash = cv2.imread(splash_path)
                    if splash is not None:
                        splash_resized = cv2.resize(splash, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
                        menu_splash_cache = splash_resized
                        logger.info(f"Loaded and cached '{splash_path}' for menu splash.")
                    else:
                        logger.error(f"Failed to load '{splash_path}'. Using fallback for menu splash.")
                        menu_splash_cache = "fallback"
                except Exception as e:
                    logger.error(f"Error loading or resizing '{splash_path}' for menu splash: {e}. Using fallback.")
                    menu_splash_cache = "fallback"
            else:
                logger.warning(f"'{splash_path}' not found for menu splash. Using fallback.")
                menu_splash_cache = "fallback"

        # Display the cached splash or fallback
        if menu_splash_cache is not None and menu_splash_cache != "fallback":
            frame[:, :] = menu_splash_cache.copy() # Display the splash over the whole frame
            # Add instruction text
            instruction_text = "Click or press any key to return"
            (tw, th), _ = cv2.getTextSize(instruction_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.FONT_THICKNESS)
            nx = (UIConstants.WINDOW_WIDTH - tw) // 2
            ny = UIConstants.WINDOW_HEIGHT - 30
            _draw_text_with_background(frame, instruction_text, (nx, ny), UIConstants.FONT_SCALE_MEDIUM, UIConstants.YELLOW, UIConstants.BLACK, thickness=UIConstants.FONT_THICKNESS, alpha=0.7)

        else: # Fallback drawing if splash failed to load
            cv2.rectangle(frame, (0, 0), (frame.shape[1], frame.shape[0]), (30, 30, 30), -1)
            error_text = "Splash Image Not Found"
            (tw, th), _ = cv2.getTextSize(error_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.FONT_THICKNESS)
            cv2.putText(frame, error_text, ((frame.shape[1] - tw) // 2, frame.shape[0] // 2), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.RED, UIConstants.FONT_THICKNESS)
            instruction_text = "Click or press any key to return"
            (tw_i, th_i), _ = cv2.getTextSize(instruction_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.FONT_THICKNESS)
            cv2.putText(frame, instruction_text, ((frame.shape[1] - tw_i) // 2, frame.shape[0] // 2 + th + 20), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.YELLOW, UIConstants.FONT_THICKNESS)
        # Return early as nothing else should be drawn in this state
        return

    # --- Draw elements common to PLAYING and MENU states ---
    if game_state.current_state != CurrentGameState.GAME_OVER:
        # Use helper function for text with background
        player_name = game_state.get_current_player().name
        score_text = f"Player: {player_name} Score: {game_state.score}"
        _draw_text_with_background(frame, score_text, (10, 30), UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, UIConstants.GREY_BG, thickness=UIConstants.FONT_THICKNESS)

        high_score_text = f"High Score: {game_state.high_score}"
        # Calculate X position for High Score to align right (approx)
        (tw, th), _ = cv2.getTextSize(high_score_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.FONT_THICKNESS)
        high_score_x = UIConstants.WINDOW_WIDTH - tw - 10 - 3 # Adjust 10 for space, 3 for padding
        _draw_text_with_background(frame, high_score_text, (high_score_x, 30), UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, UIConstants.GREY_BG, thickness=UIConstants.FONT_THICKNESS)

        mode_text = f"Mode: {game_state.game_mode.capitalize()}"
        _draw_text_with_background(frame, mode_text, (10, 60), UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, UIConstants.GREY_BG, thickness=UIConstants.FONT_THICKNESS)

        # Timer text (no background needed, usually stands out)
        if game_state.game_mode == "timed" and game_state.game_timer is not None and game_state.current_state == CurrentGameState.PLAYING:
            timer_text = f"Time Left: {int(game_state.game_timer)}"
            time_color = UIConstants.RED if game_state.game_timer < 10 else UIConstants.YELLOW
            # Add background here too if needed, using the helper
            (tw_t, th_t), _ = cv2.getTextSize(timer_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.FONT_THICKNESS)
            timer_x = (UIConstants.WINDOW_WIDTH - tw_t) // 2 # Center timer text
            _draw_text_with_background(frame, timer_text, (timer_x, 30), UIConstants.FONT_SCALE_MEDIUM, time_color, UIConstants.BLACK, thickness=UIConstants.FONT_THICKNESS, alpha=0.7)

        if game_state.current_state == CurrentGameState.PLAYING:
             draw_scoring_zones(frame, game_state.scoring_zones, game_state.special_hole)
             if game_state.drawing and game_state.temp_zone:
                 x1, y1, w, h = game_state.temp_zone
                 cv2.rectangle(frame, (x1, y1), (x1 + w, y1 + h), UIConstants.YELLOW, 2)
             # Draw menu button using its constants (position updated in constants.txt)
             draw_menu(frame, game_state)

             if game_state.achievement_notification:
                 notif_text = game_state.achievement_notification
                 (tw, th), _ = cv2.getTextSize(notif_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.FONT_THICKNESS)
                 nx, ny = (UIConstants.WINDOW_WIDTH - tw) // 2, UIConstants.WINDOW_HEIGHT - 50
                 # Use helper for achievement notification background
                 _draw_text_with_background(frame, notif_text, (nx, ny), UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.BLACK, thickness=UIConstants.FONT_THICKNESS, alpha=0.7)


        if game_state.current_state == CurrentGameState.MENU:
             mx, my = (frame.shape[1] - game_state.menu_width) // 2, (frame.shape[0] - game_state.menu_height) // 2
             game_state.menu_pos = (mx, my)
             draw_menu_window(frame, game_state)

        if game_state.notification_text and game_state.notification_timer > 0:
             color = game_state.notification_color
             (tw, th), _ = cv2.getTextSize(game_state.notification_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.FONT_THICKNESS)
             nx, ny = (UIConstants.WINDOW_WIDTH - tw) // 2, UIConstants.WINDOW_HEIGHT - 20
             # Use helper for notification background too
             _draw_text_with_background(frame, game_state.notification_text, (nx, ny), UIConstants.FONT_SCALE_MEDIUM, color, UIConstants.BLACK, thickness=UIConstants.FONT_THICKNESS, alpha=0.7)


    # --- Draw elements specific to GAME_OVER state ---
    elif game_state.current_state == CurrentGameState.GAME_OVER:
         _draw_game_over_screen(frame, game_state)

    # --- Feature 5: Draw Visual Debug Overlay (if enabled) ---
    # Ensure it's not drawn over the menu splash
    if game_state.current_state != CurrentGameState.SHOWING_SPLASH and hasattr(game_state, 'show_debug_overlay') and game_state.show_debug_overlay:
        _draw_debug_overlay(frame, game_state)

    # --- Draw elements always on top (except over menu splash) ---
    if game_state.current_state != CurrentGameState.SHOWING_SPLASH and game_state.debug_mode:
        fps = game_state.fps if hasattr(game_state, 'fps') else 0
        state_text = str(game_state.current_state).split('.')[-1]
        overlay_status = "ON" if getattr(game_state, 'show_debug_overlay', False) else "OFF"
        debug_text = f"FPS:{fps:.1f}|State:{state_text}|Overlay(b):{overlay_status}|Tracked:{len(game_state.tracked_balls)}"
        # Use helper for debug text background
        _draw_text_with_background(frame, debug_text, (10, UIConstants.WINDOW_HEIGHT - 10), UIConstants.FONT_SCALE_SMALL, UIConstants.YELLOW, UIConstants.BLACK, alpha=0.7)


# Use GameState type hint for return value
def show_splash_screen(supabase_url: str, supabase_key: str) -> Optional[GameState]:
    """Displays the splash screen and handles initial setup."""
    logger.info("Showing splash screen...")
    splash_path = GameConstants.SPLASH_SCREEN_FILE
    splash = cv2.imread(splash_path)
    if splash is None:
        logger.error(f"Failed to load {splash_path}. Exiting.")
        splash = np.zeros((UIConstants.WINDOW_HEIGHT, UIConstants.WINDOW_WIDTH, 3), dtype=np.uint8)
        cv2.putText(splash, f"Error: {splash_path} not found!", (50, UIConstants.WINDOW_HEIGHT // 2), cv2.FONT_HERSHEY_SIMPLEX, 1, UIConstants.RED, 2)
        try: cv2.imshow(UIConstants.WINDOW_NAME, splash); cv2.waitKey(3000)
        except cv2.error as e: logger.error(f"OpenCV error: {e}")
        return None

    splash = cv2.resize(splash, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
    try: cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL)
    except cv2.error as e: logger.error(f"Failed window create: {e}"); return None

    cv2.putText(splash, "Loading...", (50, UIConstants.WINDOW_HEIGHT - 50), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.YELLOW, UIConstants.FONT_THICKNESS)
    cv2.imshow(UIConstants.WINDOW_NAME, splash); cv2.waitKey(1)

    try: # Initialize GameState
        logger.info("Initializing GameState...")
        game_state = GameState(supabase_url, supabase_key)
        logger.info("GameState initialized successfully.")
        if not game_state.camera_available:
             if game_state.static_frame is None: logger.error("Static frame None. Exiting."); return None
             first_frame = game_state.static_frame.copy(); logger.info("Using static frame.")
        else:
            ret, first_frame = game_state.cap.read()
            if not ret or first_frame is None: logger.error("Failed capture first frame."); clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state); return None
            first_frame = cv2.resize(first_frame, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT)); logger.info("Captured first frame.")
    except Exception as e: # Catch initialization errors
        logger.exception(f"Critical init error: {e}")
        cv2.putText(splash, f"Init Error", (50, UIConstants.WINDOW_HEIGHT // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, UIConstants.RED, 1)
        cv2.imshow(UIConstants.WINDOW_NAME, splash); cv2.waitKey(5000); return None

    start_time = time.time()
    logger.info("Starting splash display loop.")
    while time.time() - start_time < GameConstants.SPLASH_DURATION + GameConstants.FADE_DURATION:
        elapsed = time.time() - start_time
        display_frame = np.zeros_like(first_frame) if first_frame is not None else splash.copy()
        try: # Fade logic
            if elapsed < GameConstants.SPLASH_DURATION:
                 display_frame = splash
                 if game_state.camera_available or game_state.static_frame is not None: cv2.putText(display_frame, "Ready...", (50, UIConstants.WINDOW_HEIGHT - 50), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.YELLOW, UIConstants.FONT_THICKNESS)
            elif elapsed < GameConstants.SPLASH_DURATION + GameConstants.FADE_DURATION and first_frame is not None:
                 alpha = max(0.0, 1.0 - (elapsed - GameConstants.SPLASH_DURATION) / GameConstants.FADE_DURATION) if GameConstants.FADE_DURATION > 0 else 0.0
                 if splash.shape == first_frame.shape: display_frame = cv2.addWeighted(splash, alpha, first_frame, 1.0 - alpha, 0)
                 else: logger.warning("Splash/frame mismatch."); display_frame = first_frame
            else: display_frame = first_frame if first_frame is not None else splash
            cv2.imshow(UIConstants.WINDOW_NAME, display_frame)
        except Exception as e: logger.exception(f"Splash loop error: {e}"); cv2.putText(display_frame, "Display Error", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, UIConstants.RED, 2); cv2.imshow(UIConstants.WINDOW_NAME, display_frame)

        key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY) & 0xFF
        if key == ord('q') or key == 27: logger.info("Splash skipped."); clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state); return None
        try: # Check window close
            if cv2.getWindowProperty(UIConstants.WINDOW_NAME, 0) != -1:
                 if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1: logger.info("Splash window closed."); clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state); return None
            else: logger.info("Splash window destroyed."); return None
        except cv2.error: logger.info("Window check failed."); clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state); return None

    logger.info("Splash finished.")
    return game_state