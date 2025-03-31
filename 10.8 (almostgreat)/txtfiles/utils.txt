"""
Utility functions for the Whiffle Tracker project.

This module provides helper functions for resource cleanup.
Mouse handling has been moved to input_handler.py
"""

import cv2
import logging
import pygame
import os
import sys # Keep sys if needed by clean_exit, otherwise remove
from typing import Any, Tuple, Optional # Removed Callable

# Keep only constants needed by clean_exit
from constants import UIConstants, GameConstants
# Keep imports needed by clean_exit or related saving logic if any remain
from menu import save_zones # Keep if clean_exit calls it directly or indirectly
# from leaderboard import Leaderboard # Keep only if clean_exit uses Leaderboard type hint explicitly
# from game_state_utils import save_achievements # Keep if clean_exit calls it
from game_state import CurrentGameState # Keep if clean_exit uses it

# Use existing logger
logger = logging.getLogger(__name__)

# --- Mouse Callback Helpers ---
# _process_drawing_event, _process_menu_or_gameover_click, mouse_callback MOVED to input_handler.py

# --- Resource Cleanup (Kept in utils.txt) ---

def clean_exit(cap: Optional[cv2.VideoCapture], background_music: Optional[pygame.mixer.Sound], background_music_on: bool, game_state: Optional[Any] = None) -> None:
    """Cleanly exit the game, saving state and releasing resources."""
    logger.info("Initiating clean exit...")

    # Save game state (scores, zones, achievements, high scores)
    if game_state:
        try:
            # Determine player name safely
            player_name = 'Unknown Player'
            if hasattr(game_state, 'get_current_player'):
                player = game_state.get_current_player()
                if player and hasattr(player, 'name'):
                    player_name = player.name

            # Save score if game wasn't over and score exists
            current_state_attr = getattr(game_state, 'current_state', None)
            if current_state_attr != CurrentGameState.GAME_OVER and getattr(game_state, 'score', 0) > 0:
                logger.info(f"Saving score for {player_name} on exit...")
                if hasattr(game_state, 'save_score'):
                     game_state.save_score(player_name) # save_score handles high score logic now
                else:
                     logger.warning("game_state has no save_score method.")

            # Flush leaderboard if exists
            if hasattr(game_state, 'leaderboard') and game_state.leaderboard:
                 # Check if leaderboard object itself has the flush method
                 if hasattr(game_state.leaderboard, 'flush_pending_scores'):
                      logger.info("Flushing leaderboard...")
                      game_state.leaderboard.flush_pending_scores()
                 else:
                      logger.warning("Leaderboard object has no flush_pending_scores method.")


            logger.info("Saving zones...")
            save_zones(game_state) # Assumes save_zones is still imported

            # Save achievements
            logger.info("Saving achievements...")
            try:
                # Assuming save_achievements is available in game_state or globally
                # If it was in game_state_utils, ensure it's imported here or called via game_state
                if hasattr(game_state, 'save_achievements'): # Example if it became a method
                     game_state.save_achievements(GameConstants.ACHIEVEMENTS_FILE)
                else:
                     # If it's still a separate function, make sure it's imported
                     from game_state_utils import save_achievements
                     save_achievements(game_state, GameConstants.ACHIEVEMENTS_FILE)
            except ImportError:
                logger.error("Could not import save_achievements function.")
            except AttributeError:
                 logger.error("save_achievements function/method not found on game_state.")
            except Exception as e:
                 logger.exception(f"Error saving achievements: {e}")


            # Note: High score saving is now handled within game_state.save_score based on latest logic
            # logger.info("Saving high scores...")
            # if hasattr(game_state, '_save_high_score'):
            #     game_state._save_high_score()


        except Exception as e:
            logger.exception(f"Error during game state save/flush on exit: {e}")

    # Stop background music
    if background_music and background_music_on:
        try:
            # Check if pygame mixer is still initialized
            if pygame.mixer.get_init():
                background_music.stop()
                logger.debug("Stopped background music.")
            else:
                logger.warning("Pygame mixer not initialized, cannot stop music.")
        except pygame.error as e:
            logger.error(f"Error stopping background music: {e}")
        except Exception as e:
             logger.exception(f"Unexpected error stopping music: {e}")


    # Release camera
    if cap and hasattr(cap, 'isOpened') and cap.isOpened():
        try:
            cap.release()
            logger.debug("Released camera.")
        except cv2.error as e:
            logger.error(f"Error releasing camera: {e}")
        except Exception as e:
             logger.exception(f"Unexpected error releasing camera: {e}")


    # Destroy all OpenCV windows (ensure this happens even if other steps fail)
    try:
        # Check if window exists before trying to destroy
        # Using getWindowProperty can throw error if window never created or already destroyed
        # A simple destroyAllWindows might be safer if unsure about window state
        # if UIConstants.WINDOW_NAME and cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 0:
        #     cv2.destroyWindow(UIConstants.WINDOW_NAME)
        #     logger.debug(f"Window '{UIConstants.WINDOW_NAME}' destroyed.")
        cv2.destroyAllWindows()
        cv2.waitKey(1) # Add small waitkey needed sometimes for windows to close properly
        logger.debug("Attempted destroyAllWindows().")
    except cv2.error as e:
        # Ignore errors like "window not found" which are expected if already closed
        logger.debug(f"Ignoring OpenCV error destroying windows (may be already closed): {e}")
    except Exception as e:
        logger.error(f"Generic error destroying OpenCV windows: {e}")

    # Quit Pygame
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

    # Ensure the process exits
    logger.info("Clean exit complete.")
    # Use sys.exit instead of raising SystemExit directly for standard practice
    sys.exit("Exiting Whiffle Tracker.")