# utils_mouse_logic.py

import cv2
import logging
from typing import Any, Tuple, Optional, Callable

# Imports needed for mouse_callback helpers
from constants import UIConstants, GameConstants, ScoringConstants
from menu import (
    save_zones,
    reset_game,
    load_zones,
    clear_zones,
)

# Import CurrentGameState enum and GameState for type hints
from game_state import GameState, CurrentGameState

# Import set_special_hole
from game_state_utils import set_special_hole

# Import Player class
from player import Player

# Import the modal splash function from ui_screens
from ui_screens import display_modal_splash

# Import overlap check function
from scoring import _zones_overlap

# Potentially import clean_exit if needed directly (or handle it in the main loop)
try:
    from cleanup_utils import clean_exit
except ImportError:
    # Define a placeholder or handle the error if cleanup_utils might be missing
    def clean_exit(*args, **kwargs):
        logging.error("clean_exit function not available.")
        # Decide on fallback behavior, e.g., raise SystemExit
        raise SystemExit("Exiting due to missing cleanup_utils.")


logger = logging.getLogger(__name__)


# --- Helper: Process Interactive Zone Editing Mouse Events ---
def _process_zone_editing_event(
    event: int, x: int, y: int, game_state: GameState, get_click_loc_func: Callable
) -> bool:
    """Process mouse events during interactive zone move/resize."""
    handled = False
    zone_idx = game_state.selected_zone_for_edit

    if zone_idx is None or not (0 <= zone_idx < len(game_state.scoring_zones)):
        logger.warning("Zone editing event called with invalid selected_zone_for_edit.")
        # Reset state just in case
        game_state.zone_editing_action = None
        game_state.drag_start_pos = None
        game_state.selected_zone_for_edit = None
        game_state.original_zone_on_drag_start = None
        game_state.current_state = (
            game_state.previous_state or CurrentGameState.MENU
        ) # Revert state
        return False

    current_zone = game_state.scoring_zones[zone_idx]
    zx, zy, zw, zh, zp = current_zone # Unpack including points

    min_size = ScoringConstants.MIN_ZONE_SIZE # Minimum width/height

    if event == cv2.EVENT_LBUTTONDOWN:
        # Use the passed-in function to get click location
        click_location = get_click_loc_func(x, y, (zx, zy, zw, zh))
        if click_location:
            game_state.zone_editing_action = click_location
            game_state.drag_start_pos = (x, y)
            game_state.original_zone_on_drag_start = (
                current_zone # Store original state
            )
            logger.info(
                f"Starting zone edit action: {click_location} for zone {zone_idx} at ({x},{y})"
            )
            handled = True
        else:
             # Click outside the selected zone while in editing mode could perhaps cancel?
             logger.debug("Click outside selected zone during ZONE_EDITING state.")
             pass # Currently, clicking outside does nothing, requires ESC

    elif event == cv2.EVENT_MOUSEMOVE:
        if game_state.drag_start_pos and game_state.zone_editing_action:
            drag_x_start, drag_y_start = game_state.drag_start_pos
            dx = x - drag_x_start
            dy = y - drag_y_start

            new_x, new_y, new_w, new_h = zx, zy, zw, zh
            action = game_state.zone_editing_action

            if action == "move":
                new_x = zx + dx
                new_y = zy + dy
            elif action == "resize_tl":
                new_x = zx + dx
                new_y = zy + dy
                new_w = zw - dx
                new_h = zh - dy
            elif action == "resize_tr":
                new_y = zy + dy
                new_w = zw + dx
                new_h = zh - dy
            elif action == "resize_bl":
                new_x = zx + dx
                new_w = zw - dx
                new_h = zh + dy
            elif action == "resize_br":
                new_w = zw + dx
                new_h = zh + dy

            # Enforce minimum size during resize
            if action.startswith("resize"):
                new_w = max(min_size, new_w)
                new_h = max(min_size, new_h)
                # Adjust position if width/height change affected top-left corner
                if action == "resize_tl":
                    new_x = zx + zw - new_w
                    new_y = zy + zh - new_h
                elif action == "resize_tr":
                    new_y = zy + zh - new_h
                elif action == "resize_bl":
                    new_x = zx + zw - new_w

            # Update the zone in the list *directly* for immediate feedback
            game_state.scoring_zones[zone_idx] = (new_x, new_y, new_w, new_h, zp)
            # Update drag start position for next move event
            game_state.drag_start_pos = (x, y)
            handled = True # Mouse move during drag is handled

    elif event == cv2.EVENT_LBUTTONUP:
        if game_state.drag_start_pos and game_state.zone_editing_action:
            logger.info(
                f"Finished zone edit action: {game_state.zone_editing_action} for zone {zone_idx}"
            )

            # Final validation and overlap check
            final_zone = game_state.scoring_zones[zone_idx]
            fx, fy, fw, fh, fp = final_zone

            # Check for overlap with OTHER zones
            other_zones = [
                 z for i, z in enumerate(game_state.scoring_zones) if i != zone_idx
            ]
            if _zones_overlap(final_zone[:4], other_zones):
                logger.warning(
                    f"Edited zone {zone_idx} overlaps with another zone. Reverting."
                )
                game_state.show_notification(
                    "Edit causes overlap! Reverted.", is_error=True, duration=3.0
                )
                # Revert to original state
                if game_state.original_zone_on_drag_start:
                    game_state.scoring_zones[zone_idx] = (
                        game_state.original_zone_on_drag_start
                    )
                else:
                     # Should not happen, but maybe delete if revert fails? Risky.
                     logger.error(
                        "Cannot revert overlapping zone, original state missing!"
                    )
            else:
                logger.debug(f"Zone {zone_idx} updated to: {final_zone}")
                # Update special hole if necessary
                game_state.special_hole = set_special_hole(game_state.scoring_zones)

            # Reset editing state
            game_state.zone_editing_action = None
            game_state.drag_start_pos = None
            game_state.original_zone_on_drag_start = None
            # Stay in ZONE_EDITING state until user explicitly exits via ESC or menu
            handled = True

    return handled


# --- Drawing Event Processing ---
def _process_drawing_event(event: int, x: int, y: int, game_state: GameState) -> None:
    """Process mouse events for drawing scoring zones."""
    if event == cv2.EVENT_LBUTTONDOWN:
        if game_state.drawing:
            game_state.start_x, game_state.start_y = x, y
            game_state.temp_zone = None
            game_state.drawing_points_input = ""
            logger.info(f"Drawing started at ({x}, {y}). Points input reset.")

    elif event == cv2.EVENT_MOUSEMOVE:
        if (
            game_state.drawing
            and game_state.start_x is not None
            and game_state.start_y is not None
        ):
            x1 = min(game_state.start_x, x)
            y1 = min(game_state.start_y, y)
            w = abs(game_state.start_x - x)
            h = abs(game_state.start_y - y)
            game_state.temp_zone = (x1, y1, w, h)

    elif event == cv2.EVENT_LBUTTONUP:
        if game_state.drawing:
            if game_state.temp_zone:
                x1, y1, w, h = game_state.temp_zone
                if (
                    w > ScoringConstants.MIN_ZONE_SIZE
                    and h > ScoringConstants.MIN_ZONE_SIZE
                ):
                    points_str = game_state.drawing_points_input
                    try:
                        points = int(points_str)
                        if not (1 <= points <= ScoringConstants.MAX_POINTS):
                            logger.warning(
                                f"Entered points {points} out of range (1-{ScoringConstants.MAX_POINTS}). Using default {ScoringConstants.DEFAULT_POINTS}."
                            )
                            points = ScoringConstants.DEFAULT_POINTS
                            game_state.show_notification(
                                f"Points must be 1-{ScoringConstants.MAX_POINTS}. Using default.",
                                is_error=True,
                                duration=3.0,
                             )
                        else:
                            logger.info(f"Using entered points: {points}")
                    except ValueError:
                         logger.warning(
                            f"Invalid points input '{points_str}'. Using default {ScoringConstants.DEFAULT_POINTS}."
                        )
                         points = ScoringConstants.DEFAULT_POINTS
                         if points_str:
                            game_state.show_notification(
                                f"Invalid points input. Using default.",
                                is_error=True,
                                duration=3.0,
                            )

                    new_zone = (x1, y1, w, h, points)
                    if not _zones_overlap(new_zone[:4], game_state.scoring_zones):
                        game_state.scoring_zones.append(new_zone)
                        game_state.special_hole = set_special_hole(
                            game_state.scoring_zones
                        )
                        logger.info(f"Added scoring zone: {new_zone}")
                        game_state.show_notification(f"Zone Added ({points} pts)")
                    else:
                        logger.warning(
                            f"Drawn zone overlaps existing zone. Not adding."
                        )
                        game_state.show_notification("Zone Overlaps!", is_error=True)
                else:
                    logger.warning(
                        f"Ignoring drawn zone with width/height <= {ScoringConstants.MIN_ZONE_SIZE}."
                    )
                    game_state.show_notification("Zone too small", is_error=True)
            else:
                logger.debug(
                    "LBUTTONUP received but no temp_zone defined (likely just a click)."
                )

            game_state.drawing = False
            game_state.temp_zone = None
            game_state.start_x = None
            game_state.start_y = None
            game_state.drawing_points_input = ""
            logger.info("Drawing finished.")


# --- Menu/Game Over Click Processing ---
def _process_menu_or_gameover_click(x: int, y: int, game_state: GameState, main_mouse_callback: Callable) -> bool:
    """Process clicks within the menu or game over screen, including zone edit actions."""
    if game_state.current_state not in [
        CurrentGameState.MENU,
        CurrentGameState.GAME_OVER,
    ]:
        return False

    if not all(
        hasattr(game_state, attr) for attr in ["menu_pos", "menu_width", "menu_height"]
    ):
        logger.warning("Menu position/size attributes missing in game_state.")
        return False

    menu_x, menu_y = game_state.menu_pos
    menu_w, menu_h = game_state.menu_width, game_state.menu_height

    if menu_w <= 0 or menu_h <= 0:
        logger.debug("Menu dimensions are invalid, skipping click processing.")
        return False

    if not (menu_x <= x < menu_x + menu_w and menu_y <= y < menu_y + menu_h):
        logger.debug(f"Click at ({x},{y}) is outside menu/gameover area bounds.")
        return False

    relative_x = x - menu_x
    relative_y = y - menu_y

    logger.debug(
        f"Click detected within {game_state.current_state} bounds at window ({x}, {y}), relative ({relative_x}, {relative_y}). Checking items..."
    )

    if not hasattr(game_state, "submenu_items") or not isinstance(
        game_state.submenu_items, list
    ):
        logger.warning(
            f"submenu_items not found or not a list in state {game_state.current_state}. Cannot process click."
        )
        return False

    for item_rect, action, label in reversed(game_state.submenu_items):
        if not isinstance(item_rect, tuple) or len(item_rect) != 4:
            logger.warning(
                f"Invalid item_rect format found: {item_rect}. Skipping item '{label}'."
            )
            continue

        item_x, item_y, item_w, item_h = item_rect
        if (
            item_x <= relative_x <= item_x + item_w
            and item_y <= relative_y <= item_y + item_h
        ):
            logger.info(
                f"Clicked on item: '{label}' with action: {action} in state {game_state.current_state}"
            )

            def reset_editing_states():
                game_state.editing_zone_index = None
                game_state.editing_zone_mode = None
                game_state.editing_zone_points_input = None
                game_state.editing_player_index = None
                game_state.editing_player_mode = None
                game_state.editing_player_name_input = None
                # Don't reset interactive zone edit state here, handled by specific actions/ESC key
                game_state.menu_cache = None

            if isinstance(action, Callable):
                logger.debug("Action is Callable.")
                try:
                    # If the action is display_modal_splash, it needs the main mouse callback
                    if action.__name__ == 'display_modal_splash':
                         action(game_state, main_mouse_callback, game_state) # Pass main callback
                    else:
                         action()
                except Exception as e:
                    logger.error(f"Error executing callable action for '{label}': {e}")
                if game_state.current_state == CurrentGameState.MENU:
                    game_state.menu_cache = None
                return True

            elif isinstance(action, str):
                 logger.debug("Action is string. Checking specific string values...")

                 # Universal Quit Action
                 if action == "quit":
                    logger.debug("Action matched: 'quit'")
                    try:
                         # Attempt to save score before exiting
                         try:
                             if hasattr(game_state, "get_current_player") and hasattr(
                                 game_state, "save_score"
                             ):
                                 player = game_state.get_current_player()
                                 if player and hasattr(player, "name"):
                                     game_state.save_score(player.name)
                         except Exception as e:
                             logger.error(f"Error saving score on quit action: {e}")
                         # Call clean_exit (now imported at the top)
                         clean_exit(
                            game_state.cap,
                            game_state.background_music,
                            game_state.background_music_on,
                            game_state,
                         )
                    except NameError: # Catch if clean_exit wasn't imported
                         logger.error("clean_exit function not loaded. Cannot quit properly via menu.")
                    except Exception as e:
                         logger.error(f"Error during clean_exit call: {e}")
                         raise SystemExit("Exiting due to error during cleanup.")
                    return True # Indicate quit action was processed

                 # Menu State Actions (Logic remains the same as before)
                 if game_state.current_state == CurrentGameState.MENU:
                     logger.debug("Processing actions for MENU state...")

                     if action == "show_splash":
                        logger.debug("Action matched: 'show_splash'")
                        # Call display_modal_splash with the main mouse_callback
                        display_modal_splash(game_state, main_mouse_callback, game_state)
                        game_state.menu_cache = None
                        return True

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
                            current_player = game_state.get_current_player()
                            if current_player:
                                game_state.save_score(
                                    current_player.name,
                                    mode=game_state.game_mode,
                                )
                            game_state.game_mode = new_mode
                            reset_game(game_state)
                        else:
                            logger.info(f"Game mode already set to: {new_mode}")
                        reset_editing_states()
                        game_state.submenu_active = None
                        game_state.current_state = CurrentGameState.PLAYING
                     elif action.startswith("select_player_"):
                        logger.debug("Action matched: 'select_player_*'")
                        try:
                            index = int(action.split("select_player_")[1])
                            if (
                                0 <= index < len(game_state.players)
                                and index != game_state.current_player_index
                            ):
                                current_player = game_state.get_current_player()
                                if current_player:
                                    game_state.save_score(current_player.name)
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

                     # Zone Points Editing
                     elif action.startswith("edit_zone_"):
                        logger.debug("Action matched: 'edit_zone_*' (Points)")
                        try:
                            index = int(action.split("edit_zone_")[1])
                            if 0 <= index < len(game_state.scoring_zones):
                                if not (
                                    game_state.editing_zone_index == index
                                    and game_state.editing_zone_mode == "edit_points"
                                ):
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

                     # Interactive Zone Move/Resize Trigger
                     elif action.startswith(("move_zone_", "resize_zone_")):
                        zone_action_type = "move" if action.startswith("move_") else "resize"
                        logger.debug(f"Action matched: '{zone_action_type}_zone_*'")
                        try:
                            index_str = action.split(f"{zone_action_type}_zone_")[1]
                            index = int(index_str)
                            if 0 <= index < len(game_state.scoring_zones):
                                reset_editing_states() # Clear points/delete confirms
                                game_state.selected_zone_for_edit = index
                                game_state.previous_state = CurrentGameState.MENU
                                game_state.current_state = CurrentGameState.ZONE_EDITING
                                game_state.zone_editing_action = None
                                game_state.drag_start_pos = None
                                game_state.original_zone_on_drag_start = None
                                logger.info(
                                    f"Entering ZONE_EDITING state to {zone_action_type} zone {index+1}."
                                )
                                game_state.show_notification(
                                    "Click inside zone to move, handles to resize, ESC to cancel",
                                    duration=0,
                                ) # Persistent until ESC
                            else:
                                logger.warning(f"Invalid zone index for {zone_action_type}: {index}")
                        except (ValueError, IndexError, Exception) as e:
                            logger.error(
                                f"Error parsing zone index from {zone_action_type} action: {action} - {e}"
                            )

                     # Player Name Editing
                     elif action.startswith("edit_player_name_"):
                        logger.debug("Action matched: 'edit_player_name_*'")
                        try:
                            index = int(action.split("edit_player_name_")[1])
                            if 0 <= index < len(game_state.players):
                                if not (
                                    game_state.editing_player_index == index
                                    and game_state.editing_player_mode == "edit_name"
                                ):
                                    reset_editing_states()
                                    current_name = game_state.players[index].name
                                    game_state.editing_player_index = index
                                    game_state.editing_player_mode = "edit_name"
                                    game_state.editing_player_name_input = str(
                                        current_name
                                    )
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

                     # Zone Deletion
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
                        # Default action: Submenu navigation
                        logger.debug(
                            f"Action '{action}' not explicitly handled, assuming submenu switch."
                        )
                        logger.info(f"Switching to submenu: {action}")
                        game_state.submenu_active = action
                        reset_editing_states()

                 # Game Over State Actions
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

                 return True # Click handled by string action

            else:
                logger.warning(
                    f"Clicked item '{label}' has unhandled action type: {type(action)}"
                )
                return True # Consider it handled

    logger.debug(
        f"Click in {game_state.current_state} area but not on a specific registered item."
    )
    return False