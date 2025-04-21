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
from constants import GameConstants, UIConstants

# Import Enum from new location
from game_types import CurrentGameState

# Use _draw_button from menu_utils
try:
    from menu_utils import _draw_button
except ImportError:
    logger.error(
        "Failed to import _draw_button from menu_utils. Button drawing will fail."
    )

    def _draw_button(*args, **kwargs):
        pass


# Imports for Heatmap
try:
    from heatmap_utils import generate_heatmap
except ImportError:
    logger.error(
        "Failed to import generate_heatmap from heatmap_utils. Heatmap feature disabled."
    )
    generate_heatmap = None
try:
    from data_logger import SessionData
except ImportError:
    SessionData = Any  # Fallback type

# Import _draw_text_with_background
try:
    from ui_utils import _draw_text_with_background
except ImportError:
    logger.error(
        "Failed to import _draw_text_with_background from ui_utils. Text drawing will fail."
    )

    def _draw_text_with_background(*args, **kwargs):
        pass


# Type hint for GameState using string literal
if TYPE_CHECKING:
    from game_state import GameState

logger = logging.getLogger(__name__)

# Cache for game over splash image
game_over_splash_cache = None


# --- Game Over Screen Drawing ---
def _draw_game_over_screen(frame: np.ndarray, game_state: "GameState") -> None:
    """Draws the Game Over screen using game_over.png and adds buttons."""
    global game_over_splash_cache
    if game_over_splash_cache is None:
        splash_path = GameConstants.GAME_OVER_SPLASH_FILE
        if os.path.exists(splash_path):
            try:
                splash = cv2.imread(splash_path)
                if splash is not None and splash.size > 0:
                    splash_resized = cv2.resize(
                        splash, (frame.shape[1], frame.shape[0]))
                    game_over_splash_cache = splash_resized
                else:
                    logger.error(
                        f"Loaded game_over.png but it was empty or invalid.")
                    game_over_splash_cache = "fallback"
            except Exception as e:
                logger.error(f"Error loading or resizing game_over.png: {e}")
                game_over_splash_cache = "fallback"
        else:
            logger.warning(f"Game over splash file not found: {splash_path}")
            game_over_splash_cache = "fallback"

    if isinstance(game_over_splash_cache, np.ndarray):
        if frame.shape != game_over_splash_cache.shape:
            logger.warning("Frame shape changed. Resizing game over cache.")
            game_over_splash_cache = cv2.resize(
                game_over_splash_cache, (frame.shape[1], frame.shape[0]))
        frame[:, :] = game_over_splash_cache.copy()
    else:  # Fallback drawing
        cv2.rectangle(frame, (0, 0), (frame.shape[1], frame.shape[0]),
                      (0, 0, 0), -1)
        win_condition = getattr(game_state, "win_condition_met", False)
        title_text = "You Win!" if win_condition else "Game Over!"
        title_color = UIConstants.GREEN if win_condition else UIConstants.RED
        (tw, th), _ = cv2.getTextSize(
            title_text,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_XLARGE,
            UIConstants.FONT_THICKNESS + 1,
        )
        title_x = (frame.shape[1] - tw) // 2
        title_y = frame.shape[0] // 3
        cv2.putText(
            frame,
            title_text,
            (title_x, title_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_XLARGE,
            title_color,
            UIConstants.FONT_THICKNESS + 1,
        )
        score = getattr(game_state, "score", 0)
        score_text = f"Final Score: {score}"
        (sw, sh), _ = cv2.getTextSize(
            score_text,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.FONT_THICKNESS,
        )
        score_x = (frame.shape[1] - sw) // 2
        score_y = title_y + th + 30
        cv2.putText(
            frame,
            score_text,
            (score_x, score_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )

    # Draw Buttons
    button_width, button_height, button_y, button_spacing = (
        200,
        50,
        frame.shape[0] - 90,
        60,
    )
    total_button_width = button_width * 2 + button_spacing
    start_x = (frame.shape[1] - total_button_width) // 2
    new_game_x = start_x
    new_game_rect = (new_game_x, button_y, button_width, button_height)
    _draw_button(
        frame,
        new_game_x,
        button_y,
        button_width,
        button_height,
        "New Game (N)",
        UIConstants.CV2_BLUE,
        game_state=game_state,
    )
    action_new_game = "new_game_from_gameover"
    leaderboard_x = new_game_x + button_width + button_spacing
    leaderboard_rect = (leaderboard_x, button_y, button_width, button_height)
    _draw_button(
        frame,
        leaderboard_x,
        button_y,
        button_width,
        button_height,
        "Leaderboard (L)",
        UIConstants.CV2_BLUE,
        game_state=game_state,
    )
    action_leaderboard = "show_leaderboard_from_gameover"
    if hasattr(game_state, "submenu_items"):
        game_state.submenu_items = [
            (new_game_rect, action_new_game, "New Game"),
            (leaderboard_rect, action_leaderboard, "Leaderboard"),
        ]
    if hasattr(game_state, "menu_pos"):
        game_state.menu_pos = (0, 0)
        game_state.menu_width = frame.shape[1]
        game_state.menu_height = frame.shape[0]


# --- Modal Dismissal Callback ---
def _modal_mouse_callback(event: int, x: int, y: int, flags: int, param: dict):
    if event == cv2.EVENT_LBUTTONDOWN:
        param["clicked"] = True


# --- Modal Splash Screen ---
def display_modal_splash(
    game_state: "GameState",
    main_mouse_callback: Callable,
    main_callback_param: Any,
) -> None:
    """Displays splash.png modally."""
    logger.info("Displaying modal splash screen...")
    splash_path = GameConstants.SPLASH_SCREEN_FILE
    splash_image = None
    try:
        if os.path.exists(splash_path):
            splash = cv2.imread(splash_path)
            if splash is not None and splash.size > 0:
                splash_image = cv2.resize(
                    splash,
                    (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT),
                    interpolation=cv2.INTER_AREA,
                )
        if splash_image is None:
            logger.error(f"Failed load/empty '{splash_path}'.")
    except Exception as e:
        logger.error(f"Error processing splash '{splash_path}': {e}")

    display_frame = np.zeros(
        (UIConstants.WINDOW_HEIGHT, UIConstants.WINDOW_WIDTH, 3),
        dtype=np.uint8)
    display_frame[:, :] = UIConstants.BLACK
    if splash_image is not None:
        display_frame = splash_image.copy()
        message = "Click or press any key to continue..."
        text_color = UIConstants.YELLOW
    else:
        message = "Splash Image Unavailable. Click or press any key..."
        text_color = UIConstants.RED
        cv2.putText(
            display_frame,
            "Error: Splash Not Found",
            (50, UIConstants.WINDOW_HEIGHT // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.RED,
            2,
        )
    (tw, th), _ = cv2.getTextSize(
        message,
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.FONT_THICKNESS,
    )
    cv2.putText(
        display_frame,
        message,
        ((UIConstants.WINDOW_WIDTH - tw) // 2, UIConstants.WINDOW_HEIGHT - 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        text_color,
        UIConstants.FONT_THICKNESS,
    )

    dismiss_flag = {"clicked": False}
    cv2.setMouseCallback(UIConstants.WINDOW_NAME, _modal_mouse_callback,
                         dismiss_flag)
    while True:
        try:
            if cv2.getWindowProperty(UIConstants.WINDOW_NAME,
                                     cv2.WND_PROP_VISIBLE) < 1:
                logger.warning("Modal splash window closed.")
                break
            cv2.imshow(UIConstants.WINDOW_NAME, display_frame)
            key = cv2.waitKey(30)
            if key != -1 or dismiss_flag["clicked"]:
                logger.info("Dismissing modal splash.")
                break
        except cv2.error as e:
            logger.error(f"OpenCV error during modal splash loop: {e}")
            break
        except Exception as e:
            logger.exception(f"Unexpected error during modal splash loop: {e}")
            break
    try:
        cv2.setMouseCallback(UIConstants.WINDOW_NAME, main_mouse_callback,
                             main_callback_param)
        logger.info("Restored main mouse callback after modal splash.")
    except Exception as e:
        logger.exception(f"Error restoring mouse callback: {e}")


# --- Display Heatmap Modally ---
def display_heatmap_modal(game_state: "GameState",
                          main_mouse_callback: Callable,
                          main_callback_param: Any) -> None:
    """Generates and displays the session heatmap overlayed on the live feed modally until dismissed."""
    logger.info("Attempting to display heatmap modal...")
    if not generate_heatmap:
        logger.error(
            "generate_heatmap function not available. Cannot display heatmap.")
        if hasattr(game_state, "notification_text"):
            show_notification(game_state,
                              "Error: Heatmap unavailable",
                              is_error=True,
                              duration=3.0)
        return
    if not hasattr(game_state, "data_logger") or not game_state.data_logger:
        logger.warning("No data logger found in game_state for heatmap.")
        if hasattr(game_state, "notification_text"):
            show_notification(game_state,
                              "No session data for heatmap",
                              is_error=True,
                              duration=3.0)
        return
    current_session = game_state.data_logger.get_current_session_data()
    if not current_session:
        logger.warning("No active session data found for heatmap.")
        if hasattr(game_state, "notification_text"):
            show_notification(
                game_state,
                "No active session data for heatmap",
                is_error=True,
                duration=3.0,
            )
        return

    try:
        heatmap_image = generate_heatmap(
            current_session,
            width=UIConstants.WINDOW_WIDTH,
            height=UIConstants.WINDOW_HEIGHT,
        )
    except Exception as e:
        logger.exception(f"Error generating heatmap: {e}")
        if hasattr(game_state, "notification_text"):
            show_notification(game_state,
                              "Error generating heatmap",
                              is_error=True,
                              duration=3.0)
        return
    if heatmap_image is None:
        logger.info("Heatmap generation returned None (likely no data).")
        if hasattr(game_state, "notification_text"):
            show_notification(game_state,
                              "No position data to generate heatmap",
                              duration=3.0)
        return

    dismiss_flag = {"clicked": False}
    cv2.setMouseCallback(UIConstants.WINDOW_NAME, _modal_mouse_callback,
                         dismiss_flag)
    if hasattr(game_state, "show_heatmap"):
        game_state.show_heatmap = True
    logger.info("Entering heatmap display loop...")
    while True:
        try:
            if cv2.getWindowProperty(UIConstants.WINDOW_NAME,
                                     cv2.WND_PROP_VISIBLE) < 1:
                logger.warning("Heatmap display window closed.")
                break
            background_frame = None
            cap = getattr(game_state, "cap", None)
            static_frame = getattr(game_state, "static_frame", None)
            if (getattr(game_state, "camera_available", False) and cap
                    and cap.isOpened()):
                ret, frame_read = cap.read()
                if ret and frame_read is not None:
                    background_frame = cv2.resize(
                        frame_read,
                        (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT),
                    )
                else:
                    logger.error("Failed camera frame during heatmap.")
                    background_frame = (static_frame.copy() if static_frame
                                        is not None else np.zeros(
                                            (UIConstants.WINDOW_HEIGHT,
                                             UIConstants.WINDOW_WIDTH, 3),
                                            dtype=np.uint8,
                                        ))
            elif static_frame is not None:
                background_frame = static_frame.copy()
            else:
                logger.error("No frame source during heatmap.")
                background_frame = np.zeros(
                    (UIConstants.WINDOW_HEIGHT, UIConstants.WINDOW_WIDTH, 3),
                    dtype=np.uint8,
                )
            heatmap_alpha = 0.2
            blended_frame = cv2.addWeighted(heatmap_image, heatmap_alpha,
                                            background_frame,
                                            1.0 - heatmap_alpha, 0)
            display_frame = blended_frame
            message = "Heatmap View - Click or press ESC/Any Key to Close"
            text_color = UIConstants.WHITE
            bg_color = UIConstants.BLACK
            (tw, th), _ = cv2.getTextSize(
                message,
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_MEDIUM,
                UIConstants.FONT_THICKNESS,
            )
            text_pos = (
                (UIConstants.WINDOW_WIDTH - tw) // 2,
                UIConstants.WINDOW_HEIGHT - 30,
            )
            try:
                _draw_text_with_background(
                    display_frame,
                    message,
                    text_pos,
                    UIConstants.FONT_SCALE_MEDIUM,
                    text_color,
                    bg_color,
                    thickness=UIConstants.FONT_THICKNESS,
                    alpha=0.7,
                )
            except Exception as e:
                logger.exception(f"Error drawing text on heatmap overlay: {e}")
                cv2.putText(
                    display_frame,
                    message,
                    text_pos,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    UIConstants.FONT_SCALE_MEDIUM,
                    text_color,
                    UIConstants.FONT_THICKNESS,
                )
            cv2.imshow(UIConstants.WINDOW_NAME, display_frame)
            key = cv2.waitKey(30)
            if key == 27 or key != -1 or dismiss_flag["clicked"]:
                logger.info("Dismissing heatmap display.")
                break
        except cv2.error as e:
            logger.error(f"OpenCV error during heatmap display loop: {e}")
            break
        except Exception as e:
            logger.exception(
                f"Unexpected error during heatmap display loop: {e}")
            break
    try:
        cv2.setMouseCallback(UIConstants.WINDOW_NAME, main_mouse_callback,
                             main_callback_param)
        logger.info("Restored main mouse callback after heatmap display.")
    except Exception as e:
        logger.exception(f"Error restoring mouse callback after heatmap: {e}")
    if hasattr(game_state, "show_heatmap"):
        game_state.show_heatmap = False


# --- Initial Splash Screen (MODIFIED for Syntax Errors) ---
def show_splash_screen(supabase_url: str,
                       supabase_key: str) -> Optional["GameState"]:
    """Displays the initial loading splash screen and handles initial setup."""
    logger.info("Showing splash screen...")
    splash_path = GameConstants.SPLASH_SCREEN_FILE
    splash = cv2.imread(splash_path)
    window_created = False
    try:
        cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(UIConstants.WINDOW_NAME, UIConstants.WINDOW_WIDTH,
                         UIConstants.WINDOW_HEIGHT)
        window_created = True
    except cv2.error as e:
        logger.error(f"Failed to create or resize named window: {e}")
        return None

    if splash is None:
        logger.error(f"Failed to load {splash_path}. Showing error message.")
        splash = np.zeros(
            (UIConstants.WINDOW_HEIGHT, UIConstants.WINDOW_WIDTH, 3),
            dtype=np.uint8)
        error_text = f"Error: {os.path.basename(splash_path)} not found!"
        (tw_err, th_err), _ = cv2.getTextSize(error_text,
                                              cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
        cv2.putText(
            splash,
            error_text,
            ((UIConstants.WINDOW_WIDTH - tw_err) // 2,
             UIConstants.WINDOW_HEIGHT // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            UIConstants.RED,
            2,
        )
        # --- Fixed Syntax ---
        cv2.imshow(UIConstants.WINDOW_NAME, splash)
        cv2.waitKey(3000)
        try:
            cv2.destroyWindow(UIConstants.WINDOW_NAME)
        except:
            pass
        # --- End Fixed Syntax ---
        return None
    try:
        splash = cv2.resize(
            splash, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
    except cv2.error as e:
        logger.error(f"Failed to resize splash image: {e}. Displaying error.")
        splash = np.zeros(
            (UIConstants.WINDOW_HEIGHT, UIConstants.WINDOW_WIDTH, 3),
            dtype=np.uint8)
        cv2.putText(
            splash,
            "Error resizing splash",
            (50, UIConstants.WINDOW_HEIGHT // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            UIConstants.RED,
            2,
        )
        # --- Fixed Syntax ---
        cv2.imshow(UIConstants.WINDOW_NAME, splash)
        cv2.waitKey(3000)
        try:
            cv2.destroyWindow(UIConstants.WINDOW_NAME)
        except:
            pass
        # --- End Fixed Syntax ---
        return None

    cv2.putText(
        splash,
        "Loading...",
        (50, UIConstants.WINDOW_HEIGHT - 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.YELLOW,
        UIConstants.FONT_THICKNESS,
    )
    cv2.imshow(UIConstants.WINDOW_NAME, splash)
    cv2.waitKey(1)

    game_state: Optional["GameState"] = None
    first_frame: Optional[np.ndarray] = None
    from game_state import GameState

    try:
        logger.info("Initializing GameState...")
        game_state = GameState(supabase_url, supabase_key)
        if not game_state.camera_available:
            if game_state.static_frame is None:
                logger.error("No Camera/Static Frame available. Exiting.")
                cv2.putText(
                    splash,
                    "ERROR: No Camera or Static Frame",
                    (50, UIConstants.WINDOW_HEIGHT // 2 - 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    UIConstants.RED,
                    1,
                )
                cv2.imshow(UIConstants.WINDOW_NAME, splash)
                cv2.waitKey(3000)
                clean_exit(None, None, False, game_state)
                return None
            first_frame = game_state.static_frame.copy()
        else:
            if game_state.cap is None or not game_state.cap.isOpened():
                logger.error(
                    "Camera requested but not available/opened. Exiting.")
                clean_exit(None, None, False, game_state)
                return None
            ret, frame_read = game_state.cap.read()
            if not ret or frame_read is None:
                logger.error("Failed initial camera frame capture. Exiting.")
                clean_exit(game_state.cap, None, False, game_state)
                return None
            first_frame = cv2.resize(
                frame_read,
                (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
    except Exception as e:
        logger.exception(
            f"Critical error during GameState initialization or first frame capture: {e}"
        )
        cv2.putText(
            splash,
            f"Initialization Error",
            (50, UIConstants.WINDOW_HEIGHT // 2 - 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            UIConstants.RED,
            1,
        )
        # --- Fixed Syntax ---
        cv2.imshow(UIConstants.WINDOW_NAME, splash)
        cv2.waitKey(5000)  # Show error longer
        # --- End Fixed Syntax ---
        cap = getattr(game_state, "cap", None) if game_state else None
        music = getattr(game_state, "background_music",
                        None) if game_state else None
        music_on = (getattr(game_state, "background_music_on", False)
                    if game_state else False)
        clean_exit(cap, music, music_on, game_state)
        return None
    if first_frame is None:
        logger.error("First frame is None after init. Cannot proceed.")
        clean_exit(
            game_state.cap,
            game_state.background_music,
            game_state.background_music_on,
            game_state,
        )
        return None

    start_time = time.time()
    logger.info("Starting initial splash display loop with fade.")
    while (time.time() - start_time
           < GameConstants.SPLASH_DURATION + GameConstants.FADE_DURATION):
        try:
            if cv2.getWindowProperty(UIConstants.WINDOW_NAME,
                                     cv2.WND_PROP_VISIBLE) < 1:
                logger.warning("Splash window closed during fade loop.")
                clean_exit(
                    game_state.cap,
                    game_state.background_music,
                    game_state.background_music_on,
                    game_state,
                )
                return None
        except cv2.error:
            logger.warning(
                "Window check failed during fade loop, assuming closed.")
            clean_exit(
                game_state.cap,
                game_state.background_music,
                game_state.background_music_on,
                game_state,
            )
            return None

        elapsed = time.time() - start_time
        display_frame = np.zeros_like(first_frame)
        try:
            if elapsed < GameConstants.SPLASH_DURATION:
                display_frame = splash.copy()
                cv2.putText(
                    display_frame,
                    "Ready...",
                    (50, UIConstants.WINDOW_HEIGHT - 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    UIConstants.FONT_SCALE_MEDIUM,
                    UIConstants.YELLOW,
                    UIConstants.FONT_THICKNESS,
                )
            elif elapsed < GameConstants.SPLASH_DURATION + GameConstants.FADE_DURATION:
                fade_duration = GameConstants.FADE_DURATION
                alpha = (max(
                    0.0,
                    1.0 -
                    (elapsed - GameConstants.SPLASH_DURATION) / fade_duration,
                ) if fade_duration > 0 else 0.0)
                display_frame = cv2.addWeighted(splash, alpha, first_frame,
                                                1.0 - alpha, 0)
            else:
                display_frame = first_frame.copy()
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
        if key == ord("q") or key == 27:
            logger.info("Splash skipped by user.")
            clean_exit(
                game_state.cap,
                game_state.background_music,
                game_state.background_music_on,
                game_state,
            )
            return None

    logger.info("Initial splash screen finished.")
    try:
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME,
                                 cv2.WND_PROP_VISIBLE) >= 1:
            cv2.imshow(UIConstants.WINDOW_NAME, first_frame)
            cv2.waitKey(1)
    except cv2.error:
        logger.warning(
            "Could not display final first_frame after splash fade.")

    return game_state
