"""
Main entry point for the Whiffle Tracker project.
Initializes the game and runs the main loop.
"""

import logging
import os
from dotenv import load_dotenv
import cv2

from game_state import GameState
from game_loop import run_game_loop
from ui_screens import (
    show_splash_screen,
)  # Import show_splash_screen from its new location

# Updated imports: clean_exit from utils, mouse_callback from utils
from cleanup_utils import clean_exit
from utils import mouse_callback # Import from the main utils.py
from constants import UIConstants

# Set up logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


def validate_config(supabase_url: str, supabase_key: str) -> None:
    """Validate Supabase configuration at startup."""
    if (
        supabase_url == "https://default-supabase-url.supabase.co"
        or supabase_key == "default-supabase-api-key"
    ):
        logger.error(
            "Invalid Supabase configuration. Please set SUPABASE_URL and SUPABASE_KEY in .env file."
        )
        raise ValueError("Invalid Supabase URL or key")


def main() -> None:
    """Run the main game loop for Whiffle Tracker."""
    load_dotenv()
    supabase_url = os.getenv("SUPABASE_URL", "https://default-supabase-url.supabase.co")
    supabase_key = os.getenv("SUPABASE_KEY", "default-supabase-api-key")

    validate_config(supabase_url, supabase_key)

    game_state = show_splash_screen(supabase_url, supabase_key)
    if game_state is None:
        logger.info(
            "Exiting due to None game_state from show_splash_screen (likely window closed or initialization failed)."
        )
        return

    # Check for window close immediately after splash screen
    try:
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
            logger.info("Window closed after splash screen.")
            clean_exit(
                game_state.cap,
                game_state.background_music,
                game_state.background_music_on,
                game_state,
            )
            return
    except cv2.error:
        logger.info(
            "Window property check failed after splash screen (cv2.error), assuming window closed."
        )
        clean_exit(
            game_state.cap,
            game_state.background_music,
            game_state.background_music_on,
            game_state,
        )
        return

    # Set the mouse callback using the imported function
    cv2.setMouseCallback(UIConstants.WINDOW_NAME, mouse_callback, game_state)

    print(
        "Press 'q' to quit, 's' to start drawing a scoring zone, 'd' to toggle debug mode"
    )

    # Capture and display initial frame
    ret, frame = (
        game_state.cap.read()
        if game_state.camera_available
        else (True, game_state.static_frame.copy())
    )
    if ret and frame is not None:
        cv2.imshow(UIConstants.WINDOW_NAME, frame)
        cv2.waitKey(100)
    else:
        logger.error("Failed to capture initial frame for display.")
        clean_exit(
            game_state.cap,
            game_state.background_music,
            game_state.background_music_on,
            game_state,
        )
        return

    # Run the main game loop with exception handling
    try:
        run_game_loop(game_state)
    except SystemExit:
        # This is expected when clean_exit is called
        logger.info("Program exited via clean_exit")
    except Exception as e:
        logger.exception(f"Unexpected error in main loop: {e}")
        # Attempt cleanup even after an unexpected error
        if "game_state" in locals() and game_state is not None:
            try:
                # Safely attempt to save score
                if hasattr(game_state, "get_current_player") and hasattr(
                    game_state, "save_score"
                ):
                    player = game_state.get_current_player()
                    if player and hasattr(player, "name"):
                        game_state.save_score(player.name)
                else:
                    logger.warning(
                        "game_state object does not have get_current_player or save_score method during exception handling."
                    )
                # Perform cleanup
                clean_exit(
                    game_state.cap,
                    game_state.background_music,
                    game_state.background_music_on,
                    game_state,
                )
            except Exception as cleanup_error:
                logger.error(
                    f"Error during cleanup after main loop exception: {cleanup_error}"
                )
        else:
            logger.error(
                "game_state not initialized before exception occurred. Cannot save score or perform full cleanup."
            )
            # Minimal cleanup if game_state is not available
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass  # Ignore errors during minimal cleanup


if __name__ == "__main__":
    main()
