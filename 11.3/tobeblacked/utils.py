# utils.py
"""
Utility functions for the Whiffle Tracker project.

This module provides helper functions for mouse event handling.
clean_exit function is moved to cleanup_utils.py
"""

import cv2
import logging

# Pygame, os, sys removed as they were only for clean_exit
from typing import Any, Tuple, Optional, Callable

# Imports needed for mouse_callback helpers
from constants import UIConstants, GameConstants, ScoringConstants
from menu import (
    save_zones,  # Still needed for potential future use? Keep for now.
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

# Import the modal splash function from ui_screens
from ui_screens import display_modal_splash

# DO NOT import clean_exit here

# Use existing logger
logger = logging.getLogger(__name__)

# --- clean_exit function is REMOVED from this file ---


# --- START: Mouse Callback Functions ---


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
            if (
                w > ScoringConstants.MIN_ZONE_SIZE
                and h > ScoringConstants.MIN_ZONE_SIZE
            ):
                points = ScoringConstants.DEFAULT_POINTS
                new_zone = (x1, y1, w, h, points)
                game_state.scoring_zones.append(new_zone)
                game_state.special_hole = set_special_hole(game_state.scoring_zones)
                logger.info(f"Added scoring zone: {new_zone}")
                game_state.show_notification(f"Zone Added ({points} pts)")
            else:
                logger.warning(
                    f"Ignoring drawn zone with width/height <= {ScoringConstants.MIN_ZONE_SIZE}."
                )
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
    # Check if current state requires menu processing
    if game_state.current_state not in [
        CurrentGameState.MENU,
        CurrentGameState.GAME_OVER,
    ]:
        return False

    menu_x, menu_y = game_state.menu_pos
    menu_w, menu_h = game_state.menu_width, game_state.menu_height

    # Check if the click is within the general menu/game over area bounds
    # Ensure menu_w and menu_h are valid before check
    if menu_w <= 0 or menu_h <= 0:
        logger.debug("Menu dimensions are invalid, skipping click processing.")
        return False  # Cannot process click if menu dimensions are not set

    if not (menu_x <= x < menu_x + menu_w and menu_y <= y < menu_y + menu_h):
        # For GAME_OVER state, clicks outside buttons should be ignored
        if game_state.current_state == CurrentGameState.GAME_OVER:
            logger.debug("Click outside buttons on GAME_OVER screen.")
            return False  # Don't handle clicks outside buttons on this screen
        else:
            # Optionally, close menu if clicking outside in MENU state
            # logger.debug("Click outside MENU area.")
            # game_state.current_state = CurrentGameState.PLAYING
            # game_state.submenu_active = None
            # game_state.menu_cache = None
            # return True # Consume the click
            return False  # Or ignore clicks outside menu

    # Calculate click position relative to the menu/screen origin
    relative_x = x - menu_x
    relative_y = y - menu_y

    logger.debug(
        f"Click detected within {game_state.current_state} bounds at window ({x}, {y}), relative ({relative_x}, {relative_y}). Checking items..."
    )

    # Iterate through clickable items defined for the current state/submenu
    # game_state.submenu_items stores [(rect, action, label), ...]
    # Check if submenu_items exists and is iterable
    if not hasattr(game_state, "submenu_items") or not isinstance(
        game_state.submenu_items, list
    ):
        logger.warning(
            f"submenu_items not found or not a list in state {game_state.current_state}. Cannot process click."
        )
        return False

    for item_rect, action, label in game_state.submenu_items:
        # Ensure item_rect is valid
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
                game_state.menu_cache = None  # Invalidate cache after any action

            # Handle callable actions (like toggles in settings)
            if isinstance(action, Callable):
                logger.debug("Action is Callable.")
                action()
                # If the action was in the menu, invalidate the cache to force redraw
                if game_state.current_state == CurrentGameState.MENU:
                    game_state.menu_cache = None
                return True  # Click handled

            # Handle string-based actions
            elif isinstance(action, str):
                logger.debug("Action is string. Checking specific string values...")

                # --- Universal Actions ---
                if action == "quit":
                    logger.debug("Action matched: 'quit'")
                    # clean_exit is now imported separately or handled by caller
                    # Need to import it if used here:
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
                    # clean_exit raises SystemExit
                    return True

                # --- Menu State Actions ---
                if game_state.current_state == CurrentGameState.MENU:
                    logger.debug("Processing actions for MENU state...")

                    # === MODIFICATION: Handle "show_splash" action ===
                    if action == "show_splash":
                        logger.debug("Action matched: 'show_splash'")
                        # Directly call the modal display function
                        display_modal_splash(game_state)
                        # No state change needed here, stay in MENU
                        # Invalidate menu cache to ensure the menu redraws correctly after splash closes
                        game_state.menu_cache = None
                        return True  # Click handled
                    # === END MODIFICATION ===

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
                        game_state.current_state = CurrentGameState.PLAYING
                        reset_editing_states()
                        game_state.submenu_active = None
                    elif action == "clear_zones":
                        logger.debug("Action matched: 'clear_zones'")
                        clear_zones(game_state)
                        reset_editing_states()
                    elif action == "save_zones":
                        logger.debug("Action matched: 'save_zones'")
                        save_zones(game_state)
                        game_state.menu_cache = None
                    elif action == "load_zones":
                        logger.debug("Action matched: 'load_zones'")
                        load_zones(game_state)
                        reset_editing_states()
                    elif action.startswith("set_mode_"):
                        logger.debug("Action matched: 'set_mode_*'")
                        new_mode = action.split("set_mode_")[1]
                        if game_state.game_mode != new_mode:
                            logger.info(f"Game mode changing to: {new_mode}")
                            game_state.save_score(
                                game_state.get_current_player().name,
                                mode=game_state.game_mode,
                            )
                            game_state.game_mode = new_mode
                            reset_game(game_state)
                        else:
                            logger.info(f"Game mode already set to: {new_mode}")
                        reset_editing_states()
                    elif action.startswith("select_player_"):
                        logger.debug("Action matched: 'select_player_*'")
                        try:
                            index = int(action.split("select_player_")[1])
                            if (
                                0 <= index < len(game_state.players)
                                and index != game_state.current_player_index
                            ):
                                game_state.save_score(
                                    game_state.get_current_player().name
                                )
                                game_state.current_player_index = index
                                logger.info(
                                    f"Switched to player: {game_state.get_current_player().name}"
                                )
                                reset_game(game_state)
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
                        reset_editing_states()
                    elif action == "add_player":
                        logger.debug("Action matched: 'add_player'")
                        if len(game_state.players) < 2:
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
                        reset_editing_states()
                    elif action == "back_to_manage_zones":
                        logger.debug("Action matched: 'back_to_manage_zones'")
                        game_state.submenu_active = "manage_zones"
                        reset_editing_states()
                    elif action.startswith("edit_zone_"):
                        logger.debug("Action matched: 'edit_zone_*'")
                        try:
                            index = int(action.split("edit_zone_")[1])
                            if 0 <= index < len(game_state.scoring_zones):
                                reset_editing_states()
                                current_points = game_state.scoring_zones[index][4]
                                game_state.editing_zone_index = index
                                game_state.editing_zone_mode = "edit_points"
                                game_state.editing_zone_points_input = str(
                                    current_points
                                )
                                game_state.menu_cache = None
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
                                reset_editing_states()
                                current_name = game_state.players[index].name
                                game_state.editing_player_index = index
                                game_state.editing_player_mode = "edit_name"
                                game_state.editing_player_name_input = str(current_name)
                                game_state.menu_cache = None
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
                                    logger.info(f"Confirmed deleting zone {index+1}.")
                                    del game_state.scoring_zones[index]
                                    game_state.special_hole = set_special_hole(
                                        game_state.scoring_zones
                                    )
                                    game_state.show_notification(
                                        f"Zone {index+1} Deleted"
                                    )
                                    reset_editing_states()
                                else:
                                    reset_editing_states()
                                    game_state.editing_zone_index = index
                                    game_state.editing_zone_mode = "confirm_delete"
                                    game_state.menu_cache = None
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
                        reset_editing_states()

                # --- Game Over State Actions ---
                elif game_state.current_state == CurrentGameState.GAME_OVER:
                    logger.debug("Processing actions for GAME_OVER state...")
                    if action == "new_game_from_gameover":
                        logger.debug("Action matched: 'new_game_from_gameover'")
                        logger.info("Starting new game from game over screen.")
                        reset_game(game_state)
                        game_state.current_state = CurrentGameState.GETTING_PLAYER_NAME
                        logger.info(f"Game state set to: {game_state.current_state}")
                        game_state.win_condition_met = False
                    elif action == "show_leaderboard_from_gameover":
                        logger.debug("Action matched: 'show_leaderboard_from_gameover'")
                        logger.info("Showing leaderboard from game over screen.")
                        game_state.current_state = CurrentGameState.MENU
                        game_state.submenu_active = "leaderboard"
                        game_state.win_condition_met = False
                        game_state.menu_cache = None

                # If we reached here, the click was on a known item and action was processed
                return True  # Click handled

    # If the loop finishes without finding a matching item
    logger.debug(
        f"Click in {game_state.current_state} area but not on a specific registered item."
    )
    return False


def mouse_callback(event: int, x: int, y: int, flags: int, param: Any) -> None:
    """Handle mouse events for the main application window."""
    game_state = param
    if game_state is None:
        logger.warning("Mouse callback received None for game_state param.")
        return

    logger.debug(
        f"Mouse event: {event} at ({x}, {y}). Current State: {game_state.current_state}, Drawing Active: {getattr(game_state, 'drawing', 'N/A')}"
    )

    click_handled = False

    # Ignore clicks during initial name input
    if game_state.current_state == CurrentGameState.GETTING_PLAYER_NAME:
        logger.debug("Ignoring mouse click during initial player name input.")
        return

    # 1. Handle click on Menu button while PLAYING
    if (
        not click_handled
        and game_state.current_state == CurrentGameState.PLAYING
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
            game_state.submenu_active = None
            game_state.menu_cache = None
            # Reset editing states
            game_state.editing_zone_index = None
            game_state.editing_zone_mode = None
            game_state.editing_zone_points_input = None
            game_state.editing_player_index = None
            game_state.editing_player_mode = None
            game_state.editing_player_name_input = None
            click_handled = True

    # 2. Handle clicks within MENU or GAME_OVER states
    elif (
        not click_handled
        and game_state.current_state
        in [CurrentGameState.MENU, CurrentGameState.GAME_OVER]
        and event == cv2.EVENT_LBUTTONDOWN
    ):
        click_handled = _process_menu_or_gameover_click(x, y, game_state)

    # 3. Handle mouse events related to drawing zones (only when PLAYING and drawing active)
    elif (
        not click_handled
        and game_state.current_state == CurrentGameState.PLAYING
        and getattr(game_state, "drawing", False)
    ):
        if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP, cv2.EVENT_MOUSEMOVE]:
            _process_drawing_event(event, x, y, game_state)
            if event != cv2.EVENT_MOUSEMOVE:
                click_handled = True

    # 4. Log unhandled clicks
    if not click_handled and event == cv2.EVENT_LBUTTONDOWN:
        logger.debug(
            f"Unhandled click at ({x},{y}) in state {game_state.current_state}"
        )


# --- END: Mouse Callback Functions ---
