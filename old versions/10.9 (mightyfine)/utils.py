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
from constants import UIConstants, GameConstants # [cite: 28]
# Keep imports needed by clean_exit or related saving logic if any remain
from menu import save_zones # [cite: 28] Keep if clean_exit calls it directly or indirectly
# from leaderboard import Leaderboard # Keep only if clean_exit uses Leaderboard type hint explicitly
# from game_state_utils import save_achievements # Keep if clean_exit calls it
from game_state import CurrentGameState # [cite: 29] Keep if clean_exit uses it

# Use existing logger
logger = logging.getLogger(__name__) # [cite: 29]

# --- Mouse Callback Helpers ---
# _process_drawing_event, _process_menu_or_gameover_click, mouse_callback MOVED to input_handler.py

# --- Resource Cleanup (Kept in utils.txt) ---

def clean_exit(cap: Optional[cv2.VideoCapture], background_music: Optional[pygame.mixer.Sound], background_music_on: bool, game_state: Optional[Any] = None) -> None: # [cite: 29]
    """Cleanly exit the game, saving state and releasing resources."""
    logger.info("Initiating clean exit...") # [cite: 29]

    # Save game state (scores, zones, achievements, high scores)
    if game_state: # [cite: 29]
        try: # [cite: 29]
            # Determine player name safely
            player_name = 'Unknown Player' # [cite: 30]
            if hasattr(game_state, 'get_current_player'): # [cite: 30]
                player = game_state.get_current_player() # [cite: 30]
                if player and hasattr(player, 'name'): # [cite: 30]
                    player_name = player.name # [cite: 30]

            # Save score if game wasn't over and score exists
            current_state_attr = getattr(game_state, 'current_state', None) # [cite: 31]
            if current_state_attr != CurrentGameState.GAME_OVER and getattr(game_state, 'score', 0) > 0: # [cite: 31]
                logger.info(f"Saving score for {player_name} on exit...") # [cite: 31]
                if hasattr(game_state, 'save_score'): # [cite: 31]
                     game_state.save_score(player_name) # [cite: 32] save_score handles high score logic now
                else: # [cite: 32]
                     logger.warning("game_state has no save_score method.") # [cite: 32]

            # Flush leaderboard if exists
            if hasattr(game_state, 'leaderboard') and game_state.leaderboard: # [cite: 32]
                 # Check if leaderboard object itself has the flush method
                 if hasattr(game_state.leaderboard, 'flush_pending_scores'): # [cite: 33]
                      logger.info("Flushing leaderboard...") # [cite: 33]
                      game_state.leaderboard.flush_pending_scores() # [cite: 33]
                 else: # [cite: 33]
                      logger.warning("Leaderboard object has no flush_pending_scores method.") # [cite: 34]


            logger.info("Saving zones...") # [cite: 34]
            save_zones(game_state) # [cite: 34] Assumes save_zones is still imported

            # Save achievements
            logger.info("Saving achievements...") # [cite: 34]
            try: # [cite: 34]
                 # Assuming save_achievements is available in game_state or globally
                # If it was in game_state_utils, ensure it's imported here or called via game_state
                if hasattr(game_state, 'save_achievements'): # [cite: 35] Example if it became a method
                     game_state.save_achievements(GameConstants.ACHIEVEMENTS_FILE) # [cite: 35]
                else: # [cite: 36]
                     # If it's still a separate function, make sure it's imported
                     from game_state_utils import save_achievements # [cite: 36]
                     save_achievements(game_state, GameConstants.ACHIEVEMENTS_FILE) # [cite: 36]
            except ImportError: # [cite: 36]
                 logger.error("Could not import save_achievements function.") # [cite: 37]
            except AttributeError: # [cite: 37]
                 logger.error("save_achievements function/method not found on game_state.") # [cite: 37]
            except Exception as e: # [cite: 37]
                 logger.exception(f"Error saving achievements: {e}") # [cite: 37]


            # Note: High score saving is now handled within game_state.save_score # [cite: 38]
            # logger.info("Saving high scores...")
            # if hasattr(game_state, '_save_high_score'):
            #     game_state._save_high_score()


        except Exception as e: # [cite: 38]
            logger.exception(f"Error during game state save/flush on exit: {e}") # [cite: 38]

    # --- MODIFICATION START ---
    # Quit Pygame FIRST
    logger.debug("Attempting to quit Pygame...")
    try: # [cite: 44]
        if pygame.mixer.get_init(): # [cite: 44]
            pygame.mixer.quit() # [cite: 44]
            logger.debug("Pygame mixer quit.") # [cite: 44]
        if pygame.get_init(): # [cite: 44]
            pygame.quit() # [cite: 44]
            logger.debug("Pygame quit.") # [cite: 44]
    except pygame.error as e: # [cite: 44]
        logger.error(f"Error quitting Pygame: {e}") # [cite: 44]
    except Exception as e: # [cite: 44]
         logger.exception(f"Unexpected error quitting Pygame: {e}") # [cite: 45]
    # --- MODIFICATION END ---


    # Release camera
    if cap and hasattr(cap, 'isOpened') and cap.isOpened(): # [cite: 40]
        logger.debug("Attempting to release camera...")
        try: # [cite: 40]
            cap.release() # [cite: 41]
            logger.debug("Released camera.") # [cite: 41]
        except cv2.error as e: # [cite: 41]
            logger.error(f"Error releasing camera: {e}") # [cite: 41]
        except Exception as e: # [cite: 41]
             logger.exception(f"Unexpected error releasing camera: {e}") # [cite: 41]


    # Destroy all OpenCV windows (ensure this happens even if other steps fail)
    logger.debug("Attempting to destroy OpenCV windows...")
    try: # [cite: 42]
        # Check if window exists before trying to destroy
        # Using getWindowProperty can throw error if window never created or already destroyed
        # A simple destroyAllWindows might be safer if unsure about window state
        # if UIConstants.WINDOW_NAME and cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 0:
        #     cv2.destroyWindow(UIConstants.WINDOW_NAME)
        #     logger.debug(f"Window '{UIConstants.WINDOW_NAME}' destroyed.")
        cv2.destroyAllWindows() # [cite: 42]
        cv2.waitKey(1) # [cite: 43] Add small waitkey needed sometimes for windows to close properly
        logger.debug("cv2.destroyAllWindows() called.") # [cite: 43]
    except cv2.error as e: # [cite: 43]
        # Ignore errors like "window not found" which are expected if already closed
        logger.debug(f"Ignoring OpenCV error destroying windows (may be already closed): {e}") # [cite: 43]
    except Exception as e: # [cite: 43]
        logger.error(f"Generic error destroying OpenCV windows: {e}") # [cite: 43]

    # Ensure the process exits
    logger.info("Clean exit sequence complete. Terminating process.") # [cite: 45]
    sys.exit("Exiting Whiffle Tracker.") # [cite: 45] Ensure this is the very last thing called