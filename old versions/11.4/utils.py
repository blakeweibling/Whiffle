# utils.py
"""
Utility functions for the Whiffle Tracker project.

This module provides helper functions for mouse event handling.
clean_exit function is moved to cleanup_utils.py
"""

import cv2
import logging

# Pygame, os, sys removed as they were only for clean_exit
from typing import Any, Tuple, Optional, Callable # Added Callable, Any

# Imports needed for mouse_callback helpers
from constants import UIConstants, GameConstants, ScoringConstants
from menu import (
    save_zones, # Keep for now, might be needed if menu actions call it directly
    reset_game,
    load_zones,
    clear_zones,
)

# Import CurrentGameState enum
from game_state import CurrentGameState

# Import set_special_hole (used in drawing event)
from game_state_utils import set_special_hole

# Import Player class
from player import Player

# Import the new modal splash function from ui_screens
from ui_screens import display_modal_splash

# DO NOT import clean_exit here

# Use existing logger
logger = logging.getLogger(__name__)

# --- clean_exit function is REMOVED from this file ---


# --- START: Mouse Callback Functions ---


def _process_drawing_event(event: int, x: int, y: int, game_state: Any) -> None:
    """Process mouse events for drawing scoring zones."""
    # Added detailed logging inside
    if event == cv2.EVENT_LBUTTONDOWN:
        logger.debug(f"_process_drawing_event: Received LBUTTONDOWN at ({x}, {y})")
        if game_state.drawing:
            logger.debug(f"_process_drawing_event: Drawing IS active. Setting start coords.")
            game_state.start_x, game_state.start_y = x, y
            game_state.temp_zone = None # Reset temp_zone on new click
            # --- Reset points input on new draw attempt ---
            game_state.drawing_points_input = ""
            logger.info(f"Drawing started at ({x}, {y}). Points input reset.")
        else:
            # This case should ideally not be reached if called correctly from mouse_callback
            logger.warning("_process_drawing_event: LBUTTONDOWN called but game_state.drawing is False.")

    elif event == cv2.EVENT_MOUSEMOVE:
        # Only process if drawing is active AND started
        if game_state.drawing and game_state.start_x is not None and game_state.start_y is not None:
            x1 = min(game_state.start_x, x)
            y1 = min(game_state.start_y, y)
            w = abs(game_state.start_x - x)
            h = abs(game_state.start_y - y)
            game_state.temp_zone = (x1, y1, w, h)
            # logger.debug(f"MOUSEMOVE: Updated temp_zone = {game_state.temp_zone}") # Optional: can be verbose

    elif event == cv2.EVENT_LBUTTONUP:
        logger.debug(f"_process_drawing_event: Received LBUTTONUP at ({x}, {y})")
        if game_state.drawing: # Check if drawing was active
            if game_state.temp_zone:
                x1, y1, w, h = game_state.temp_zone
                logger.debug(f"Finalizing draw with temp_zone: {game_state.temp_zone}")
                if (
                    w > ScoringConstants.MIN_ZONE_SIZE
                    and h > ScoringConstants.MIN_ZONE_SIZE
                ):
                    # --- Use entered points ---
                    points_str = game_state.drawing_points_input
                    try:
                        points = int(points_str)
                        # Validate range
                        if not (1 <= points <= ScoringConstants.MAX_POINTS):
                            logger.warning(f"Entered points {points} out of range (1-{ScoringConstants.MAX_POINTS}). Using default {ScoringConstants.DEFAULT_POINTS}.")
                            points = ScoringConstants.DEFAULT_POINTS
                            game_state.show_notification(f"Points must be 1-{ScoringConstants.MAX_POINTS}. Using default.", is_error=True, duration=3.0)
                        else:
                             logger.info(f"Using entered points: {points}")
                    except ValueError:
                        logger.warning(f"Invalid points input '{points_str}'. Using default {ScoringConstants.DEFAULT_POINTS}.")
                        points = ScoringConstants.DEFAULT_POINTS
                        # Show notification only if something non-empty was entered but invalid
                        if points_str:
                              game_state.show_notification(f"Invalid points input. Using default.", is_error=True, duration=3.0)
                    # --- End using entered points ---

                    new_zone = (x1, y1, w, h, points) # Use validated/default points
                    # Check for overlap before adding
                    try:
                         # Assuming _zones_overlap exists and works correctly
                         from scoring import _zones_overlap
                         if not _zones_overlap(new_zone[:4], game_state.scoring_zones):
                              game_state.scoring_zones.append(new_zone)
                              game_state.special_hole = set_special_hole(game_state.scoring_zones)
                              logger.info(f"Added scoring zone: {new_zone}")
                              game_state.show_notification(f"Zone Added ({points} pts)")
                         else:
                              logger.warning(f"Drawn zone overlaps existing zone. Not adding.")
                              game_state.show_notification("Zone Overlaps!", is_error=True)
                    except ImportError:
                         logger.error("Could not import _zones_overlap to check overlap. Adding zone anyway.")
                         game_state.scoring_zones.append(new_zone)
                         game_state.special_hole = set_special_hole(game_state.scoring_zones)
                         logger.info(f"Added scoring zone (overlap check failed): {new_zone}")
                         game_state.show_notification(f"Zone Added ({points} pts) - Overlap Check Failed")

                else:
                    logger.warning(
                        f"Ignoring drawn zone with width/height <= {ScoringConstants.MIN_ZONE_SIZE}."
                    )
                    game_state.show_notification("Zone too small", is_error=True)
            else:
                logger.debug("LBUTTONUP received but no temp_zone was defined (likely just a click).")

            # Reset drawing state regardless of whether zone was added
            game_state.drawing = False
            game_state.temp_zone = None
            game_state.start_x = None
            game_state.start_y = None
            game_state.drawing_points_input = "" # Reset points input buffer
            logger.info("Drawing finished.")
        else:
            # This case should ideally not be reached if called correctly from mouse_callback
             logger.warning("_process_drawing_event: LBUTTONUP called but game_state.drawing is False.")


def _process_menu_or_gameover_click(x: int, y: int, game_state: Any) -> bool:
    """
    Process mouse clicks within the active menu, submenu, or game over screen.
    Returns True if the click was handled, False otherwise.
    """
    # Check if current state requires menu processing
    if game_state.current_state not in [
        CurrentGameState.MENU,
        CurrentGameState.GAME_OVER,
    ]:
        return False

    # Ensure menu attributes exist before accessing
    if not all(hasattr(game_state, attr) for attr in ['menu_pos', 'menu_width', 'menu_height']):
         logger.warning("Menu position/size attributes missing in game_state.")
         return False

    menu_x, menu_y = game_state.menu_pos
    menu_w, menu_h = game_state.menu_width, game_state.menu_height

    # Check if the click is within the general menu/game over area bounds
    # Ensure menu_w and menu_h are valid before check
    if menu_w <= 0 or menu_h <= 0:
        logger.debug("Menu dimensions are invalid, skipping click processing.")
        return False

    if not (menu_x <= x < menu_x + menu_w and menu_y <= y < menu_y + menu_h):
        # If game over, clicks outside buttons do nothing relevant here
        # If menu, clicks outside menu close it (handled in main callback if enabled)
        logger.debug(f"Click at ({x},{y}) is outside menu/gameover area bounds.")
        return False

    # Calculate click position relative to the menu/screen origin
    relative_x = x - menu_x
    relative_y = y - menu_y

    logger.debug(
        f"Click detected within {game_state.current_state} bounds at window ({x}, {y}), relative ({relative_x}, {relative_y}). Checking items..."
    )

    # Iterate through clickable items
    if not hasattr(game_state, "submenu_items") or not isinstance(
        game_state.submenu_items, list
    ):
        logger.warning(
            f"submenu_items not found or not a list in state {game_state.current_state}. Cannot process click."
        )
        return False

    for item_rect, action, label in reversed(game_state.submenu_items): # Check topmost items first
        if not isinstance(item_rect, tuple) or len(item_rect) != 4:
            logger.warning(
                f"Invalid item_rect format found: {item_rect}. Skipping item '{label}'."
            )
            continue

        item_x, item_y, item_w, item_h = item_rect
        # Check if the relative click coordinates are within the current item's rectangle
        if (
            item_x <= relative_x <= item_x + item_w
            and item_y <= relative_y <= item_y + item_h
        ):
            logger.info(
                f"Clicked on item: '{label}' with action: {action} in state {game_state.current_state}"
            )

            # --- Action Handling ---
            logger.debug(
                f"Checking action: '{action}' (type: {type(action)}) in state: {game_state.current_state}"
            )

            # Reset editing states helper function
            def reset_editing_states():
                game_state.editing_zone_index = None
                game_state.editing_zone_mode = None
                game_state.editing_zone_points_input = None
                game_state.editing_player_index = None
                game_state.editing_player_mode = None
                game_state.editing_player_name_input = None
                game_state.menu_cache = None # Invalidate cache on action

            # Handle callable actions
            if isinstance(action, Callable):
                logger.debug("Action is Callable.")
                try:
                    action()
                except Exception as e:
                    logger.error(f"Error executing callable action for '{label}': {e}")
                if game_state.current_state == CurrentGameState.MENU:
                    game_state.menu_cache = None # Invalidate cache
                return True # Click handled

            # Handle string-based actions
            elif isinstance(action, str):
                logger.debug("Action is string. Checking specific string values...")

                # Universal Quit Action
                if action == "quit":
                    logger.debug("Action matched: 'quit'")
                    try:
                        from cleanup_utils import clean_exit

                        # Attempt to save score before exiting cleanly
                        try:
                            if hasattr(game_state, "get_current_player") and hasattr(
                                game_state, "save_score"
                            ):
                                player = game_state.get_current_player()
                                if player and hasattr(player, "name"):
                                    game_state.save_score(player.name)
                        except Exception as e:
                            logger.error(f"Error saving score on quit action: {e}")
                        # Proceed with clean exit
                        clean_exit(
                            game_state.cap,
                            game_state.background_music,
                            game_state.background_music_on,
                            game_state,
                        )
                    except ImportError:
                        logger.error(
                            "Could not import clean_exit. Cannot quit properly via menu."
                        )
                    # No need to return True, clean_exit handles termination
                    # If clean_exit fails, we might fall through, but ideally it exits
                    return True # Indicate click was processed

                # Menu State Actions
                if game_state.current_state == CurrentGameState.MENU:
                    logger.debug("Processing actions for MENU state...")

                    # Updated show_splash action
                    if action == "show_splash":
                        logger.debug("Action matched: 'show_splash'")
                        # Pass the main callback function and its parameter (game_state)
                        display_modal_splash(game_state, mouse_callback, game_state)
                        game_state.menu_cache = None # Invalidate cache
                        return True # Click handled

                    elif action == "resume":
                        logger.debug("Action matched: 'resume'")
                        game_state.current_state = CurrentGameState.PLAYING
                        reset_editing_states()
                        game_state.submenu_active = None
                    elif action == "back_to_main":
                        logger.debug("Action matched: 'back_to_main'")
                        reset_editing_states()
                        game_state.submenu_active = None
                    elif action == "add_zone_info":
                        logger.debug("Action matched: 'add_zone_info'")
                        game_state.show_notification(
                            "Press 's', then click and drag to draw zone"
                        )
                        # Stay in menu? Or switch to playing? User expectation might vary.
                        # Switching to playing allows immediate 's' press.
                        game_state.current_state = CurrentGameState.PLAYING
                        reset_editing_states()
                        game_state.submenu_active = None
                    elif action == "clear_zones":
                        logger.debug("Action matched: 'clear_zones'")
                        clear_zones(game_state)
                        reset_editing_states() # Reset editing state if any
                    elif action == "save_zones":
                        logger.debug("Action matched: 'save_zones'")
                        save_zones(game_state)
                        # No state change, but invalidate cache if content depends on zones
                        game_state.menu_cache = None
                    elif action == "load_zones":
                        logger.debug("Action matched: 'load_zones'")
                        load_zones(game_state)
                        reset_editing_states() # Reset editing state if any
                    elif action.startswith("set_mode_"):
                        logger.debug("Action matched: 'set_mode_*'")
                        new_mode = action.split("set_mode_")[1]
                        if game_state.game_mode != new_mode:
                            logger.info(f"Game mode changing to: {new_mode}")
                            # Save score for old mode before resetting
                            game_state.save_score(
                                game_state.get_current_player().name,
                                mode=game_state.game_mode, # Pass the mode being left
                            )
                            game_state.game_mode = new_mode
                            reset_game(game_state) # Resets state FOR THE NEW MODE
                        else:
                            logger.info(f"Game mode already set to: {new_mode}")
                        # Always reset editing states and submenu after mode select attempt
                        reset_editing_states()
                        game_state.submenu_active = None # Go back to main menu
                        game_state.current_state = CurrentGameState.PLAYING # Or MENU? Let's go back to PLAYING
                    elif action.startswith("select_player_"):
                        logger.debug("Action matched: 'select_player_*'")
                        try:
                            index = int(action.split("select_player_")[1])
                            if (
                                0 <= index < len(game_state.players)
                                and index != game_state.current_player_index
                            ):
                                # Save score for the player being switched away from
                                game_state.save_score(
                                    game_state.get_current_player().name
                                )
                                game_state.current_player_index = index
                                logger.info(
                                    f"Switched to player: {game_state.get_current_player().name}"
                                )
                                reset_game(game_state) # Reset state for the newly selected player
                            elif index == game_state.current_player_index:
                                logger.debug("Selected current player again.")
                            else:
                                logger.warning(
                                    f"Invalid player index selected: {index}"
                                )
                        except (ValueError, IndexError) as e:
                            logger.error(
                                f"Error parsing player index from action: {action} - {e}"
                            )
                        reset_editing_states() # Reset editing state after attempt
                    elif action == "add_player":
                        logger.debug("Action matched: 'add_player'")
                        if len(game_state.players) < 2: # Limit to 2 players
                            player_number = len(game_state.players) + 1
                            new_player = Player(f"Player {player_number}")
                            game_state.players.append(new_player)
                            logger.info(f"Added {new_player.name}")
                            game_state.show_notification(f"{new_player.name} Added")
                        else:
                            logger.warning(
                                "Attempted to add player when 2 players already exist."
                            )
                            game_state.show_notification(
                                "Maximum 2 players supported", is_error=True
                            )
                        reset_editing_states() # Reset editing state after attempt
                    elif action == "back_to_manage_zones":
                        logger.debug("Action matched: 'back_to_manage_zones'")
                        game_state.submenu_active = "manage_zones"
                        reset_editing_states()
                    elif action.startswith("edit_zone_"):
                        logger.debug("Action matched: 'edit_zone_*'")
                        try:
                            index = int(action.split("edit_zone_")[1])
                            if 0 <= index < len(game_state.scoring_zones):
                                # Only reset if not already editing this specific zone
                                if not (game_state.editing_zone_index == index and game_state.editing_zone_mode == "edit_points"):
                                     reset_editing_states()
                                     current_points = game_state.scoring_zones[index][4]
                                     game_state.editing_zone_index = index
                                     game_state.editing_zone_mode = "edit_points"
                                     game_state.editing_zone_points_input = str(
                                         current_points
                                     )
                                     game_state.menu_cache = None # Invalidate cache
                                     logger.info(
                                         f"Selected zone {index+1} for editing points. Initial value: {current_points}"
                                     )
                            else:
                                logger.warning(f"Invalid zone index for edit: {index}")
                                reset_editing_states()
                        except (ValueError, IndexError) as e:
                            logger.error(
                                f"Error parsing zone index from edit action: {action} - {e}"
                            )
                            reset_editing_states()
                    elif action.startswith("edit_player_name_"):
                        logger.debug("Action matched: 'edit_player_name_*'")
                        try:
                            index = int(action.split("edit_player_name_")[1])
                            if 0 <= index < len(game_state.players):
                                 # Only reset if not already editing this specific player
                                if not (game_state.editing_player_index == index and game_state.editing_player_mode == "edit_name"):
                                     reset_editing_states()
                                     current_name = game_state.players[index].name
                                     game_state.editing_player_index = index
                                     game_state.editing_player_mode = "edit_name"
                                     # Use current name as initial input buffer
                                     game_state.editing_player_name_input = str(current_name)
                                     game_state.menu_cache = None # Invalidate cache
                                     logger.info(
                                         f"Selected player {index+1} for editing name. Initial value: '{current_name}'"
                                     )
                            else:
                                logger.warning(
                                    f"Invalid player index for edit name: {index}"
                                )
                                reset_editing_states()
                        except (ValueError, IndexError) as e:
                            logger.error(
                                f"Error parsing player index from edit name action: {action} - {e}"
                            )
                            reset_editing_states()
                    elif action.startswith("delete_zone_"):
                        logger.debug("Action matched: 'delete_zone_*'")
                        try:
                            index = int(action.split("delete_zone_")[1])
                            if 0 <= index < len(game_state.scoring_zones):
                                if (
                                    game_state.editing_zone_index == index
                                    and game_state.editing_zone_mode == "confirm_delete"
                                ):
                                    # Second click: confirm delete
                                    logger.info(f"Confirmed deleting zone {index+1}.")
                                    del game_state.scoring_zones[index]
                                    # Recalculate special hole
                                    game_state.special_hole = set_special_hole(
                                        game_state.scoring_zones
                                    )
                                    game_state.show_notification(
                                        f"Zone {index+1} Deleted"
                                    )
                                    reset_editing_states() # Reset state after delete
                                else:
                                    # First click: enter confirm mode
                                    reset_editing_states() # Reset any other editing modes
                                    game_state.editing_zone_index = index
                                    game_state.editing_zone_mode = "confirm_delete"
                                    game_state.menu_cache = None # Invalidate cache
                                    logger.info(
                                        f"Selected zone {index+1} for deletion. Click again to confirm."
                                    )
                                    game_state.show_notification(
                                        f"Click Delete again for zone {index+1} to confirm",
                                        duration=4.0,
                                    )
                            else:
                                logger.warning(
                                    f"Invalid zone index for delete: {index}"
                                )
                                reset_editing_states()
                        except (ValueError, IndexError) as e:
                            logger.error(
                                f"Error parsing zone index from delete action: {action} - {e}"
                            )
                            reset_editing_states()
                    else:
                        # Default action: Treat as submenu navigation if not handled above
                        logger.debug(
                            f"Action '{action}' not explicitly handled, assuming submenu switch."
                        )
                        logger.info(f"Switching to submenu: {action}")
                        game_state.submenu_active = action
                        reset_editing_states() # Reset editing state when switching submenus

                # Game Over State Actions
                elif game_state.current_state == CurrentGameState.GAME_OVER:
                    logger.debug("Processing actions for GAME_OVER state...")
                    if action == "new_game_from_gameover":
                        logger.debug("Action matched: 'new_game_from_gameover'")
                        logger.info("Starting new game from game over screen.")
                        reset_game(game_state)
                        # Go to name input for the new game
                        game_state.current_state = CurrentGameState.GETTING_PLAYER_NAME
                        logger.info(f"Game state set to: {game_state.current_state}")
                        game_state.win_condition_met = False # Reset win flag
                    elif action == "show_leaderboard_from_gameover":
                        logger.debug("Action matched: 'show_leaderboard_from_gameover'")
                        logger.info("Showing leaderboard from game over screen.")
                        game_state.current_state = CurrentGameState.MENU
                        game_state.submenu_active = "leaderboard"
                        game_state.win_condition_met = False # Reset win flag
                        game_state.menu_cache = None # Invalidate cache

                return True # Click handled by string action

            # If action type is neither Callable nor str, log warning
            else:
                 logger.warning(f"Clicked item '{label}' has unhandled action type: {type(action)}")
                 return True # Consider it handled to prevent fall-through

    # Click was inside menu/game over area but not on a specific item rectangle
    logger.debug(
        f"Click in {game_state.current_state} area but not on a specific registered item."
    )
    # If in menu and clicking outside buttons, potentially close menu? (optional)
    # if game_state.current_state == CurrentGameState.MENU:
    #     logger.info("Click outside menu items, closing menu.")
    #     game_state.current_state = CurrentGameState.PLAYING
    #     game_state.submenu_active = None
    #     reset_editing_states()
    #     return True # Handled by closing menu

    return False # Click not handled by any item


# --- RESTRUCTURED MOUSE CALLBACK ---
def mouse_callback(event: int, x: int, y: int, flags: int, param: Any) -> None:
    """Handle mouse events for the main application window."""
    game_state = param
    if game_state is None:
        logger.warning("Mouse callback received None for game_state param.")
        return

    # Basic log of all events for debugging if needed at TRACE level
    # logger.trace(f"Mouse event: {event} at ({x}, {y}). State: {game_state.current_state}")

    click_handled = False

    # --- Priority 1: Drawing Actions (if PLAYING and drawing is active) ---
    if (
        game_state.current_state == CurrentGameState.PLAYING
        and getattr(game_state, 'drawing', False)
        and event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONUP]
    ):
        logger.debug(f"Mouse event {event} received while drawing is active.")
        _process_drawing_event(event, x, y, game_state)
        # Mark click events (not move) as handled to prevent other checks
        if event == cv2.EVENT_LBUTTONDOWN or event == cv2.EVENT_LBUTTONUP:
            click_handled = True
        # Note: MOUSEMOVE doesn't set click_handled = True, as it's continuous

    # --- Priority 2: Clicks within MENU or GAME_OVER states ---
    # Only process LBUTTONDOWN for menu/game over items
    elif (
        not click_handled
        and game_state.current_state in [CurrentGameState.MENU, CurrentGameState.GAME_OVER]
        and event == cv2.EVENT_LBUTTONDOWN
    ):
        logger.debug(f"LBUTTONDOWN in {game_state.current_state}, checking menu items...")
        click_handled = _process_menu_or_gameover_click(x, y, game_state)

    # --- Priority 3: Menu Button Click (if PLAYING and NOT drawing) ---
    elif (
        not click_handled
        and game_state.current_state == CurrentGameState.PLAYING
        and not getattr(game_state, 'drawing', False) # Ensure not drawing
        and event == cv2.EVENT_LBUTTONDOWN
    ):
        if (
            UIConstants.MENU_BUTTON_X
            <= x
            <= UIConstants.MENU_BUTTON_X + UIConstants.MENU_BUTTON_WIDTH
            and UIConstants.MENU_BUTTON_Y
            <= y
            <= UIConstants.MENU_BUTTON_Y + UIConstants.MENU_BUTTON_HEIGHT
        ):
            logger.info("Menu toggled ON via button click.")
            game_state.current_state = CurrentGameState.MENU
            # Reset menu/editing states when opening menu
            game_state.submenu_active = None
            game_state.editing_zone_index = None
            game_state.editing_zone_mode = None
            game_state.editing_zone_points_input = None
            game_state.editing_player_index = None
            game_state.editing_player_mode = None
            game_state.editing_player_name_input = None
            game_state.menu_cache = None # Invalidate cache
            click_handled = True

    # --- Priority 4: Click outside Menu closes it (if MENU state) ---
    # (Optional behavior, uncomment if desired)
    # elif (
    #     not click_handled
    #     and game_state.current_state == CurrentGameState.MENU
    #     and event == cv2.EVENT_LBUTTONDOWN
    # ):
    #      # Check if click was outside the menu bounds calculated by _process_menu_or_gameover_click
    #      if hasattr(game_state, 'menu_pos') and hasattr(game_state, 'menu_width') and hasattr(game_state, 'menu_height'):
    #           menu_x, menu_y = game_state.menu_pos
    #           menu_w, menu_h = game_state.menu_width, game_state.menu_height
    #           if not (menu_x <= x < menu_x + menu_w and menu_y <= y < menu_y + menu_h):
    #                logger.info("Click outside menu detected, closing menu.")
    #                game_state.current_state = CurrentGameState.PLAYING
    #                game_state.submenu_active = None
    #                # Reset editing states when closing menu via outside click
    #                game_state.editing_zone_index = None
    #                game_state.editing_zone_mode = None
    #                game_state.editing_zone_points_input = None
    #                game_state.editing_player_index = None
    #                game_state.editing_player_mode = None
    #                game_state.editing_player_name_input = None
    #                game_state.menu_cache = None
    #                click_handled = True
    #      else:
    #           logger.warning("Cannot check for outside menu click, menu attributes missing.")


    # --- Log Unhandled Clicks ---
    # Log only LBUTTONDOWN that wasn't handled by any specific logic above
    if not click_handled and event == cv2.EVENT_LBUTTONDOWN:
         # Ignore clicks during initial name input state
         if game_state.current_state != CurrentGameState.GETTING_PLAYER_NAME:
              logger.debug(
                   f"Unhandled click at ({x},{y}) in state {game_state.current_state}"
              )

# --- END: Mouse Callback Functions ---