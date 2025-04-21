"""
Utility functions for the Whiffle Tracker project.

This module provides helper functions for mouse event handling and resource cleanup.
"""

import cv2
import numpy as np
import logging
import pygame
import os
from typing import Any, Tuple, Optional, Callable

from constants import UIConstants, GameConstants, ScoringConstants
# Import reset_game from menu, handle potential circularity if needed
from menu import reset_game, save_zones, load_zones, clear_zones, flush_scoring_zones
from leaderboard import Leaderboard # For type hinting
from game_state_utils import set_special_hole # Need this after deleting/editing zones
from game_state import CurrentGameState # Import state enum

# Use existing logger
logger = logging.getLogger(__name__)

# --- Mouse Callback Helpers ---

def _process_drawing_event(event: int, x: int, y: int, game_state: Any) -> None:
    """Process mouse events for drawing scoring zones."""
    if event == cv2.EVENT_LBUTTONDOWN:
        # Start drawing only if 's' was pressed (indicated by drawing flag)
        if game_state.drawing:
            game_state.start_x, game_state.start_y = x, y
            game_state.temp_zone = None # Clear any previous temp zone remnant
            logger.info(f"Drawing started at ({x}, {y})")
        else:
             logger.debug("Ignoring LBUTTONDOWN for drawing, 's' key not active.")

    elif event == cv2.EVENT_MOUSEMOVE and game_state.drawing:
        # Update temp zone only if drawing is active
        if game_state.start_x is not None and game_state.start_y is not None:
            # Ensure width and height are calculated correctly regardless of drag direction
            x1 = min(game_state.start_x, x)
            y1 = min(game_state.start_y, y)
            w = abs(game_state.start_x - x)
            h = abs(game_state.start_y - y)
            game_state.temp_zone = (x1, y1, w, h)

    elif event == cv2.EVENT_LBUTTONUP and game_state.drawing:
        # Finalize drawing only if it was active
        if game_state.temp_zone:
            # --- Corrected Indentation Starts Here ---
            x1, y1, w, h = game_state.temp_zone
            # Basic validation: ensure width and height are positive
            if w > ScoringConstants.MIN_ZONE_SIZE and h > ScoringConstants.MIN_ZONE_SIZE: # Use constant
                points = ScoringConstants.DEFAULT_POINTS # Use default for now
                new_zone = (x1, y1, w, h, points)
                game_state.scoring_zones.append(new_zone)
                game_state.special_hole = set_special_hole(game_state.scoring_zones) # Update special hole
                logger.info(f"Added scoring zone: {new_zone}")
                game_state.show_notification(f"Zone Added ({points} pts)")
            else:
                logger.warning(f"Ignoring drawn zone with width/height <= {ScoringConstants.MIN_ZONE_SIZE}.")
                game_state.show_notification("Zone too small", is_error=True)
            # --- Corrected Indentation Ends Here ---

        # Reset drawing state regardless of success (Aligned with 'if game_state.temp_zone:')
        game_state.drawing = False
        game_state.temp_zone = None
        game_state.start_x = None
        game_state.start_y = None
        logger.info("Drawing finished.")


def _process_menu_or_gameover_click(x: int, y: int, game_state: Any) -> bool:
    """
    Process mouse clicks within the active menu, submenu, or game over screen.
    Returns True if the click was handled, False otherwise.
    """
    if game_state.current_state not in [CurrentGameState.MENU, CurrentGameState.GAME_OVER]:
        return False # Not in a state where clicks are handled this way

    # Use menu_pos, menu_width, menu_height which are set correctly
    # in draw_ui / _draw_game_over_screen
    menu_x, menu_y = game_state.menu_pos
    menu_w, menu_h = game_state.menu_width, game_state.menu_height

    # Check if click is within the active area (menu bounds or full screen for game over)
    if not (menu_x <= x < menu_x + menu_w and menu_y <= y < menu_y + menu_h):
        # Click was outside the active menu/game over screen bounds
        # Optionally close menu if clicked outside
        # if game_state.current_state == CurrentGameState.MENU:
        #     game_state.current_state = CurrentGameState.PLAYING
        #     game_state.submenu_active = None
        #     game_state.menu_cache = None
        #     logger.debug("Clicked outside menu, closing menu.")
        return False

    # Adjust click coordinates relative to the menu/screen's top-left corner
    relative_x = x - menu_x
    relative_y = y - menu_y

    logger.debug(f"Click detected within {game_state.current_state} bounds at window ({x}, {y}), relative ({relative_x}, {relative_y}). Checking items...")

    # Check click against currently displayed items (menu/submenu or game over buttons)
    for item_rect, action, label in game_state.submenu_items:
        item_x, item_y, item_w, item_h = item_rect
        if item_x <= relative_x <= item_x + item_w and item_y <= relative_y <= item_y + item_h:
            logger.info(f"Clicked on item: '{label}' with action: {action} in state {game_state.current_state}")

            # --- Handle Actions ---
            if isinstance(action, Callable): # Direct action (like settings toggles)
                action()
                if game_state.current_state == CurrentGameState.MENU:
                    game_state.menu_cache = None # Invalidate cache only if it's the actual menu
            elif isinstance(action, str):
                # --- Generic Actions (Apply across states if needed) ---
                if action == "quit":
                    game_state.save_score(game_state.get_current_player().name)
                    clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
                    return True # Exit triggered

                # --- Menu State Specific Actions ---
                if game_state.current_state == CurrentGameState.MENU:
                    if action == "resume":
                        game_state.current_state = CurrentGameState.PLAYING
                        game_state.submenu_active = None # Ensure submenu closes too
                        game_state.menu_cache = None
                        game_state.editing_zone_index = None # Reset editing state
                        game_state.editing_zone_mode = None
                        game_state.editing_zone_points_input = None # Clear input on resume
                    elif action == "back_to_main":
                        game_state.submenu_active = None
                        game_state.menu_cache = None
                        game_state.editing_zone_index = None # Reset editing state
                        game_state.editing_zone_mode = None
                        game_state.editing_zone_points_input = None # Clear input on back
                    elif action == "add_zone_info":
                         game_state.show_notification("Press 's', then click and drag to draw zone")
                         game_state.current_state = CurrentGameState.PLAYING # Exit menu to allow drawing
                         game_state.submenu_active = None
                         game_state.menu_cache = None
                         # Rely on 's' key to set drawing flag.
                    elif action == "clear_zones":
                        clear_zones(game_state)
                        game_state.menu_cache = None # Invalidate cache
                    elif action == "save_zones":
                         save_zones(game_state)
                    elif action == "load_zones":
                        load_zones(game_state)
                        game_state.menu_cache = None # Invalidate cache
                    elif action == "show_splash":
                        logger.warning("Show splash action needs rework for proper callback handling.")
                        game_state.show_notification("Show Splash NYI from menu", is_error=True)
                    elif action.startswith("set_mode_"):
                        new_mode = action.split("set_mode_")[1]
                        if game_state.game_mode != new_mode: # Only reset if mode actually changes
                             logger.info(f"Game mode changing to: {new_mode}")
                             game_state.save_score(game_state.get_current_player().name, mode=game_state.game_mode) # Save score for previous mode
                             game_state.game_mode = new_mode
                             reset_game(game_state) # Reset includes setting timer if needed
                             game_state.menu_cache = None
                        else:
                            logger.info(f"Game mode already set to: {new_mode}")
                    elif action.startswith("select_player_"):
                         try:
                            index = int(action.split("select_player_")[1])
                            if 0 <= index < len(game_state.players) and index != game_state.current_player_index:
                                 game_state.save_score(game_state.get_current_player().name) # Save old player score
                                 game_state.current_player_index = index
                                 logger.info(f"Switched to player: {game_state.get_current_player().name}")
                                 reset_game(game_state) # Reset game for new player
                                 game_state.menu_cache = None
                            elif index == game_state.current_player_index:
                                 logger.debug("Selected current player again.")
                            else:
                                 logger.warning(f"Invalid player index selected: {index}")
                         except (ValueError, IndexError):
                            logger.error(f"Error parsing player index from action: {action}")
                    elif action == "add_player":
                         logger.warning("Add Player functionality not yet implemented.")
                         game_state.show_notification("Add Player NYI", is_error=True)
                    elif action == "back_to_manage_zones": # Feature 2 Action
                         game_state.submenu_active = "manage_zones"
                         game_state.menu_cache = None
                         game_state.editing_zone_index = None
                         game_state.editing_zone_mode = None
                         game_state.editing_zone_points_input = None # <<< Clear input on back
                    elif action.startswith("edit_zone_"): # Feature 2 Action
                         try:
                             index = int(action.split("edit_zone_")[1])
                             if 0 <= index < len(game_state.scoring_zones):
                                  # <<< Modified: Initialize editing state >>>
                                  current_points = game_state.scoring_zones[index][4]
                                  game_state.editing_zone_index = index
                                  game_state.editing_zone_mode = 'edit_points'
                                  game_state.editing_zone_points_input = str(current_points) # Init with current value
                                  game_state.menu_cache = None # Redraw needed
                                  logger.info(f"Selected zone {index+1} for editing points. Initial value: {current_points}")
                                  # Removed NYI notification
                             else: logger.warning(f"Invalid zone index for edit: {index}")
                         except (ValueError, IndexError): logger.error(f"Error parsing zone index from edit action: {action}")
                    elif action.startswith("delete_zone_"): # Feature 2 Action
                        try:
                            index = int(action.split("delete_zone_")[1])
                            if 0 <= index < len(game_state.scoring_zones):
                                # If confirming delete for the *same* zone
                                if game_state.editing_zone_index == index and game_state.editing_zone_mode == 'confirm_delete':
                                    logger.info(f"Confirmed deleting zone {index}.")
                                    del game_state.scoring_zones[index]
                                    game_state.special_hole = set_special_hole(game_state.scoring_zones) # Update special hole
                                    # Reset state fully after deletion
                                    game_state.editing_zone_index = None
                                    game_state.editing_zone_mode = None
                                    game_state.editing_zone_points_input = None
                                    game_state.menu_cache = None # Redraw needed
                                    game_state.show_notification(f"Zone {index+1} Deleted")
                                else:
                                    # Initiate delete confirmation (clear any point edit state)
                                    game_state.editing_zone_index = index
                                    game_state.editing_zone_mode = 'confirm_delete'
                                    game_state.editing_zone_points_input = None # Clear point input
                                    game_state.menu_cache = None # Redraw needed
                                    logger.info(f"Selected zone {index} for deletion. Click again to confirm.")
                                    game_state.show_notification(f"Click Delete again for zone {index+1} to confirm", duration=4.0)
                            else: logger.warning(f"Invalid zone index for delete: {index}")
                        except (ValueError, IndexError): logger.error(f"Error parsing zone index from delete action: {action}")
                    else: # Default: Switch to Submenu
                         logger.info(f"Switching to submenu: {action}")
                         game_state.submenu_active = action
                         # Reset editing state when switching to other submenus
                         game_state.editing_zone_index = None
                         game_state.editing_zone_mode = None
                         game_state.editing_zone_points_input = None
                         game_state.menu_cache = None # Invalidate cache for submenu

                # --- Game Over State Specific Actions ---
                elif game_state.current_state == CurrentGameState.GAME_OVER:
                    if action == "new_game_from_gameover":
                        logger.info("Starting new game from game over screen.")
                        reset_game(game_state) # Reset score, timer, flags etc.
                        game_state.current_state = CurrentGameState.PLAYING # Change state
                        game_state.win_condition_met = False # Ensure reset
                        # No need to invalidate menu cache here
                    elif action == "show_leaderboard_from_gameover":
                        logger.info("Showing leaderboard from game over screen.")
                        game_state.current_state = CurrentGameState.MENU # Change state to Menu
                        game_state.submenu_active = "leaderboard" # Set specific submenu
                        game_state.menu_cache = None # Invalidate cache for menu redraw
                        game_state.win_condition_met = False # Ensure reset

            # Break after handling the first clicked item
            return True # Indicate click was handled
    else:
         # Click was inside active area but not on a specific button/item
         logger.debug(f"Click in {game_state.current_state} area but not on an item.")
         # Don't close menu on outside click for now
         # return False # Let other handlers potentially process it? No, consume click.
         return True # Click was in the active area, consume it even if not on button

    return False # Click was not handled by this function


# Main Mouse Callback
def mouse_callback(event: int, x: int, y: int, flags: int, param: Any) -> None:
    """
    Handle mouse events for the main application window. Delegates based on game state.

    Args:
        event: The type of mouse event (e.g., cv2.EVENT_LBUTTONDOWN).
        x: The x-coordinate of the mouse event.
        y: The y-coordinate of the mouse event.
        flags: Additional flags associated with the event.
        param: User-defined parameter, expected to be the game_state object.
    """
    game_state = param
    if game_state is None:
        logger.error("Mouse callback received None for game_state parameter.")
        return

    logger.debug(f"Mouse event: {event} at ({x}, {y}). State: {game_state.current_state}, Drawing: {game_state.drawing}")

    click_handled = False

    # 1. Handle Menu Button Toggle (Only relevant when Playing)
    if game_state.current_state == CurrentGameState.PLAYING and event == cv2.EVENT_LBUTTONDOWN:
        if (UIConstants.MENU_BUTTON_X <= x <= UIConstants.MENU_BUTTON_X + UIConstants.MENU_BUTTON_WIDTH and
                UIConstants.MENU_BUTTON_Y <= y <= UIConstants.MENU_BUTTON_Y + UIConstants.MENU_BUTTON_HEIGHT):
            logger.info("Menu toggled ON via button click.")
            game_state.current_state = CurrentGameState.MENU
            game_state.submenu_active = None # Ensure main menu starts
            game_state.menu_cache = None
            click_handled = True

    # 2. Handle Menu, Submenu, or Game Over Screen clicks
    if not click_handled and game_state.current_state in [CurrentGameState.MENU, CurrentGameState.GAME_OVER] and event == cv2.EVENT_LBUTTONDOWN:
        click_handled = _process_menu_or_gameover_click(x, y, game_state)

    # 3. Process Drawing Events (Only if Playing and drawing flag is set)
    if not click_handled and game_state.current_state == CurrentGameState.PLAYING and game_state.drawing:
        _process_drawing_event(event, x, y, game_state)
        # Assume drawing events consume the click if drawing is active
        if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP, cv2.EVENT_MOUSEMOVE]:
             click_handled = True

    # 4. Log unhandled clicks if needed
    if not click_handled and event == cv2.EVENT_LBUTTONDOWN:
         logger.debug(f"Unhandled click at ({x},{y}) in state {game_state.current_state}")


# --- Resource Cleanup ---

def clean_exit(cap: Optional[cv2.VideoCapture], background_music: Optional[pygame.mixer.Sound], background_music_on: bool, game_state: Optional[Any] = None) -> None:
    """
    Cleanly exit the game by releasing resources and flushing caches.
    Args:
        cap: The OpenCV VideoCapture object.
        background_music: The background music sound object.
        background_music_on: Whether background music is currently playing.
        game_state: The current game state to flush caches, save zones, etc.
    """
    logger.info("Cleaning up and exiting game...")

    # Save state before exiting
    if game_state:
        try:
            # Save score only if game wasn't already over (or maybe always save last known score?)
            if game_state.current_state != CurrentGameState.GAME_OVER and game_state.score > 0:
                 logger.info("Saving score on exit...")
                 game_state.save_score(game_state.get_current_player().name)

            # Flush leaderboard (submit pending scores)
            if hasattr(game_state, 'leaderboard') and game_state.leaderboard:
                logger.info("Flushing leaderboard...")
                game_state.leaderboard.flush_pending_scores()
            else:
                logger.warning("Leaderboard object not found in game_state during cleanup.")


            # Save current zones
            logger.info("Saving zones...")
            save_zones(game_state) # Save zones explicitly

            # Save achievements status
            logger.info("Saving achievements...")
            from game_state_utils import save_achievements # Avoid top-level import if circularity is concern
            save_achievements(game_state, GameConstants.ACHIEVEMENTS_FILE)

            # Save high scores (covers all modes)
            logger.info("Saving high scores...")
            game_state._save_high_score() # Use the internal method that saves all modes


        except Exception as e:
             logger.exception(f"Error during game state save/flush on exit: {e}") # Log full traceback


    # Release resources
    if cap and hasattr(cap, 'isOpened') and cap.isOpened():
        try:
            cap.release()
            logger.debug("Camera released")
        except Exception as e: # Catch broader exceptions
            logger.error(f"Failed to release camera: {e}")

    if background_music and background_music_on:
        try:
            background_music.stop()
            logger.debug("Background music stopped")
        except pygame.error as e:
            logger.error(f"Failed to stop background music: {e}")

    try:
        # Attempt to destroy specific window first
        if UIConstants.WINDOW_NAME and cv2.getWindowProperty(UIConstants.WINDOW_NAME, 0) != -1:
             cv2.destroyWindow(UIConstants.WINDOW_NAME)
             logger.debug(f"Window '{UIConstants.WINDOW_NAME}' destroyed.")
        cv2.destroyAllWindows() # Fallback for any other windows
        logger.debug("All OpenCV windows destroyed.")
    except cv2.error as e:
        logger.error(f"Error destroying OpenCV windows: {e}")
    except Exception as e:
        logger.error(f"Generic error destroying OpenCV windows: {e}")


    try:
        if pygame.mixer.get_init(): # Check if mixer is initialized before quitting
            pygame.mixer.quit()
            logger.debug("Pygame mixer quit.")
        if pygame.get_init(): # Check if pygame itself is initialized
             pygame.quit()
             logger.debug("Pygame quit.")
    except Exception as e: # Catch broader exceptions
        logger.error(f"Error quitting Pygame: {e}")

    logger.info("Resources released, exiting program.")
    os._exit(0) # Force exit if clean_exit is the final step