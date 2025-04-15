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
from game_state_helpers import show_notification  # Import show_notification

# Import Enum from new location
from game_types import CurrentGameState

# Set up logger at the top of the file
logger = logging.getLogger(__name__)


# Use _draw_button from menu_utils
try:
    from menu_utils import _draw_button
except ImportError as e:
    logger.error(
        f"Failed to import _draw_button from menu_utils: {e}. Button drawing will fail."
    )

    def _draw_button(*args, **kwargs):
        pass


# Imports for Heatmap
try:
    from heatmap_utils import generate_heatmap
except ImportError as e:
    logger.error(f"Failed to import generate_heatmap: {e}")
    generate_heatmap = None

try:
    from data_logger import SessionData
except ImportError as e:
    logger.error(f"Failed to import SessionData: {e}")
    SessionData = Any


# Import _draw_text_with_background
try:
    from ui_utils import _draw_text_with_background
except ImportError as e:
    logger.error(
        f"Failed to import _draw_text_with_background from ui_utils: {e}. Text drawing will fail."
    )

    def _draw_text_with_background(*args, **kwargs):
        pass


# Type hint for GameState using string literal
if TYPE_CHECKING:
    from game_state import GameState

# Cache for game over splash image
game_over_splash_cache = None


# --- Game Over Screen Drawing ---
def _draw_game_over_screen(frame: np.ndarray, game_state: "GameState") -> None:
    """Draws the game over screen and its interactive buttons."""
    global game_over_splash_cache
    current_width, current_height = game_state.get_current_resolution_dimensions()

    # Splash image handling
    if isinstance(game_over_splash_cache, np.ndarray):
        if (
            game_over_splash_cache.shape[1] != current_width
            or game_over_splash_cache.shape[0] != current_height
        ):
            logger.warning("Game over cache dimensions mismatch. Resizing.")
            try:
                game_over_splash_cache = cv2.resize(
                    game_over_splash_cache, (current_width, current_height)
                )
            except Exception as e:
                logger.error(f"Failed resize game over cache: {e}")
                game_over_splash_cache = "fallback"
    if game_over_splash_cache is None:
        splash_path = GameConstants.GAME_OVER_SPLASH_FILE
        if os.path.exists(splash_path):
            try:
                splash = cv2.imread(splash_path)
                if splash is not None and splash.size > 0:
                    game_over_splash_cache = cv2.resize(
                        splash, (current_width, current_height)
                    )
                else:
                    logger.error("Loaded game_over.png empty.")
                    game_over_splash_cache = "fallback"
            except Exception as e:
                logger.error(f"Error loading/resizing game_over.png: {e}")
                game_over_splash_cache = "fallback"
        else:
            logger.warning(f"Game over splash file not found: {splash_path}")
            game_over_splash_cache = "fallback"

    # Draw background (splash or fallback text)
    if isinstance(game_over_splash_cache, np.ndarray):
        frame[:, :] = game_over_splash_cache.copy()
    else:
        cv2.rectangle(frame, (0, 0), (current_width, current_height), (0, 0, 0), -1)
        win_condition = getattr(game_state, "win_condition_met", False)
        title_text = "You Win!" if win_condition else "Game Over!"
        title_color = UIConstants.GREEN if win_condition else UIConstants.RED
        (tw, th), _ = cv2.getTextSize(
            title_text,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_XLARGE,
            UIConstants.FONT_THICKNESS + 1,
        )
        title_x = (current_width - tw) // 2
        title_y = current_height // 3
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
        display_score = (
            score * 2
            if getattr(game_state, "special_hole_hit_this_session", False)
            else score
        )
        doubled_indicator = (
            " (x2 Bonus!)"
            if getattr(game_state, "special_hole_hit_this_session", False)
            else ""
        )
        score_text = f"Final Score: {display_score}{doubled_indicator}"
        (sw, sh), _ = cv2.getTextSize(
            score_text,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.FONT_THICKNESS,
        )
        score_x = (current_width - sw) // 2
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

    # Draw buttons
    button_width, button_height, button_spacing = (200, 50, 30)
    button_y = current_height - int(0.1 * current_height) - button_height

    # Three buttons now: Play Again, Menu, and Heatmap
    total_button_width = button_width * 3 + button_spacing * 2
    start_x = (current_width - total_button_width) // 2

    # Play Again button (previously "New Game")
    play_again_x = start_x
    play_again_rect = (play_again_x, button_y, button_width, button_height)
    _draw_button(
        frame,
        play_again_x,
        button_y,
        button_width,
        button_height,
        "Play Again (N)",
        UIConstants.CV2_BLUE,
        game_state=game_state,
    )

    # Main Menu button (previously "Leaderboard")
    menu_x = play_again_x + button_width + button_spacing
    menu_rect = (menu_x, button_y, button_width, button_height)
    _draw_button(
        frame,
        menu_x,
        button_y,
        button_width,
        button_height,
        "Main Menu (M)",
        UIConstants.CV2_BLUE,
        game_state=game_state,
    )

    # Heatmap button (new)
    heatmap_x = menu_x + button_width + button_spacing
    heatmap_rect = (heatmap_x, button_y, button_width, button_height)
    _draw_button(
        frame,
        heatmap_x,
        button_y,
        button_width,
        button_height,
        "Show Heatmap (H)",
        UIConstants.CV2_BLUE,
        game_state=game_state,
    )

    # Store rects for direct click checking in mouse_callback
    if hasattr(game_state, "game_over_buttons"):
        game_state.game_over_buttons = {
            "play_again": play_again_rect,
            "main_menu": menu_rect,
            "heatmap": heatmap_rect,
        }
    else:
        logger.warning("game_state missing 'game_over_buttons' attribute.")


# --- Modal Dismissal Callback ---
def _modal_mouse_callback(event: int, x: int, y: int, flags: int, param: dict) -> None:
    """Handle mouse events for modal windows."""
    if event == cv2.EVENT_LBUTTONDOWN:
        param["clicked"] = True


# --- Modal Splash Screen ---
def display_modal_splash(
    game_state: "GameState",
    main_mouse_callback: Callable,
    main_callback_param: Any,
) -> None:
    """Display the modal splash screen."""
    logger.info("Displaying modal splash screen...")
    splash_path = GameConstants.SPLASH_SCREEN_FILE
    splash_image = None
    target_width, target_height = game_state.get_current_resolution_dimensions()
    try:
        if os.path.exists(splash_path):
            splash = cv2.imread(splash_path)
            if splash is not None and splash.size > 0:
                splash_image = cv2.resize(
                    splash,
                    (target_width, target_height),
                    interpolation=cv2.INTER_AREA,
                )
            else:
                logger.error("Loaded splash image is empty")
                splash_image = None
        else:
            logger.warning(f"Splash file not found: {splash_path}")
            splash_image = None
    except Exception as e:
        logger.error(f"Error loading/resizing splash image: {e}")
        splash_image = None

    display_frame = np.zeros((target_height, target_width, 3), dtype=np.uint8)
    if splash_image is not None:
        display_frame = splash_image.copy()
    else:
        # Draw fallback text
        text = "Welcome to Whiffle Tracker!"
        (tw, th), _ = cv2.getTextSize(
            text,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.FONT_THICKNESS,
        )
        text_x = (target_width - tw) // 2
        text_y = target_height // 2
        cv2.putText(
            display_frame,
            text,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )

    # Display the splash screen
    cv2.imshow(UIConstants.WINDOW_NAME, display_frame)
    cv2.waitKey(3000)  # Display for 3 seconds

    # Get the first frame to show after splash
    first_frame = None
    if game_state.camera_available and game_state.cap and game_state.cap.isOpened():
        ret, frame = game_state.cap.read()
        if ret and frame is not None:
            first_frame = cv2.resize(frame, (target_width, target_height))
    elif game_state.static_frame is not None:
        first_frame = cv2.resize(game_state.static_frame, (target_width, target_height))

    if first_frame is not None:
        cv2.imshow(UIConstants.WINDOW_NAME, first_frame)
        cv2.waitKey(1)


# --- Display Heatmap Modally ---
def display_heatmap_modal(
    game_state: "GameState", main_mouse_callback: Callable, main_callback_param: Any
) -> None:
    """Display the heatmap modal window."""
    try:
        if generate_heatmap is None:
            logger.error("Heatmap generation not available")
            return

        # Get current session data
        if not hasattr(game_state, "data_logger") or not game_state.data_logger:
            logger.error("No data logger available")
            return

        current_session = game_state.data_logger.get_current_session_data()
        if not current_session:
            logger.error("No current session data available")
            return

        # Generate heatmap with current session data
        current_width, current_height = game_state.get_current_resolution_dimensions()
        heatmap = generate_heatmap(
            current_session, width=current_width, height=current_height
        )
        if heatmap is None:
            logger.error("Failed to generate heatmap")
            return

        # Set up mouse callback for dismissal
        dismiss_flag = {"clicked": False}
        cv2.setMouseCallback(
            UIConstants.WINDOW_NAME, _modal_mouse_callback, dismiss_flag
        )

        # Set heatmap display flag
        if hasattr(game_state, "show_heatmap"):
            game_state.show_heatmap = True

        logger.info("Entering heatmap display loop...")
        while True:
            try:
                # Check if window is still valid
                if (
                    cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE)
                    < 1
                ):
                    logger.info("Heatmap window closed by user")
                    break

                # Get background frame
                background_frame = None
                if (
                    getattr(game_state, "camera_available", False)
                    and hasattr(game_state, "cap")
                    and game_state.cap
                    and game_state.cap.isOpened()
                ):
                    ret, frame = game_state.cap.read()
                    if ret and frame is not None:
                        background_frame = cv2.resize(
                            frame, (current_width, current_height)
                        )
                elif (
                    hasattr(game_state, "static_frame")
                    and game_state.static_frame is not None
                ):
                    background_frame = cv2.resize(
                        game_state.static_frame, (current_width, current_height)
                    )

                if background_frame is None:
                    background_frame = np.zeros(
                        (current_height, current_width, 3), dtype=np.uint8
                    )

                # Blend heatmap with background
                heatmap_alpha = 0.2
                blended_frame = cv2.addWeighted(
                    heatmap, heatmap_alpha, background_frame, 1.0 - heatmap_alpha, 0
                )

                # Add instruction text
                message = "Heatmap View - Click or press ESC/Any Key to Close"
                text_color = UIConstants.WHITE
                bg_color = UIConstants.BLACK
                (tw, th), _ = cv2.getTextSize(
                    message,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    UIConstants.FONT_SCALE_MEDIUM,
                    UIConstants.FONT_THICKNESS,
                )
                text_pos = ((current_width - tw) // 2, current_height - 30)
                _draw_text_with_background(
                    blended_frame,
                    message,
                    text_pos,
                    UIConstants.FONT_SCALE_MEDIUM,
                    text_color,
                    bg_color,
                )

                # Display frame
                cv2.imshow(UIConstants.WINDOW_NAME, blended_frame)

                # Check for exit conditions
                key = cv2.waitKey(30)
                if key == 27 or key != -1 or dismiss_flag["clicked"]:
                    logger.info("Dismissing heatmap display")
                    break

            except cv2.error as e:
                logger.error(f"OpenCV error during heatmap display: {e}")
                break
            except Exception as e:
                logger.exception(f"Unexpected error during heatmap display: {e}")
                break

    except Exception as e:
        logger.exception(f"Error in display_heatmap_modal: {e}")
    finally:
        # Cleanup
        try:
            cv2.setMouseCallback(
                UIConstants.WINDOW_NAME, main_mouse_callback, main_callback_param
            )
            if hasattr(game_state, "show_heatmap"):
                game_state.show_heatmap = False
        except Exception as e:
            logger.exception(f"Error during heatmap cleanup: {e}")


# --- Initial Splash Screen ---
def show_splash_screen(supabase_url: str, supabase_key: str) -> Optional["GameState"]:
    """Display the splash screen and initialize the game state."""
    window_created = False
    try:
        # Initialize game state
        from game_state import GameState

        game_state = GameState(supabase_url, supabase_key)

        # Create splash window
        cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL)
        window_created = True

        # Display splash screen
        display_modal_splash(game_state, lambda *args: None, None)  # Dummy callback

        return game_state
    except Exception as e:
        logger.error(f"Error in splash screen: {e}")
        return None


# --- Add _draw_player_name_input function ---
# (Copied from ui.py correction)
def _draw_player_name_input(frame: np.ndarray, game_state: "GameState") -> None:
    """Draw the player name input interface."""
    try:
        current_width, current_height = game_state.get_current_resolution_dimensions()
        input_text = getattr(game_state, "player_name_input", "")

        # Draw background
        cv2.rectangle(frame, (0, 0), (current_width, current_height), (0, 0, 0), -1)

        # Draw title
        title = "Enter Player Name"
        (tw, th), _ = cv2.getTextSize(
            title,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.FONT_THICKNESS,
        )
        title_x = (current_width - tw) // 2
        title_y = current_height // 3
        cv2.putText(
            frame,
            title,
            (title_x, title_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )

        # Draw input box
        input_box_width = min(400, current_width - 100)
        input_box_height = 50
        input_box_x = (current_width - input_box_width) // 2
        input_box_y = title_y + th + 30

        cv2.rectangle(
            frame,
            (input_box_x, input_box_y),
            (input_box_x + input_box_width, input_box_y + input_box_height),
            UIConstants.WHITE,
            2,
        )

        # Draw input text
        if input_text:
            (iw, ih), _ = cv2.getTextSize(
                input_text,
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_MEDIUM,
                UIConstants.FONT_THICKNESS,
            )
            text_x = input_box_x + 10
            text_y = input_box_y + input_box_height - 10
            cv2.putText(
                frame,
                input_text,
                (text_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_MEDIUM,
                UIConstants.WHITE,
                UIConstants.FONT_THICKNESS,
            )

        # Draw instructions
        instructions = "Press Enter to confirm, Backspace to delete"
        (iw, ih), _ = cv2.getTextSize(
            instructions,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.FONT_THICKNESS,
        )
        inst_x = (current_width - iw) // 2
        inst_y = input_box_y + input_box_height + 30
        cv2.putText(
            frame,
            instructions,
            (inst_x, inst_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )
    except Exception as e:
        logger.error(f"Error in player name input: {e}")
        return
