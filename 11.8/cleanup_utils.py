# cleanup_utils.py
"""
Utility function for cleanly exiting the application.
"""

import cv2
import logging
import pygame
import os
import sys
from typing import Any, Tuple, Optional

# Imports potentially needed by clean_exit depending on game_state structure
# Assuming save_zones and save_achievements might be needed if not methods on game_state
from game_constants import GameConstants  # For ACHIEVEMENTS_FILE path
from menu import save_zones  # Assuming save_zones is the function to call

# If save_achievements is a separate utility:
# from game_state_utils import save_achievements
# If CurrentGameState enum is needed for checks:
from game_state import CurrentGameState

logger = logging.getLogger(__name__)


def clean_exit(
    cap: Optional[cv2.VideoCapture],
    background_music: Optional[pygame.mixer.Sound],
    background_music_on: bool,  # Keep this param even if not used directly, for consistency
    game_state: Optional[Any] = None,
) -> None:
    """Cleanly exit the game, saving state and releasing resources."""
    logger.info("Initiating clean exit...")

    # Save game state (scores, zones, achievements, high scores)
    if game_state:
        try:
            # Determine player name safely
            player_name = "Unknown Player"
            if hasattr(game_state, "get_current_player"):
                player = game_state.get_current_player()
                if player and hasattr(player, "name"):
                    player_name = player.name

            # Save score if game wasn't over and score exists
            # Check if game_state itself has the attribute 'current_state'
            if (
                hasattr(game_state, "current_state")
                and game_state.current_state != CurrentGameState.GAME_OVER
                and hasattr(game_state, "score")
                and game_state.score > 0
            ):
                logger.info(f"Saving score for {player_name} on exit...")
                if hasattr(game_state, "save_score"):
                    # save_score should handle high score logic now
                    game_state.save_score(player_name)
                else:
                    logger.warning("game_state has no save_score method.")

            # Flush leaderboard if exists
            if hasattr(game_state, "leaderboard") and game_state.leaderboard:
                # Check if leaderboard object itself has the flush method
                if hasattr(game_state.leaderboard, "flush_pending_scores"):
                    logger.info("Flushing leaderboard...")
                    game_state.leaderboard.flush_pending_scores()
                else:
                    logger.warning(
                        "Leaderboard object has no flush_pending_scores method."
                    )

            logger.info("Saving zones...")
            # Call save_zones (imported from menu)
            save_zones(game_state)

            # Save achievements
            logger.info("Saving achievements...")
            try:
                # Assuming save_achievements is available in game_state or imported
                if hasattr(game_state, "save_achievements"):  # Check if it's a method
                    game_state.save_achievements(GameConstants.ACHIEVEMENTS_FILE)
                else:
                    # If it's still a separate function, ensure it's imported
                    try:
                        from game_state_utils import save_achievements

                        save_achievements(game_state, GameConstants.ACHIEVEMENTS_FILE)
                    except ImportError:
                        logger.error(
                            "Could not import save_achievements from game_state_utils."
                        )

            except AttributeError:
                logger.error("save_achievements method/function not found.")
            except Exception as e:
                logger.exception(f"Error saving achievements: {e}")

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
    except pygame.error as e:
        logger.error(f"Error quitting Pygame: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error quitting Pygame: {e}")

    # Release camera
    if cap and hasattr(cap, "isOpened") and cap.isOpened():
        logger.debug("Attempting to release camera...")
        try:
            cap.release()
            logger.debug("Released camera.")
        except cv2.error as e:
            logger.error(f"Error releasing camera: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error releasing camera: {e}")

    # Destroy all OpenCV windows (ensure this happens even if other steps fail)
    logger.debug("Attempting to destroy OpenCV windows...")
    try:
        cv2.destroyAllWindows()
        cv2.waitKey(1)  # Add small waitkey needed sometimes
        logger.debug("cv2.destroyAllWindows() called.")
    except cv2.error as e:
        # Ignore errors like "window not found"
        logger.debug(
            f"Ignoring OpenCV error destroying windows (may be already closed): {e}"
        )
    except Exception as e:
        logger.error(f"Generic error destroying OpenCV windows: {e}")

    # Ensure the process exits
    logger.info("Clean exit sequence complete. Terminating process.")
    sys.exit("Exiting Whiffle Tracker.")
