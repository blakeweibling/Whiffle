# ui_screens.py
import cv2
import numpy as np
import logging
import time
import os
from typing import Tuple, Optional

# Local project imports
from constants import UIConstants, GameConstants

# Ensure it imports from menu_utils
from menu_utils import _draw_button

# Ensure necessary components are imported from utils if needed by show_splash_screen
from cleanup_utils import clean_exit  # Import from the new cleanup file

# Ensure GameState and Enum are imported
from game_state import GameState, CurrentGameState

# Import the helper function from its new location
from ui_utils import _draw_text_with_background

logger = logging.getLogger(__name__)

# Cache for game over splash image
game_over_splash_cache = None
# Note: The old 'draw_menu_splash' function is removed.


# Feature 3 (Revised): Draw Game Over Screen with Image
def _draw_game_over_screen(
    frame: np.ndarray, game_state: GameState
) -> None:  # Use GameState type hint
    """Draws the Game Over screen using game_over.png and adds buttons."""
    global game_over_splash_cache
    if game_over_splash_cache is None:
        splash_path = GameConstants.GAME_OVER_SPLASH_FILE
        if os.path.exists(splash_path):
            try:
                splash = cv2.imread(splash_path)
                if splash is not None:
                    splash_resized = cv2.resize(
                        splash, (frame.shape[1], frame.shape[0])
                    )
                    game_over_splash_cache = splash_resized
                    logger.info(f"Loaded and cached '{splash_path}'")
                else:
                    logger.error(f"Failed to load '{splash_path}'. Using fallback.")
                    game_over_splash_cache = "fallback"  # Mark as fallback
            except Exception as e:
                logger.error(
                    f"Error loading or resizing '{splash_path}': {e}. Using fallback."
                )
                game_over_splash_cache = "fallback"  # Mark as fallback
        else:
            logger.warning(f"'{splash_path}' not found. Using fallback.")
            game_over_splash_cache = "fallback"  # Mark as fallback

    # Use isinstance to check if it's a numpy array, not the "fallback" string or None
    if isinstance(game_over_splash_cache, np.ndarray):
        # Use copy to avoid modifying cache
        frame[:, :] = game_over_splash_cache.copy()
    else:  # Fallback drawing (if cache is None or the "fallback" string)
        cv2.rectangle(frame, (0, 0), (frame.shape[1], frame.shape[0]), (0, 0, 0), -1)
        title_text = "You Win!" if game_state.win_condition_met else "Game Over!"
        title_color = (
            UIConstants.GREEN if game_state.win_condition_met else UIConstants.RED
        )
        (text_width, text_height), _ = cv2.getTextSize(
            title_text,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_XLARGE,
            UIConstants.FONT_THICKNESS + 1,
        )
        title_x = (frame.shape[1] - text_width) // 2
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
        score_text = f"Final Score: {game_state.score}"
        (score_width, score_height), _ = cv2.getTextSize(
            score_text,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.FONT_THICKNESS,
        )
        score_x = (frame.shape[1] - score_width) // 2
        score_y = title_y + text_height + 30
        cv2.putText(
            frame,
            score_text,
            (score_x, score_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )

    # Draw Buttons (Common) - Using the improved _draw_button from menu_utils
    button_width, button_height, button_y, button_spacing = (
        200,
        50,
        frame.shape[0] - 90,  # Position buttons lower
        60,
    )
    total_button_width = button_width * 2 + button_spacing
    start_x = (frame.shape[1] - total_button_width) // 2
    new_game_x = start_x
    new_game_rect = (new_game_x, button_y, button_width, button_height)

    # Use Blue for New Game button
    _draw_button(
        frame,
        new_game_x,
        button_y,
        button_width,
        button_height,
        "New Game",
        UIConstants.CV2_BLUE,
        # font_scale/thickness are handled by the improved _draw_button defaults
    )

    action_new_game = "new_game_from_gameover"
    leaderboard_x = new_game_x + button_width + button_spacing
    leaderboard_rect = (leaderboard_x, button_y, button_width, button_height)

    # Use Blue for Leaderboard button
    _draw_button(
        frame,
        leaderboard_x,
        button_y,
        button_width,
        button_height,
        "Leaderboard",
        UIConstants.CV2_BLUE,
        # font_scale/thickness are handled by the improved _draw_button defaults
    )

    action_leaderboard = "show_leaderboard_from_gameover"

    # Update game_state submenu items
    if hasattr(game_state, "submenu_items"):
        game_state.submenu_items = [
            (new_game_rect, action_new_game, "New Game"),
            (leaderboard_rect, action_leaderboard, "Leaderboard"),
        ]
    else:
        logger.warning(
            "game_state object missing submenu_items attribute in _draw_game_over_screen"
        )

    # Set menu bounds
    if hasattr(game_state, "menu_pos"):
        game_state.menu_pos, game_state.menu_width, game_state.menu_height = (
            (0, 0),
            frame.shape[1],
            frame.shape[0],
        )
    else:
        logger.warning(
            "game_state object missing menu_pos/width/height attributes in _draw_game_over_screen"
        )


# New function to display the splash screen modally
def display_modal_splash(game_state: "GameState") -> None:
    """
    Displays a modal splash screen (splash.png) and waits for a key press or window close.
    This runs its own temporary display loop.
    """
    logger.info("Displaying modal splash screen...")
    # Use splash.png for the 'About' splash
    splash_path = GameConstants.SPLASH_SCREEN_FILE  # Using "splash.png"

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
                logger.info(f"Loaded '{splash_path}' for modal splash.")
            else:
                logger.error(f"Failed to load or empty image at '{splash_path}'.")
        else:
            logger.warning(f"Splash image file not found: '{splash_path}'.")

    except Exception as e:
        logger.error(f"Error processing splash image '{splash_path}': {e}")

    # Prepare display frame (image or fallback)
    display_frame = np.zeros(
        (UIConstants.WINDOW_HEIGHT, UIConstants.WINDOW_WIDTH, 3), dtype=np.uint8
    )
    display_frame[:, :] = UIConstants.BLACK  # Default black background

    if splash_image is not None:
        display_frame = splash_image.copy()
        message = "Press any key to continue..."
        text_color = UIConstants.YELLOW
    else:
        # Fallback text if image failed
        message = "Splash Image Unavailable. Press any key..."
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

    # Add instruction text
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

    # Temporary display loop
    while True:
        try:
            # Check if window is still open
            if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                logger.warning("Modal splash window closed by user (X button).")
                # Cannot call clean_exit directly here easily without access to all params.
                # The main loop's check should eventually catch the closed window.
                break

            cv2.imshow(UIConstants.WINDOW_NAME, display_frame)
            key = cv2.waitKey(30)  # Wait for 30ms

            # Break loop if any key is pressed (key != -1) or window closed (checked above)
            if key != -1:
                logger.info("Key press detected, closing modal splash.")
                break

        except cv2.error as e:
            logger.error(f"OpenCV error during modal splash loop: {e}")
            break  # Exit loop on OpenCV error
        except Exception as e:
            logger.exception(f"Unexpected error in modal splash loop: {e}")
            break  # Exit loop on other errors

    logger.info("Exiting modal splash display.")
    # No explicit frame return needed, the main loop will recapture and redraw


# Use GameState type hint for return value
def show_splash_screen(supabase_url: str, supabase_key: str) -> Optional[GameState]:
    """Displays the initial loading splash screen and handles initial setup."""
    logger.info("Showing splash screen...")
    # This uses the *initial* splash screen file (splash.png by default)
    splash_path = GameConstants.SPLASH_SCREEN_FILE
    splash = cv2.imread(splash_path)
    if splash is None:
        logger.error(f"Failed to load {splash_path}. Exiting.")
        splash = np.zeros(
            (UIConstants.WINDOW_HEIGHT, UIConstants.WINDOW_WIDTH, 3), dtype=np.uint8
        )
        cv2.putText(
            splash,
            f"Error: {splash_path} not found!",
            (50, UIConstants.WINDOW_HEIGHT // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            UIConstants.RED,
            2,
        )
        try:
            # Attempt to create window if not already existing for error message
            cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL)
            cv2.imshow(UIConstants.WINDOW_NAME, splash)
            cv2.waitKey(3000)
        except cv2.error as e:
            logger.error(f"OpenCV error displaying fallback splash: {e}")
        return None

    splash = cv2.resize(splash, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
    try:
        # Ensure window exists before showing splash
        cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL)
    except cv2.error as e:
        logger.error(f"Failed to create or access named window: {e}")
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
    cv2.waitKey(1)  # Ensure splash is shown briefly

    game_state: Optional[GameState] = None
    first_frame: Optional[np.ndarray] = None

    try:
        logger.info("Initializing GameState...")
        game_state = GameState(supabase_url, supabase_key)
        logger.info("GameState initialized successfully.")

        if not game_state.camera_available:
            if game_state.static_frame is None:
                logger.error("Camera unavailable and no static frame loaded. Exiting.")
                cv2.putText(
                    splash,
                    "Error: No Camera/Static Frame",
                    (50, UIConstants.WINDOW_HEIGHT // 2 - 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    UIConstants.RED,
                    1,
                )
                cv2.imshow(UIConstants.WINDOW_NAME, splash)
                cv2.waitKey(3000)
                # Attempt to destroy window before returning None
                try:
                    cv2.destroyWindow(UIConstants.WINDOW_NAME)
                except:
                    pass
                return None
            first_frame = game_state.static_frame.copy()
            first_frame = cv2.resize(
                first_frame, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT)
            )
            logger.info("Using static frame for splash fade.")
        else:
            ret, frame_read = game_state.cap.read()
            if not ret or frame_read is None:
                logger.error("Failed to capture the first frame from camera.")
                cv2.putText(
                    splash,
                    "Error: Camera Read Failed",
                    (50, UIConstants.WINDOW_HEIGHT // 2 - 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    UIConstants.RED,
                    1,
                )
                cv2.imshow(UIConstants.WINDOW_NAME, splash)
                cv2.waitKey(3000)
                # clean_exit should handle cap release and destroyWindow
                clean_exit(
                    game_state.cap,
                    game_state.background_music,
                    game_state.background_music_on,
                    game_state,
                )
                return None
            first_frame = cv2.resize(
                frame_read, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT)
            )
            logger.info("Captured first frame for splash fade.")

    except Exception as e:
        logger.exception(f"Critical initialization error: {e}")
        cv2.putText(
            splash,
            f"Initialization Error",  # Keep error simple
            (50, UIConstants.WINDOW_HEIGHT // 2 - 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            UIConstants.RED,
            1,
        )
        cv2.imshow(UIConstants.WINDOW_NAME, splash)
        cv2.waitKey(5000)
        if game_state:
            # clean_exit should handle cap release and destroyWindow
            clean_exit(
                game_state.cap,
                game_state.background_music,
                game_state.background_music_on,
                game_state,
            )
        else:
            # Attempt to destroy window if game_state init failed
            try:
                cv2.destroyWindow(UIConstants.WINDOW_NAME)
            except:
                pass
        return None

    if first_frame is None:
        logger.error("First frame is None after init attempts. Cannot proceed.")
        cv2.putText(
            splash,
            "Error: Frame Init Failed",
            (50, UIConstants.WINDOW_HEIGHT // 2 - 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            UIConstants.RED,
            1,
        )
        cv2.imshow(UIConstants.WINDOW_NAME, splash)
        cv2.waitKey(3000)
        if game_state:
            # clean_exit should handle cap release and destroyWindow
            clean_exit(
                game_state.cap,
                game_state.background_music,
                game_state.background_music_on,
                game_state,
            )
        else:
            # Attempt to destroy window if game_state init failed
            try:
                cv2.destroyWindow(UIConstants.WINDOW_NAME)
            except:
                pass
        return None

    start_time = time.time()
    logger.info("Starting initial splash display loop with fade.")
    while (
        time.time() - start_time
        < GameConstants.SPLASH_DURATION + GameConstants.FADE_DURATION
    ):
        try:
            # Check if window closed during fade loop
            if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                logger.info("Initial splash window closed by user (X button).")
                # clean_exit should handle cap release and destroyWindow
                clean_exit(
                    game_state.cap,
                    game_state.background_music,
                    game_state.background_music_on,
                    game_state,
                )
                return None
        except cv2.error:
            logger.info(
                "Window property check failed during fade, assuming window closed."
            )
            if game_state:
                # clean_exit should handle cap release and destroyWindow
                clean_exit(
                    game_state.cap,
                    game_state.background_music,
                    game_state.background_music_on,
                    game_state,
                )
            return None

        elapsed = time.time() - start_time
        # Start with a fresh black frame each time to avoid artifacts if shapes mismatch
        display_frame = np.zeros_like(first_frame)

        try:
            # Ensure splash and first_frame have compatible shapes before blending
            if splash.shape != first_frame.shape:
                logger.warning(
                    f"Initial splash ({splash.shape}) and first frame ({first_frame.shape}) shape mismatch. Cannot fade."
                )
                # Just show splash then first frame without fade
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
                else:  # Show first frame after splash duration
                    display_frame = first_frame.copy()
            else:
                # Shapes match, proceed with fade logic
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
                elif (
                    elapsed
                    < GameConstants.SPLASH_DURATION + GameConstants.FADE_DURATION
                ):
                    alpha = (
                        max(
                            0.0,
                            1.0
                            - (elapsed - GameConstants.SPLASH_DURATION)
                            / GameConstants.FADE_DURATION,
                        )
                        if GameConstants.FADE_DURATION > 0
                        else 0.0
                    )
                    display_frame = cv2.addWeighted(
                        splash, alpha, first_frame, 1.0 - alpha, 0
                    )
                else:
                    # Ensure first_frame is displayed after fade completes
                    display_frame = first_frame.copy()

            cv2.imshow(UIConstants.WINDOW_NAME, display_frame)

        except Exception as e:
            logger.exception(f"Error during initial splash display/fade loop: {e}")
            # Attempt to show error on display_frame if possible
            try:
                cv2.putText(
                    display_frame,
                    "Display Loop Error",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    UIConstants.RED,
                    2,
                )
                cv2.imshow(UIConstants.WINDOW_NAME, display_frame)
            except:
                pass  # Ignore errors during error display

        # Allow skipping with q or Esc during fade
        key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY) & 0xFF
        if key == ord("q") or key == 27:
            logger.info("Initial splash screen skipped by user (q or ESC).")
            # clean_exit should handle cap release and destroyWindow
            clean_exit(
                game_state.cap,
                game_state.background_music,
                game_state.background_music_on,
                game_state,
            )
            return None

    logger.info("Initial splash screen finished.")
    return game_state
