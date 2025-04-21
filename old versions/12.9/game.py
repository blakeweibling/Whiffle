# game.py
"""
Main entry point for the Whiffle Tracker project.
Initializes the game and runs the main loop.
"""

import logging
import os

import cv2
from dotenv import load_dotenv

# Updated imports: clean_exit from utils, mouse_callback from utils
from cleanup_utils import clean_exit
# Import constants
from constants import UIConstants
from game_loop import run_game_loop
# Import necessary classes and functions
# Import the specific utility function needed
from game_state_utils import save_score  # For exception handling
from ui_screens import show_splash_screen  # Assuming this is correct
from utils import mouse_callback  # Assuming mouse_callback remains in utils

# Set up logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


def validate_config(supabase_url: str, supabase_key: str) -> None:
    """Validate Supabase configuration at startup."""
    if not supabase_url or "default-supabase-url" in supabase_url:
        logger.error("Invalid Supabase URL. Please set SUPABASE_URL in .env file.")
        raise ValueError("Invalid Supabase URL")
    if not supabase_key or "default-supabase-api-key" in supabase_key:
        logger.error("Invalid Supabase key. Please set SUPABASE_KEY in .env file.")
        raise ValueError("Invalid Supabase key")


def main() -> None:
    """Run the main game loop for Whiffle Tracker."""
    load_dotenv()
    supabase_url = os.getenv("SUPABASE_URL")  # Get URL from env
    supabase_key = os.getenv("SUPABASE_KEY")  # Get Key from env

    try:
        validate_config(supabase_url, supabase_key)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        # Optionally, wait for user input or exit gracefully
        # input("Press Enter to exit...") # Uncomment to pause before exit
        return  # Exit if config invalid

    # Initialize game state via splash screen
    game_state = show_splash_screen(supabase_url, supabase_key)
    if game_state is None:
        logger.info(
            "Exiting due to None game_state from show_splash_screen (likely window closed or init failed)."
        )
        # No cleanup needed here as show_splash_screen should handle it if it fails
        return

    # Check for window close immediately after splash screen
    try:
        # Ensure window name is correct and window exists
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
            logger.info("Window closed after splash screen.")
            # clean_exit should be called even if window closed prematurely
            clean_exit(
                game_state.cap,
                game_state.background_music,
                game_state.background_music_on,
                game_state,
            )
            return
    except cv2.error:
        # Error likely means window doesn't exist or was closed.
        logger.info(
            "Window property check failed after splash screen (cv2.error), assuming window closed."
        )
        # Still attempt cleanup if game_state exists
        clean_exit(
            game_state.cap,
            game_state.background_music,
            game_state.background_music_on,
            game_state,
        )
        return

    # --- Set Mouse Callback ---
    try:
        # Ensure window exists before setting callback
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 1:
            cv2.setMouseCallback(UIConstants.WINDOW_NAME, mouse_callback, game_state)
            logger.debug("Mouse callback set.")
        else:
            logger.warning("Cannot set mouse callback, window not visible.")
            # Proceed without callback, or exit if essential
            # clean_exit(...) # Decide if exit is needed here
            # return
    except cv2.error as e:
        logger.error(f"Error setting mouse callback: {e}")
        # Decide how to handle this - proceed without callback or exit?
        # clean_exit(...)
        # return
    except Exception as e:
        logger.exception(f"Unexpected error setting mouse callback: {e}")
        # clean_exit(...)
        # return

    print("--- Whiffle Tracker ---")
    print("Press 'q' to quit at any time.")
    print("Press 'm' during gameplay to open the menu.")

    # --- Initial Frame Display ---
    # Ensure game_state has camera/frame attributes before accessing
    initial_frame = None
    ret = False
    if hasattr(game_state, "camera_available") and game_state.camera_available:
        if hasattr(game_state, "cap") and game_state.cap and game_state.cap.isOpened():
            ret, initial_frame = game_state.cap.read()
        else:
            logger.error(
                "Camera was expected but not available/opened for initial frame."
            )
            ret = False  # Mark as failed
    elif hasattr(game_state, "static_frame") and game_state.static_frame is not None:
        initial_frame = game_state.static_frame.copy()
        ret = True  # Static frame counts as success
    else:
        logger.error("Neither camera nor static frame available for initial display.")
        ret = False

    if ret and initial_frame is not None:
        try:
            # Ensure window exists before showing frame
            if (
                cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE)
                >= 1
            ):
                cv2.imshow(UIConstants.WINDOW_NAME, initial_frame)
                cv2.waitKey(100)  # Short delay to ensure frame displays
            else:
                logger.warning("Cannot display initial frame, window not visible.")
                # clean_exit(...) # Decide if exit needed
                # return
        except cv2.error as e:
            logger.error(f"Error showing initial frame: {e}")
            # clean_exit(...) # Decide if exit needed
            # return
    else:
        logger.error("Failed to capture or load initial frame for display.")
        clean_exit(
            getattr(game_state, "cap", None),  # Safely get attributes
            getattr(game_state, "background_music", None),
            getattr(game_state, "background_music_on", False),
            game_state,  # Pass game_state itself
        )
        return

    # --- Run Main Game Loop ---
    try:
        run_game_loop(game_state)
    except SystemExit:
        # This is expected when clean_exit is called
        logger.info("Program exited via clean_exit.")
    except Exception as e:
        logger.exception(f"Unexpected error in main loop: {e}")
        # Attempt cleanup even after an unexpected error
        # Check if game_state was successfully initialized
        if "game_state" in locals() and game_state is not None:
            try:
                # Safely attempt to save score using utility function
                player = None
                player_name = None
                if hasattr(game_state, "get_current_player"):
                    player = game_state.get_current_player()
                    if player and hasattr(player, "name"):
                        player_name = player.name

                if player_name:
                    logger.info(
                        f"Attempting to save score for {player_name} due to error..."
                    )
                    # Use the utility function
                    save_score(game_state, player_name)
                else:
                    logger.warning(
                        "Could not determine player name to save score during error handling."
                    )

            except Exception as save_error:
                logger.error(
                    f"Error attempting to save score during exception handling: {save_error}"
                )
            finally:
                # Always attempt final cleanup
                logger.info("Performing cleanup after main loop exception...")
                clean_exit(
                    getattr(game_state, "cap", None),
                    getattr(game_state, "background_music", None),
                    getattr(game_state, "background_music_on", False),
                    game_state,
                )
        else:
            logger.error(
                "game_state not initialized before exception occurred. Cannot save score or perform full cleanup."
            )
            # Minimal cleanup if game_state is not available
            try:
                logger.info("Attempting minimal cleanup (destroy windows)...")
                cv2.destroyAllWindows()
            except Exception as minimal_cleanup_error:
                logger.error(f"Error during minimal cleanup: {minimal_cleanup_error}")


if __name__ == "__main__":
    main()
