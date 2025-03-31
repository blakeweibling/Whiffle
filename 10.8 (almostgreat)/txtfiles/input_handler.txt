"""
Handles mouse input events for the Whiffle Tracker project.
Processes clicks for drawing zones, menu interactions, and game over screen.
"""

import cv2
import logging
from typing import Any, Tuple, Optional, Callable

# Import necessary components used by the moved functions
from constants import UIConstants, GameConstants, ScoringConstants
from menu import reset_game, save_zones, load_zones, clear_zones # Import functions called by actions
from utils import clean_exit # clean_exit is called on quit action
from game_state_utils import set_special_hole
from game_state import CurrentGameState # Import state enum
from player import Player

logger = logging.getLogger(__name__)

# --- Mouse Callback Helpers (Moved from utils.txt) ---

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

    # Check if the click is within the general menu/game over area bounds
    # Note: Game Over screen uses full window, so this check might always pass for it.
    if not (menu_x <= x < menu_x + menu_w and menu_y <= y < menu_y + menu_h):
        return False # Click outside the menu/game over area

    # Calculate click position relative to the menu/screen origin
    relative_x = x - menu_x
    relative_y = y - menu_y

    logger.debug(f"Click detected within {game_state.current_state} bounds at window ({x}, {y}), relative ({relative_x}, {relative_y}). Checking items...")

    # Iterate through clickable items defined for the current state/submenu
    # game_state.submenu_items stores [(rect, action, label), ...]
    for item_rect, action, label in game_state.submenu_items:
        item_x, item_y, item_w, item_h = item_rect
        # Check if the relative click coordinates are within the current item's rectangle
        if item_x <= relative_x <= item_x + item_w and item_y <= relative_y <= item_y + item_h:
            logger.info(f"Clicked on item: '{label}' with action: {action} in state {game_state.current_state}")

            # --- Action Handling ---
            logger.debug(f"Checking action: '{action}' (type: {type(action)}) in state: {game_state.current_state}")

            # Handle callable actions (like toggles in settings)
            if isinstance(action, Callable):
                logger.debug("Action is Callable.")
                action()
                # If the action was in the menu, invalidate the cache to force redraw
                if game_state.current_state == CurrentGameState.MENU:
                    game_state.menu_cache = None
                return True # Click handled

            # Handle string-based actions
            elif isinstance(action, str):
                logger.debug("Action is string. Checking specific string values...")

                # --- Universal Actions ---
                if action == "quit":
                    logger.debug("Action matched: 'quit'")
                    # Attempt to save score before exiting cleanly
                    try:
                         if hasattr(game_state, 'get_current_player') and hasattr(game_state, 'save_score'):
                              player = game_state.get_current_player()
                              if player and hasattr(player, 'name'):
                                   game_state.save_score(player.name)
                    except Exception as e:
                         logger.error(f"Error saving score on quit action: {e}")
                    clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
                    # clean_exit raises SystemExit, so code below won't run, but return True for clarity
                    return True

                # --- Menu State Actions ---
                if game_state.current_state == CurrentGameState.MENU:
                    logger.debug("Processing actions for MENU state...")

                    # Reset editing modes helper function
                    def reset_editing_states():
                        game_state.editing_zone_index = None
                        game_state.editing_zone_mode = None
                        game_state.editing_zone_points_input = None
                        game_state.editing_player_index = None
                        game_state.editing_player_mode = None
                        game_state.editing_player_name_input = None
                        game_state.menu_cache = None # Invalidate cache after any action

                    if action == "show_splash":
                        logger.info("Switching to SHOWING_SPLASH state.")
                        game_state.previous_state = game_state.current_state # Remember where we came from
                        game_state.current_state = CurrentGameState.SHOWING_SPLASH
                        reset_editing_states() # Clear editing state when leaving menu
                    elif action == "resume":
                        logger.debug("Action matched: 'resume'")
                        game_state.current_state = CurrentGameState.PLAYING
                        reset_editing_states() # Clear menu/editing state
                        game_state.submenu_active = None # Ensure no submenu active
                    elif action == "back_to_main":
                        logger.debug("Action matched: 'back_to_main'")
                        reset_editing_states() # Clear editing state
                        game_state.submenu_active = None # Go to main menu
                    elif action == "add_zone_info":
                        logger.debug("Action matched: 'add_zone_info'")
                        game_state.show_notification("Press 's', then click and drag to draw zone")
                        game_state.current_state = CurrentGameState.PLAYING # Switch to playing to allow drawing
                        reset_editing_states()
                        game_state.submenu_active = None
                    elif action == "clear_zones":
                        logger.debug("Action matched: 'clear_zones'")
                        clear_zones(game_state)
                        reset_editing_states() # Zone list changed, redraw
                    elif action == "save_zones":
                        logger.debug("Action matched: 'save_zones'")
                        save_zones(game_state)
                        # No need to reset editing state here usually
                        game_state.menu_cache = None # Maybe redraw confirmation?
                    elif action == "load_zones":
                        logger.debug("Action matched: 'load_zones'")
                        load_zones(game_state)
                        reset_editing_states() # Zone list changed, redraw
                    elif action.startswith("set_mode_"):
                        logger.debug("Action matched: 'set_mode_*'")
                        new_mode = action.split("set_mode_")[1]
                        if game_state.game_mode != new_mode:
                            logger.info(f"Game mode changing to: {new_mode}")
                            # Save score for the *previous* mode before switching
                            game_state.save_score(game_state.get_current_player().name, mode=game_state.game_mode)
                            game_state.game_mode = new_mode
                            reset_game(game_state) # Reset score, timer etc. for new mode
                        else:
                            logger.info(f"Game mode already set to: {new_mode}")
                        reset_editing_states() # Mode changed, redraw
                    elif action.startswith("select_player_"):
                        logger.debug("Action matched: 'select_player_*'")
                        try:
                            index = int(action.split("select_player_")[1])
                            if 0 <= index < len(game_state.players) and index != game_state.current_player_index:
                                game_state.save_score(game_state.get_current_player().name) # Save previous player's score
                                game_state.current_player_index = index
                                logger.info(f"Switched to player: {game_state.get_current_player().name}")
                                reset_game(game_state) # Reset game state for the new player
                            elif index == game_state.current_player_index:
                                logger.debug("Selected current player again.")
                            else:
                                logger.warning(f"Invalid player index selected: {index}")
                        except (ValueError, IndexError) as e:
                            logger.error(f"Error parsing player index from action: {action} - {e}")
                        reset_editing_states() # Player changed, redraw
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
                        reset_editing_states() # Player list changed, redraw
                    elif action == "back_to_manage_zones":
                        logger.debug("Action matched: 'back_to_manage_zones'")
                        game_state.submenu_active = "manage_zones" # Go back to parent menu
                        reset_editing_states() # Clear editing state
                    elif action.startswith("edit_zone_"):
                        logger.debug("Action matched: 'edit_zone_*'")
                        try:
                            index = int(action.split("edit_zone_")[1])
                            if 0 <= index < len(game_state.scoring_zones):
                                reset_editing_states() # Clear any previous edit state first
                                current_points = game_state.scoring_zones[index][4]
                                game_state.editing_zone_index = index
                                game_state.editing_zone_mode = 'edit_points'
                                game_state.editing_zone_points_input = str(current_points) # Init with current points
                                game_state.menu_cache = None # Redraw needed
                                logger.info(f"Selected zone {index+1} for editing points. Initial value: {current_points}")
                            else:
                                logger.warning(f"Invalid zone index for edit: {index}")
                                reset_editing_states() # Clear potentially invalid state
                        except (ValueError, IndexError) as e:
                            logger.error(f"Error parsing zone index from edit action: {action} - {e}")
                            reset_editing_states()
                    elif action.startswith("edit_player_name_"):
                        logger.debug("Action matched: 'edit_player_name_*'")
                        try:
                            index = int(action.split("edit_player_name_")[1])
                            if 0 <= index < len(game_state.players):
                                reset_editing_states() # Clear any previous edit state first
                                current_name = game_state.players[index].name
                                game_state.editing_player_index = index
                                game_state.editing_player_mode = 'edit_name'
                                game_state.editing_player_name_input = str(current_name) # Init with current name
                                game_state.menu_cache = None # Redraw needed
                                logger.info(f"Selected player {index+1} for editing name. Initial value: '{current_name}'")
                            else:
                                logger.warning(f"Invalid player index for edit name: {index}")
                                reset_editing_states() # Clear potentially invalid state
                        except (ValueError, IndexError) as e:
                            logger.error(f"Error parsing player index from edit name action: {action} - {e}")
                            reset_editing_states()
                    elif action.startswith("delete_zone_"):
                        logger.debug("Action matched: 'delete_zone_*'")
                        try:
                            index = int(action.split("delete_zone_")[1])
                            if 0 <= index < len(game_state.scoring_zones):
                                # Check if this is the confirmation click
                                if game_state.editing_zone_index == index and game_state.editing_zone_mode == 'confirm_delete':
                                    logger.info(f"Confirmed deleting zone {index+1}.")
                                    del game_state.scoring_zones[index]
                                    game_state.special_hole = set_special_hole(game_state.scoring_zones) # Recalculate special hole
                                    game_state.show_notification(f"Zone {index+1} Deleted")
                                    reset_editing_states() # Clear confirm state and redraw
                                else:
                                    # First click: enter confirmation mode for this zone
                                    reset_editing_states() # Clear other editing modes
                                    game_state.editing_zone_index = index
                                    game_state.editing_zone_mode = 'confirm_delete'
                                    game_state.menu_cache = None # Redraw to show confirmation state
                                    logger.info(f"Selected zone {index+1} for deletion. Click again to confirm.")
                                    game_state.show_notification(f"Click Delete again for zone {index+1} to confirm", duration=4.0)
                            else:
                                logger.warning(f"Invalid zone index for delete: {index}")
                                reset_editing_states() # Clear potentially invalid state
                        except (ValueError, IndexError) as e:
                            logger.error(f"Error parsing zone index from delete action: {action} - {e}")
                            reset_editing_states()
                    else:
                        # Default action: Treat as submenu navigation if not handled above
                        logger.debug(f"Action '{action}' not explicitly handled, assuming submenu switch.")
                        logger.info(f"Switching to submenu: {action}")
                        game_state.submenu_active = action
                        reset_editing_states() # Clear editing state when navigating

                # --- Game Over State Actions ---
                elif game_state.current_state == CurrentGameState.GAME_OVER:
                    logger.debug("Processing actions for GAME_OVER state...")
                    if action == "new_game_from_gameover":
                        logger.debug("Action matched: 'new_game_from_gameover'")
                        logger.info("Starting new game from game over screen.")
                        reset_game(game_state)
                        game_state.current_state = CurrentGameState.PLAYING
                        game_state.win_condition_met = False # Reset win flag
                        # No need to reset editing states here as we left GAME_OVER
                    elif action == "show_leaderboard_from_gameover":
                        logger.debug("Action matched: 'show_leaderboard_from_gameover'")
                        logger.info("Showing leaderboard from game over screen.")
                        game_state.current_state = CurrentGameState.MENU # Go to menu
                        game_state.submenu_active = "leaderboard"      # Directly to leaderboard submenu
                        game_state.win_condition_met = False # Reset win flag
                        game_state.menu_cache = None # Ensure menu redraws

                # If we reached here, the click was on a known item and action was processed
                return True # Click handled

    # If the loop finishes without finding a matching item, the click was inside the menu area
    # but not on any specific registered button/item.
    logger.debug(f"Click in {game_state.current_state} area but not on a specific registered item.")
    # We might want to consume the click anyway to prevent it falling through,
    # unless specific behavior is desired (e.g., clicking background closes menu).
    # For now, let's consider it handled as it was within the menu boundary.
    return True

# Main Mouse Callback (Moved from utils.txt)
def mouse_callback(event: int, x: int, y: int, flags: int, param: Any) -> None:
    """Handle mouse events for the main application window."""
    game_state = param
    if game_state is None:
        logger.warning("Mouse callback received None for game_state param.")
        return

    logger.debug(f"Mouse event: {event} at ({x}, {y}). State: {game_state.current_state}, Drawing: {game_state.drawing}")

    # --- Event Handling Logic ---
    click_handled = False # Flag to track if the event was processed

    # 1. Handle click during SHOWING_SPLASH state (overrides everything else)
    if game_state.current_state == CurrentGameState.SHOWING_SPLASH and event == cv2.EVENT_LBUTTONDOWN:
        logger.info("Click detected during splash, returning to previous state.")
        if game_state.previous_state:
            game_state.current_state = game_state.previous_state
        else:
            # Fallback if previous_state wasn't set (shouldn't happen often)
            game_state.current_state = CurrentGameState.MENU
            logger.warning("Previous state was None when exiting splash, returning to MENU.")
        game_state.previous_state = None # Clear previous state marker
        game_state.menu_cache = None # Ensure menu redraws if returning to it
        click_handled = True

    # 2. Handle click on Menu button while PLAYING
    elif not click_handled and game_state.current_state == CurrentGameState.PLAYING and event == cv2.EVENT_LBUTTONDOWN:
        # Check if click is within the menu button bounds defined in UIConstants
        if (UIConstants.MENU_BUTTON_X <= x <= UIConstants.MENU_BUTTON_X + UIConstants.MENU_BUTTON_WIDTH and
                UIConstants.MENU_BUTTON_Y <= y <= UIConstants.MENU_BUTTON_Y + UIConstants.MENU_BUTTON_HEIGHT):
            logger.info("Menu toggled ON via button click.")
            game_state.current_state = CurrentGameState.MENU
            game_state.submenu_active = None # Start at main menu
            game_state.menu_cache = None # Ensure menu redraws
            # Reset any lingering editing state when opening menu
            game_state.editing_zone_index = None
            game_state.editing_zone_mode = None
            game_state.editing_zone_points_input = None
            game_state.editing_player_index = None
            game_state.editing_player_mode = None
            game_state.editing_player_name_input = None
            click_handled = True

    # 3. Handle clicks within MENU or GAME_OVER states
    elif not click_handled and game_state.current_state in [CurrentGameState.MENU, CurrentGameState.GAME_OVER] and event == cv2.EVENT_LBUTTONDOWN:
        # Delegate click processing to the helper function
        click_handled = _process_menu_or_gameover_click(x, y, game_state)

    # 4. Handle mouse events related to drawing zones (only when PLAYING and drawing active)
    # Process LBUTTONDOWN, MOUSEMOVE, LBUTTONUP for drawing logic
    elif not click_handled and game_state.current_state == CurrentGameState.PLAYING and game_state.drawing:
        if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP, cv2.EVENT_MOUSEMOVE]:
             _process_drawing_event(event, x, y, game_state)
             # Assume drawing events are always handled if conditions met
             click_handled = True # Prevent further processing

    # 5. Log unhandled clicks (optional)
    if not click_handled and event == cv2.EVENT_LBUTTONDOWN:
        logger.debug(f"Unhandled click at ({x},{y}) in state {game_state.current_state}")