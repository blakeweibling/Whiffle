"""
Main entry point for the Whiffle Tracker project.
Initializes the game and runs the main loop.
"""

import os
import logging
from dotenv import load_dotenv
import cv2

from game_state import GameState
from game_loop import run_game_loop
from ui import show_splash_screen
from utils import clean_exit, mouse_callback
from constants import UIConstants

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Frame capture settings
CAPTURED_FRAMES_DIR = "captured_frames"
FRAME_CAPTURE_INTERVAL = 10  # Capture a frame every 10 seconds

def validate_config(supabase_url: str, supabase_key: str) -> None:
    """Validate Supabase configuration at startup."""
    if supabase_url == "https://default-supabase-url.supabase.co" or supabase_key == "default-supabase-api-key":
        logger.error("Invalid Supabase configuration. Please set SUPABASE_URL and SUPABASE_KEY in .env file.")
        raise ValueError("Invalid Supabase URL or key")

def main() -> None:
    """Run the main game loop for Whiffle Tracker."""
    load_dotenv()
    supabase_url = os.getenv("SUPABASE_URL", "https://default-supabase-url.supabase.co")
    supabase_key = os.getenv("SUPABASE_KEY", "default-supabase-api-key")
    
    validate_config(supabase_url, supabase_key)

    # Ensure captured_frames directory exists
    os.makedirs(CAPTURED_FRAMES_DIR, exist_ok=True)

    game_state = show_splash_screen(supabase_url, supabase_key)
    if game_state is None:
        return

    cv2.setMouseCallback(UIConstants.WINDOW_NAME, mouse_callback, game_state)

    print("Press 'q' to quit, 's' to start drawing a scoring zone, 'd' to toggle debug mode")

    ret, frame = game_state.cap.read()
    if ret:
        cv2.imshow(UIConstants.WINDOW_NAME, frame)
        cv2.waitKey(100)

    try:
        # Pass frame capture settings to the game loop
        run_game_loop(game_state, CAPTURED_FRAMES_DIR, FRAME_CAPTURE_INTERVAL)
    except SystemExit:
        logger.info("Program exited via clean_exit")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
        game_state.save_score(game_state.get_current_player().name)
        clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on)

if __name__ == "__main__":
    main()