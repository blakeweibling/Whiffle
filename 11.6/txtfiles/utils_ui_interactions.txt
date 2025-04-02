# utils_ui_interactions.py

import logging
import math # For pagination calculation
from typing import Callable

# Imports needed for UI interactions
from constants import MenuConstants, ScoringConstants # Added ScoringConstants for point edits
from game_state import GameState, CurrentGameState
from player import Player
from menu import (
    save_zones,
    reset_game,
    load_zones,
    clear_zones,
)
# Import display_modal_splash directly here again
from ui_screens import display_modal_splash
# Need set_special_hole if deleting zones affects it
from game_state_utils import set_special_hole
# Import mouse_callback for splash screen re-hooking - Requires careful structure or passing GameState directly
# from utils import mouse_callback # Potential circular import - pass game_state to splash instead

logger = logging.getLogger(__name__)

# Helper function to reset various editing states
def _reset_all_editing_states(game_state: GameState):
    """Resets all temporary editing states (zone points, player name, delete confirmations)."""
    game_state.editing_zone_index = None
    game_state.editing_zone_mode = None
    game_state.editing_zone_points_input = None
    game_state.editing_player_index = None
    game_state.editing_player_mode = None
    game_state.editing_player_name_input = None
    # Note: Interactive zone editing state (selected_zone_for_edit, etc.) is handled separately
    # by specific actions (like starting an edit) or cancellations (ESC key, opening menu).

# --- Menu/Game Over Click Processing (Modified for Zone Edit Actions) ---
def _process_menu_or_gameover_click(x: int, y: int, game_state: GameState) -> bool:
    """Process clicks within the menu or game over screen, including zone edit actions."""
    if game_state.current_state not in [
        CurrentGameState.MENU,
        CurrentGameState.GAME_OVER,
    ]:
        return False

    if not all(hasattr(game_state, attr) for attr in ['menu_pos', 'menu_width', 'menu_height']):
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
            logger.warning(f"Invalid item_rect format found: {item_rect}. Skipping item '{label}'.")
            continue

        item_x, item_y, item_w, item_h = item_rect
        if (
            item_x <= relative_x <= item_x + item_w
            and item_y <= relative_y <= item_y + item_h
        ):
            logger.info(
                f"Clicked on item: '{label}' with action: {action} in state {game_state.current_state}"
            )

            # --- Use helper to reset editing states ---
            # Moved the reset logic inside specific actions where needed,
            # but keep the helper function available.
            # def reset_editing_states(): ... (defined above)

            if isinstance(action, Callable):
                logger.debug("Action is Callable.")
                try:
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
                        from cleanup_utils import clean_exit
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
                        logger.error("Could not import clean_exit. Cannot quit properly via menu.")
                    return True

                # Menu State Actions
                if game_state.current_state == CurrentGameState.MENU:
                    logger.debug("Processing actions for MENU state...")

                    needs_reset = True # Flag to reset editing states by default for most menu actions
                    needs_cache_invalidate = True # Flag to invalidate menu cache

                    if action == "show_splash":
                        logger.debug("Action matched: 'show_splash'")
                        # --- MODIFICATION START ---
                        # Retrieve the main callback from game_state
                        main_callback = getattr(game_state, 'main_mouse_callback', None)
                        if callable(main_callback):
                            display_modal_splash(game_state, main_callback, game_state) # Pass the retrieved callback
                        else:
                            logger.error("Main mouse callback not found or not callable in game_state. Cannot show modal splash correctly.")
                            game_state.show_notification("Error: Cannot show splash.", is_error=True)
                        # --- MODIFICATION END ---
                        needs_reset = True
                    elif action == "resume":
                        logger.debug("Action matched: 'resume'")
                        game_state.current_state = CurrentGameState.PLAYING
                        game_state.submenu_active = None
                        needs_reset = True
                    elif action == "back_to_main":
                        logger.debug("Action matched: 'back_to_main'")
                        game_state.submenu_active = None
                        needs_reset = True
                    elif action == "add_zone_info":
                        logger.debug("Action matched: 'add_zone_info'")
                        game_state.show_notification("Press 's', then click and drag to draw zone")
                        game_state.current_state = CurrentGameState.PLAYING
                        game_state.submenu_active = None
                        needs_reset = True
                    elif action == "clear_zones":
                        logger.debug("Action matched: 'clear_zones'")
                        clear_zones(game_state)
                        needs_reset = True
                    elif action == "save_zones":
                        logger.debug("Action matched: 'save_zones'")
                        save_zones(game_state)
                        needs_reset = False # Saving doesn't require full reset
                    elif action == "load_zones":
                        logger.debug("Action matched: 'load_zones'")
                        load_zones(game_state)
                        needs_reset = True
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
                        game_state.submenu_active = None
                        game_state.current_state = CurrentGameState.PLAYING
                        needs_reset = True
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
                                logger.warning(f"Invalid player index selected: {index}")
                        except (ValueError, IndexError) as e:
                            logger.error(f"Error parsing player index from action: {action} - {e}")
                        needs_reset = True
                    elif action == "add_player":
                        logger.debug("Action matched: 'add_player'")
                        if len(game_state.players) < 2:
                            player_number = len(game_state.players) + 1
                            new_player = Player(f"Player {player_number}")
                            game_state.players.append(new_player)
                            logger.info(f"Added {new_player.name}")
                            game_state.show_notification(f"{new_player.name} Added")
                        else:
                            logger.warning("Attempted to add player when 2 players already exist.")
                            game_state.show_notification("Maximum 2 players supported", is_error=True)
                        needs_reset = True
                    elif action == "back_to_manage_zones":
                         logger.debug("Action matched: 'back_to_manage_zones'")
                         game_state.submenu_active = "manage_zones"
                         needs_reset = True
                    # --- Zone Points Editing ---
                    elif action.startswith("edit_zone_"):
                        logger.debug("Action matched: 'edit_zone_*' (Points)")
                        try:
                            index = int(action.split("edit_zone_")[1])
                            if 0 <= index < len(game_state.scoring_zones):
                                if not (game_state.editing_zone_index == index and game_state.editing_zone_mode == "edit_points"):
                                     _reset_all_editing_states(game_state) # Reset before starting new edit
                                     current_points = game_state.scoring_zones[index][4]
                                     game_state.editing_zone_index = index
                                     game_state.editing_zone_mode = "edit_points"
                                     game_state.editing_zone_points_input = str(current_points)
                                     logger.info(f"Selected zone {index+1} for editing points. Initial value: {current_points}")
                            else:
                                 logger.warning(f"Invalid zone index for edit: {index}")
                                 _reset_all_editing_states(game_state) # Reset if index invalid
                        except (ValueError, IndexError) as e:
                             logger.error(f"Error parsing zone index from edit action: {action} - {e}")
                             _reset_all_editing_states(game_state) # Reset on error
                        needs_reset = False # Don't reset immediately, user needs to input
                        needs_cache_invalidate = True # Need to redraw with input field
                    # --- Interactive Zone Move ---
                    elif action.startswith("move_zone_"):
                         logger.debug("Action matched: 'move_zone_*'")
                         try:
                            index = int(action.split("move_zone_")[1])
                            if 0 <= index < len(game_state.scoring_zones):
                                _reset_all_editing_states(game_state) # Clear points/delete confirms
                                game_state.selected_zone_for_edit = index
                                game_state.previous_state = CurrentGameState.MENU # Store where we came from
                                game_state.current_state = CurrentGameState.ZONE_EDITING
                                game_state.zone_editing_action = None # Start in selecting mode within ZONE_EDITING
                                game_state.drag_start_pos = None
                                game_state.original_zone_on_drag_start = None
                                logger.info(f"Entering ZONE_EDITING state to move zone {index+1}.")
                                game_state.show_notification("Click inside zone to move, ESC to cancel", duration=0) # Persistent until ESC
                            else:
                                 logger.warning(f"Invalid zone index for move: {index}")
                         except (ValueError, IndexError) as e:
                             logger.error(f"Error parsing zone index from move action: {action} - {e}")
                         needs_reset = False # State change handles reset implicitly
                         needs_cache_invalidate = False # State change will redraw
                    # --- Interactive Zone Resize ---
                    elif action.startswith("resize_zone_"):
                         logger.debug("Action matched: 'resize_zone_*'")
                         try:
                            index = int(action.split("resize_zone_")[1])
                            if 0 <= index < len(game_state.scoring_zones):
                                 _reset_all_editing_states(game_state) # Clear points/delete confirms
                                 game_state.selected_zone_for_edit = index
                                 game_state.previous_state = CurrentGameState.MENU # Store where we came from
                                 game_state.current_state = CurrentGameState.ZONE_EDITING
                                 game_state.zone_editing_action = None # Start in selecting mode within ZONE_EDITING
                                 game_state.drag_start_pos = None
                                 game_state.original_zone_on_drag_start = None
                                 logger.info(f"Entering ZONE_EDITING state to resize zone {index+1}.")
                                 game_state.show_notification("Click corner handles to resize, ESC to cancel", duration=0) # Persistent until ESC
                            else:
                                 logger.warning(f"Invalid zone index for resize: {index}")
                         except (ValueError, IndexError) as e:
                             logger.error(f"Error parsing zone index from resize action: {action} - {e}")
                         needs_reset = False # State change handles reset
                         needs_cache_invalidate = False # State change redraws
                    # --- Edit Zones Pagination ---
                    elif action == "edit_zones_prev_page":
                        logger.debug("Action matched: 'edit_zones_prev_page'")
                        if game_state.edit_zones_page > 0:
                             game_state.edit_zones_page -= 1
                        else:
                             logger.debug("Already on the first page.")
                        needs_reset = False # Pagination doesn't reset edits
                        needs_cache_invalidate = True # Need to redraw previous page
                    elif action == "edit_zones_next_page":
                        logger.debug("Action matched: 'edit_zones_next_page'")
                        total_zones = len(game_state.scoring_zones)
                        per_page = game_state.edit_zones_per_page
                        total_pages = max(1, math.ceil(total_zones / per_page))
                        if game_state.edit_zones_page < total_pages - 1:
                             game_state.edit_zones_page += 1
                        else:
                             logger.debug("Already on the last page.")
                        needs_reset = False # Pagination doesn't reset edits
                        needs_cache_invalidate = True # Need to redraw next page
                    # --- Player Name Editing ---
                    elif action.startswith("edit_player_name_"):
                         logger.debug("Action matched: 'edit_player_name_*'")
                         try:
                            index = int(action.split("edit_player_name_")[1])
                            if 0 <= index < len(game_state.players):
                                 if not (game_state.editing_player_index == index and game_state.editing_player_mode == "edit_name"):
                                     _reset_all_editing_states(game_state) # Reset before new edit
                                     current_name = game_state.players[index].name
                                     game_state.editing_player_index = index
                                     game_state.editing_player_mode = "edit_name"
                                     game_state.editing_player_name_input = str(current_name)
                                     logger.info(f"Selected player {index+1} for editing name. Initial value: '{current_name}'")
                            else:
                                 logger.warning(f"Invalid player index for edit name: {index}")
                                 _reset_all_editing_states(game_state) # Reset if invalid
                         except (ValueError, IndexError) as e:
                             logger.error(f"Error parsing player index from edit name action: {action} - {e}")
                             _reset_all_editing_states(game_state) # Reset on error
                         needs_reset = False # Don't reset immediately
                         needs_cache_invalidate = True # Redraw with input
                    # --- Zone Deletion ---
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
                                     # Adjust page if deleting the last item on a page higher than 0
                                     zones_before_delete = len(game_state.scoring_zones)
                                     per_page = game_state.edit_zones_per_page
                                     page_before_delete = game_state.edit_zones_page

                                     del game_state.scoring_zones[index]
                                     game_state.special_hole = set_special_hole(game_state.scoring_zones)
                                     game_state.show_notification(f"Zone {index+1} Deleted")

                                     # Adjust page only if we were on the last page and it's now empty
                                     total_pages_after_delete = max(1, math.ceil(len(game_state.scoring_zones) / per_page))
                                     if page_before_delete > 0 and page_before_delete >= total_pages_after_delete:
                                         game_state.edit_zones_page = max(0, total_pages_after_delete - 1)
                                         logger.debug(f"Adjusted edit zones page to {game_state.edit_zones_page} after deletion.")

                                     _reset_all_editing_states(game_state) # Reset state after delete
                                     needs_reset = False # Already reset
                                else:
                                     # First click: enter confirm mode
                                     _reset_all_editing_states(game_state) # Reset any other editing modes
                                     game_state.editing_zone_index = index
                                     game_state.editing_zone_mode = "confirm_delete"
                                     logger.info(f"Selected zone {index+1} for deletion. Click again to confirm.")
                                     game_state.show_notification(f"Click Delete again for zone {index+1} to confirm", duration=4.0)
                                     needs_reset = False # Don't reset, waiting for confirm
                            else:
                                 logger.warning(f"Invalid zone index for delete: {index}")
                                 _reset_all_editing_states(game_state) # Reset if invalid
                                 needs_reset = False
                        except (ValueError, IndexError) as e:
                             logger.error(f"Error parsing zone index from delete action: {action} - {e}")
                             _reset_all_editing_states(game_state) # Reset on error
                             needs_reset = False
                        needs_cache_invalidate = True # Need to redraw potentially changed button text/page
                    else:
                        # Default action: Submenu navigation
                        logger.debug(f"Action '{action}' not explicitly handled, assuming submenu switch.")
                        valid_submenus = [item[1] for item in MenuConstants.MAIN_MENU_ITEMS] + ["edit_zones", "manage_players", "leaderboard", "settings"] # Add known submenus
                        if action in valid_submenus:
                             logger.info(f"Switching to submenu: {action}")
                             game_state.submenu_active = action
                             needs_reset = True
                             # Reset page to 0 when navigating TO edit_zones
                             if action == "edit_zones":
                                 game_state.edit_zones_page = 0
                        else:
                             logger.warning(f"Ignoring unknown string action: {action}")
                             needs_reset = False # Don't reset for unknown action
                             needs_cache_invalidate = False # Don't invalidate for unknown action

                    # --- Reset states and invalidate cache if needed ---
                    if needs_reset:
                         _reset_all_editing_states(game_state)
                    if needs_cache_invalidate:
                        game_state.menu_cache = None # Invalidate cache

                    return True # Click handled by string action in MENU


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
                        return True # Handled
                    elif action == "show_leaderboard_from_gameover":
                        logger.debug("Action matched: 'show_leaderboard_from_gameover'")
                        logger.info("Showing leaderboard from game over screen.")
                        game_state.current_state = CurrentGameState.MENU
                        game_state.submenu_active = "leaderboard"
                        game_state.win_condition_met = False
                        game_state.menu_cache = None
                        return True # Handled

            else:
                  logger.warning(f"Clicked item '{label}' has unhandled action type: {type(action)}")
                  return True # Consider it handled

    logger.debug(f"Click in {game_state.current_state} area but not on a specific registered item.")
    return False