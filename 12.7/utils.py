# utils.py

import logging
from math import ceil
from typing import Any, Optional, Tuple

import cv2

# Import cleanup util
from cleanup_utils import clean_exit

# Imports needed for mouse_callback helpers
from constants import GameConstants, MenuConstants, ScoringConstants, UIConstants

# Import GameState class and CurrentGameState enum from correct locations
from game_state import GameState  # Keep import for GameState class

# Import the necessary utility functions from CORRECT locations
from game_state_helpers import (  # Helpers that were moved to helpers
    clear_zones,
    load_zones,
    save_score,
    save_zones,
    set_special_hole,
    show_notification,
)
from game_state_utils import reset_game  # Correct import location
from game_state_utils import (  # Utils that remained (or need to be) in utils
    change_music_track,
    save_settings,
    set_volume,
    toggle_background_music,
    toggle_game_sounds,
)
from game_types import CurrentGameState  # Import Enum from new location

# Import Player class
from player import Player

# Import overlap check function from scoring
from scoring import _zones_overlap

# Import UI screens/modals
from ui_screens import display_modal_splash

# Removed imports from menu for zone functions and reset_game

logger = logging.getLogger(__name__)


# --- Helper: Find which handle/area of a zone is clicked ---
def _get_zone_click_location(
    x: int, y: int, zone_rect: Tuple[int, int, int, int]
) -> Optional[str]:
    """Determine if a click is on a corner, edge, or inside a zone."""
    # (Code unchanged)
    zx, zy, zw, zh = zone_rect
    handle_size = UIConstants.ZONE_EDIT_HANDLE_SIZE
    half_handle = handle_size // 2
    # Check corners first
    if abs(x - zx) < half_handle and abs(y - zy) < half_handle:
        return "resize_tl" # Top-left
    if abs(x - (zx + zw)) < half_handle and abs(y - zy) < half_handle:
        return "resize_tr" # Top-right
    if abs(x - zx) < half_handle and abs(y - (zy + zh)) < half_handle:
        return "resize_bl" # Bottom-left
    if abs(x - (zx + zw)) < half_handle and abs(y - (zy + zh)) < half_handle:
        return "resize_br" # Bottom-right
    # Check if inside the zone (but not on a corner)
    if zx < x < zx + zw and zy < y < zy + zh:
        return "move"
    return None # Click was outside the zone


# --- Helper: Process Interactive Zone Editing Mouse Events ---
def _process_zone_editing_event(
    event: int, x: int, y: int, game_state: GameState
) -> bool:
    """Process mouse events during interactive zone move/resize."""
    # (Code unchanged, uses helpers imported above)
    handled = False
    zone_idx = game_state.selected_zone_for_edit
    # Validate state before proceeding
    if zone_idx is None or not (0 <= zone_idx < len(game_state.scoring_zones)):
        # Invalid state, reset and return to previous screen
        logger.warning("Zone editing event processed with invalid selected_zone_for_edit.")
        game_state.zone_editing_action = None
        game_state.drag_start_pos = None
        game_state.selected_zone_for_edit = None
        game_state.original_zone_on_drag_start = None
        try:
            game_state.current_state = (
                game_state.previous_state
                if game_state.previous_state
                else CurrentGameState.MENU
            )
        except AttributeError:
            game_state.current_state = CurrentGameState.MENU
        game_state.previous_state = None # Clear stored previous state
        return False # Indicate event not handled for editing

    current_zone = game_state.scoring_zones[zone_idx]
    zx, zy, zw, zh, zp = current_zone
    min_size = ScoringConstants.MIN_ZONE_SIZE

    if event == cv2.EVENT_LBUTTONDOWN:
        click_location = _get_zone_click_location(x, y, (zx, zy, zw, zh))
        if click_location:
            game_state.zone_editing_action = click_location
            game_state.drag_start_pos = (x, y)
            game_state.original_zone_on_drag_start = current_zone # Store original state
            logger.debug(f"Zone editing started: Action={click_location}, Start=({x},{y})")
            handled = True
        else:
             # Click outside the selected zone while editing probably shouldn't do anything
             logger.debug("Click outside selected zone during ZONE_EDITING state.")
             pass

    elif event == cv2.EVENT_MOUSEMOVE:
        if game_state.drag_start_pos and game_state.zone_editing_action:
            drag_x_start, drag_y_start = game_state.drag_start_pos
            dx = x - drag_x_start
            dy = y - drag_y_start
            new_x, new_y, new_w, new_h = zx, zy, zw, zh # Start with current values
            action = game_state.zone_editing_action

            # Calculate new dimensions/position based on action
            if action == "move":
                new_x = zx + dx
                new_y = zy + dy
            elif action == "resize_tl": # Top-left handle
                new_x = zx + dx
                new_y = zy + dy
                new_w = zw - dx
                new_h = zh - dy
            elif action == "resize_tr": # Top-right handle
                new_y = zy + dy
                new_w = zw + dx
                new_h = zh - dy
            elif action == "resize_bl": # Bottom-left handle
                new_x = zx + dx
                new_w = zw - dx
                new_h = zh + dy
            elif action == "resize_br": # Bottom-right handle
                new_w = zw + dx
                new_h = zh + dy

            # Apply minimum size constraints during resize
            if action.startswith("resize"):
                # Ensure width and height don't go below minimum
                prev_w, prev_h = new_w, new_h
                new_w = max(min_size, new_w)
                new_h = max(min_size, new_h)

                # Adjust opposite corner position if needed due to min size enforcement
                if action == "resize_tl":
                    if new_w != prev_w: new_x = (zx + zw) - new_w
                    if new_h != prev_h: new_y = (zy + zh) - new_h
                elif action == "resize_tr":
                    if new_h != prev_h: new_y = (zy + zh) - new_h
                elif action == "resize_bl":
                     if new_w != prev_w: new_x = (zx + zw) - new_w

            # Update the zone in the list immediately for visual feedback
            game_state.scoring_zones[zone_idx] = (new_x, new_y, new_w, new_h, zp)
            # Update drag start for continuous dragging feel
            # game_state.drag_start_pos = (x, y) # This caused drift, better to use original + delta
            handled = True

    elif event == cv2.EVENT_LBUTTONUP:
        if game_state.drag_start_pos and game_state.zone_editing_action:
            logger.debug(f"Zone editing finished: Action={game_state.zone_editing_action}")
            # Final validation on release
            final_zone = game_state.scoring_zones[zone_idx]
            fx, fy, fw, fh, fp = final_zone

            # Check minimum size again on release
            if fw < min_size or fh < min_size:
                show_notification(
                    game_state, f"Zone too small! Min size {min_size}. Reverted.", is_error=True, duration=3.0
                ) # Use helper
                if game_state.original_zone_on_drag_start:
                    game_state.scoring_zones[zone_idx] = (
                        game_state.original_zone_on_drag_start
                    )
            else:
                # Check for overlap with other zones
                other_zones = [
                    z for i, z in enumerate(game_state.scoring_zones) if i != zone_idx
                ]
                if _zones_overlap(final_zone[:4], other_zones):
                    show_notification(
                        game_state,
                        "Edit causes overlap! Reverted.",
                        is_error=True,
                        duration=3.0,
                    ) # Use helper
                    if game_state.original_zone_on_drag_start:
                        game_state.scoring_zones[zone_idx] = (
                            game_state.original_zone_on_drag_start
                        )
                else:
                    # Edit was valid, recalculate special hole
                    game_state.special_hole = set_special_hole(
                        game_state.scoring_zones
                    ) # Use helper
                    show_notification(game_state, f"Zone {zone_idx+1} updated", duration=1.5)

            # Reset editing state variables regardless of validity
            game_state.zone_editing_action = None
            game_state.drag_start_pos = None
            game_state.original_zone_on_drag_start = None
            handled = True

    return handled


# --- Drawing Event Processing ---
def _process_drawing_event(event: int, x: int, y: int, game_state: GameState) -> None:
    """Process mouse events for drawing scoring zones."""
    # (Code unchanged, uses helpers imported above)
    if event == cv2.EVENT_LBUTTONDOWN:
        if game_state.drawing:
            game_state.start_x, game_state.start_y = x, y
            game_state.temp_zone = None # Reset temp zone on new click
            game_state.drawing_points_input = "" # Reset points input
            logger.debug(f"Drawing started at ({x}, {y})")

    elif event == cv2.EVENT_MOUSEMOVE:
        if (
            game_state.drawing
            and game_state.start_x is not None
            and game_state.start_y is not None
        ):
            # Update temporary rectangle dimensions based on mouse movement
            x1 = min(game_state.start_x, x)
            y1 = min(game_state.start_y, y)
            w = abs(game_state.start_x - x)
            h = abs(game_state.start_y - y)
            game_state.temp_zone = (x1, y1, w, h)

    elif event == cv2.EVENT_LBUTTONUP:
        if game_state.drawing:
            logger.debug("Drawing mouse up.")
            if game_state.temp_zone:
                x1, y1, w, h = game_state.temp_zone
                # Validate size
                if (
                    w >= ScoringConstants.MIN_ZONE_SIZE
                    and h >= ScoringConstants.MIN_ZONE_SIZE
                ):
                    # Validate points input
                    points_str = game_state.drawing_points_input
                    points = ScoringConstants.DEFAULT_POINTS # Default
                    try:
                        if points_str: # If user entered something
                            points = int(points_str)
                        # Clamp points to valid range
                        if not (1 <= points <= ScoringConstants.MAX_POINTS):
                            show_notification(
                                game_state,
                                f"Points must be 1-{ScoringConstants.MAX_POINTS}. Using default {ScoringConstants.DEFAULT_POINTS}.",
                                is_error=True,
                                duration=3.0,
                            ) # Use helper
                            points = ScoringConstants.DEFAULT_POINTS
                    except ValueError:
                        # Handle case where input is not a valid integer
                        if points_str: # Only show error if they typed invalid chars
                           show_notification(
                                game_state,
                                f"Invalid points entered '{points_str}'. Using default {ScoringConstants.DEFAULT_POINTS}.",
                                is_error=True,
                                duration=3.0,
                            ) # Use helper
                        points = ScoringConstants.DEFAULT_POINTS # Use default if input is bad or empty

                    # Check for overlap before adding
                    new_zone = (x1, y1, w, h, points)
                    if not _zones_overlap(new_zone[:4], game_state.scoring_zones):
                        game_state.scoring_zones.append(new_zone)
                        game_state.special_hole = set_special_hole(
                            game_state.scoring_zones
                        ) # Use helper
                        show_notification(
                            game_state, f"Zone Added ({points} pts)"
                        ) # Use helper
                        logger.info(f"Added zone: {new_zone}")
                    else:
                        show_notification(
                            game_state, "Zone Overlaps! Not Added.", is_error=True
                        ) # Use helper
                        logger.warning("Zone overlap detected, not adding.")
                else:
                    # Zone too small
                    show_notification(
                        game_state, f"Zone too small (Min: {ScoringConstants.MIN_ZONE_SIZE}x{ScoringConstants.MIN_ZONE_SIZE})", is_error=True
                    ) # Use helper
                    logger.warning("Drawn zone was too small.")

            # Reset drawing state after mouse up regardless of success
            game_state.drawing = False # Turn off drawing mode
            game_state.temp_zone = None
            game_state.start_x = None
            game_state.start_y = None
            game_state.drawing_points_input = ""


# --- Helper to reset menu editing states ---
def _reset_all_menu_editing_states(game_state: GameState) -> None:
    """Resets all flags and temporary inputs related to menu editing."""
    # (Code unchanged)
    game_state.editing_zone_index = None
    game_state.editing_zone_mode = None
    game_state.editing_zone_points_input = None
    game_state.editing_player_index = None
    game_state.editing_player_mode = None
    game_state.editing_player_name_input = None
    game_state.selected_zone_for_edit = None # For interactive move/resize
    game_state.zone_editing_action = None
    game_state.drag_start_pos = None
    game_state.original_zone_on_drag_start = None
    game_state.edit_zones_current_page = 1 # Reset pagination
    game_state.menu_cache = None # Invalidate menu cache


# --- Process Menu/Game Over Click (Uses Utility Functions) ---
def _process_menu_or_gameover_click(x: int, y: int, game_state: GameState) -> bool:
    """Process clicks within the menu or game over screen, including sliders."""
    # Uses helpers imported from game_state_helpers
    # Uses utils imported from game_state_utils
    if game_state.current_state not in [
        CurrentGameState.MENU,
        CurrentGameState.GAME_OVER,
    ]:
        return False # Not in a state where menu clicks apply

    # Check if game_state has necessary menu attributes
    if not all(
        hasattr(game_state, attr) for attr in ["menu_pos", "menu_width", "menu_height", "submenu_items"]
    ):
        logger.warning("Menu attributes missing in game_state for click processing.")
        return False

    menu_x, menu_y = game_state.menu_pos
    menu_w, menu_h = game_state.menu_width, game_state.menu_height

    # Check if click is outside the general menu area (unless it's the close button)
    is_outside_menu = not (menu_x <= x < menu_x + menu_w and menu_y <= y < menu_y + menu_h)

    # Close Button Check (only applicable in MENU state)
    if game_state.current_state == CurrentGameState.MENU:
        pad = UIConstants.MENU_CLOSE_BUTTON_PADDING
        size = UIConstants.MENU_CLOSE_BUTTON_SIZE
        close_btn_x1 = menu_x + menu_w - pad - size
        close_btn_y1 = menu_y + pad
        close_btn_x2 = menu_x + menu_w - pad
        close_btn_y2 = menu_y + pad + size
        if close_btn_x1 <= x < close_btn_x2 and close_btn_y1 <= y < close_btn_y2:
            logger.debug("Menu close button clicked.")
            game_state.current_state = CurrentGameState.PLAYING # Resume game
            game_state.submenu_active = None
            _reset_all_menu_editing_states(game_state) # Clear any editing state
            return True # Click handled

    # If click was outside and not the close button, ignore it
    if is_outside_menu:
        return False

    # Calculate click coordinates relative to the menu's top-left corner
    relative_x = x - menu_x
    relative_y = y - menu_y

    # Check against registered submenu items
    if not isinstance(game_state.submenu_items, list):
        logger.error("game_state.submenu_items is not a list.")
        return False

    # Known navigation actions that change the active submenu
    known_submenu_nav_actions = { item[1] for item in MenuConstants.MAIN_MENU_ITEMS if isinstance(item[1], str) }
    known_submenu_nav_actions.update({ item[1] for item in MenuConstants.ZONE_SUBMENU_ITEMS if isinstance(item[1], str) })
    # Remove actions that don't just navigate to a submenu
    non_nav_actions = {
        "resume", "quit", "back_to_main", "back_to_manage_zones",
        "save_zones", "load_zones", "clear_zones", "add_zone_info",
    }
    known_submenu_nav_actions -= non_nav_actions

    volume_adjusted = False # Flag to prevent action dispatch if slider adjusted

    # Iterate through clickable items (buttons, sliders, etc.)
    # Reverse iteration allows handling clicks on overlapping elements correctly (topmost first)
    for item_data in reversed(game_state.submenu_items):
         # Basic validation of item_data structure
        if not isinstance(item_data, tuple) or len(item_data) < 2:
            logger.warning(f"Skipping invalid item in submenu_items: {item_data}")
            continue

        item_rect, action = item_data[0], item_data[1]
        # label = item_data[2] if len(item_data) > 2 else "" # Optional label for logging

        # Validate rectangle format
        if not isinstance(item_rect, tuple) or len(item_rect) != 4:
            logger.warning(f"Skipping item with invalid rect: {item_rect}")
            continue

        item_x, item_y, item_w, item_h = item_rect

        # Check if click is within this item's bounds
        if (
            item_x <= relative_x < item_x + item_w
            and item_y <= relative_y < item_y + item_h
        ):
            logger.debug(f"Click detected on item with action: {action}")

            # Handle specific actions first (like sliders)
            if isinstance(action, str):
                # Settings Sliders
                if action == "adjust_sound_volume":
                    click_offset = relative_x - item_x
                    # Ensure item_w is not zero to avoid division error
                    new_volume = max(0.0, min(1.0, click_offset / item_w if item_w > 0 else 0.0))
                    game_state.current_sound_volume = new_volume
                    set_volume(game_state) # Update sound system volume
                    save_settings(game_state) # Persist setting
                    game_state.menu_cache = None # Redraw menu to show new slider pos
                    volume_adjusted = True
                    logger.debug(f"Adjusted sound volume to {new_volume:.2f}")
                    # break # Found clickable item, stop checking lower items
                elif action == "adjust_music_volume":
                    click_offset = relative_x - item_x
                    new_volume = max(0.0, min(1.0, click_offset / item_w if item_w > 0 else 0.0))
                    game_state.current_music_volume = new_volume
                    set_volume(game_state)
                    save_settings(game_state)
                    game_state.menu_cache = None
                    volume_adjusted = True
                    logger.debug(f"Adjusted music volume to {new_volume:.2f}")
                    # break

                # --- Other Button Actions (only process if volume wasn't adjusted) ---
                elif not volume_adjusted:
                    # <<< MODIFIED: Handle "quit" action >>>
                    if action == "quit":
                        logger.debug("Menu quit action triggered, entering CONFIRM_QUIT state.")
                        # Store the state we were just in (MENU)
                        game_state.previous_state_before_quit_confirm = CurrentGameState.MENU
                        # Change to the confirmation state
                        game_state.current_state = CurrentGameState.CONFIRM_QUIT
                        # Reset any menu editing state when going to confirm
                        _reset_all_menu_editing_states(game_state)
                        # Do NOT call clean_exit or save score here
                        return True # Click handled
                    # <<< END MODIFICATION >>>

                    # Handle actions specific to the MENU state
                    if game_state.current_state == CurrentGameState.MENU:
                        if action == "toggle_game_sounds":
                            toggle_game_sounds(game_state) # Use util
                            game_state.menu_cache = None
                        elif action == "toggle_background_music":
                            toggle_background_music(game_state) # Use util
                            game_state.menu_cache = None
                        elif action == "toggle_debug_overlay":
                            game_state.show_debug_overlay = not game_state.show_debug_overlay
                            show_notification(game_state, f"Debug Overlay: {'ON' if game_state.show_debug_overlay else 'OFF'}")
                            game_state.menu_cache = None # May need redraw if settings change appearance
                        elif action == "toggle_debug_mode":
                            game_state.debug_mode = not game_state.debug_mode
                            log_level = logging.DEBUG if game_state.debug_mode else logging.INFO
                            logging.getLogger().setLevel(log_level)
                            for h in logging.getLogger().handlers: h.setLevel(log_level)
                            show_notification(game_state, f"Debug Mode: {'ON' if game_state.debug_mode else 'OFF'}")
                            game_state.menu_cache = None
                        elif action == "cycle_music_track":
                            total_tracks = len(GameConstants.BACKGROUND_MUSIC_TRACKS)
                            if total_tracks > 0:
                                change_music_track(
                                    game_state,
                                    (game_state.selected_music_track_index + 1) % total_tracks,
                                ) # Use util
                                game_state.menu_cache = None
                        elif action == "show_splash":
                             # Need the main mouse callback to restore it after splash
                             # Assuming mouse_callback is the main one passed initially
                             display_modal_splash(game_state, mouse_callback, game_state)
                             game_state.menu_cache = None # Splash might overlay, force redraw
                        elif action == "resume":
                            game_state.current_state = CurrentGameState.PLAYING
                            game_state.submenu_active = None
                            _reset_all_menu_editing_states(game_state)
                        elif action == "back_to_main":
                            _reset_all_menu_editing_states(game_state)
                            game_state.submenu_active = None # Go to main menu
                        elif action == "add_zone_info":
                             # Inform user how to draw, then exit menu
                             show_notification(game_state, "Press 's', then click and drag to draw zone") # Use helper
                             game_state.current_state = CurrentGameState.PLAYING
                             game_state.submenu_active = None
                             _reset_all_menu_editing_states(game_state)
                        elif action == "clear_zones":
                             clear_zones(game_state) # Use helper
                             _reset_all_menu_editing_states(game_state) # Reset menu state too
                        elif action == "save_zones":
                             save_zones(game_state) # Use helper
                             game_state.menu_cache = None # No visual change, but maybe good practice
                        elif action == "load_zones":
                             load_zones(game_state) # Use helper
                             _reset_all_menu_editing_states(game_state) # Reset menu state
                        elif action.startswith("set_mode_"):
                             new_mode = action.split("set_mode_")[1]
                             valid_modes = ["classic", "timed", "fun", "practice", "survival", "retro"]
                             if new_mode in valid_modes:
                                 if game_state.game_mode != new_mode:
                                     # Save score for the mode being left
                                     try:
                                         save_score(game_state, game_state.get_current_player().name, mode=game_state.game_mode) # Use helper
                                     except Exception as e:
                                         logger.error(f"Error saving score before mode change: {e}")
                                     # Change mode and reset game
                                     game_state.game_mode = new_mode
                                     reset_game(game_state) # Use util
                                     show_notification(game_state, f"Mode set to: {new_mode.capitalize()}")
                                     game_state.current_state = CurrentGameState.PLAYING # Start playing directly
                                     game_state.submenu_active = None
                                     _reset_all_menu_editing_states(game_state)
                                 else:
                                     # Already in this mode, just close menu
                                     game_state.current_state = CurrentGameState.PLAYING
                                     game_state.submenu_active = None
                                     _reset_all_menu_editing_states(game_state)
                        elif action.startswith("select_player_"):
                            try:
                                index = int(action.split("select_player_")[1])
                                if 0 <= index < len(game_state.players):
                                    if index != game_state.current_player_index:
                                        # Save score for current player before switching
                                        try:
                                            save_score(game_state, game_state.get_current_player().name) # Use helper
                                        except Exception as e:
                                             logger.error(f"Error saving score before player switch: {e}")
                                        # Switch player and reset game state (score, timer etc)
                                        game_state.current_player_index = index
                                        logger.info(f"Switched to player: {game_state.get_current_player().name}")
                                        reset_game(game_state) # Use util
                                        # Optionally return to main menu or playing state? Let's go back to player menu.
                                        # game_state.current_state = CurrentGameState.PLAYING
                                        # game_state.submenu_active = None
                                    else:
                                         logger.debug("Selected current player, no change.")
                                else:
                                    logger.warning(f"Invalid player index {index} from action '{action}'")
                                _reset_all_menu_editing_states(game_state) # Reset editing states, force redraw
                            except (ValueError, IndexError) as e:
                                logger.error(f"Error parsing player index from action '{action}': {e}")
                                _reset_all_menu_editing_states(game_state)
                        elif action == "add_player":
                            if len(game_state.players) < 2: # Limit to 2 players for now
                                game_state.players.append(Player(f"Player {len(game_state.players) + 1}"))
                                show_notification(game_state, "Player Added") # Use helper
                            else:
                                show_notification(game_state, "Maximum 2 players supported", is_error=True) # Use helper
                            _reset_all_menu_editing_states(game_state) # Reset menu state
                        elif action == "back_to_manage_zones": # Navigate back from edit zones list
                            _reset_all_menu_editing_states(game_state)
                            game_state.submenu_active = "manage_zones"
                        elif action == "prev_edit_zone_page":
                            if game_state.edit_zones_current_page > 1:
                                game_state.edit_zones_current_page -= 1
                                game_state.menu_cache = None # Redraw page
                        elif action == "next_edit_zone_page":
                            total_pages = max(1, ceil(len(game_state.scoring_zones) / game_state.edit_zones_items_per_page))
                            if game_state.edit_zones_current_page < total_pages:
                                game_state.edit_zones_current_page += 1
                                game_state.menu_cache = None # Redraw page
                        elif action == "leaderboard_classic":
                            game_state.leaderboard_mode = "classic"
                            game_state.menu_cache = None # Redraw leaderboard
                        elif action == "leaderboard_timed":
                            game_state.leaderboard_mode = "timed"
                            game_state.menu_cache = None
                        elif action == "leaderboard_survival":
                            game_state.leaderboard_mode = "survival"
                            game_state.menu_cache = None
                        elif action.startswith("edit_zone_"): # Edit Zone Points
                            try:
                                index = int(action.split("edit_zone_")[1])
                                if 0 <= index < len(game_state.scoring_zones):
                                    # Only enter edit mode if not already editing this zone's points
                                    if not (game_state.editing_zone_index == index and game_state.editing_zone_mode == "edit_points"):
                                        _reset_all_menu_editing_states(game_state) # Reset others
                                        game_state.editing_zone_index = index
                                        game_state.editing_zone_mode = "edit_points"
                                        game_state.editing_zone_points_input = str(game_state.scoring_zones[index][4]) # Pre-fill input
                                        game_state.menu_cache = None # Redraw to show input field
                                        logger.info(f"Started editing points for zone {index+1}")
                                else:
                                    logger.warning(f"Invalid zone index {index} for edit points action '{action}'")
                                    _reset_all_menu_editing_states(game_state)
                            except (ValueError, IndexError) as e:
                                logger.error(f"Error parsing zone index from action '{action}': {e}")
                                _reset_all_menu_editing_states(game_state)
                        elif action.startswith("move_zone_"): # Initiate Zone Move
                             try:
                                index = int(action.split("move_zone_")[1])
                                if 0 <= index < len(game_state.scoring_zones):
                                     _reset_all_menu_editing_states(game_state) # Reset menus first
                                     game_state.selected_zone_for_edit = index
                                     game_state.previous_state = CurrentGameState.MENU # Store state before edit
                                     game_state.current_state = CurrentGameState.ZONE_EDITING # Switch to interactive state
                                     show_notification(game_state, "Click inside zone to move, then drag. ESC to cancel.", duration=0) # Use helper
                                else:
                                    logger.warning(f"Invalid zone index {index} for move action '{action}'")
                             except (ValueError, IndexError) as e:
                                logger.error(f"Error parsing zone index from action '{action}': {e}")
                        elif action.startswith("resize_zone_"): # Initiate Zone Resize
                             try:
                                index = int(action.split("resize_zone_")[1])
                                if 0 <= index < len(game_state.scoring_zones):
                                     _reset_all_menu_editing_states(game_state)
                                     game_state.selected_zone_for_edit = index
                                     game_state.previous_state = CurrentGameState.MENU
                                     game_state.current_state = CurrentGameState.ZONE_EDITING
                                     show_notification(game_state, "Click & drag corner handles to resize. ESC to cancel.", duration=0) # Use helper
                                else:
                                     logger.warning(f"Invalid zone index {index} for resize action '{action}'")
                             except (ValueError, IndexError) as e:
                                logger.error(f"Error parsing zone index from action '{action}': {e}")
                        elif action.startswith("edit_player_name_"): # Edit Player Name
                            try:
                                index = int(action.split("edit_player_name_")[1])
                                if 0 <= index < len(game_state.players):
                                     # Only enter edit mode if not already editing this player
                                     if not (game_state.editing_player_index == index and game_state.editing_player_mode == "edit_name"):
                                         _reset_all_menu_editing_states(game_state) # Reset others
                                         game_state.editing_player_index = index
                                         game_state.editing_player_mode = "edit_name"
                                         game_state.editing_player_name_input = str(game_state.players[index].name) # Pre-fill
                                         game_state.menu_cache = None # Redraw menu
                                         logger.info(f"Started editing name for player {index+1}")
                                else:
                                     logger.warning(f"Invalid player index {index} for edit name action '{action}'")
                                     _reset_all_menu_editing_states(game_state)
                            except (ValueError, IndexError) as e:
                                logger.error(f"Error parsing player index from action '{action}': {e}")
                                _reset_all_menu_editing_states(game_state)
                        elif action.startswith("delete_zone_"): # Delete Zone (requires confirmation)
                             try:
                                index = int(action.split("delete_zone_")[1])
                                if 0 <= index < len(game_state.scoring_zones):
                                     if (game_state.editing_zone_index == index and game_state.editing_zone_mode == "confirm_delete"):
                                         # Second click confirms delete
                                         logger.info(f"Confirmed deleting zone {index+1}")
                                         del game_state.scoring_zones[index]
                                         game_state.special_hole = set_special_hole(game_state.scoring_zones) # Use helper
                                         show_notification(game_state, f"Zone {index+1} Deleted") # Use helper
                                         _reset_all_menu_editing_states(game_state) # Reset fully
                                     else:
                                         # First click, enter confirmation mode for this zone
                                         _reset_all_menu_editing_states(game_state) # Reset others
                                         game_state.editing_zone_index = index
                                         game_state.editing_zone_mode = "confirm_delete"
                                         game_state.menu_cache = None # Redraw menu to highlight
                                         show_notification(game_state, f"Click Delete again for zone {index+1} to confirm", duration=4.0) # Use helper
                                else:
                                     logger.warning(f"Invalid zone index {index} for delete action '{action}'")
                                     _reset_all_menu_editing_states(game_state)
                             except (ValueError, IndexError) as e:
                                logger.error(f"Error parsing zone index from action '{action}': {e}")
                                _reset_all_menu_editing_states(game_state)
                        elif action in known_submenu_nav_actions: # Navigate to a submenu
                            _reset_all_menu_editing_states(game_state) # Reset editing state first
                            game_state.submenu_active = action
                        else:
                            logger.warning(f"Unhandled MENU action string: {action}")

                    # Handle actions specific to the GAME_OVER state
                    elif game_state.current_state == CurrentGameState.GAME_OVER:
                        if action == "new_game_from_gameover":
                            reset_game(game_state) # Use util
                            game_state.current_state = CurrentGameState.GETTING_PLAYER_NAME # Start new game flow
                            game_state.win_condition_met = False
                        elif action == "show_leaderboard_from_gameover":
                            game_state.current_state = CurrentGameState.MENU # Switch state
                            game_state.submenu_active = "leaderboard" # Set submenu
                            game_state.win_condition_met = False
                            game_state.menu_cache = None # Force menu redraw
                        else:
                            logger.warning(f"Unhandled GAME_OVER action string: {action}")

                    # If any button action was processed, mark click handled and stop checking lower items
                    return True

            # If the loop completes without finding a matching button action (and volume wasn't adjusted)
            # This means the click was inside the menu area but not on a specific item we handle here.
            # This could happen if clicking on background space within the menu.
            # Return False as the click didn't trigger a specific *item* action.
            if not volume_adjusted:
                 logger.debug("Click inside menu area but not on a handled item.")
                 # It's debatable whether this should return True or False.
                 # Returning False means the main loop might log it as unhandled.
                 # Returning True means we acknowledge the click hit the menu, even if no action.
                 # Let's return False for now to indicate no *specific* action was taken.
                 pass # Continue loop or fall through

    # If the loop finishes and volume was adjusted, return True
    if volume_adjusted:
        return True

    # If loop finishes and nothing was handled
    return False


# --- Main Mouse Callback ---
def mouse_callback(event: int, x: int, y: int, flags: int, param: Any) -> None:
    """Handle mouse events for the main application window."""
    # (Code unchanged)
    game_state: GameState = param
    click_handled = False # Flag to track if the event was handled by specific logic

    if game_state is None:
        logger.error("Mouse callback invoked with None game_state parameter.")
        return

    # 1. Handle interactive zone editing first (if in that state)
    if game_state.current_state == CurrentGameState.ZONE_EDITING and event in [
        cv2.EVENT_LBUTTONDOWN,
        cv2.EVENT_MOUSEMOVE,
        cv2.EVENT_LBUTTONUP,
    ]:
        click_handled = _process_zone_editing_event(event, x, y, game_state)
        # We only want to consume the event (return early) if it was a button down/up
        # Mouse move should still allow other checks if needed (though unlikely here)
        if click_handled and event != cv2.EVENT_MOUSEMOVE:
            return # Event fully handled by zone editing logic

    # 2. Handle zone drawing (if in PLAYING state and drawing is active)
    if (
        not click_handled # Only process if not handled by zone editing
        and game_state.current_state == CurrentGameState.PLAYING
        and getattr(game_state, "drawing", False)
        and event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONUP]
    ):
        _process_drawing_event(event, x, y, game_state)
        # Mouse down/up during drawing are considered handled events
        if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP]:
            click_handled = True
            return # Event fully handled by drawing logic

    # 3. Handle clicks on menu items or game over buttons (only on LBUTTONDOWN)
    if (
        not click_handled # Only process if not handled above
        and game_state.current_state in [CurrentGameState.MENU, CurrentGameState.GAME_OVER]
        and event == cv2.EVENT_LBUTTONDOWN
    ):
        click_handled = _process_menu_or_gameover_click(x, y, game_state)
        if click_handled:
            return # Event fully handled by menu/gameover click logic

    # 4. Handle click on the main "Menu" button (only in PLAYING state, not drawing)
    if (
        not click_handled # Only process if not handled above
        and game_state.current_state == CurrentGameState.PLAYING
        and not getattr(game_state, "drawing", False) # Ensure drawing mode is OFF
        and event == cv2.EVENT_LBUTTONDOWN
    ):
        # Check if click is within the Menu button bounds
        if (
            UIConstants.MENU_BUTTON_X
            <= x
            <= UIConstants.MENU_BUTTON_X + UIConstants.MENU_BUTTON_WIDTH
            and UIConstants.MENU_BUTTON_Y
            <= y
            <= UIConstants.MENU_BUTTON_Y + UIConstants.MENU_BUTTON_HEIGHT
        ):
            logger.debug("Main Menu button clicked.")
            game_state.current_state = CurrentGameState.MENU
            game_state.submenu_active = None # Ensure main menu shows
            _reset_all_menu_editing_states(game_state) # Clear any lingering edit state
            click_handled = True
            return # Event handled

    # 5. Log unhandled clicks if desired (optional)
    # if not click_handled and event == cv2.EVENT_LBUTTONDOWN:
    #    if game_state.current_state not in [CurrentGameState.GETTING_PLAYER_NAME]: # Avoid logging clicks during name input
    #        logger.debug(f"Unhandled LBUTTONDOWN click at ({x},{y}) in state {game_state.current_state}")