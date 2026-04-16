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
                    logger.error("Loaded assets/game_over.png empty.")
                    game_over_splash_cache = "fallback"
            except Exception as e:
                logger.error(f"Error loading/resizing assets/game_over.png: {e}")
                game_over_splash_cache = "fallback"
        else:
            logger.warning(f"Game over splash file not found: {splash_path}")
            game_over_splash_cache = "fallback"

    # Draw background (splash or fallback solid fill)
    if isinstance(game_over_splash_cache, np.ndarray):
        frame[:, :] = game_over_splash_cache.copy()
    else:
        cv2.rectangle(frame, (0, 0), (current_width, current_height), (0, 0, 0), -1)

    # Always draw title and final score on top of whatever background is shown
    win_condition = getattr(game_state, "win_condition_met", False)
    title_text = "You Win!" if win_condition else "Game Over!"
    title_color = UIConstants.ACCENT if win_condition else UIConstants.RED
    title_font_scale = UIConstants.FONT_SCALE_XLARGE
    title_thickness = UIConstants.FONT_THICKNESS + 1
    (tw, th), _ = cv2.getTextSize(
        title_text,
        cv2.FONT_HERSHEY_SIMPLEX,
        title_font_scale,
        title_thickness,
    )
    title_x = (current_width - tw) // 2
    title_y = current_height // 3

    # Semi-transparent backdrop behind the text so it reads over any splash image
    backdrop_pad = 20
    overlay = frame.copy()
    cv2.rectangle(
        overlay,
        (title_x - backdrop_pad, title_y - th - backdrop_pad),
        (title_x + tw + backdrop_pad, title_y + backdrop_pad + 60),
        (0, 0, 0),
        -1,
    )
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    cv2.putText(
        frame,
        title_text,
        (title_x, title_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        title_font_scale,
        title_color,
        title_thickness,
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
    player_name = ""
    try:
        player_name = game_state.get_current_player().name
    except Exception:
        pass
    score_text = f"Final Score: {display_score}{doubled_indicator}"
    if player_name:
        score_text = f"{player_name} - {score_text}"
    (sw, _sh), _ = cv2.getTextSize(
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
        UIConstants.PRIMARY,
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
        UIConstants.PRIMARY,
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
        UIConstants.PRIMARY,
        game_state=game_state,
    )

    # Store rects for direct click checking in mouse_callback
    if not hasattr(game_state, "game_over_buttons"):
        game_state.game_over_buttons = {}
    game_state.game_over_buttons = {
        "play_again": play_again_rect,
        "main_menu": menu_rect,
        "heatmap": heatmap_rect,
    }

    # ESC to quit hint
    hint_text = "ESC to quit"
    (hw, _), _ = cv2.getTextSize(
        hint_text, cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, 1
    )
    hint_x = (current_width - hw) // 2
    hint_y = button_y + button_height + 28
    cv2.putText(
        frame,
        hint_text,
        (hint_x, hint_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_SMALL,
        (180, 180, 180),
        1,
        cv2.LINE_AA,
    )


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
    logger.debug("Displaying modal splash screen...")
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

    # Add tip and instruction text at the bottom
    tip_text = "Tip: Define zones in Menu > Manage Zones"
    (tw_tip, th_tip), _ = cv2.getTextSize(
        tip_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
    )
    tip_x = (target_width - tw_tip) // 2
    tip_y = target_height - 75
    cv2.putText(
        display_frame,
        tip_text,
        (tip_x, tip_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (180, 180, 180),
        1,
        cv2.LINE_AA,
    )
    instruction = "Click or press any key to continue"
    (tw, th), _ = cv2.getTextSize(
        instruction,
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.FONT_THICKNESS,
    )
    text_x = (target_width - tw) // 2
    text_y = target_height - 50
    cv2.putText(
        display_frame,
        instruction,
        (text_x, text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        UIConstants.FONT_SCALE_MEDIUM,
        UIConstants.YELLOW,
        UIConstants.FONT_THICKNESS,
    )

    # Set up mouse callback for dismissal
    dismiss_flag = {"clicked": False}
    cv2.setMouseCallback(UIConstants.WINDOW_NAME, _modal_mouse_callback, dismiss_flag)

    # Display the splash screen
    cv2.imshow(UIConstants.WINDOW_NAME, display_frame)

    # Wait for key press or mouse click (up to 3 seconds)
    start_time = time.time()
    while (time.time() - start_time) < 3.0:
        key = cv2.waitKey(30)
        if key != -1 or dismiss_flag["clicked"]:
            logger.info("Splash screen dismissed via user input")
            break
        # Check if window is still valid
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
            logger.info("Splash window closed by user")
            break

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

    # Restore the original mouse callback
    cv2.setMouseCallback(
        UIConstants.WINDOW_NAME, main_mouse_callback, main_callback_param
    )


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
        if hasattr(game_state, "has_viewed_heatmap"):
            game_state.has_viewed_heatmap = True
        try:
            from operator_remote import update_remote_status_snapshot

            update_remote_status_snapshot(game_state)
        except Exception as exc:
            logger.debug(f"Could not publish heatmap-open state to remote: {exc}")

        logger.info("Entering heatmap display loop...")
        opened_at = time.time()
        dismiss_input_guard_seconds = 0.2
        # Keys that explicitly dismiss the heatmap. Previously "any key" dismissed, which made
        # the modal close on accidental keypresses and collided with keystrokes that were meant
        # to start another action.
        _DISMISS_KEYS = {27, 13, 32, ord("h"), ord("H"), ord("q"), ord("Q")}
        while True:
            try:
                # Check if window is still valid
                if (
                    cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE)
                    < 1
                ):
                    logger.info("Heatmap window closed by user")
                    break

                # Let the operator-remote action queue be drained so the remote can dismiss the
                # heatmap or trigger other actions while the modal is open. Without this, the
                # whole game freezes on the main thread until the player closes the heatmap.
                try:
                    from operator_remote import process_remote_actions

                    process_remote_actions(game_state)
                except Exception as exc:
                    logger.debug(f"Could not process remote actions during heatmap: {exc}")

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

                # Apply a light blue tint to the playfield so the heatmap stands out more
                try:
                    # Light blue tint in BGR
                    tint_color = (255, 200, 150)
                    tint_overlay = np.full_like(background_frame, tint_color)
                    tint_alpha = 0.35  # How strong the tint is
                    tinted_background = cv2.addWeighted(
                        tint_overlay, tint_alpha, background_frame, 1.0 - tint_alpha, 0
                    )
                except Exception:
                    # Fallback to original background if tinting fails
                    tinted_background = background_frame

                # Blend heatmap with tinted background
                heatmap_alpha = 0.3  # Slightly stronger than before so points pop more
                blended_frame = cv2.addWeighted(
                    heatmap, heatmap_alpha, tinted_background, 1.0 - heatmap_alpha, 0
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
                if not getattr(game_state, "show_heatmap", False):
                    logger.info("Dismissing heatmap display from remote action")
                    break
                key = cv2.waitKey(30)
                elapsed_since_open = time.time() - opened_at
                if elapsed_since_open < dismiss_input_guard_seconds:
                    # Ignore the input that may have triggered the modal to open.
                    if key != -1:
                        key = -1
                    if dismiss_flag["clicked"]:
                        dismiss_flag["clicked"] = False
                key_masked = (key & 0xFF) if key != -1 else -1
                if key_masked in _DISMISS_KEYS or dismiss_flag["clicked"]:
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
            try:
                from operator_remote import update_remote_status_snapshot

                update_remote_status_snapshot(game_state)
            except Exception as exc:
                logger.debug(f"Could not publish heatmap-close state to remote: {exc}")
        except Exception as e:
            logger.exception(f"Error during heatmap cleanup: {e}")


# --- Initial Splash Screen ---
def show_splash_screen(supabase_url: str, supabase_key: str) -> Optional["GameState"]:
    """Display the splash screen and initialize the game state."""
    try:
        # Initialize game state
        from game_state import GameState

        game_state = GameState(supabase_url, supabase_key)

        # Ensure the main window exists before proceeding
        cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL)
        window_created = True  # Assume we might have just created it

        # Get the current resolution dimensions
        current_width, current_height = game_state.get_current_resolution_dimensions()

        # Center the window on the screen (Windows only - windll is not available on Linux)
        try:
            import sys

            if sys.platform == "win32":
                import ctypes

                user32 = ctypes.windll.user32
                screen_width = user32.GetSystemMetrics(0)
                screen_height = user32.GetSystemMetrics(1)
                x_pos = max(0, (screen_width - current_width) // 2)
                y_pos = max(0, (screen_height - current_height) // 2)
                cv2.moveWindow(UIConstants.WINDOW_NAME, x_pos, y_pos)
                logger.debug(f"Centered main window at ({x_pos}, {y_pos})")
            else:
                logger.debug("Window centering skipped on non-Windows (windll not available).")
        except Exception as e:
            logger.error(f"Failed to center main window: {e}")

        # Display splash screen
        display_modal_splash(game_state, lambda *args: None, None)  # Dummy callback

        return game_state
    except Exception as e:
        logger.error(f"Error in splash screen: {e}")
        return None


# --- Add _draw_player_name_input function ---
def _draw_player_name_input(frame: np.ndarray, game_state: "GameState") -> None:
    """Draw the player name input interface with improved visuals and cursor movement."""
    try:
        current_width, current_height = game_state.get_current_resolution_dimensions()

        # IMPORTANT: Use current_player_name_input instead of player_name_input
        input_text = getattr(game_state, "current_player_name_input", "")
        cursor_pos = getattr(game_state, "player_name_cursor_pos", len(input_text))

        # Create a semi-transparent overlay instead of full cover
        overlay = frame.copy()
        cv2.rectangle(
            overlay, (0, 0), (current_width, current_height), (10, 10, 10), -1
        )
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Create a contained popup box instead of using the whole screen
        popup_width, popup_height = 700, 300
        popup_x = (current_width - popup_width) // 2
        popup_y = (current_height - popup_height) // 2

        # Draw popup background - changed to light blue
        cv2.rectangle(
            frame,
            (popup_x, popup_y),
            (popup_x + popup_width, popup_y + popup_height),
            (170, 130, 100),  # Light blue background (BGR format)
            -1,
        )

        # Draw border
        cv2.rectangle(
            frame,
            (popup_x, popup_y),
            (popup_x + popup_width, popup_y + popup_height),
            UIConstants.WHITE,
            2,
        )

        # Draw header - changed to light blue
        cv2.rectangle(
            frame,
            (popup_x, popup_y),
            (popup_x + popup_width, popup_y + 60),
            (200, 150, 100),  # Sky blue header (BGR format)
            -1,
        )

        # Draw title
        title = "Enter Player Name"
        (tw, th), _ = cv2.getTextSize(
            title,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.FONT_THICKNESS + 1,
        )
        title_x = popup_x + (popup_width - tw) // 2
        title_y = popup_y + 40
        cv2.putText(
            frame,
            title,
            (title_x, title_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS + 1,
        )

        # Add a red X button in the top-right corner
        x_button_size = 30
        x_button_x = popup_x + popup_width - x_button_size - 10
        x_button_y = popup_y + 10

        # Choose the appropriate color based on colorblind mode
        x_button_color = UIConstants.RED
        if getattr(game_state, "colorblind_mode", False):
            x_button_color = UIConstants.CB_HIGHLIGHT

        # Draw X button circle
        cv2.circle(
            frame,
            (x_button_x + x_button_size // 2, x_button_y + x_button_size // 2),
            x_button_size // 2,
            x_button_color,
            -1,
        )

        # Draw X
        line_thickness = 2
        offset = x_button_size // 4
        cv2.line(
            frame,
            (x_button_x + offset, x_button_y + offset),
            (x_button_x + x_button_size - offset, x_button_y + x_button_size - offset),
            UIConstants.WHITE,
            line_thickness,
        )
        cv2.line(
            frame,
            (x_button_x + offset, x_button_y + x_button_size - offset),
            (x_button_x + x_button_size - offset, x_button_y + offset),
            UIConstants.WHITE,
            line_thickness,
        )

        # Store X button coordinates for mouse detection
        if hasattr(game_state, "username_x_button"):
            game_state.username_x_button = (
                x_button_x,
                x_button_y,
                x_button_size,
                x_button_size,
            )
        else:
            # Always create the attribute if it doesn't exist
            setattr(
                game_state,
                "username_x_button",
                (x_button_x, x_button_y, x_button_size, x_button_size),
            )

        # Draw input box
        input_box_width = popup_width - 80
        input_box_height = 60
        input_box_x = popup_x + 40
        input_box_y = popup_y + 100

        # Draw box shadow
        cv2.rectangle(
            frame,
            (input_box_x + 3, input_box_y + 3),
            (input_box_x + input_box_width + 3, input_box_y + input_box_height + 3),
            (30, 30, 30),
            -1,
        )

        # Draw main box
        cv2.rectangle(
            frame,
            (input_box_x, input_box_y),
            (input_box_x + input_box_width, input_box_y + input_box_height),
            (50, 50, 50),
            -1,
        )

        # Draw box border
        cv2.rectangle(
            frame,
            (input_box_x, input_box_y),
            (input_box_x + input_box_width, input_box_y + input_box_height),
            (120, 120, 120),
            2,
        )

        # Draw input text
        if input_text:
            font_scale = UIConstants.FONT_SCALE_LARGE
            font_thickness = UIConstants.FONT_THICKNESS + 1
            text_x = input_box_x + 15
            text_y = input_box_y + (input_box_height // 2) + 10

            # Draw text before cursor
            before_cursor = input_text[:cursor_pos]
            if before_cursor:
                cv2.putText(
                    frame,
                    before_cursor,
                    (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    font_scale,
                    UIConstants.WHITE,  # Use white for better visibility
                    font_thickness,
                )

                # Calculate width of text before cursor
                (before_width, _), _ = cv2.getTextSize(
                    before_cursor,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    font_scale,
                    font_thickness,
                )
            else:
                before_width = 0

            # Draw cursor
            cursor_height = 25
            cursor_x = text_x + before_width
            cursor_y_top = text_y - cursor_height
            cursor_y_bottom = text_y + 5

            # Make cursor blink
            current_time = time.time()
            if int(current_time * 2) % 2 == 0:
                cv2.line(
                    frame,
                    (cursor_x, cursor_y_top),
                    (cursor_x, cursor_y_bottom),
                    UIConstants.WHITE,
                    2,
                )

            # Draw text after cursor
            after_cursor = input_text[cursor_pos:]
            if after_cursor:
                cv2.putText(
                    frame,
                    after_cursor,
                    (cursor_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    font_scale,
                    UIConstants.WHITE,  # Use white for better visibility
                    font_thickness,
                )
        else:
            # Draw cursor at start position when there's no text
            text_x = input_box_x + 15
            text_y = input_box_y + (input_box_height // 2) + 10
            cursor_height = 25
            cursor_y_top = text_y - cursor_height
            cursor_y_bottom = text_y + 5

            # Blinking cursor
            current_time = time.time()
            if int(current_time * 2) % 2 == 0:
                cv2.line(
                    frame,
                    (text_x, cursor_y_top),
                    (text_x, cursor_y_bottom),
                    UIConstants.WHITE,
                    2,
                )

            # Draw placeholder text
            placeholder = "Type your name here..."
            cv2.putText(
                frame,
                placeholder,
                (text_x + 5, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_MEDIUM,
                (120, 120, 120),  # Gray placeholder text
                UIConstants.FONT_THICKNESS,
            )

        # Draw instructions
        instructions_y = input_box_y + input_box_height + 50

        # Instructions line 1
        instructions1 = "Enter=Confirm, Esc=Default (Player 1), Backspace=Delete"
        (iw1, ih1), _ = cv2.getTextSize(
            instructions1,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.FONT_THICKNESS,
        )
        inst1_x = popup_x + (popup_width - iw1) // 2
        cv2.putText(
            frame,
            instructions1,
            (inst1_x, instructions_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )

        # Instructions line 2
        instructions2 = "Use Left/Right arrows to move cursor"
        (iw2, ih2), _ = cv2.getTextSize(
            instructions2,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.FONT_THICKNESS,
        )
        inst2_x = popup_x + (popup_width - iw2) // 2
        cv2.putText(
            frame,
            instructions2,
            (inst2_x, instructions_y + ih1 + 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )
    except Exception as e:
        logger.error(f"Error in player name input: {e}")
        return


def _draw_playfield_selection(frame: np.ndarray, game_state: "GameState") -> None:
    """Draw the playfield selection interface."""
    try:
        def _wrap_text_to_width(
            text: str, max_width: int, font_scale: float, thickness: int
        ) -> list[str]:
            words = text.split()
            lines = []
            current_line = ""
            for word in words:
                candidate = word if not current_line else f"{current_line} {word}"
                (candidate_width, _), _ = cv2.getTextSize(
                    candidate, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
                )
                if candidate_width <= max_width or not current_line:
                    current_line = candidate
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            return lines

        current_width, current_height = game_state.get_current_resolution_dimensions()

        overlay = frame.copy()
        cv2.rectangle(
            overlay, (0, 0), (current_width, current_height), (10, 10, 10), -1
        )
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        popup_width, popup_height = 780, 380
        popup_x = (current_width - popup_width) // 2
        popup_y = (current_height - popup_height) // 2

        cv2.rectangle(
            frame,
            (popup_x, popup_y),
            (popup_x + popup_width, popup_y + popup_height),
            (170, 130, 100),
            -1,
        )
        cv2.rectangle(
            frame,
            (popup_x, popup_y),
            (popup_x + popup_width, popup_y + popup_height),
            UIConstants.WHITE,
            2,
        )

        title = "Select Playfield"
        (tw, th), _ = cv2.getTextSize(
            title,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.FONT_THICKNESS + 1,
        )
        title_x = popup_x + (popup_width - tw) // 2
        title_y = popup_y + 45
        cv2.putText(
            frame,
            title,
            (title_x, title_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS + 1,
        )

        card_width = 300
        card_height = 145
        card_gap = 30
        cards_y = popup_y + 95
        whiffle_x = popup_x + 75
        fivestar_x = whiffle_x + card_width + card_gap

        selected_playfield = getattr(game_state, "playfield_type", "whiffle")
        playfield_cards = [
            (
                "whiffle",
                whiffle_x,
                "Whiffle",
                "Classic layout, standard scoring zones",
                "Keys: 1, W, Enter",
            ),
            (
                "fivestar",
                fivestar_x,
                "Five Star",
                "Alternate layout with its own model and zones",
                "Keys: 2, F",
            ),
        ]
        game_state.playfield_option_rects = {}

        for playfield_key, card_x, title_text, subtitle_text, shortcut_text in playfield_cards:
            card_rect = (card_x, cards_y, card_width, card_height)
            game_state.playfield_option_rects[playfield_key] = card_rect
            is_selected = selected_playfield == playfield_key
            fill_color = (92, 68, 48) if is_selected else (58, 58, 58)
            border_color = UIConstants.ACCENT if is_selected else UIConstants.WHITE
            cv2.rectangle(
                frame,
                (card_x, cards_y),
                (card_x + card_width, cards_y + card_height),
                fill_color,
                -1,
            )
            cv2.rectangle(
                frame,
                (card_x, cards_y),
                (card_x + card_width, cards_y + card_height),
                border_color,
                2,
            )
            cv2.putText(
                frame,
                title_text,
                (card_x + 18, cards_y + 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_MEDIUM,
                UIConstants.WHITE,
                UIConstants.FONT_THICKNESS + 1,
            )

            wrapped_subtitle = _wrap_text_to_width(
                subtitle_text,
                card_width - 36,
                UIConstants.FONT_SCALE_SMALL,
                UIConstants.FONT_THICKNESS,
            )
            subtitle_y = cards_y + 65
            line_step = 22
            for line in wrapped_subtitle[:3]:
                cv2.putText(
                    frame,
                    line,
                    (card_x + 18, subtitle_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    UIConstants.FONT_SCALE_SMALL,
                    (220, 220, 220),
                    UIConstants.FONT_THICKNESS,
                )
                subtitle_y += line_step

            cv2.putText(
                frame,
                shortcut_text,
                (card_x + 18, cards_y + card_height - 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                UIConstants.FONT_SCALE_SMALL,
                UIConstants.YELLOW,
                UIConstants.FONT_THICKNESS,
            )

        helper_text = "Click a playfield or use the keyboard shortcuts below."
        (helper_width, _), _ = cv2.getTextSize(
            helper_text,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.FONT_THICKNESS,
        )
        cv2.putText(
            frame,
            helper_text,
            (popup_x + (popup_width - helper_width) // 2, popup_y + popup_height - 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )

        hint = "Enter / Esc defaults to Whiffle"
        (hw, _), _ = cv2.getTextSize(
            hint,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.FONT_THICKNESS,
        )
        cv2.putText(
            frame,
            hint,
            (popup_x + (popup_width - hw) // 2, popup_y + popup_height - 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_SMALL,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )
    except Exception as e:
        logger.error(f"Error drawing playfield selection: {e}")