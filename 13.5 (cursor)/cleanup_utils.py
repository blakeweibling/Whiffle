# cleanup_utils.py
"""
Utility function for cleanly exiting the application, ensuring game state,
including session stats, is saved.
"""

import logging
import sys
from typing import Any, Optional

import cv2
import pygame

# Import necessary constants
from constants import GameConstants

# Import helper functions used for saving game elements
# Note: save_score might be called here OR when game ends normally (timer/win)
from game_state_helpers import save_score, save_zones

# Import utility function for saving achievements
from game_state_utils import save_achievements

# Import GameState enum
from game_types import CurrentGameState

# Import UI cache clearing function
try:
    from ui import clear_ui_caches
except ImportError:

    def clear_ui_caches():
        pass  # Stub function if import fails


logger = logging.getLogger(__name__)


def clean_exit(
    cap: Optional[cv2.VideoCapture],
    background_music: Optional[pygame.mixer.Sound],
    background_music_on: bool,
    game_state: Optional[Any] = None,  # Expecting a GameState object or similar
) -> None:
    """
    Cleanly exit the game, saving state (scores, zones, achievements, stats),
    and releasing resources.
    """
    logger.info("Initiating clean exit sequence...")

    # --- Save Game State ---
    if game_state:
        try:
            # --- Save Score (if appropriate) ---
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

            # Save score if game wasn't already over and score > 0
            # (Game Over state usually saves score immediately when entered)
            current_state = getattr(game_state, "current_state", None)
            score_val = getattr(game_state, "score", 0)
            if (
                player_name != "Unknown Player"
                and current_state
                != CurrentGameState.GAME_OVER  # Don't re-save if game over already handled it
                and score_val > 0
            ):
                logger.info(f"Saving score ({score_val}) for {player_name} on exit...")
                try:
                    # Use save_score helper, passing current mode if available
                    current_mode = getattr(game_state, "game_mode", "classic")
                    save_score(game_state, player_name, mode=current_mode)
                except Exception as e:
                    logger.error(f"Error calling save_score during cleanup: {e}")
            elif player_name == "Unknown Player":
                logger.warning("Cannot save score on exit: player name unknown.")
            else:
                logger.info(
                    "Score not saved on exit (already game over or score is 0)."
                )

            # --- Flush Leaderboard ---
            if hasattr(game_state, "leaderboard") and game_state.leaderboard:
                if hasattr(game_state.leaderboard, "flush_pending_scores"):
                    logger.info("Flushing pending leaderboard scores...")
                    try:
                        game_state.leaderboard.flush_pending_scores()
                    except Exception as e:
                        logger.error(f"Error flushing leaderboard: {e}")
                else:
                    logger.warning(
                        "Leaderboard object missing flush_pending_scores method."
                    )
            else:
                logger.debug("No leaderboard found in game_state to flush.")

            # --- Save Zones ---
            logger.info("Saving zones...")
            try:
                save_zones(game_state)  # Use helper
            except Exception as e:
                logger.exception(f"Error calling save_zones during cleanup: {e}")

            # --- Save Achievements ---
            logger.info("Saving achievements...")
            try:
                ach_file = getattr(
                    GameConstants, "ACHIEVEMENTS_FILE", "achievements_status.json"
                )
                save_achievements(game_state, ach_file)  # Use util
            except Exception as e:
                logger.exception(f"Error calling save_achievements during cleanup: {e}")

            # --- >>> ADDED: End and Save Current Session Stats <<< ---
            logger.info("Ending current session data log...")
            if hasattr(game_state, "data_logger") and game_state.data_logger:
                try:
                    # Use the current score and zones from game_state
                    final_score = getattr(game_state, "score", 0)
                    zones = getattr(game_state, "scoring_zones", [])
                    game_state.data_logger.end_current_session(final_score, zones)
                    # Note: end_current_session in DataLogger handles saving the history file
                    logger.info("Current session data finalized and history saved.")
                except Exception as e:
                    logger.error(
                        f"Error ending data logger session during cleanup: {e}"
                    )
            else:
                logger.warning(
                    "Data logger not found in game_state. Cannot end session log."
                )
            # --- >>> END ADDED <<< ---

        except Exception as e:
            # Catch any broad errors during the state saving phase
            logger.exception(f"Error during game state saving/flushing on exit: {e}")
            # Continue to resource cleanup despite errors

    # --- Clear Caches ---
    logger.debug("Clearing UI and rendering caches...")
    try:
        # Clear UI text cache
        clear_ui_caches()

        # Clear any module-level caches in game_loop
        try:
            from game_loop import retro_frame_cache

            retro_frame_cache.clear()
            logger.debug("Cleared retro_frame_cache")
        except (ImportError, AttributeError):
            logger.debug("No retro_frame_cache to clear or import error")

        # Clear any game_state caches
        if game_state:
            # Clear menu cache
            if hasattr(game_state, "menu_cache") and game_state.menu_cache is not None:
                game_state.menu_cache = None
                logger.debug("Cleared game_state.menu_cache")

            # Clear any other game_state caches as necessary

    except Exception as cache_error:
        logger.error(f"Error during cache clearing: {cache_error}")

    # --- Release Resources ---
    # Quit Pygame FIRST (especially mixer)
    logger.debug("Attempting to quit Pygame mixer...")
    try:
        if pygame.mixer.get_init():
            pygame.mixer.quit()
            logger.debug("Pygame mixer quit.")
        else:
            logger.debug("Pygame mixer was not initialized.")
    except Exception as e:
        logger.exception(f"Unexpected error quitting Pygame mixer: {e}")

    logger.debug("Attempting to quit Pygame...")
    try:
        if pygame.get_init():
            pygame.quit()
            logger.debug("Pygame quit.")
        else:
            logger.debug("Pygame was not initialized.")
    except Exception as e:
        logger.exception(f"Unexpected error quitting Pygame: {e}")

    # Release Camera
    logger.debug("Attempting to release camera...")
    if cap and hasattr(cap, "release"):  # Check if cap exists and has release method
        try:
            if hasattr(cap, "isOpened") and cap.isOpened():
                cap.release()
                logger.debug("Camera released.")
            else:
                logger.debug("Camera was not opened, no release needed.")
        except Exception as e:
            logger.exception(f"Unexpected error releasing camera: {e}")
    elif cap:
        logger.warning("Camera object provided but seems invalid (no release method?).")
    else:
        logger.debug("No camera object (cap) provided to release.")

    # Destroy all OpenCV windows
    logger.debug("Attempting to destroy OpenCV windows...")
    try:
        # Check if any windows are actually open to avoid potential errors
        # Note: cv2.getWindowProperty might fail if window already closed, hence the broad except
        # A more robust check might involve tracking window creation/visibility
        cv2.destroyAllWindows()
        cv2.waitKey(1)  # Short delay might help ensure windows close
        logger.debug("cv2.destroyAllWindows() called.")
    except cv2.error as e:
        # Ignore errors like "could not find window" if they were already closed
        logger.debug(
            f"Ignoring OpenCV error destroying windows (likely already closed): {e}"
        )
    except Exception as e:
        logger.exception(f"Unexpected error destroying OpenCV windows: {e}")

    # Ensure the process exits cleanly
    logger.info("Clean exit sequence complete. Terminating process.")
    sys.exit(0)  # Exit with code 0 indicating success
