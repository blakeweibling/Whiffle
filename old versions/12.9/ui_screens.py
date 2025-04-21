# ui_screens.py
import logging
import os
import time
# <<< ADDED IMPORT >>>
from typing import Any, Callable, Optional, TYPE_CHECKING

import cv2
import numpy as np

# Import clean_exit from the new cleanup file
from cleanup_utils import clean_exit
# Local project imports
from constants import GameConstants, UIConstants
# Import GameState class and CurrentGameState enum from NEW location
# <<< MODIFIED: Avoid direct GameState import if causing cycles, use TYPE_CHECKING >>>
# from game_state import GameState
# Import Enum from new location
from game_types import CurrentGameState
# <<< MODIFIED: Pass game_state to _draw_button >>>
from menu_utils import _draw_button

# <<< ADDED FOR TYPE HINTING >>>
if TYPE_CHECKING:
    from game_state import GameState

logger = logging.getLogger(__name__)

# Cache for game over splash image
game_over_splash_cache = None


def _draw_game_over_screen(frame: np.ndarray, game_state: "GameState") -> None:
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
                else:
                    game_over_splash_cache = "fallback"
            except Exception as e:
                logger.error(f"Error loading game_over.png: {e}")
                game_over_splash_cache = "fallback"
        else:
            game_over_splash_cache = "fallback"

    if isinstance(game_over_splash_cache, np.ndarray):
        frame[:, :] = game_over_splash_cache.copy()
    else: # Fallback drawing
        cv2.rectangle(frame, (0, 0), (frame.shape[1], frame.shape[0]), (0, 0, 0), -1)
        title_text = "You Win!" if game_state.win_condition_met else "Game Over!"
        title_color = UIConstants.GREEN if game_state.win_condition_met else UIConstants.RED
        (tw, th), _ = cv2.getTextSize(title_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_XLARGE, UIConstants.FONT_THICKNESS + 1)
        title_x = (frame.shape[1] - tw) // 2
        title_y = frame.shape[0] // 3
        cv2.putText(frame, title_text, (title_x, title_y), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_XLARGE, title_color, UIConstants.FONT_THICKNESS + 1)
        score_text = f"Final Score: {game_state.score}"
        (sw, sh), _ = cv2.getTextSize(score_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.FONT_THICKNESS)
        score_x = (frame.shape[1] - sw) // 2
        score_y = title_y + th + 30
        cv2.putText(frame, score_text, (score_x, score_y), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.WHITE, UIConstants.FONT_THICKNESS)

    # Draw Buttons
    button_width, button_height, button_y, button_spacing = (200, 50, frame.shape[0] - 90, 60)
    total_button_width = button_width * 2 + button_spacing
    start_x = (frame.shape[1] - total_button_width) // 2
    new_game_x = start_x
    new_game_rect = (new_game_x, button_y, button_width, button_height)
    _draw_button(
        frame, new_game_x, button_y, button_width, button_height, "New Game (N)", UIConstants.CV2_BLUE,
        # <<< ADDED game_state >>>
        game_state=game_state
    )
    action_new_game = "new_game_from_gameover"

    leaderboard_x = new_game_x + button_width + button_spacing
    leaderboard_rect = (leaderboard_x, button_y, button_width, button_height)
    _draw_button(
        frame, leaderboard_x, button_y, button_width, button_height, "Leaderboard (L)", UIConstants.CV2_BLUE,
        # <<< ADDED game_state >>>
        game_state=game_state
    )
    action_leaderboard = "show_leaderboard_from_gameover"

    # Store button info for potential clicks (handled in utils.py)
    if hasattr(game_state, "submenu_items"):
        game_state.submenu_items = [
            (new_game_rect, action_new_game, "New Game"),
            (leaderboard_rect, action_leaderboard, "Leaderboard"),
        ]
    if hasattr(game_state, "menu_pos"):
        game_state.menu_pos, game_state.menu_width, game_state.menu_height = (
            (0, 0), frame.shape[1], frame.shape[0]
        )


def display_modal_splash(
    game_state: "GameState",
    main_mouse_callback: Callable,
    main_callback_param: Any,
) -> None:
    """
    Displays a modal splash screen (splash.png) and waits for a key press,
    mouse click, or window close. Restores the main mouse callback afterward.
    """
    logger.info("Displaying modal splash screen...")
    splash_path = GameConstants.SPLASH_SCREEN_FILE
    splash_image = None
    try:
        if os.path.exists(splash_path):
            splash = cv2.imread(splash_path)
            if splash is not None and splash.size > 0:
                splash_image = cv2.resize(
                    splash, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT),
                    interpolation=cv2.INTER_AREA,
                )
        if splash_image is None: logger.error(f"Failed load/empty '{splash_path}'.")
    except Exception as e: logger.error(f"Error processing splash '{splash_path}': {e}")

    display_frame = np.zeros((UIConstants.WINDOW_HEIGHT, UIConstants.WINDOW_WIDTH, 3), dtype=np.uint8)
    display_frame[:, :] = UIConstants.BLACK
    if splash_image is not None:
        display_frame = splash_image.copy()
        message = "Click or press any key to continue..."
        text_color = UIConstants.YELLOW
    else:
        message = "Splash Image Unavailable. Click or press any key..."
        text_color = UIConstants.RED
        cv2.putText(display_frame, "Error: Splash Not Found", (50, UIConstants.WINDOW_HEIGHT // 2), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.RED, 2)

    (tw, th), _ = cv2.getTextSize(message, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.FONT_THICKNESS)
    cv2.putText(display_frame, message, ((UIConstants.WINDOW_WIDTH - tw) // 2, UIConstants.WINDOW_HEIGHT - 50), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, text_color, UIConstants.FONT_THICKNESS)

    dismiss_flag = {"clicked": False}
    def _modal_mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN: param["clicked"] = True
    cv2.setMouseCallback(UIConstants.WINDOW_NAME, _modal_mouse_callback, dismiss_flag)

    while True:
        try:
            if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1: break
            cv2.imshow(UIConstants.WINDOW_NAME, display_frame)
            key = cv2.waitKey(30)
            if key != -1 or dismiss_flag["clicked"]: break
        except Exception as e:
            logger.error(f"Error during modal splash loop: {e}")
            break
    cv2.setMouseCallback(UIConstants.WINDOW_NAME, main_mouse_callback, main_callback_param)
    logger.info("Exiting modal splash display.")


def show_splash_screen(supabase_url: str, supabase_key: str) -> Optional["GameState"]:
    """Displays the initial loading splash screen and handles initial setup."""
    logger.info("Showing splash screen...")
    splash_path = GameConstants.SPLASH_SCREEN_FILE
    splash = cv2.imread(splash_path)
    if splash is None:
        logger.error(f"Failed to load {splash_path}. Exiting.")
        splash = np.zeros((UIConstants.WINDOW_HEIGHT, UIConstants.WINDOW_WIDTH, 3), dtype=np.uint8)
        cv2.putText(splash, f"Error: {splash_path} not found!", (50, UIConstants.WINDOW_HEIGHT // 2), cv2.FONT_HERSHEY_SIMPLEX, 1, UIConstants.RED, 2)
        try:
            cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL)
            cv2.imshow(UIConstants.WINDOW_NAME, splash)
            cv2.waitKey(3000)
        except cv2.error: pass
        return None

    splash = cv2.resize(splash, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
    try: cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL)
    except cv2.error as e: logger.error(f"Failed to create named window: {e}"); return None

    cv2.putText(splash, "Loading...", (50, UIConstants.WINDOW_HEIGHT - 50), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.YELLOW, UIConstants.FONT_THICKNESS)
    cv2.imshow(UIConstants.WINDOW_NAME, splash)
    cv2.waitKey(1)

    game_state: Optional["GameState"] = None
    first_frame: Optional[np.ndarray] = None

    try:
        logger.info("Initializing GameState...")
        # Use string literal 'GameState' for type hint within the same file if needed
        from game_state import GameState # Import locally for instantiation
        game_state = GameState(supabase_url, supabase_key)
        if not game_state.camera_available:
            if game_state.static_frame is None: logger.error("No Camera/Static Frame. Exiting."); return None
            first_frame = game_state.static_frame.copy()
            first_frame = cv2.resize(first_frame, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
        else:
            ret, frame_read = game_state.cap.read()
            if not ret or frame_read is None:
                logger.error("Failed camera capture.")
                clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
                return None
            first_frame = cv2.resize(frame_read, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
    except Exception as e:
        logger.exception(f"Critical initialization error: {e}")
        cv2.putText(splash, f"Initialization Error", (50, UIConstants.WINDOW_HEIGHT // 2 - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, UIConstants.RED, 1)
        cv2.imshow(UIConstants.WINDOW_NAME, splash)
        cv2.waitKey(5000)
        if game_state: clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
        else:
            try: logger.debug("Attempting to destroy window after init failure (no game_state)..."); cv2.destroyWindow(UIConstants.WINDOW_NAME); cv2.waitKey(1)
            except Exception as destroy_err: logger.error(f"Error destroying window during init failure cleanup: {destroy_err}")
        return None

    if first_frame is None:
        logger.error("First frame is None. Cannot proceed.")
        if game_state: clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
        return None

    start_time = time.time()
    logger.info("Starting initial splash display loop with fade.")
    while time.time() - start_time < GameConstants.SPLASH_DURATION + GameConstants.FADE_DURATION:
        try:
            if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                logger.info("Splash window closed.")
                clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
                return None
        except cv2.error:
            logger.info("Window check failed, assuming closed.")
            clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
            return None

        elapsed = time.time() - start_time
        display_frame = np.zeros_like(first_frame)
        try:
            if splash.shape != first_frame.shape:
                display_frame = splash.copy() if elapsed < GameConstants.SPLASH_DURATION else first_frame.copy()
                if elapsed < GameConstants.SPLASH_DURATION: cv2.putText(display_frame, "Ready...", (50, UIConstants.WINDOW_HEIGHT - 50), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.YELLOW, UIConstants.FONT_THICKNESS)
            else:
                if elapsed < GameConstants.SPLASH_DURATION:
                    display_frame = splash.copy()
                    cv2.putText(display_frame, "Ready...", (50, UIConstants.WINDOW_HEIGHT - 50), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.YELLOW, UIConstants.FONT_THICKNESS)
                elif elapsed < GameConstants.SPLASH_DURATION + GameConstants.FADE_DURATION:
                    alpha = (max(0.0, 1.0 - (elapsed - GameConstants.SPLASH_DURATION) / GameConstants.FADE_DURATION) if GameConstants.FADE_DURATION > 0 else 0.0)
                    display_frame = cv2.addWeighted(splash, alpha, first_frame, 1.0 - alpha, 0)
                else:
                    display_frame = first_frame.copy()
            cv2.imshow(UIConstants.WINDOW_NAME, display_frame)
        except Exception as e: logger.exception(f"Error during splash fade loop: {e}")

        key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY) & 0xFF
        if key == ord("q") or key == 27:
            logger.info("Splash skipped.")
            clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
            return None

    logger.info("Initial splash screen finished.")
    return game_state