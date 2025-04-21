# ui_screens.py
import cv2
import numpy as np
import logging
import time
import os
from typing import Tuple, Optional

# Local project imports
from constants import UIConstants, GameConstants
from menu_utils import _draw_button  # Import necessary utils
from utils import clean_exit
from game_state import GameState, CurrentGameState  # Added CurrentGameState

# Import the helper function from its new location
from ui_utils import _draw_text_with_background

logger = logging.getLogger(__name__)

# Cache for game over splash image
game_over_splash_cache = None
# Cache for menu splash image
menu_splash_cache = None


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
                    logger.error(
                        f"Failed to load '{splash_path}'. Using fallback.")
                    game_over_splash_cache = "fallback"
            except Exception as e:
                logger.error(
                    f"Error loading or resizing '{splash_path}': {e}. Using fallback."
                )
                game_over_splash_cache = "fallback"
        else:
            logger.warning(f"'{splash_path}' not found. Using fallback.")
            game_over_splash_cache = "fallback"

    if game_over_splash_cache is not None and game_over_splash_cache != "fallback":
        # Use copy to avoid modifying cache
        frame[:, :] = game_over_splash_cache.copy()
    else:  # Fallback drawing
        cv2.rectangle(
            frame, (0, 0), (frame.shape[1], frame.shape[0]), (0, 0, 0), -1)
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

    # Draw Buttons (Common) - Requires _draw_button from menu_utils
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
    _draw_button(  # Make sure _draw_button is imported or defined here
        frame,
        new_game_x,
        button_y,
        button_width,
        button_height,
        "New Game",
        UIConstants.GREEN,
        font_scale=UIConstants.FONT_SCALE_MEDIUM,
    )
    action_new_game = "new_game_from_gameover"
    leaderboard_x = new_game_x + button_width + button_spacing
    leaderboard_rect = (leaderboard_x, button_y, button_width, button_height)
    _draw_button(  # Make sure _draw_button is imported or defined here
        frame,
        leaderboard_x,
        button_y,
        button_width,
        button_height,
        "Leaderboard",
        UIConstants.YELLOW,
        font_scale=UIConstants.FONT_SCALE_MEDIUM,
    )
    action_leaderboard = "show_leaderboard_from_gameover"
    # Update game_state submenu items (careful with direct state modification from UI code)
    game_state.submenu_items = [
        (new_game_rect, action_new_game, "New Game"),
        (leaderboard_rect, action_leaderboard, "Leaderboard"),
    ]
    game_state.menu_pos, game_state.menu_width, game_state.menu_height = (
        (0, 0),
        frame.shape[1],
        frame.shape[0],
    )


# Function to handle drawing the menu splash (previously inside draw_ui)
def draw_menu_splash(frame: np.ndarray, game_state: GameState) -> Optional[np.ndarray]:
    """Loads (if needed) and draws the menu splash screen."""
    global menu_splash_cache
    if menu_splash_cache is None:  # Load splash on demand
        splash_path = GameConstants.SPLASH_SCREEN_FILE
        if os.path.exists(splash_path):
            try:
                splash = cv2.imread(splash_path)
                if splash is not None:
                    splash_resized = cv2.resize(
                        splash,
                        (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT),
                    )
                    menu_splash_cache = splash_resized
                    logger.info(
                        f"Loaded and cached '{splash_path}' for menu splash.")
                else:
                    logger.error(
                        f"Failed to load '{splash_path}'. Using fallback for menu splash."
                    )
                    menu_splash_cache = "fallback"
            except Exception as e:
                logger.error(
                    f"Error loading or resizing '{splash_path}' for menu splash: {e}. Using fallback."
                )
                menu_splash_cache = "fallback"
        else:
            logger.warning(
                f"'{splash_path}' not found for menu splash. Using fallback."
            )
            menu_splash_cache = "fallback"

    # Display the cached splash or fallback
    # Check if the cache actually holds the numpy array (image)
    if isinstance(menu_splash_cache, np.ndarray):
        frame[:, :] = (
            menu_splash_cache.copy()
        )  # Display the splash over the whole frame
        # Add instruction text
        instruction_text = "Click or press any key to return"
        (tw, th), _ = cv2.getTextSize(
            instruction_text,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.FONT_THICKNESS,
        )
        nx = (UIConstants.WINDOW_WIDTH - tw) // 2
        ny = UIConstants.WINDOW_HEIGHT - 30
        _draw_text_with_background(  # Use the imported helper
            frame,
            instruction_text,
            (nx, ny),
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.YELLOW,
            UIConstants.BLACK,
            thickness=UIConstants.FONT_THICKNESS,
            alpha=0.7,
        )

    else:  # Fallback drawing if splash is None or the "fallback" string
        cv2.rectangle(
            frame, (0, 0), (frame.shape[1], frame.shape[0]), (30, 30, 30), -1)
        error_text = "Splash Image Not Found"
        (tw, th), _ = cv2.getTextSize(
            error_text,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.FONT_THICKNESS,
        )
        cv2.putText(
            frame,
            error_text,
            ((frame.shape[1] - tw) // 2, frame.shape[0] // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.RED,
            UIConstants.FONT_THICKNESS,
        )
        instruction_text = "Click or press any key to return"
        (tw_i, th_i), _ = cv2.getTextSize(
            instruction_text,
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.FONT_THICKNESS,
        )
        cv2.putText(
            frame,
            instruction_text,
            ((frame.shape[1] - tw_i) // 2, frame.shape[0] // 2 + th + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_MEDIUM,
            UIConstants.YELLOW,
            UIConstants.FONT_THICKNESS,
        )
    return menu_splash_cache  # Return the cache status/object


# Use GameState type hint for return value
def show_splash_screen(supabase_url: str, supabase_key: str) -> Optional[GameState]:
    """Displays the initial loading splash screen and handles initial setup."""
    logger.info("Showing splash screen...")
    splash_path = GameConstants.SPLASH_SCREEN_FILE
    splash = cv2.imread(splash_path)
    if splash is None:
        logger.error(f"Failed to load {splash_path}. Exiting.")
        # Create a fallback black screen with error text
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
            cv2.imshow(UIConstants.WINDOW_NAME, splash)
            cv2.waitKey(3000)  # Show error for 3 seconds
        except cv2.error as e:
            logger.error(f"OpenCV error displaying fallback splash: {e}")
        return None  # Indicate failure

    splash = cv2.resize(
        splash, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
    try:
        # Ensure window exists or create it
        cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL)
        # Set window size explicitly if needed
        # cv2.resizeWindow(UIConstants.WINDOW_NAME, UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT)
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
    cv2.waitKey(1)  # Allow window to draw

    game_state: Optional[GameState] = None  # Initialize game_state variable
    first_frame: Optional[np.ndarray] = None  # Initialize first_frame

    try:  # Initialize GameState
        logger.info("Initializing GameState...")
        game_state = GameState(supabase_url, supabase_key)
        logger.info("GameState initialized successfully.")

        if not game_state.camera_available:
            if game_state.static_frame is None:
                logger.error(
                    "Camera unavailable and no static frame loaded. Exiting.")
                # Display error on splash
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
                return None
            first_frame = game_state.static_frame.copy()
            first_frame = cv2.resize(
                first_frame, (UIConstants.WINDOW_WIDTH,
                              UIConstants.WINDOW_HEIGHT)
            )  # Ensure size match
            logger.info("Using static frame for splash fade.")
        else:
            ret, frame_read = game_state.cap.read()
            if not ret or frame_read is None:
                logger.error("Failed to capture the first frame from camera.")
                # Display error on splash
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
                clean_exit(
                    game_state.cap,
                    game_state.background_music,
                    game_state.background_music_on,
                    game_state,
                )
                return None
            first_frame = cv2.resize(
                frame_read, (UIConstants.WINDOW_WIDTH,
                             UIConstants.WINDOW_HEIGHT)
            )
            logger.info("Captured first frame for splash fade.")

    except Exception as e:  # Catch initialization errors
        logger.exception(f"Critical initialization error: {e}")
        cv2.putText(
            splash,
            f"Initialization Error: {e}",  # Show error details if possible
            (50, UIConstants.WINDOW_HEIGHT // 2 - 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,  # Smaller font for potentially long errors
            UIConstants.RED,
            1,
        )
        cv2.imshow(UIConstants.WINDOW_NAME, splash)
        cv2.waitKey(5000)  # Show error longer
        # Attempt cleanup even if game_state partially initialized
        if game_state:
            clean_exit(
                game_state.cap,
                game_state.background_music,
                game_state.background_music_on,
                game_state,
            )
        return None

    # Ensure first_frame is available for the loop
    if first_frame is None:
        logger.error(
            "First frame is None after init attempts. Cannot proceed with fade."
        )
        # Display error on splash
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
        clean_exit(
            game_state.cap,
            game_state.background_music,
            game_state.background_music_on,
            game_state,
        )
        return None

    start_time = time.time()
    logger.info("Starting splash display loop.")
    while (
        time.time() - start_time
        < GameConstants.SPLASH_DURATION + GameConstants.FADE_DURATION
    ):
        # Check for window close event
        try:
            # Check if the window is still visible/exists
            if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                logger.info("Splash window closed by user (X button).")
                clean_exit(
                    game_state.cap,
                    game_state.background_music,
                    game_state.background_music_on,
                    game_state,
                )
                return None
        except cv2.error:
            # Error likely means window was closed forcefully or doesn't exist
            logger.info(
                "Window property check failed (cv2.error), assuming window closed."
            )
            clean_exit(
                game_state.cap,
                game_state.background_music,
                game_state.background_music_on,
                game_state,
            )
            return None  # Exit if window closed

        elapsed = time.time() - start_time
        # Initialize display_frame based on first_frame's structure
        display_frame = np.zeros_like(first_frame)

        try:  # Fade logic
            if elapsed < GameConstants.SPLASH_DURATION:
                display_frame = splash.copy()  # Start with the splash
                # Add "Ready..." text only when game state is ready
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
                # Calculate fade alpha (splash fades out, first_frame fades in)
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
                # Ensure shapes match before blending
                if splash.shape == first_frame.shape:
                    display_frame = cv2.addWeighted(
                        splash, alpha, first_frame, 1.0 - alpha, 0
                    )
                else:
                    # Fallback if shapes mismatch (should not happen with resizing)
                    logger.warning(
                        "Splash/first_frame shape mismatch during fade. Displaying first_frame."
                    )
                    display_frame = first_frame.copy()
            else:
                # After fade duration, show only the first frame
                display_frame = first_frame.copy()

            cv2.imshow(UIConstants.WINDOW_NAME, display_frame)

        except Exception as e:
            logger.exception(f"Error during splash display/fade loop: {e}")
            # Attempt to show an error message on the current frame
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
            # Consider breaking the loop or handling the error more robustly

        key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY) & 0xFF
        if key == ord("q") or key == 27:  # Allow skipping splash
            logger.info("Splash screen skipped by user (q or ESC).")
            clean_exit(
                game_state.cap,
                game_state.background_music,
                game_state.background_music_on,
                game_state,
            )
            return None  # Indicate user quit

    logger.info("Splash screen finished.")
    return game_state  # Return the initialized game state
