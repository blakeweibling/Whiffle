# cleanup_utils.py
"""
Utility function for cleanly exiting the application.
"""

import logging
import sys
from typing import Any, Optional

import cv2
import pygame

# Import necessary constants
from constants import GameConstants
from game_state_helpers import save_score, save_zones  # <--- IMPORT HELPERS
from game_state_utils import save_achievements  # <--- IMPORT UTILS

# Import necessary utilities from correct locations
from game_types import CurrentGameState  # <--- IMPORT ENUM FROM NEW LOCATION

# Removed: from menu import save_zones
# Removed: from game_state import CurrentGameState

logger = logging.getLogger(__name__)


def clean_exit(
    cap: Optional[cv2.VideoCapture],
    background_music: Optional[pygame.mixer.Sound],
    background_music_on: bool,
    game_state: Optional[Any] = None,
) -> None:
    """Cleanly exit the game, saving state and releasing resources."""
    logger.info("Initiating clean exit...")

    # Save game state (scores, zones, achievements)
    if game_state:
        try:
            # Determine player name safely
            player_name = "Unknown Player"
            if hasattr(game_state, "get_current_player"):
                player = game_state.get_current_player()
                if player and hasattr(player, "name"):
                    player_name = player.name
                else:
                    logger.warning("Could not get valid player name during cleanup.")
            else:
                logger.warning("game_state missing get_current_player during cleanup.")

            # Save score if game wasn't over and score exists
            if (
                player_name != "Unknown Player"
                and hasattr(game_state, "current_state")
                and game_state.current_state
                != CurrentGameState.GAME_OVER  # Use imported enum
                and hasattr(game_state, "score")
                and game_state.score > 0
            ):
                logger.info(f"Saving score for {player_name} on exit...")
                save_score(game_state, player_name)  # Use helper
            elif player_name == "Unknown Player":
                logger.warning("Cannot save score on exit: player name unknown.")
            else:
                logger.info("Score not saved on exit (game over or score is 0).")

            # Flush leaderboard if exists
            if hasattr(game_state, "leaderboard") and game_state.leaderboard:
                if hasattr(game_state.leaderboard, "flush_pending_scores"):
                    logger.info("Flushing leaderboard...")
                    game_state.leaderboard.flush_pending_scores()
                else:
                    logger.warning(
                        "Leaderboard object has no flush_pending_scores method."
                    )
            else:
                logger.debug("No leaderboard found in game_state to flush.")

            # Save zones using the utility function from helpers
            logger.info("Saving zones...")
            try:
                save_zones(game_state)  # Use helper
            except Exception as e:
                logger.exception(f"Error calling save_zones during cleanup: {e}")

            # Save achievements using the utility function from utils
            logger.info("Saving achievements...")
            try:
                save_achievements(
                    game_state, GameConstants.ACHIEVEMENTS_FILE
                )  # Use util
            except Exception as e:
                logger.exception(f"Error calling save_achievements during cleanup: {e}")

        except Exception as e:
            logger.exception(f"Error during game state save/flush on exit: {e}")

    # Quit Pygame FIRST
    logger.debug("Attempting to quit Pygame...")
    try:
        if pygame.mixer.get_init():
            pygame.mixer.quit()
            logger.debug("Pygame mixer quit.")
        if pygame.get_init():
            pygame.quit()
            logger.debug("Pygame quit.")
    except Exception as e:
        logger.exception(f"Unexpected error quitting Pygame: {e}")

    # Release camera
    if cap and hasattr(cap, "isOpened") and cap.isOpened():
        logger.debug("Attempting to release camera...")
        try:
            cap.release()
            logger.debug("Released camera.")
        except Exception as e:
            logger.exception(f"Unexpected error releasing camera: {e}")
    elif cap:
        logger.debug("Camera was not opened, no need to release.")
    else:
        logger.debug("No camera object (cap) to release.")

    # Destroy all OpenCV windows
    logger.debug("Attempting to destroy OpenCV windows...")
    try:
        cv2.destroyAllWindows()
        cv2.waitKey(1)
        logger.debug("cv2.destroyAllWindows() called.")
    except Exception as e:
        logger.debug(f"Ignoring OpenCV error destroying windows: {e}")

    # Ensure the process exits
    logger.info("Clean exit sequence complete. Terminating process.")
    sys.exit("Exiting Whiffle Tracker.")
