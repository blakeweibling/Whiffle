"""
Utility functions for the Whiffle Tracker project.

This module provides helper functions for mouse event handling and resource cleanup.
"""

import cv2
import numpy as np
import logging
import pygame
import os
import sys # Added for sys.exit
from typing import Any, Tuple, Optional, Callable

from constants import UIConstants, GameConstants, ScoringConstants
# Import reset_game from menu, handle potential circularity if needed
from menu import reset_game, save_zones, load_zones, clear_zones, flush_scoring_zones
from leaderboard import Leaderboard # For type hinting
from game_state_utils import set_special_hole # Need this after deleting/editing zones
from game_state import CurrentGameState # Import state enum
# Import Player class
from player import Player

# Use existing logger
logger = logging.getLogger(__name__)

# --- Mouse Callback Helpers ---

def _process_drawing_event(event: int, x: int, y: int, game_state: Any) -> None:
    """Process mouse events for drawing scoring zones."""
    if event == cv2.EVENT_LBUTTONDOWN:
        if game_state.drawing:
            game_state.start_x, game_state.start_y = x, y
            game_state.temp_zone = None
            logger.info(f"Drawing started at ({x}, {y})")
        else:
             logger.debug("Ignoring LBUTTONDOWN for drawing, 's' key not active.")

    elif event == cv2.EVENT_MOUSEMOVE and game_state.drawing:
        if game_state.start_x is not None and game_state.start_y is not None:
            x1 = min(game_state.start_x, x)
            y1 = min(game_state.start_y, y)
            w = abs(game_state.start_x - x)
            h = abs(game_state.start_y - y)
            game_state.temp_zone = (x1, y1, w, h)

    elif event == cv2.EVENT_LBUTTONUP and game_state.drawing:
        if game_state.temp_zone:
            x1, y1, w, h = game_state.temp_zone
            if w > ScoringConstants.MIN_ZONE_SIZE and h > ScoringConstants.MIN_ZONE_SIZE:
                points = ScoringConstants.DEFAULT_POINTS
                new_zone = (x1, y1, w, h, points)
                game_state.scoring_zones.append(new_zone)
                game_state.special_hole = set_special_hole(game_state.scoring_zones)
                logger.info(f"Added scoring zone: {new_zone}")
                game_state.show_notification(f"Zone Added ({points} pts)")
            else:
                logger.warning(f"Ignoring drawn zone with width/height <= {ScoringConstants.MIN_ZONE_SIZE}.")
                game_state.show_notification("Zone too small", is_error=True)

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
        return False

    menu_x, menu_y = game_state.menu_pos
    menu_w, menu_h = game_state.menu_width, game_state.menu_height

    if not (menu_x <= x < menu_x + menu_w and menu_y <= y < menu_y + menu_h):
        return False

    relative_x = x - menu_x
    relative_y = y - menu_y

    logger.debug(f"Click detected within {game_state.current_state} bounds at window ({x}, {y}), relative ({relative_x}, {relative_y}). Checking items...")

    for item_rect, action, label in game_state.submenu_items:
        item_x, item_y, item_w, item_h = item_rect
        if item_x <= relative_x <= item_x + item_w and item_y <= relative_y <= item_y + item_h:
            logger.info(f"Clicked on item: '{label}' with action: {action} in state {game_state.current_state}")

            logger.debug(f"Checking action: '{action}' (type: {type(action)}) in state: {game_state.current_state}")

            if isinstance(action, Callable):
                logger.debug("Action is Callable.")
                action()
                if game_state.current_state == CurrentGameState.MENU:
                    game_state.menu_cache = None
            elif isinstance(action, str):
                logger.debug("Action is string. Checking specific string values...")
                if action == "quit":
                    logger.debug("Action matched: 'quit'")
                    game_state.save_score(game_state.get_current_player().name)
                    clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
                    return True

                if game_state.current_state == CurrentGameState.MENU:
                    logger.debug("Processing actions for MENU state...")
                    if action == "show_splash":
                        logger.critical("<<<<< ENTERING CORRECT 'show_splash' ACTION BLOCK >>>>>")
                        logger.info("Switching to SHOWING_SPLASH state.")
                        game_state.previous_state = game_state.current_state
                        game_state.current_state = CurrentGameState.SHOWING_SPLASH
                        game_state.menu_cache = None
                    elif action == "resume":
                        logger.debug("Action matched: 'resume'")
                        game_state.current_state = CurrentGameState.PLAYING
                        game_state.submenu_active = None; game_state.menu_cache = None
                        game_state.editing_zone_index = None; game_state.editing_zone_mode = None; game_state.editing_zone_points_input = None
                        game_state.editing_player_index = None; game_state.editing_player_mode = None; game_state.editing_player_name_input = None # Reset player edit too
                    elif action == "back_to_main":
                        logger.debug("Action matched: 'back_to_main'")
                        game_state.submenu_active = None; game_state.menu_cache = None
                        game_state.editing_zone_index = None; game_state.editing_zone_mode = None; game_state.editing_zone_points_input = None
                        game_state.editing_player_index = None; game_state.editing_player_mode = None; game_state.editing_player_name_input = None # Reset player edit too
                    elif action == "add_zone_info":
                         logger.debug("Action matched: 'add_zone_info'")
                         game_state.show_notification("Press 's', then click and drag to draw zone")
                         game_state.current_state = CurrentGameState.PLAYING
                         game_state.submenu_active = None; game_state.menu_cache = None
                    elif action == "clear_zones":
                        logger.debug("Action matched: 'clear_zones'")
                        clear_zones(game_state)
                        game_state.menu_cache = None
                    elif action == "save_zones":
                         logger.debug("Action matched: 'save_zones'")
                         save_zones(game_state)
                    elif action == "load_zones":
                        logger.debug("Action matched: 'load_zones'")
                        load_zones(game_state)
                        game_state.menu_cache = None
                    elif action.startswith("set_mode_"):
                        logger.debug("Action matched: 'set_mode_*'")
                        new_mode = action.split("set_mode_")[1]
                        if game_state.game_mode != new_mode:
                             logger.info(f"Game mode changing to: {new_mode}")
                             game_state.save_score(game_state.get_current_player().name, mode=game_state.game_mode)
                             game_state.game_mode = new_mode
                             reset_game(game_state)
                             game_state.menu_cache = None
                        else: logger.info(f"Game mode already set to: {new_mode}")
                    elif action.startswith("select_player_"):
                         logger.debug("Action matched: 'select_player_*'")
                         try:
                            index = int(action.split("select_player_")[1])
                            if 0 <= index < len(game_state.players) and index != game_state.current_player_index:
                                 game_state.save_score(game_state.get_current_player().name)
                                 game_state.current_player_index = index
                                 logger.info(f"Switched to player: {game_state.get_current_player().name}")
                                 reset_game(game_state) # Reset game state for the new player
                                 # Reset editing modes when switching player
                                 game_state.editing_player_index = None; game_state.editing_player_mode = None; game_state.editing_player_name_input = None
                                 game_state.editing_zone_index = None; game_state.editing_zone_mode = None; game_state.editing_zone_points_input = None
                                 game_state.menu_cache = None
                            elif index == game_state.current_player_index: logger.debug("Selected current player again.")
                            else: logger.warning(f"Invalid player index selected: {index}")
                         except (ValueError, IndexError): logger.error(f"Error parsing player index from action: {action}")
                    elif action == "add_player":
                         logger.debug("Action matched: 'add_player'")
                         if len(game_state.players) < 2:
                             player_number = len(game_state.players) + 1
                             new_player = Player(f"Player {player_number}")
                             game_state.players.append(new_player)
                             logger.info(f"Added {new_player.name}")
                             game_state.show_notification(f"{new_player.name} Added")
                             game_state.menu_cache = None # Redraw player list
                         else:
                             logger.warning("Attempted to add player when 2 players already exist.")
                             game_state.show_notification("Maximum 2 players supported", is_error=True)
                    elif action == "back_to_manage_zones":
                         logger.debug("Action matched: 'back_to_manage_zones'")
                         game_state.submenu_active = "manage_zones"
                         game_state.menu_cache = None
                         game_state.editing_zone_index = None; game_state.editing_zone_mode = None; game_state.editing_zone_points_input = None
                    elif action.startswith("edit_zone_"):
                         logger.debug("Action matched: 'edit_zone_*'")
                         try:
                             index = int(action.split("edit_zone_")[1])
                             if 0 <= index < len(game_state.scoring_zones):
                                  current_points = game_state.scoring_zones[index][4]
                                  game_state.editing_zone_index = index
                                  game_state.editing_zone_mode = 'edit_points'
                                  game_state.editing_zone_points_input = str(current_points)
                                  # Reset player editing state if starting zone edit
                                  game_state.editing_player_index = None; game_state.editing_player_mode = None; game_state.editing_player_name_input = None
                                  game_state.menu_cache = None
                                  logger.info(f"Selected zone {index+1} for editing points. Initial value: {current_points}")
                             else: logger.warning(f"Invalid zone index for edit: {index}")
                         except (ValueError, IndexError): logger.error(f"Error parsing zone index from edit action: {action}")
                    # <<< Added: Handle 'edit_player_name_{i}' action >>>
                    elif action.startswith("edit_player_name_"):
                         logger.debug("Action matched: 'edit_player_name_*'")
                         try:
                             index = int(action.split("edit_player_name_")[1])
                             if 0 <= index < len(game_state.players):
                                  current_name = game_state.players[index].name
                                  game_state.editing_player_index = index
                                  game_state.editing_player_mode = 'edit_name'
                                  game_state.editing_player_name_input = str(current_name) # Init with current name
                                  # Reset zone editing state if starting player edit
                                  game_state.editing_zone_index = None; game_state.editing_zone_mode = None; game_state.editing_zone_points_input = None
                                  game_state.menu_cache = None # Redraw needed
                                  logger.info(f"Selected player {index+1} for editing name. Initial value: '{current_name}'")
                             else:
                                  logger.warning(f"Invalid player index for edit name: {index}")
                         except (ValueError, IndexError):
                              logger.error(f"Error parsing player index from edit name action: {action}")
                    elif action.startswith("delete_zone_"):
                        logger.debug("Action matched: 'delete_zone_*'")
                        try:
                            index = int(action.split("delete_zone_")[1])
                            if 0 <= index < len(game_state.scoring_zones):
                                if game_state.editing_zone_index == index and game_state.editing_zone_mode == 'confirm_delete':
                                    logger.info(f"Confirmed deleting zone {index}.")
                                    del game_state.scoring_zones[index]
                                    game_state.special_hole = set_special_hole(game_state.scoring_zones)
                                    game_state.editing_zone_index = None; game_state.editing_zone_mode = None; game_state.editing_zone_points_input = None
                                    game_state.menu_cache = None
                                    game_state.show_notification(f"Zone {index+1} Deleted")
                                else:
                                    game_state.editing_zone_index = index
                                    game_state.editing_zone_mode = 'confirm_delete'
                                    game_state.editing_zone_points_input = None
                                    game_state.menu_cache = None
                                    logger.info(f"Selected zone {index} for deletion. Click again to confirm.")
                                    game_state.show_notification(f"Click Delete again for zone {index+1} to confirm", duration=4.0)
                            else: logger.warning(f"Invalid zone index for delete: {index}")
                        except (ValueError, IndexError): logger.error(f"Error parsing zone index from delete action: {action}")
                    else: # Default: Switch to Submenu if action wasn't handled above
                         logger.debug(f"Action '{action}' not explicitly handled, assuming submenu switch.")
                         logger.info(f"Switching to submenu: {action}")
                         game_state.submenu_active = action
                         game_state.editing_zone_index = None; game_state.editing_zone_mode = None; game_state.editing_zone_points_input = None
                         game_state.editing_player_index = None; game_state.editing_player_mode = None; game_state.editing_player_name_input = None # Reset player edit too
                         game_state.menu_cache = None

                elif game_state.current_state == CurrentGameState.GAME_OVER:
                    logger.debug("Processing actions for GAME_OVER state...")
                    if action == "new_game_from_gameover":
                        logger.debug("Action matched: 'new_game_from_gameover'")
                        logger.info("Starting new game from game over screen.")
                        reset_game(game_state)
                        game_state.current_state = CurrentGameState.PLAYING
                        game_state.win_condition_met = False
                    elif action == "show_leaderboard_from_gameover":
                        logger.debug("Action matched: 'show_leaderboard_from_gameover'")
                        logger.info("Showing leaderboard from game over screen.")
                        game_state.current_state = CurrentGameState.MENU
                        game_state.submenu_active = "leaderboard"
                        game_state.menu_cache = None
                        game_state.win_condition_met = False

            return True # Click handled

    logger.debug(f"Click in {game_state.current_state} area but not on a specific registered item.")
    return True # Consume click

# Main Mouse Callback
def mouse_callback(event: int, x: int, y: int, flags: int, param: Any) -> None:
    """Handle mouse events for the main application window."""
    game_state = param
    if game_state is None: return

    logger.debug(f"Mouse event: {event} at ({x}, {y}). State: {game_state.current_state}, Drawing: {game_state.drawing}")
    click_handled = False

    if game_state.current_state == CurrentGameState.SHOWING_SPLASH and event == cv2.EVENT_LBUTTONDOWN:
        logger.info("Click detected during splash, returning to previous state.")
        if game_state.previous_state:
            game_state.current_state = game_state.previous_state
        else:
            game_state.current_state = CurrentGameState.MENU
            logger.warning("Previous state was None when exiting splash, returning to MENU.")
        game_state.previous_state = None
        game_state.menu_cache = None
        click_handled = True

    elif not click_handled and game_state.current_state == CurrentGameState.PLAYING and event == cv2.EVENT_LBUTTONDOWN:
        if (UIConstants.MENU_BUTTON_X <= x <= UIConstants.MENU_BUTTON_X + UIConstants.MENU_BUTTON_WIDTH and
                UIConstants.MENU_BUTTON_Y <= y <= UIConstants.MENU_BUTTON_Y + UIConstants.MENU_BUTTON_HEIGHT):
            logger.info("Menu toggled ON via button click.")
            game_state.current_state = CurrentGameState.MENU
            game_state.submenu_active = None
            game_state.menu_cache = None
            click_handled = True

    elif not click_handled and game_state.current_state in [CurrentGameState.MENU, CurrentGameState.GAME_OVER] and event == cv2.EVENT_LBUTTONDOWN:
        click_handled = _process_menu_or_gameover_click(x, y, game_state)

    elif not click_handled and game_state.current_state == CurrentGameState.PLAYING and game_state.drawing:
        _process_drawing_event(event, x, y, game_state)
        if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP, cv2.EVENT_MOUSEMOVE]:
             click_handled = True

    if not click_handled and event == cv2.EVENT_LBUTTONDOWN:
         logger.debug(f"Unhandled click at ({x},{y}) in state {game_state.current_state}")


# --- Resource Cleanup ---

def clean_exit(cap: Optional[cv2.VideoCapture], background_music: Optional[pygame.mixer.Sound], background_music_on: bool, game_state: Optional[Any] = None) -> None:
    """Cleanly exit the game."""
    logger.info("Cleaning up and exiting game...")
    # ...(rest of clean_exit remains the same)...

    if game_state:
        try:
            current_state_attr = getattr(game_state, 'current_state', None)
            player = getattr(game_state, 'get_current_player', lambda: None)()
            player_name = getattr(player, 'name', 'Unknown Player') if player else 'Unknown Player'

            if current_state_attr != CurrentGameState.GAME_OVER and getattr(game_state, 'score', 0) > 0:
                 logger.info(f"Saving score for {player_name} on exit...")
                 game_state.save_score(player_name)

            if hasattr(game_state, 'leaderboard') and game_state.leaderboard:
                logger.info("Flushing leaderboard...")
                game_state.leaderboard.flush_pending_scores()

            logger.info("Saving zones...")
            save_zones(game_state) # Assuming save_zones is correctly imported or defined

            logger.info("Saving achievements...")
            try:
                from game_state_utils import save_achievements
                save_achievements(game_state, GameConstants.ACHIEVEMENTS_FILE)
            except ImportError: logger.error("Could not import save_achievements function from game_state_utils.")
            except AttributeError: logger.error("save_achievements function not found after import.")


            logger.info("Saving high scores...")
            if hasattr(game_state, '_save_high_score'):
                 game_state._save_high_score()

        except Exception as e:
             logger.exception(f"Error during game state save/flush on exit: {e}")

    if cap and hasattr(cap, 'isOpened') and cap.isOpened():
        try: cap.release(); logger.debug("Camera released")
        except Exception as e: logger.error(f"Failed to release camera: {e}")

    if background_music and background_music_on:
        try: background_music.stop(); logger.debug("Background music stopped")
        except pygame.error as e: logger.error(f"Failed to stop background music: {e}")

    try:
        if UIConstants.WINDOW_NAME and cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 0:
             cv2.destroyWindow(UIConstants.WINDOW_NAME)
             logger.debug(f"Window '{UIConstants.WINDOW_NAME}' destroyed.")
        cv2.destroyAllWindows()
        logger.debug("Attempted destroyAllWindows().")
    except cv2.error as e: logger.debug(f"Ignoring OpenCV error destroying windows: {e}")
    except Exception as e: logger.error(f"Generic error destroying OpenCV windows: {e}")

    try:
        if pygame.mixer.get_init(): pygame.mixer.quit(); logger.debug("Pygame mixer quit.")
        if pygame.get_init(): pygame.quit(); logger.debug("Pygame quit.")
    except Exception as e: logger.error(f"Error quitting Pygame: {e}")

    logger.info("Resources released, exiting program.")
    sys.exit(0) # Use sys.exit