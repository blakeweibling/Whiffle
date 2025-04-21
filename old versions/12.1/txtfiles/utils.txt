# utils.py

import cv2
import logging
import numpy as np
from typing import Any, Tuple, Optional, Callable
from math import ceil

# Imports needed for mouse_callback helpers
from constants import (
    UIConstants,
    GameConstants,
    ScoringConstants,
    MenuConstants,
)
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

logger = logging.getLogger(__name__)


# --- Helper: Find which handle/area of a zone is clicked ---
def _get_zone_click_location(
    x: int, y: int, zone_rect: Tuple[int, int, int, int]
) -> Optional[str]:
    """Determine if a click is on a corner, edge, or inside a zone."""
    zx, zy, zw, zh = zone_rect
    handle_size = UIConstants.ZONE_EDIT_HANDLE_SIZE
    half_handle = handle_size // 2

    # Check corners first (priority)
    if abs(x - zx) < half_handle and abs(y - zy) < half_handle:
        return "resize_tl"
    if abs(x - (zx + zw)) < half_handle and abs(y - zy) < half_handle:
        return "resize_tr"
    if abs(x - zx) < half_handle and abs(y - (zy + zh)) < half_handle:
        return "resize_bl"
    if abs(x - (zx + zw)) < half_handle and abs(y - (zy + zh)) < half_handle:
        return "resize_br"

    # Check edges (optional, could add later if needed)
    # Check if inside
    if zx < x < zx + zw and zy < y < zy + zh:
        return "move"

    return None


# --- Helper: Process Interactive Zone Editing Mouse Events ---
def _process_zone_editing_event(
    event: int, x: int, y: int, game_state: GameState
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
        )  # Revert state
        return False

    current_zone = game_state.scoring_zones[zone_idx]
    zx, zy, zw, zh, zp = current_zone  # Unpack including points

    min_size = ScoringConstants.MIN_ZONE_SIZE  # Minimum width/height

    if event == cv2.EVENT_LBUTTONDOWN:
        click_location = _get_zone_click_location(x, y, (zx, zy, zw, zh))
        if click_location:
            game_state.zone_editing_action = click_location
            game_state.drag_start_pos = (x, y)
            game_state.original_zone_on_drag_start = (
                current_zone  # Store original state
            )
            logger.info(
                f"Starting zone edit action: {click_location} for zone {zone_idx} at ({x},{y})"
            )
            handled = True
        else:
            logger.debug("Click outside selected zone during ZONE_EDITING state.")
            pass  # Currently, clicking outside does nothing, requires ESC

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
            handled = True  # Mouse move during drag is handled

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


# --- Drawing Event Processing (Unchanged but included for context) ---
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


# --- Helper to reset menu editing states ---
def _reset_all_menu_editing_states(game_state: GameState) -> None:
    """Resets all flags and temporary inputs related to menu editing."""
    game_state.editing_zone_index = None
    game_state.editing_zone_mode = None
    game_state.editing_zone_points_input = None
    game_state.editing_player_index = None
    game_state.editing_player_mode = None
    game_state.editing_player_name_input = None
    # Reset interactive zone editing state as well when closing menu entirely
    game_state.selected_zone_for_edit = None
    game_state.zone_editing_action = None
    game_state.drag_start_pos = None
    game_state.original_zone_on_drag_start = None
    # --- NEW: Reset Pagination ---
    game_state.edit_zones_current_page = 1
    # --- END NEW ---
    game_state.menu_cache = None  # Invalidate cache


# --- UPDATED: Handle new action strings ---
def _process_menu_or_gameover_click(x: int, y: int, game_state: GameState) -> bool:
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

    # --- Check for Close Button Click FIRST (Only in MENU state) ---
    if game_state.current_state == CurrentGameState.MENU:
        pad = UIConstants.MENU_CLOSE_BUTTON_PADDING
        size = UIConstants.MENU_CLOSE_BUTTON_SIZE
        # Calculate button's absolute screen coordinates
        close_btn_x1 = menu_x + menu_w - pad - size
        close_btn_y1 = menu_y + pad
        close_btn_x2 = menu_x + menu_w - pad
        close_btn_y2 = menu_y + pad + size

        if close_btn_x1 <= x < close_btn_x2 and close_btn_y1 <= y < close_btn_y2:
            logger.info("Menu close button clicked. Resuming game.")
            game_state.current_state = CurrentGameState.PLAYING
            game_state.submenu_active = None
            _reset_all_menu_editing_states(game_state)  # Reset all editing states
            return True  # Click handled
    # --- End Close Button Check ---

    # Check if click is within the general menu/gameover area (excluding close button check above)
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

    # Define sets of known submenu actions for easier checking
    # Extract action keys from MenuConstants
    main_menu_actions = {
        item[1] for item in MenuConstants.MAIN_MENU_ITEMS if isinstance(item[1], str)
    }
    zone_submenu_actions = {
        item[1] for item in MenuConstants.ZONE_SUBMENU_ITEMS if isinstance(item[1], str)
    }
    known_submenu_nav_actions = main_menu_actions.union(zone_submenu_actions) - {
        "resume",
        "quit",
        "back_to_main",
        "back_to_manage_zones",
        "save_zones",
        "load_zones",
        "clear_zones",
        "add_zone_info",
    }  # Remove non-nav actions

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

            # Use the consolidated reset function
            def reset_editing_states():
                _reset_all_menu_editing_states(game_state)

            # --- Removed Callable action handling as we switched to strings ---
            # if isinstance(action, Callable): ...
            # ---

            if isinstance(action, str):
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
                        logger.error(
                            "Could not import clean_exit. Cannot quit properly via menu."
                        )
                    return True

                # Menu State Actions
                if game_state.current_state == CurrentGameState.MENU:
                    logger.debug("Processing actions for MENU state...")

                    # --- NEW: Handle settings toggles and music cycle ---
                    if action == "toggle_game_sounds":
                        game_state.game_sounds_on = not game_state.game_sounds_on
                        logger.info(f"Game sounds toggled {'ON' if game_state.game_sounds_on else 'OFF'}")
                        game_state.set_volume() # Apply volume change
                        game_state.menu_cache = None # Redraw menu
                    elif action == "toggle_background_music":
                        # Let the method handle the logic and logging
                        game_state.toggle_background_music()
                        game_state.menu_cache = None # Redraw menu
                    elif action == "toggle_debug_overlay":
                         game_state.show_debug_overlay = not game_state.show_debug_overlay
                         logger.info(f"Debug overlay toggled {'ON' if game_state.show_debug_overlay else 'OFF'}")
                         game_state.menu_cache = None # Redraw menu
                    elif action == "toggle_debug_mode":
                         game_state.debug_mode = not game_state.debug_mode
                         log_level = logging.DEBUG if game_state.debug_mode else logging.INFO
                         logging.getLogger().setLevel(log_level)
                         for handler in logging.getLogger().handlers:
                             handler.setLevel(log_level)
                         logger.info(f"Debug mode toggled {'ON' if game_state.debug_mode else 'OFF'} (Level: {logging.getLevelName(log_level)})")
                         game_state.menu_cache = None # Redraw menu
                    elif action == "cycle_music_track":
                        logger.debug("Action matched: 'cycle_music_track'")
                        current_index = game_state.selected_music_track_index
                        total_tracks = len(GameConstants.BACKGROUND_MUSIC_TRACKS)
                        if total_tracks > 0:
                            next_index = (current_index + 1) % total_tracks
                            game_state.change_music_track(next_index) # Call the state method
                        else:
                            logger.warning("Cannot cycle music tracks, track list is empty.")
                        game_state.menu_cache = None # Redraw menu with new track number
                     # --- END NEW ---

                    elif action == "show_splash":
                        logger.debug("Action matched: 'show_splash'")
                        display_modal_splash(game_state, mouse_callback, game_state)
                        game_state.menu_cache = (
                            None  # Splash covers menu, redraw needed
                        )
                        # No return True needed here as we want loop to continue
                    elif action == "resume":
                        logger.debug("Action matched: 'resume'")
                        game_state.current_state = CurrentGameState.PLAYING
                        game_state.submenu_active = None
                        reset_editing_states()  # Reset states when resuming
                    elif action == "back_to_main":
                        logger.debug("Action matched: 'back_to_main'")
                        reset_editing_states()  # Reset specific edit modes
                        game_state.submenu_active = None
                    elif action == "add_zone_info":
                        logger.debug("Action matched: 'add_zone_info'")
                        game_state.show_notification(
                            "Press 's', then click and drag to draw zone"
                        )
                        game_state.current_state = CurrentGameState.PLAYING
                        game_state.submenu_active = None
                        reset_editing_states()
                    elif action == "clear_zones":
                        logger.debug("Action matched: 'clear_zones'")
                        clear_zones(game_state)
                        reset_editing_states()  # Reset edit modes
                    elif action == "save_zones":
                        logger.debug("Action matched: 'save_zones'")
                        save_zones(game_state)
                        game_state.menu_cache = (
                            None  # Content doesn't change, but feedback shown
                        )
                    elif action == "load_zones":
                        logger.debug("Action matched: 'load_zones'")
                        load_zones(game_state)
                        reset_editing_states()  # Reset edit modes
                    elif action.startswith("set_mode_"):
                        logger.debug("Action matched: 'set_mode_*'")
                        new_mode = action.split("set_mode_")[1]
                        valid_modes = ["classic", "timed", "fun", "practice", "survival"]
                        if new_mode not in valid_modes:
                             logger.error(f"Invalid mode '{new_mode}' extracted from action '{action}'. Ignoring.")
                        elif game_state.game_mode != new_mode:
                            logger.info(f"Game mode changing to: {new_mode}")
                            game_state.save_score(
                                game_state.get_current_player().name,
                                mode=game_state.game_mode, # Save score for the *old* mode
                            )
                            game_state.game_mode = new_mode
                            reset_game(game_state)  # Full reset for mode change
                            game_state.current_state = CurrentGameState.PLAYING
                            logger.info(f"Game state set to: {game_state.current_state}")
                            game_state.submenu_active = None
                            reset_editing_states()
                        else:
                            logger.info(f"Game mode already set to: {new_mode}")
                            game_state.current_state = CurrentGameState.PLAYING
                            game_state.submenu_active = None
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
                                reset_game(game_state)  # Full reset for player switch
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
                        reset_editing_states()  # Reset edit modes after selection attempt
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
                        reset_editing_states()  # Reset edit modes
                    elif action == "back_to_manage_zones":
                        logger.debug("Action matched: 'back_to_manage_zones'")
                        reset_editing_states()  # Reset specific edit modes
                        game_state.submenu_active = "manage_zones"

                    elif action == "prev_edit_zone_page":
                        logger.debug("Action matched: 'prev_edit_zone_page'")
                        if game_state.edit_zones_current_page > 1:
                            game_state.edit_zones_current_page -= 1
                            game_state.menu_cache = None  # Force redraw
                        else:
                            logger.debug("Already on first page.")
                    elif action == "next_edit_zone_page":
                        logger.debug("Action matched: 'next_edit_zone_page'")
                        items_per_page = game_state.edit_zones_items_per_page
                        total_zones = len(game_state.scoring_zones)
                        total_pages = max(1, ceil(total_zones / items_per_page))
                        if game_state.edit_zones_current_page < total_pages:
                            game_state.edit_zones_current_page += 1
                            game_state.menu_cache = None  # Force redraw
                        else:
                            logger.debug("Already on last page.")

                    # --- NEW: Leaderboard mode switching ---
                    elif action == "leaderboard_classic":
                        logger.debug("Setting leaderboard view to Classic")
                        game_state.leaderboard_mode = "classic"
                        game_state.menu_cache = None
                    elif action == "leaderboard_timed":
                         logger.debug("Setting leaderboard view to Timed")
                         game_state.leaderboard_mode = "timed"
                         game_state.menu_cache = None
                    # Add elif for "leaderboard_survival" etc. if needed
                    # --- END NEW ---

                    elif action.startswith("edit_zone_"):
                        logger.debug("Action matched: 'edit_zone_*' (Points)")
                        try:
                            index = int(action.split("edit_zone_")[1])
                            if 0 <= index < len(game_state.scoring_zones):
                                if not (
                                    game_state.editing_zone_index == index
                                    and game_state.editing_zone_mode == "edit_points"
                                ):
                                    _reset_all_menu_editing_states(
                                        game_state
                                    )  # Reset others first
                                    current_points = game_state.scoring_zones[index][4]
                                    game_state.editing_zone_index = index
                                    game_state.editing_zone_mode = "edit_points"
                                    game_state.editing_zone_points_input = str(
                                        current_points
                                    )
                                    game_state.menu_cache = None  # Force redraw
                                    logger.info(
                                        f"Selected zone {index+1} for editing points. Initial value: {current_points}"
                                    )
                            else:
                                logger.warning(f"Invalid zone index for edit: {index}")
                                _reset_all_menu_editing_states(game_state)
                        except (ValueError, IndexError) as e:
                            logger.error(
                                f"Error parsing zone index from edit action: {action} - {e}"
                            )
                            _reset_all_menu_editing_states(game_state)

                    elif action.startswith("move_zone_"):
                        logger.debug("Action matched: 'move_zone_*'")
                        try:
                            index = int(action.split("move_zone_")[1])
                            if 0 <= index < len(game_state.scoring_zones):
                                _reset_all_menu_editing_states(
                                    game_state
                                )  # Clear points/delete confirms etc.
                                game_state.selected_zone_for_edit = index
                                game_state.previous_state = (
                                    CurrentGameState.MENU
                                )  # Store where we came from
                                game_state.current_state = CurrentGameState.ZONE_EDITING
                                game_state.zone_editing_action = (
                                    None  # Start in selecting mode within ZONE_EDITING
                                )
                                game_state.drag_start_pos = None
                                game_state.original_zone_on_drag_start = None
                                logger.info(
                                    f"Entering ZONE_EDITING state to move zone {index+1}."
                                )
                                game_state.show_notification(
                                    "Click inside zone to move, ESC to cancel",
                                    duration=0,
                                )  # Persistent until ESC
                            else:
                                logger.warning(f"Invalid zone index for move: {index}")
                        except (ValueError, IndexError) as e:
                            logger.error(
                                f"Error parsing zone index from move action: {action} - {e}"
                            )

                    elif action.startswith("resize_zone_"):
                        logger.debug("Action matched: 'resize_zone_*'")
                        try:
                            index = int(action.split("resize_zone_")[1])
                            if 0 <= index < len(game_state.scoring_zones):
                                _reset_all_menu_editing_states(
                                    game_state
                                )  # Clear points/delete confirms etc.
                                game_state.selected_zone_for_edit = index
                                game_state.previous_state = (
                                    CurrentGameState.MENU
                                )  # Store where we came from
                                game_state.current_state = CurrentGameState.ZONE_EDITING
                                game_state.zone_editing_action = (
                                    None  # Start in selecting mode within ZONE_EDITING
                                )
                                game_state.drag_start_pos = None
                                game_state.original_zone_on_drag_start = None
                                logger.info(
                                    f"Entering ZONE_EDITING state to resize zone {index+1}."
                                )
                                game_state.show_notification(
                                    "Click corner handles to resize, ESC to cancel",
                                    duration=0,
                                )  # Persistent until ESC
                            else:
                                logger.warning(
                                    f"Invalid zone index for resize: {index}"
                                )
                        except (ValueError, IndexError) as e:
                            logger.error(
                                f"Error parsing zone index from resize action: {action} - {e}"
                            )

                    elif action.startswith("edit_player_name_"):
                        logger.debug("Action matched: 'edit_player_name_*'")
                        try:
                            index = int(action.split("edit_player_name_")[1])
                            if 0 <= index < len(game_state.players):
                                if not (
                                    game_state.editing_player_index == index
                                    and game_state.editing_player_mode == "edit_name"
                                ):
                                    _reset_all_menu_editing_states(
                                        game_state
                                    ) # Reset others first
                                    current_name = game_state.players[index].name
                                    game_state.editing_player_index = index
                                    game_state.editing_player_mode = "edit_name"
                                    game_state.editing_player_name_input = str(
                                        current_name
                                    )
                                    game_state.menu_cache = None  # Force redraw
                                    logger.info(
                                        f"Selected player {index+1} for editing name. Initial value: '{current_name}'"
                                    )
                            else:
                                logger.warning(
                                    f"Invalid player index for edit name: {index}"
                                )
                                _reset_all_menu_editing_states(game_state)
                        except (ValueError, IndexError) as e:
                            logger.error(
                                f"Error parsing player index from edit name action: {action} - {e}"
                            )
                            _reset_all_menu_editing_states(game_state)

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
                                    _reset_all_menu_editing_states(
                                        game_state
                                    )  # Reset state after delete
                                else:
                                    # First click: enter confirm mode
                                    _reset_all_menu_editing_states(
                                        game_state
                                    )  # Reset any other editing modes
                                    game_state.editing_zone_index = index
                                    game_state.editing_zone_mode = "confirm_delete"
                                    game_state.menu_cache = None  # Invalidate cache
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
                                _reset_all_menu_editing_states(game_state)
                        except (ValueError, IndexError) as e:
                            logger.error(
                                f"Error parsing zone index from delete action: {action} - {e}"
                            )
                            _reset_all_menu_editing_states(game_state)

                    elif action in known_submenu_nav_actions:
                        logger.info(f"Switching to submenu: {action}")
                        reset_editing_states()  # Reset editing states and page number
                        game_state.submenu_active = action
                    else:
                        logger.warning(
                            f"Unhandled string action in MENU state: {action}"
                        )

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
                    else:
                        logger.warning(
                            f"Unhandled string action in GAME_OVER state: {action}"
                        )

                return True  # Click handled by string action

            else:
                logger.warning(
                    f"Clicked item '{label}' has unhandled action type: {type(action)}"
                )
                return True  # Consider it handled

    logger.debug(
        f"Click in {game_state.current_state} area but not on a specific registered item."
    )
    return False


# --- RESTRUCTURED MOUSE CALLBACK ---
def mouse_callback(event: int, x: int, y: int, flags: int, param: Any) -> None:
    """Handle mouse events for the main application window."""
    game_state: GameState = param  # Type hint for clarity
    if game_state is None:
        logger.warning("Mouse callback received None for game_state param.")
        return

    click_handled = False

    # --- Priority 1: Interactive Zone Editing (if in ZONE_EDITING state) ---
    if game_state.current_state == CurrentGameState.ZONE_EDITING and event in [
        cv2.EVENT_LBUTTONDOWN,
        cv2.EVENT_MOUSEMOVE,
        cv2.EVENT_LBUTTONUP,
    ]:
        logger.debug(f"Mouse event {event} received during ZONE_EDITING.")
        click_handled = _process_zone_editing_event(event, x, y, game_state)
        # Prevent other actions if a drag/click was handled within zone editing
        # Allow mouse move events to fall through if not handled by dragging
        if click_handled and event != cv2.EVENT_MOUSEMOVE:
            return

    # --- Priority 2: Drawing New Zones (if PLAYING and drawing is active) ---
    if (
        not click_handled  # Check if not handled above
        and game_state.current_state == CurrentGameState.PLAYING
        and getattr(game_state, "drawing", False)
        and event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONUP]
    ):
        logger.debug(f"Mouse event {event} received while drawing is active.")
        _process_drawing_event(event, x, y, game_state)
        # Drawing handles its own state transitions on LBUTTONUP
        if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP]:
            click_handled = True
            return  # Prevent menu button check if drawing finished on this click

    # --- Priority 3: Clicks within MENU or GAME_OVER states ---
    if (
        not click_handled
        and game_state.current_state
        in [CurrentGameState.MENU, CurrentGameState.GAME_OVER]
        and event == cv2.EVENT_LBUTTONDOWN
    ):
        logger.debug(
            f"LBUTTONDOWN in {game_state.current_state}, checking menu/close button..."
        )
        # _process_menu_or_gameover_click now includes the close button check
        click_handled = _process_menu_or_gameover_click(x, y, game_state)

    # --- Priority 4: Menu Button Click (if PLAYING and NOT drawing) ---
    if (
        not click_handled
        and game_state.current_state == CurrentGameState.PLAYING
        and not getattr(game_state, "drawing", False)  # Ensure not drawing
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
            _reset_all_menu_editing_states(game_state)  # Reset all editing states
            click_handled = True

    # --- Log Unhandled Clicks ---
    if not click_handled and event == cv2.EVENT_LBUTTONDOWN:
        # Ignore clicks during some states
        if game_state.current_state not in [
            CurrentGameState.GETTING_PLAYER_NAME,
            CurrentGameState.ZONE_EDITING,  # Clicks outside zone already logged/ignored in helper
        ]:
            logger.debug(
                f"Unhandled click at ({x},{y}) in state {game_state.current_state}"
            )