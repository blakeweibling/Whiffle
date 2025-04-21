"""
Main entry point for the Whiffle Tracker project.
Initializes the game and runs the main loop.
"""

import logging
import os  # Added back for os.getenv
from dotenv import load_dotenv
import cv2

from game_state import GameState
from game_loop import run_game_loop
from ui import show_splash_screen
from utils import clean_exit, mouse_callback
from constants import UIConstants

# Set up logging
# --- MODIFIED LINE ---
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
# --- END MODIFIED LINE ---
logger = logging.getLogger(__name__)

def validate_config(supabase_url: str, supabase_key: str) -> None:
    """Validate Supabase configuration at startup."""
    if supabase_url == "https://default-supabase-url.supabase.co" or supabase_key == "default-supabase-api-key":
        logger.error("Invalid Supabase configuration. Please set SUPABASE_URL and SUPABASE_KEY in .env file.")
        raise ValueError("Invalid Supabase URL or key") #

def main() -> None:
    """Run the main game loop for Whiffle Tracker."""
    load_dotenv()
    supabase_url = os.getenv("SUPABASE_URL", "https://default-supabase-url.supabase.co")
    supabase_key = os.getenv("SUPABASE_KEY", "default-supabase-api-key")

    validate_config(supabase_url, supabase_key)

    game_state = show_splash_screen(supabase_url, supabase_key)
    if game_state is None:
        return

    cv2.setMouseCallback(UIConstants.WINDOW_NAME, mouse_callback, game_state)

    print("Press 'q' to quit, 's' to start drawing a scoring zone, 'd' to toggle debug mode")

    ret, frame = game_state.cap.read() #
    if ret:
        cv2.imshow(UIConstants.WINDOW_NAME, frame)
        cv2.waitKey(100)

    try:
        run_game_loop(game_state)
    except SystemExit:
        logger.info("Program exited via clean_exit")
    except Exception as e:
        logger.exception(f"Unexpected error in main loop: {e}") # Use logger.exception to include traceback
        # Ensure game_state exists before trying to save score or clean exit
        if 'game_state' in locals() and game_state is not None:
            try:
                 # Check if get_current_player method exists before calling
                 if hasattr(game_state, 'get_current_player'):
                     player = game_state.get_current_player()
                     if player and hasattr(player, 'name'):
                         game_state.save_score(player.name)
                 else:
                      logger.warning("game_state object does not have get_current_player method during exception handling.")
                 # Pass game_state to clean_exit if available
                 clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state) # Pass game_state
            except Exception as cleanup_error:
                 logger.error(f"Error during cleanup after main loop exception: {cleanup_error}")
        else:
             logger.error("game_state not initialized before exception occurred. Cannot save score or perform full cleanup.")
             # Perform minimal cleanup if possible (e.g., destroy windows)
             try:
                 cv2.destroyAllWindows()
             except Exception:
                 pass # Ignore errors during minimal cleanup

if __name__ == "__main__":
    main()