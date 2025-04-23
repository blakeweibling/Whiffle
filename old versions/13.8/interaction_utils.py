# interaction_utils.py

import logging
import time
import traceback  # Add traceback module import
from math import ceil
from typing import Any, Dict, Optional, Tuple, Callable
import os  # Make sure os is imported at the top level
import cv2
import json
import requests

# Import cleanup util
from cleanup_utils import clean_exit

# Imports needed for mouse_callback helpers
from constants import (
    GameConstants,
    MenuConstants,
    ScoringConstants,
    UIConstants,
    ResolutionConstants,
    DiscordConstants,
    XConstants,
)

# Import GameState class and CurrentGameState enum from correct locations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game_state import GameState

    # Only import for type checking, not at runtime
    from utils import mouse_callback

# Import the necessary utility functions from CORRECT locations
from game_state_helpers import (
    clear_zones,
    load_zones,
    save_score,
    save_zones,
    set_special_hole,
    show_notification,
)

from game_state_utils import reset_game
from game_state_utils import (
    change_music_track,
    save_settings,
    set_volume,
    toggle_background_music,
    toggle_game_sounds,
)
from game_types import CurrentGameState

# Import Player class
from player import Player

# Import overlap check function from scoring
from scoring import _zones_overlap

# Import UI screens/modals
from ui_screens import display_modal_splash, display_heatmap_modal

# Add tweepy for X.com API
try:
    import tweepy
except ImportError:
    logging.warning(
        "tweepy module not found. X.com sharing will not work. Install with: pip install tweepy"
    )

# Add Google Drive utils
import google_drive_utils

# Add YouTube utils
import youtube_utils

logger = logging.getLogger(__name__)

# Mouse event handler lookup for more efficient state dispatching
MouseEventHandlers = Dict[CurrentGameState, Dict[int, Callable]]


# Create a more efficient dispatch system for mouse callbacks
def _get_mouse_event_handlers() -> MouseEventHandlers:
    """Create a lookup table for efficiently dispatching mouse events based on game state."""
    handlers = {}

    # Define a helper for menu states that share common handlers
    def menu_handler(event: int, x: int, y: int, game_state: "GameState") -> bool:
        """Common handler for menu interaction states"""
        return _process_menu_or_modal_click(x, y, game_state)

    # Game over handler that uses our specialized function - get mouse_callback at runtime
    def game_over_handler(event: int, x: int, y: int, game_state: "GameState") -> bool:
        """Specialized handler for game over screen"""
        # Import at function level to avoid circular import
        import utils

        return _process_game_over_click(x, y, game_state, utils.mouse_callback)

    # Handler for username input screen
    def username_input_handler(
        event: int, x: int, y: int, game_state: "GameState"
    ) -> bool:
        """Handler for username input screen X button click"""
        # Check if X button exists and was clicked
        if hasattr(game_state, "username_x_button"):
            btn_x, btn_y, btn_w, btn_h = game_state.username_x_button
            if btn_x <= x <= btn_x + btn_w and btn_y <= y <= btn_y + btn_h:
                logger.debug("Username input X button clicked")
                # Same behavior as pressing ESC - use default name
                if hasattr(game_state, "players") and game_state.players:
                    try:
                        game_state.players[0].name = "Player 1"  # Use default
                        game_state.player_name_input_active = False
                        game_state.current_state = CurrentGameState.PLAYING
                        show_notification(
                            game_state, "Using default name 'Player 1'", duration=2.0
                        )
                        return True
                    except Exception as e:
                        logger.error(f"Error setting default name via X button: {e}")
        return False

    # State-specific handlers
    handlers[CurrentGameState.PLAYING] = {
        cv2.EVENT_LBUTTONDOWN: lambda e, x, y, g: (
            _process_drawing_event(e, x, y, g)
            if getattr(g, "drawing", False)
            else _process_menu_or_modal_click(x, y, g)
        ),
        cv2.EVENT_MOUSEMOVE: lambda e, x, y, g: (
            _process_drawing_event(e, x, y, g)
            if getattr(g, "drawing", False)
            else False
        ),
        cv2.EVENT_LBUTTONUP: lambda e, x, y, g: (
            _process_drawing_event(e, x, y, g)
            if getattr(g, "drawing", False)
            else False
        ),
    }

    handlers[CurrentGameState.ZONE_EDITING] = {
        cv2.EVENT_LBUTTONDOWN: lambda e, x, y, g: _process_zone_editing_event(
            e, x, y, g
        ),
        cv2.EVENT_MOUSEMOVE: lambda e, x, y, g: _process_zone_editing_event(e, x, y, g),
        cv2.EVENT_LBUTTONUP: lambda e, x, y, g: _process_zone_editing_event(e, x, y, g),
    }

    # GAME_OVER has its own specialized handler
    handlers[CurrentGameState.GAME_OVER] = {cv2.EVENT_LBUTTONDOWN: game_over_handler}

    # For states that just handle menu clicks
    for state in [
        CurrentGameState.MENU,
        CurrentGameState.PAUSED,
        CurrentGameState.CONFIRM_QUIT,
    ]:
        handlers[state] = {cv2.EVENT_LBUTTONDOWN: menu_handler}

    # Register username input handler
    handlers[CurrentGameState.GETTING_PLAYER_NAME] = {
        cv2.EVENT_LBUTTONDOWN: username_input_handler
    }

    return handlers


# Get the handlers once at module init time
EVENT_HANDLERS = _get_mouse_event_handlers()


# --- Helper: Find which handle/area of a zone is clicked ---
def _get_zone_click_location(
    x: int, y: int, zone_rect: Tuple[int, int, int, int]
) -> Optional[str]:
    zx, zy, zw, zh = zone_rect
    handle_size = UIConstants.ZONE_EDIT_HANDLE_SIZE
    half_handle = handle_size // 2
    if abs(x - zx) < half_handle and abs(y - zy) < half_handle:
        return "resize_tl"
    if abs(x - (zx + zw)) < half_handle and abs(y - zy) < half_handle:
        return "resize_tr"
    if abs(x - zx) < half_handle and abs(y - (zy + zh)) < half_handle:
        return "resize_bl"
    if abs(x - (zx + zw)) < half_handle and abs(y - (zy + zh)) < half_handle:
        return "resize_br"
    if zx <= x < zx + zw and zy <= y < zy + zh:
        return "move"
    return None


# --- Helper: Process Interactive Zone Editing Mouse Events ---
def _process_zone_editing_event(
    event: int, x: int, y: int, game_state: "GameState", is_dragging: bool = False
) -> bool:
    handled = False
    zone_idx = getattr(game_state, "selected_zone_for_edit", None)
    if zone_idx is None or not (
        0 <= zone_idx < len(getattr(game_state, "scoring_zones", []))
    ):
        if game_state.current_state == CurrentGameState.ZONE_EDITING:
            logger.warning(
                "Zone editing event processed with invalid/no selected zone index. Reverting state."
            )
        if hasattr(game_state, "current_state"):
            try:
                prev_state = getattr(game_state, "previous_state", None)
                game_state.current_state = (
                    prev_state if prev_state else CurrentGameState.MENU
                )
                game_state.previous_state = None
            except AttributeError:
                game_state.current_state = CurrentGameState.MENU
            game_state.selected_zone_for_edit = None
            game_state.zone_editing_action = None
            game_state.drag_start_pos = None
            game_state.original_zone_on_drag_start = None
        return False
    current_zone = game_state.scoring_zones[zone_idx]
    zx, zy, zw, zh, zp = current_zone
    min_size = getattr(ScoringConstants, "MIN_ZONE_SIZE", 10)

    # If dragging, treat as MOUSEMOVE regardless of event type
    if is_dragging:
        event = cv2.EVENT_MOUSEMOVE

    if event == cv2.EVENT_LBUTTONDOWN:
        click_location = _get_zone_click_location(x, y, (zx, zy, zw, zh))
        if click_location:
            game_state.zone_editing_action = click_location
            game_state.drag_start_pos = (x, y)
            game_state.original_zone_on_drag_start = current_zone
            logger.debug(
                f"Zone editing started: Action={click_location}, Start=({x},{y})"
            )
            handled = True
        else:
            logger.debug(
                "Click outside selected zone handles during ZONE_EDITING state."
            )
    elif event == cv2.EVENT_MOUSEMOVE:
        if getattr(game_state, "drag_start_pos", None) and getattr(
            game_state, "zone_editing_action", None
        ):
            drag_x_start, drag_y_start = game_state.drag_start_pos
            dx, dy = x - drag_x_start, y - drag_y_start
            new_x, new_y, new_w, new_h = zx, zy, zw, zh
            action = game_state.zone_editing_action
            orig_zone = getattr(game_state, "original_zone_on_drag_start", None)
            if not orig_zone:
                logger.error("Original zone state missing during drag move/resize.")
                game_state.zone_editing_action = None
                game_state.drag_start_pos = None
                return False
            orig_x, orig_y, orig_w, orig_h, _ = orig_zone
            if action == "move":
                new_x, new_y = orig_x + dx, orig_y + dy
            elif action.startswith("resize"):
                if action == "resize_tl":
                    new_x, new_y, new_w, new_h = (
                        orig_x + dx,
                        orig_y + dy,
                        orig_w - dx,
                        orig_h - dy,
                    )
                elif action == "resize_tr":
                    new_x, new_y, new_w, new_h = (
                        orig_x,
                        orig_y + dy,
                        orig_w + dx,
                        orig_h - dy,
                    )
                elif action == "resize_bl":
                    new_x, new_y, new_w, new_h = (
                        orig_x + dx,
                        orig_y,
                        orig_w - dx,
                        orig_h + dy,
                    )
                elif action == "resize_br":
                    new_x, new_y, new_w, new_h = (
                        orig_x,
                        orig_y,
                        orig_w + dx,
                        orig_h + dy,
                    )
                new_w = max(min_size, new_w)
                new_h = max(min_size, new_h)
                if action == "resize_tl":
                    new_x = (orig_x + orig_w) - new_w
                    new_y = (orig_y + orig_h) - new_h
                elif action == "resize_tr":
                    new_y = (orig_y + orig_h) - new_h
                elif action == "resize_bl":
                    new_x = (orig_x + orig_w) - new_w
            game_state.scoring_zones[zone_idx] = (new_x, new_y, new_w, new_h, zp)
            handled = True
    elif event == cv2.EVENT_LBUTTONUP:
        if getattr(game_state, "drag_start_pos", None) and getattr(
            game_state, "zone_editing_action", None
        ):
            logger.debug(
                f"Zone editing finished: Action={game_state.zone_editing_action}"
            )
            final_zone = game_state.scoring_zones[zone_idx]
            fx, fy, fw, fh, fp = final_zone
            valid_edit = True
            error_message = None
            if fw < min_size or fh < min_size:
                error_message = f"Zone too small! Min size {min_size}. Reverted."
                valid_edit = False
            else:
                other_zones = [
                    z for i, z in enumerate(game_state.scoring_zones) if i != zone_idx
                ]
                if _zones_overlap(final_zone[:4], other_zones):
                    error_message = "Edit causes overlap! Reverted."
                    valid_edit = False
            if not valid_edit:
                show_notification(
                    game_state, error_message, is_error=True, duration=3.0
                )
                if game_state.original_zone_on_drag_start:
                    game_state.scoring_zones[zone_idx] = (
                        game_state.original_zone_on_drag_start
                    )
                else:
                    logger.error("Cannot revert zone edit, original state was None.")
            else:
                game_state.special_hole = set_special_hole(game_state.scoring_zones)
                show_notification(
                    game_state, f"Zone {zone_idx+1} updated", duration=1.5
                )
            game_state.zone_editing_action = None
            game_state.drag_start_pos = None
            game_state.original_zone_on_drag_start = None
            handled = True
    return handled


# --- Drawing Event Processing ---
def _process_drawing_event(event: int, x: int, y: int, game_state: "GameState") -> None:
    if event == cv2.EVENT_LBUTTONDOWN:
        if game_state.drawing:
            game_state.start_x, game_state.start_y = x, y
            game_state.temp_zone = None
            game_state.drawing_points_input = ""
            logger.debug(f"Drawing started at ({x}, {y})")
    elif event == cv2.EVENT_MOUSEMOVE:
        if (
            game_state.drawing
            and game_state.start_x is not None
            and game_state.start_y is not None
        ):
            x1, y1 = min(game_state.start_x, x), min(game_state.start_y, y)
            w, h = abs(game_state.start_x - x), abs(game_state.start_y - y)
            game_state.temp_zone = (x1, y1, w, h)
    elif event == cv2.EVENT_LBUTTONUP:
        if game_state.drawing:
            logger.debug("Drawing mouse up.")
            if game_state.temp_zone:
                x1, y1, w, h = game_state.temp_zone
                min_size = getattr(ScoringConstants, "MIN_ZONE_SIZE", 10)
                if w >= min_size and h >= min_size:
                    points_str = game_state.drawing_points_input
                    points = getattr(ScoringConstants, "DEFAULT_POINTS", 100)
                    try:
                        if points_str:
                            points = int(points_str)
                            max_pts = getattr(ScoringConstants, "MAX_POINTS", 999)
                            if not (1 <= points <= max_pts):
                                show_notification(
                                    game_state,
                                    f"Points must be 1-{max_pts}. Using default {ScoringConstants.DEFAULT_POINTS}.",
                                    is_error=True,
                                    duration=3.0,
                                )
                                points = ScoringConstants.DEFAULT_POINTS
                    except ValueError:
                        if points_str:
                            show_notification(
                                game_state,
                                f"Invalid points '{points_str}'. Using default {ScoringConstants.DEFAULT_POINTS}.",
                                is_error=True,
                                duration=3.0,
                            )
                        points = ScoringConstants.DEFAULT_POINTS
                    new_zone = (x1, y1, w, h, points)
                    if not _zones_overlap(
                        new_zone[:4], getattr(game_state, "scoring_zones", [])
                    ):
                        game_state.scoring_zones.append(new_zone)
                        game_state.special_hole = set_special_hole(
                            game_state.scoring_zones
                        )
                        show_notification(game_state, f"Zone Added ({points} pts)")
                        logger.info(f"Added zone: {new_zone}")
                    else:
                        show_notification(
                            game_state, "Zone Overlaps! Not Added.", is_error=True
                        )
                        logger.warning("Zone overlap detected, not adding.")
                else:
                    show_notification(
                        game_state,
                        f"Zone too small (Min: {min_size}x{min_size})",
                        is_error=True,
                    )
                    logger.warning("Drawn zone was too small.")
            game_state.drawing = False
            game_state.temp_zone = None
            game_state.start_x = None
            game_state.start_y = None
            game_state.drawing_points_input = ""


# --- Helper to reset menu editing states ---
def _reset_all_menu_editing_states(game_state: "GameState") -> None:
    attrs_to_reset = {
        "editing_zone_index": None,
        "editing_zone_mode": None,
        "editing_zone_points_input": None,
        "editing_player_index": None,
        "editing_player_mode": None,
        "editing_player_name_input": None,
        "selected_zone_for_edit": None,
        "zone_editing_action": None,
        "drag_start_pos": None,
        "original_zone_on_drag_start": None,
        "edit_zones_current_page": 1,
        "menu_cache": None,
        "click_feedback_state": None,
    }
    for attr, value in attrs_to_reset.items():
        if hasattr(game_state, attr):
            setattr(game_state, attr, value)


# === Process Game Over Screen Clicks ===
def _process_game_over_click(
    x: int, y: int, game_state: "GameState", callback: Callable
) -> bool:
    """
    Handle clicks on the Game Over screen, including the heatmap button.
    Returns True if click was handled, False otherwise.
    """
    logger.debug(f"Processing Game Over screen click at ({x}, {y})")

    if not hasattr(game_state, "game_over_buttons"):
        logger.warning("Missing game_over_buttons dictionary in game_state")
        return False

    # Check for heatmap button click
    if "heatmap" in game_state.game_over_buttons:
        heatmap_button_rect = game_state.game_over_buttons["heatmap"]
        bx, by, bw, bh = heatmap_button_rect

        if bx <= x < bx + bw and by <= y < by + bh:
            logger.info("Show Heatmap button clicked on Game Over screen.")
            game_state.click_feedback_state = (heatmap_button_rect, time.time())
            try:
                display_heatmap_modal(game_state, callback, game_state)
                return True
            except Exception as e:
                logger.exception(f"Error occurred when trying to display heatmap: {e}")
                show_notification(game_state, "Error displaying heatmap", is_error=True)
                return True

    # Handle play again button
    if "play_again" in game_state.game_over_buttons:
        play_again_rect = game_state.game_over_buttons["play_again"]
        bx, by, bw, bh = play_again_rect

        if bx <= x < bx + bw and by <= y < by + bh:
            logger.info("Play Again button clicked.")
            game_state.click_feedback_state = (play_again_rect, time.time())
            reset_game(game_state)
            game_state.current_state = CurrentGameState.PLAYING
            return True

    # Handle main menu button
    if "main_menu" in game_state.game_over_buttons:
        main_menu_rect = game_state.game_over_buttons["main_menu"]
        bx, by, bw, bh = main_menu_rect

        if bx <= x < bx + bw and by <= y < by + bh:
            logger.info("Main Menu button clicked.")
            game_state.click_feedback_state = (main_menu_rect, time.time())
            game_state.current_state = CurrentGameState.MENU
            return True

    return False


# --- Process Menu / CONFIRM_QUIT Click ---
def _process_menu_or_modal_click(x: int, y: int, game_state: "GameState") -> bool:
    """Handles clicks ONLY for MENU and CONFIRM_QUIT states."""
    current_state = getattr(game_state, "current_state", None)

    # Debug logging for function entry
    logger.debug(
        f"_process_menu_or_modal_click called with coords ({x}, {y}) in state {current_state}"
    )

    # Check for PLAYING state to handle menu button click
    if current_state == CurrentGameState.PLAYING:
        # Handle menu button click
        menu_button_rect = (
            UIConstants.MENU_BUTTON_X,
            UIConstants.MENU_BUTTON_Y,
            UIConstants.MENU_BUTTON_WIDTH,
            UIConstants.MENU_BUTTON_HEIGHT,
        )
        menu_btn_x, menu_btn_y, menu_btn_w, menu_btn_h = menu_button_rect
        logger.debug(
            f"Menu button is at ({menu_btn_x}, {menu_btn_y}) with size {menu_btn_w}x{menu_btn_h}"
        )

        if (
            menu_btn_x <= x < menu_btn_x + menu_btn_w
            and menu_btn_y <= y < menu_btn_y + menu_btn_h
        ):
            logger.info(f"Menu button clicked at ({x}, {y})")
            game_state.click_feedback_state = (menu_button_rect, time.time())
            game_state.current_state = CurrentGameState.MENU
            game_state.menu_cache = None  # Force menu redraw
            logger.info("Switched to MENU state")
            return True

    # Exclude GAME_OVER from this function's responsibility
    if current_state not in [
        CurrentGameState.MENU,
        CurrentGameState.CONFIRM_QUIT,
        CurrentGameState.PAUSED,
    ]:
        return False

    # Debug logging for mouse position
    logger.debug(
        f"Menu click: processing at coordinates ({x}, {y}) in state {current_state}"
    )

    # Check for stats panel heatmap button click (in MENU or PAUSED state)
    if current_state in [CurrentGameState.MENU, CurrentGameState.PAUSED]:
        # Calculate stats panel dimensions and position - using the same calculations as _draw_stats_display in ui.py
        current_width, current_height = game_state.get_current_resolution_dimensions()
        menu_x, menu_y = getattr(game_state, "menu_pos", (0, 0))
        menu_w = getattr(game_state, "menu_width", 600)
        stats_content_height = 230
        button_height = 35
        panel_padding_bottom = 15
        total_content_height = (
            stats_content_height + button_height + panel_padding_bottom
        )
        panel_width = 350
        panel_height = max(
            total_content_height + 40, getattr(game_state, "menu_height", 450)
        )
        padding = 20
        panel_x = menu_x + menu_w + padding
        panel_y = menu_y

        # Adjust panel position if it would go off-screen
        if panel_x + panel_width > current_width - padding:
            panel_x = menu_x - panel_width - padding
        if panel_x < padding:
            panel_x = (current_width - panel_width) // 2
            panel_y = menu_y + getattr(game_state, "menu_height", 450) + padding
            panel_height = total_content_height + 40

        panel_x = max(padding, min(panel_x, current_width - panel_width - padding))
        panel_y = max(padding, min(panel_y, current_height - panel_height - padding))

        # Calculate heatmap button position and dimensions
        text_x_offset = 15
        button_y_pos = panel_y + panel_height - button_height - panel_padding_bottom
        button_x_pos = panel_x + text_x_offset
        heatmap_button_width = panel_width - (2 * text_x_offset)

        # Check if click is within heatmap button
        heatmap_button_rect = (
            button_x_pos,
            button_y_pos,
            heatmap_button_width,
            button_height,
        )
        bx, by, bw, bh = heatmap_button_rect

        if bx <= x < bx + bw and by <= y < by + bh:
            logger.info("Stats panel heatmap button clicked.")
            game_state.click_feedback_state = (heatmap_button_rect, time.time())
            try:
                # Call the heatmap display function with a dynamic import of mouse_callback
                import utils

                display_heatmap_modal(game_state, utils.mouse_callback, game_state)
                return True
            except Exception as e:
                logger.exception(f"Error displaying heatmap from stats panel: {e}")
                show_notification(game_state, "Error displaying heatmap", is_error=True)
                return True

    # Rest of the function remains largely unchanged, but actions related to GAME_OVER are now unreachable
    required_attrs = ["menu_pos", "menu_width", "menu_height", "submenu_items"]
    if not all(hasattr(game_state, attr) for attr in required_attrs):
        logger.warning(
            "UI attributes missing in game_state for menu/modal click processing."
        )
        return False
    menu_x, menu_y = game_state.menu_pos
    logger.debug(f"Menu position: {menu_x}, {menu_y}")
    relative_x, relative_y = x - menu_x, y - menu_y
    logger.debug(f"Relative click position within menu: {relative_x}, {relative_y}")
    menu_w = game_state.menu_width
    menu_h = game_state.menu_height
    logger.debug(f"Menu dimensions: width={menu_w}, height={menu_h}")

    # Log if the click is within the menu bounds
    if 0 <= relative_x < menu_w and 0 <= relative_y < menu_h:
        logger.debug("Click is WITHIN menu bounds")
    else:
        logger.debug("Click is OUTSIDE menu bounds")

    # Handle resolution button click (outside of menu window)
    res_button_rect = (
        UIConstants.RESOLUTION_BUTTON_X,
        UIConstants.RESOLUTION_BUTTON_Y,
        UIConstants.RESOLUTION_BUTTON_WIDTH,
        UIConstants.RESOLUTION_BUTTON_HEIGHT,
    )
    res_x, res_y, res_w, res_h = res_button_rect
    if res_x <= x < res_x + res_w and res_y <= y < res_y + res_h:
        logger.debug(f"Resolution button clicked at ({x}, {y})")
        game_state.click_feedback_state = (res_button_rect, time.time())

        # Toggle between available resolutions
        if hasattr(game_state, "set_resolution") and hasattr(
            game_state, "current_resolution_key"
        ):
            available_resolutions = list(ResolutionConstants.RESOLUTIONS.keys())
            current_index = available_resolutions.index(
                game_state.current_resolution_key
            )
            new_index = (current_index + 1) % len(available_resolutions)
            new_resolution = available_resolutions[new_index]

            logger.info(
                f"Changing resolution from {game_state.current_resolution_key} to {new_resolution}"
            )
            game_state.set_resolution(new_resolution)

        # Return True to indicate the click was handled
        return True

    if current_state == CurrentGameState.MENU:
        pad = getattr(UIConstants, "MENU_CLOSE_BUTTON_PADDING", 10)
        size = getattr(UIConstants, "MENU_CLOSE_BUTTON_SIZE", 40)
        close_btn_rel_x1, close_btn_rel_y1 = menu_w - pad - size, pad
        close_btn_rel_x2, close_btn_rel_y2 = menu_w - pad, pad + size
        logger.debug(
            f"Close button bounds: ({close_btn_rel_x1},{close_btn_rel_y1}) to ({close_btn_rel_x2},{close_btn_rel_y2})"
        )
        if (
            close_btn_rel_x1 <= relative_x < close_btn_rel_x2
            and close_btn_rel_y1 <= relative_y < close_btn_rel_y2
        ):
            logger.debug("Menu close 'X' button clicked.")
            close_btn_abs_rect = (
                menu_x + close_btn_rel_x1,
                menu_y + close_btn_rel_y1,
                size,
                size,
            )
            game_state.click_feedback_state = (close_btn_abs_rect, time.time())
            game_state.current_state = CurrentGameState.PLAYING
            game_state.submenu_active = None
            _reset_all_menu_editing_states(game_state)
            return True

    submenu_items_list = getattr(game_state, "submenu_items", [])
    logger.debug(f"Checking {len(submenu_items_list)} submenu items for clicks")
    if not isinstance(submenu_items_list, list):
        logger.error("game_state.submenu_items is not a list.")
        return False

    # Log all menu items for debugging
    for i, item_data in enumerate(submenu_items_list):
        if not isinstance(item_data, tuple) or len(item_data) < 2:
            continue
        item_rect_orig, action = item_data[0], item_data[1]
        if not isinstance(item_rect_orig, tuple) or len(item_rect_orig) != 4:
            continue
        item_x, item_y, item_w, item_h = item_rect_orig
        # Absolute coordinates in MENU state
        abs_x = (
            item_x + menu_x
            if current_state != CurrentGameState.CONFIRM_QUIT
            else item_x
        )
        abs_y = (
            item_y + menu_y
            if current_state != CurrentGameState.CONFIRM_QUIT
            else item_y
        )
        logger.debug(
            f"Menu item {i}: {action} at ({abs_x},{abs_y}) size {item_w}x{item_h}"
        )

    volume_adjusted = False
    for item_data in reversed(submenu_items_list):
        if not isinstance(item_data, tuple) or len(item_data) < 2:
            continue
        item_rect_orig, action = item_data[0], item_data[1]
        if not isinstance(item_rect_orig, tuple) or len(item_rect_orig) != 4:
            continue
        item_x, item_y, item_w, item_h = item_rect_orig

        # Calculate absolute rect based on state
        if current_state != CurrentGameState.CONFIRM_QUIT:
            # MENU state: item rect is relative to menu_pos
            item_rect_abs = (item_x + menu_x, item_y + menu_y, item_w, item_h)
            click_x_to_check, click_y_to_check = x, y
        else:
            # CONFIRM_QUIT state: item rect is absolute (as drawn)
            item_rect_abs = item_rect_orig
            click_x_to_check, click_y_to_check = x, y

        abs_item_x, abs_item_y, abs_item_w, abs_item_h = item_rect_abs

        # Log the check for each item
        logger.debug(
            f"Checking if click ({click_x_to_check},{click_y_to_check}) is within item {action} at ({abs_item_x},{abs_item_y}) size {abs_item_w}x{abs_item_h}"
        )

        if (
            abs_item_x <= click_x_to_check < abs_item_x + abs_item_w
            and abs_item_y <= click_y_to_check < abs_item_y + abs_item_h
        ):
            logger.info(
                f"Click detected on item with action: {action} at rect {item_rect_abs}"
            )
            if isinstance(action, str):
                # Volume slider checks
                if current_state == CurrentGameState.MENU:
                    rel_click_x_in_item = click_x_to_check - (abs_item_x)
                    if action == "adjust_sound_volume":
                        new_volume = max(
                            0.0,
                            min(
                                1.0,
                                (
                                    rel_click_x_in_item / abs_item_w
                                    if abs_item_w > 0
                                    else 0.0
                                ),
                            ),
                        )
                        if (
                            abs(
                                getattr(game_state, "current_sound_volume", 0)
                                - new_volume
                            )
                            > 0.01
                        ):
                            game_state.current_sound_volume = new_volume
                            set_volume(game_state)
                            save_settings(game_state)
                            game_state.menu_cache = None
                            volume_adjusted = True
                            logger.debug(f"Adjusted sound volume to {new_volume:.2f}")
                            return True
                    elif action == "adjust_music_volume":
                        new_volume = max(
                            0.0,
                            min(
                                1.0,
                                (
                                    rel_click_x_in_item / abs_item_w
                                    if abs_item_w > 0
                                    else 0.0
                                ),
                            ),
                        )
                        if (
                            abs(
                                getattr(game_state, "current_music_volume", 0)
                                - new_volume
                            )
                            > 0.01
                        ):
                            game_state.current_music_volume = new_volume
                            set_volume(game_state)
                            save_settings(game_state)
                            game_state.menu_cache = None
                            volume_adjusted = True
                            logger.debug(f"Adjusted music volume to {new_volume:.2f}")
                            return True

                # Confirm Quit checks
                if current_state == CurrentGameState.CONFIRM_QUIT:
                    if action == "confirm_quit_yes":
                        logger.info("Quit confirmed via 'Yes' button click.")
                        game_state.click_feedback_state = (item_rect_abs, time.time())
                        cap = getattr(game_state, "cap", None)
                        music = getattr(game_state, "background_music", None)
                        music_on = getattr(game_state, "background_music_on", False)
                        clean_exit(cap, music, music_on, game_state)
                        return True
                    elif action == "confirm_quit_no":
                        logger.debug("Quit cancelled via 'No' button click.")
                        game_state.click_feedback_state = (item_rect_abs, time.time())
                        prev_state = getattr(
                            game_state,
                            "previous_state_before_quit_confirm",
                            CurrentGameState.PLAYING,
                        )
                        game_state.current_state = prev_state
                        game_state.previous_state_before_quit_confirm = None
                        game_state.submenu_items = []
                        game_state.menu_cache = None
                        return True

                # Set feedback state if not a volume adjustment
                if not volume_adjusted:
                    game_state.click_feedback_state = (item_rect_abs, time.time())

                # General menu action handling (only for MENU state now)
                known_submenu_nav_actions = {
                    item[1]
                    for item in MenuConstants.MAIN_MENU_ITEMS
                    if isinstance(item[1], str)
                } | {
                    item[1]
                    for item in MenuConstants.ZONE_SUBMENU_ITEMS
                    if isinstance(item[1], str)
                }
                non_nav_actions = {
                    "resume",
                    "quit",
                    "back_to_main",
                    "back_to_manage_zones",
                    "save_zones",
                    "load_zones",
                    "clear_zones",
                    "add_zone_info",
                }
                known_submenu_nav_actions -= non_nav_actions

                if current_state == CurrentGameState.MENU:
                    logger.info(f"Processing menu action: {action}")

                    # Add specific submenu activation code for main menu items
                    # This is needed to navigate to submenus
                    if action in known_submenu_nav_actions:
                        logger.info(f"Setting submenu_active to: {action}")
                        game_state.submenu_active = action
                        game_state.menu_cache = None  # Force menu redraw
                        return True

                    if action == "quit":
                        game_state.previous_state_before_quit_confirm = (
                            CurrentGameState.MENU
                        )
                        game_state.current_state = CurrentGameState.CONFIRM_QUIT
                        _reset_all_menu_editing_states(game_state)
                        return True
                    elif action == "toggle_game_sounds":
                        toggle_game_sounds(game_state)
                        game_state.menu_cache = None
                        return True
                    elif action == "toggle_background_music":
                        toggle_background_music(game_state)
                        game_state.menu_cache = None
                        return True
                    elif action == "toggle_debug_overlay":
                        game_state.show_debug_overlay = not getattr(
                            game_state, "show_debug_overlay", False
                        )
                        show_notification(
                            game_state,
                            f"Debug Overlay: {'ON' if game_state.show_debug_overlay else 'OFF'}",
                        )
                        game_state.menu_cache = None
                        return True
                    elif action == "toggle_debug_mode":
                        game_state.debug_mode = not getattr(
                            game_state, "debug_mode", False
                        )
                        log_level = (
                            logging.DEBUG if game_state.debug_mode else logging.INFO
                        )
                        logging.getLogger().setLevel(log_level)
                        [h.setLevel(log_level) for h in logging.getLogger().handlers]
                        show_notification(
                            game_state,
                            f"Debug Mode: {'ON' if game_state.debug_mode else 'OFF'}",
                        )
                        game_state.menu_cache = None
                        return True
                    elif action == "cycle_music_track":
                        available_tracks = getattr(
                            GameConstants, "BACKGROUND_MUSIC_TRACKS", []
                        )
                        (
                            change_music_track(
                                game_state,
                                (
                                    getattr(game_state, "selected_music_track_index", 0)
                                    + 1
                                )
                                % len(available_tracks),
                            )
                            if available_tracks
                            else None
                        )
                        game_state.menu_cache = None
                        return True
                    elif action == "show_splash":
                        import utils

                        display_modal_splash(
                            game_state, utils.mouse_callback, game_state
                        )
                        game_state.menu_cache = None
                        return True
                    elif action == "resume":
                        game_state.current_state = CurrentGameState.PLAYING
                        game_state.submenu_active = None
                        _reset_all_menu_editing_states(game_state)
                        return True
                    elif action == "back_to_main":
                        logger.info("Returning to main menu")
                        _reset_all_menu_editing_states(game_state)
                        game_state.submenu_active = None
                        game_state.menu_cache = None
                        return True

                    # Add zone info handler
                    elif action == "add_zone_info":
                        show_notification(
                            game_state,
                            "Press 's', then click and drag to draw zone",
                        )
                        game_state.current_state = CurrentGameState.PLAYING
                        game_state.submenu_active = None
                        _reset_all_menu_editing_states(game_state)
                        return True

                    # Zone management actions
                    elif action == "clear_zones":
                        clear_zones(game_state)
                        _reset_all_menu_editing_states(game_state)
                        return True

                    elif action == "save_zones":
                        save_zones(game_state)
                        game_state.menu_cache = None
                        return True

                    elif action == "load_zones":
                        load_zones(game_state)
                        _reset_all_menu_editing_states(game_state)
                        return True

                    # Game mode selection
                    elif action.startswith("set_mode_"):
                        new_mode = action.split("set_mode_")[-1]
                        valid_modes = {
                            "classic",
                            "timed",
                            "fun",
                            "practice",
                            "survival",
                            "retro",
                        }
                        if (
                            new_mode in valid_modes
                            and getattr(game_state, "game_mode", "classic") != new_mode
                        ):
                            try:
                                save_score(
                                    game_state,
                                    game_state.get_current_player().name,
                                    mode=game_state.game_mode,
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error saving score before mode change: {e}"
                                )
                            game_state.game_mode = new_mode
                            game_state.menu_cache = None
                            logger.info(f"Switched to mode: {new_mode}")

                            # Reset the game state to start fresh with the new mode
                            reset_game(game_state)

                            # Switch to retro music if retro mode is activated
                            if new_mode == "retro":
                                # Switch to the fourth track (index 3)
                                change_music_track(game_state, 3)

                            show_notification(
                                game_state, f"Mode changed to {new_mode.capitalize()}"
                            )
                        return True

                    # Replay system actions
                    elif action == "view_replays":
                        game_state.submenu_active = "view_replays"
                        game_state.menu_cache = None
                        # Initialize replay browser state if needed
                        if not hasattr(game_state, "replay_browser_page"):
                            game_state.replay_browser_page = 1
                        if not hasattr(game_state, "selected_replay_id"):
                            game_state.selected_replay_id = None
                        return True

                    elif action == "start_recording":
                        if (
                            hasattr(game_state, "replay_manager")
                            and game_state.replay_manager
                        ):
                            try:
                                logger.info(
                                    "Start recording action triggered in interaction_utils"
                                )
                                if not game_state.replay_manager:
                                    logger.error("game_state.replay_manager is None")
                                game_state.replay_manager.start_recording(game_state)
                                game_state.menu_cache = (
                                    None  # Reset menu cache to reflect recording state
                                )
                                show_notification(game_state, "Recording started")
                                logger.info("Started replay recording")
                                return True
                            except Exception as e:
                                logger.error(f"Error starting replay recording: {e}")
                                logger.exception(
                                    "Full traceback for start_recording error in interaction_utils:"
                                )
                                show_notification(
                                    game_state,
                                    "Error starting recording",
                                    is_error=True,
                                )
                                return True
                        else:
                            logger.error(
                                "Cannot start recording - replay_manager not available"
                            )
                            show_notification(
                                game_state,
                                "Cannot start recording - replay system not initialized",
                                is_error=True,
                            )
                        return False

                    elif action == "stop_recording":
                        if (
                            hasattr(game_state, "replay_manager")
                            and game_state.replay_manager
                        ):
                            try:
                                replay_id = game_state.replay_manager.stop_recording(
                                    game_state.score, game_state
                                )
                                game_state.menu_cache = None  # Reset menu cache to reflect recording stopped
                                if replay_id:
                                    show_notification(game_state, "Recording saved")
                                    logger.info(f"Replay saved with ID: {replay_id}")
                                else:
                                    show_notification(
                                        game_state,
                                        "Error saving recording",
                                        is_error=True,
                                    )
                                return True
                            except Exception as e:
                                logger.error(f"Error stopping replay recording: {e}")
                                show_notification(
                                    game_state,
                                    "Error stopping recording",
                                    is_error=True,
                                )
                                return True
                        return False

                    # Handle replay navigation
                    elif action.startswith("select_replay_"):
                        replay_id = action[len("select_replay_") :]
                        logger.info(f"Selected replay: {replay_id}")
                        game_state.selected_replay_id = replay_id
                        game_state.menu_cache = None
                        return True

                    elif action == "back_to_replays":
                        game_state.submenu_active = "replays"
                        game_state.menu_cache = None
                        return True

                    elif action == "back_to_view_replays":
                        game_state.submenu_active = "view_replays"
                        game_state.menu_cache = None
                        return True

                    elif action == "prev_replay_page":
                        if hasattr(game_state, "replay_browser_page"):
                            game_state.replay_browser_page = max(
                                1, game_state.replay_browser_page - 1
                            )
                            game_state.menu_cache = None
                        return True

                    elif action == "next_replay_page":
                        if (
                            hasattr(game_state, "replay_browser_page")
                            and hasattr(game_state, "replay_manager")
                            and game_state.replay_manager
                        ):
                            # Calculate total pages
                            from constants import ReplayConstants

                            replays = game_state.replay_manager.get_all_replays()
                            total_pages = max(
                                1,
                                (len(replays) + ReplayConstants.REPLAYS_PER_PAGE - 1)
                                // ReplayConstants.REPLAYS_PER_PAGE,
                            )
                            game_state.replay_browser_page = min(
                                total_pages, game_state.replay_browser_page + 1
                            )
                            game_state.menu_cache = None
                        return True

                    # Play selected replay
                    elif action.startswith("play_replay_"):
                        if (
                            hasattr(game_state, "replay_manager")
                            and game_state.replay_manager
                        ):
                            replay_id = action[len("play_replay_") :]
                            try:
                                replay = game_state.replay_manager.load_replay(
                                    replay_id
                                )
                                if replay:
                                    # Initialize replay playback state
                                    game_state.replay_playback = {
                                        "playing": False,
                                        "current_frame_idx": 0,
                                        "playback_speed": 1.0,
                                        "current_replay_id": replay_id,
                                        "current_replay": replay,
                                        "last_update_time": time.time(),
                                    }
                                    game_state.submenu_active = "replay_playback"
                                    game_state.menu_cache = None
                                    show_notification(
                                        game_state, f"Loaded replay: {replay.title}"
                                    )
                                else:
                                    show_notification(
                                        game_state,
                                        "Error loading replay",
                                        is_error=True,
                                    )
                            except Exception as e:
                                logger.error(f"Error loading replay for playback: {e}")
                                show_notification(
                                    game_state, "Error loading replay", is_error=True
                                )
                        return True

                    # Delete replay
                    elif action.startswith("delete_replay_"):
                        if (
                            hasattr(game_state, "replay_manager")
                            and game_state.replay_manager
                        ):
                            replay_id = action[len("delete_replay_") :]
                            try:
                                success = game_state.replay_manager.delete_replay(
                                    replay_id
                                )
                                if success:
                                    game_state.selected_replay_id = None
                                    show_notification(game_state, "Replay deleted")
                                else:
                                    show_notification(
                                        game_state,
                                        "Error deleting replay",
                                        is_error=True,
                                    )
                                game_state.menu_cache = None
                            except Exception as e:
                                logger.error(f"Error deleting replay: {e}")
                                show_notification(
                                    game_state, "Error deleting replay", is_error=True
                                )
                        return True

                    # Export and share options
                    elif action.startswith("export_video_") or action.startswith(
                        "share_replay_"
                    ):
                        if action.startswith("export_video_"):
                            replay_id = action[len("export_video_") :]
                        else:
                            replay_id = action[len("share_replay_") :]

                        game_state.selected_replay_id = replay_id
                        game_state.submenu_active = "replay_share"
                        game_state.menu_cache = None
                        # Show notification to guide user
                        show_notification(
                            game_state,
                            "Select export format and destination",
                            duration=3.0,
                        )
                        return True

                    # Format selection buttons
                    elif action.startswith("select_format_"):
                        if hasattr(game_state, "replay_sharing"):
                            format_type = action[len("select_format_") :]
                            # Validate that this is a supported format
                            from constants import ReplayConstants

                            if format_type in ReplayConstants.EXPORT_FORMATS:
                                game_state.replay_sharing["selected_format"] = (
                                    format_type
                                )
                                game_state.menu_cache = None  # Force UI update
                                show_notification(
                                    game_state, f"Selected format: {format_type}"
                                )
                                logger.info(f"Selected format: {format_type}")
                        return True

                    # Player management actions
                    elif action.startswith("edit_player_name_"):
                        try:
                            player_index = int(action[len("edit_player_name_") :])
                            if 0 <= player_index < len(game_state.players):
                                # Set up editing state
                                game_state.editing_player_index = player_index
                                game_state.editing_player_mode = "edit_name"
                                game_state.editing_player_name_input = (
                                    game_state.players[player_index].name
                                )
                                game_state.menu_cache = None  # Force menu redraw
                                logger.info(f"Editing player {player_index} name")
                                # Switch to keyboard input mode for name editing
                                from game_input import _handle_text_input

                                _handle_text_input(None, game_state)
                        except (ValueError, IndexError) as e:
                            logger.error(f"Error setting up player edit: {e}")
                        return True

                    elif action == "add_player":
                        # Only allow adding if we have fewer than max players
                        if len(game_state.players) < 2:  # Max 2 players
                            from player import Player

                            # Create a new player with default name
                            new_player = Player(f"Player {len(game_state.players) + 1}")
                            game_state.players.append(new_player)
                            # Start editing the new player's name
                            game_state.editing_player_index = (
                                len(game_state.players) - 1
                            )
                            game_state.editing_player_mode = "edit_name"
                            game_state.editing_player_name_input = new_player.name
                            game_state.menu_cache = None  # Force menu redraw
                            logger.info(f"Added new player: {new_player.name}")
                            # Switch to keyboard input mode for name editing
                            from game_input import _handle_text_input

                            _handle_text_input(None, game_state)
                        return True

                    elif action.startswith("select_player_"):
                        try:
                            player_index = int(action[len("select_player_") :])
                            if 0 <= player_index < len(game_state.players):
                                game_state.current_player_index = player_index
                                game_state.menu_cache = None  # Force menu redraw
                                player_name = game_state.players[player_index].name
                                show_notification(
                                    game_state, f"Selected player: {player_name}"
                                )
                                logger.info(
                                    f"Selected player {player_index}: {player_name}"
                                )
                        except (ValueError, IndexError) as e:
                            logger.error(f"Error selecting player: {e}")
                        return True

                    # Platform selection buttons
                    elif action.startswith("select_platform_"):
                        if hasattr(game_state, "replay_sharing"):
                            platform = action[len("select_platform_") :]
                            # Validate that this is a supported platform
                            from constants import ReplayConstants

                            if platform in ReplayConstants.SHARING_PLATFORMS:
                                game_state.replay_sharing["selected_platform"] = (
                                    platform
                                )
                                game_state.menu_cache = None  # Force UI update
                                show_notification(
                                    game_state, f"Selected platform: {platform}"
                                )
                                logger.info(f"Selected platform: {platform}")
                        return True

                    # Replay playback control actions
                    elif action == "replay_toggle_play":
                        if (
                            hasattr(game_state, "replay_playback")
                            and game_state.replay_playback
                        ):
                            # Toggle play/pause
                            game_state.replay_playback["playing"] = (
                                not game_state.replay_playback.get("playing", False)
                            )
                            game_state.replay_playback["last_update_time"] = time.time()
                            game_state.menu_cache = None  # Force UI update
                            logger.info(
                                f"Replay playback toggled to: {'playing' if game_state.replay_playback['playing'] else 'paused'}"
                            )
                        return True

                    elif action == "replay_next_frame":
                        if (
                            hasattr(game_state, "replay_playback")
                            and game_state.replay_playback
                        ):
                            replay = game_state.replay_playback.get("current_replay")
                            if replay and hasattr(replay, "frames"):
                                # Advance one frame
                                current_idx = game_state.replay_playback.get(
                                    "current_frame_idx", 0
                                )
                                max_idx = len(replay.frames) - 1
                                game_state.replay_playback["current_frame_idx"] = min(
                                    max_idx, current_idx + 1
                                )
                                game_state.menu_cache = None  # Force UI update
                                logger.info(
                                    f"Advanced to next frame: {game_state.replay_playback['current_frame_idx']}/{max_idx}"
                                )
                        return True

                    elif action == "replay_prev_frame":
                        if (
                            hasattr(game_state, "replay_playback")
                            and game_state.replay_playback
                        ):
                            # Go back one frame
                            current_idx = game_state.replay_playback.get(
                                "current_frame_idx", 0
                            )
                            game_state.replay_playback["current_frame_idx"] = max(
                                0, current_idx - 1
                            )
                            game_state.menu_cache = None  # Force UI update
                            logger.info(
                                f"Went back to previous frame: {game_state.replay_playback['current_frame_idx']}"
                            )
                        return True

                    elif action == "replay_rewind":
                        if (
                            hasattr(game_state, "replay_playback")
                            and game_state.replay_playback
                        ):
                            # Rewind to beginning
                            game_state.replay_playback["current_frame_idx"] = 0
                            game_state.menu_cache = None  # Force UI update
                            logger.info("Rewound replay to beginning")
                        return True

                    elif action == "replay_ffwd":
                        if (
                            hasattr(game_state, "replay_playback")
                            and game_state.replay_playback
                        ):
                            replay = game_state.replay_playback.get("current_replay")
                            if replay and hasattr(replay, "frames"):
                                # Fast forward to end
                                game_state.replay_playback["current_frame_idx"] = (
                                    len(replay.frames) - 1
                                )
                                game_state.menu_cache = None  # Force UI update
                                logger.info("Fast-forwarded replay to end")
                        return True

                    elif action == "replay_timeline":
                        # This is handled by _process_replay_timeline_drag in game_input.py
                        # Just log that the click was processed
                        logger.info(
                            "Timeline click detected, processing via drag handler"
                        )
                        return True

                    elif action == "replay_slower":
                        if (
                            hasattr(game_state, "replay_playback")
                            and game_state.replay_playback
                        ):
                            from constants import ReplayConstants

                            # Decrease playback speed
                            current_speed = game_state.replay_playback.get(
                                "playback_speed", ReplayConstants.DEFAULT_PLAYBACK_SPEED
                            )
                            new_speed = max(
                                ReplayConstants.MIN_PLAYBACK_SPEED,
                                current_speed
                                - ReplayConstants.PLAYBACK_SPEED_INCREMENT,
                            )
                            game_state.replay_playback["playback_speed"] = new_speed
                            game_state.menu_cache = None  # Force UI update
                            logger.info(f"Decreased playback speed to {new_speed}x")
                        return True

                    elif action == "replay_faster":
                        if (
                            hasattr(game_state, "replay_playback")
                            and game_state.replay_playback
                        ):
                            from constants import ReplayConstants

                            # Increase playback speed
                            current_speed = game_state.replay_playback.get(
                                "playback_speed", ReplayConstants.DEFAULT_PLAYBACK_SPEED
                            )
                            new_speed = min(
                                ReplayConstants.MAX_PLAYBACK_SPEED,
                                current_speed
                                + ReplayConstants.PLAYBACK_SPEED_INCREMENT,
                            )
                            game_state.replay_playback["playback_speed"] = new_speed
                            game_state.menu_cache = None  # Force UI update
                            logger.info(f"Increased playback speed to {new_speed}x")
                        return True

                    elif action == "close_replay_playback":
                        # Return to the replay selection screen
                        game_state.submenu_active = "view_replays"
                        game_state.menu_cache = None  # Force UI update
                        logger.info(
                            "Closed replay playback, returning to replay selection"
                        )
                        return True

                    # Share to platform actions
                    elif action.startswith("share_to_"):
                        if (
                            hasattr(game_state, "replay_manager")
                            and game_state.replay_manager
                        ):
                            parts = action.split("_")
                            if len(parts) >= 3:
                                platform = parts[2]
                                replay_id = parts[3] if len(parts) > 3 else ""

                                # Set status in UI
                                if hasattr(game_state, "replay_sharing"):
                                    game_state.replay_sharing["export_status"] = (
                                        f"Preparing to share to {platform}..."
                                    )
                                    game_state.replay_sharing["export_progress"] = 0.1
                                    game_state.menu_cache = None  # Force UI update

                                if platform == "Local":
                                    # For local sharing, just show file path
                                    try:
                                        # First generate video if needed
                                        video_path = None
                                        if hasattr(
                                            game_state, "replay_sharing"
                                        ) and game_state.replay_sharing.get(
                                            "last_export_path"
                                        ):
                                            video_path = game_state.replay_sharing[
                                                "last_export_path"
                                            ]
                                        else:
                                            # Set status in UI
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Generating video first..."
                                                game_state.menu_cache = (
                                                    None  # Force UI update
                                                )

                                            video_path = game_state.replay_manager.generate_video(
                                                replay_id
                                            )

                                            # Update status
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "last_export_path"
                                                ] = video_path

                                        if video_path:
                                            # Verify video file exists and is valid
                                            if not os.path.exists(video_path):
                                                logger.error(
                                                    f"Video file not found: {video_path}"
                                                )
                                                if hasattr(
                                                    game_state, "replay_sharing"
                                                ):
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = "Video file not found"
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 0.0
                                                show_notification(
                                                    game_state,
                                                    "Video file not found",
                                                    is_error=True,
                                                )
                                                return True

                                            # Check file size
                                            file_size = os.path.getsize(video_path)
                                            if file_size < 1000:  # Less than 1KB
                                                logger.error(
                                                    f"Video file too small or empty: {file_size} bytes"
                                                )
                                                if hasattr(
                                                    game_state, "replay_sharing"
                                                ):
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = "Video file too small or corrupted"
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 0.0
                                                show_notification(
                                                    game_state,
                                                    "Video file too small or corrupted",
                                                    is_error=True,
                                                )
                                                return True
                                    except Exception as e:
                                        logger.error(f"Error sharing locally: {e}")

                                        # Set status in UI
                                        if hasattr(game_state, "replay_sharing"):
                                            game_state.replay_sharing[
                                                "export_status"
                                            ] = f"Error: {str(e)}"
                                            game_state.replay_sharing[
                                                "export_progress"
                                            ] = 0.0

                                        show_notification(
                                            game_state,
                                            "Error sharing locally",
                                            is_error=True,
                                        )
                                elif platform == "Discord":
                                    try:
                                        # First generate video if needed
                                        video_path = None
                                        if hasattr(
                                            game_state, "replay_sharing"
                                        ) and game_state.replay_sharing.get(
                                            "last_export_path"
                                        ):
                                            video_path = game_state.replay_sharing[
                                                "last_export_path"
                                            ]
                                        else:
                                            # Set status in UI
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Generating video first..."
                                                game_state.menu_cache = (
                                                    None  # Force UI update
                                                )

                                            video_path = game_state.replay_manager.generate_video(
                                                replay_id
                                            )

                                            # Update status
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "last_export_path"
                                                ] = video_path

                                        if not video_path:
                                            # Update UI status if video generation failed
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Error generating video for Discord"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.0

                                            show_notification(
                                                game_state,
                                                "Error generating video for Discord",
                                                is_error=True,
                                            )
                                            return True

                                        # Get the player name and score for the message
                                        replay = game_state.replay_manager.load_replay(
                                            replay_id
                                        )
                                        player_name = (
                                            replay.player_name
                                            if replay and hasattr(replay, "player_name")
                                            else "Player"
                                        )
                                        # Fix: retrieve score properly from the replay
                                        score = 0
                                        if (
                                            replay
                                            and hasattr(replay, "frames")
                                            and replay.frames
                                        ):
                                            # Get score from the last frame
                                            score = replay.frames[-1].score
                                        game_mode = (
                                            replay.game_mode
                                            if replay and hasattr(replay, "game_mode")
                                            else "classic"
                                        )

                                        # Verify video file exists and is valid
                                        if not os.path.exists(video_path):
                                            logger.error(
                                                f"Video file not found: {video_path}"
                                            )
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Video file not found"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.0
                                            show_notification(
                                                game_state,
                                                "Video file not found",
                                                is_error=True,
                                            )
                                            return True

                                        # Check file size
                                        file_size = os.path.getsize(video_path)
                                        if file_size < 1000:  # Less than 1KB
                                            logger.error(
                                                f"Video file too small or empty: {file_size} bytes"
                                            )
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Video file too small or corrupted"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.0
                                            show_notification(
                                                game_state,
                                                "Video file too small or corrupted",
                                                is_error=True,
                                            )
                                            return True

                                        # Import requests for HTTP
                                        import requests
                                        from requests.exceptions import RequestException

                                        # Check if Discord webhook URL is configured
                                        if not DiscordConstants.WEBHOOK_URL:
                                            logger.error(
                                                "Discord webhook URL not properly configured in constants.py"
                                            )

                                            # Update UI status
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Discord webhook not configured"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.0

                                            show_notification(
                                                game_state,
                                                "Discord webhook not configured",
                                                is_error=True,
                                            )
                                            return True

                                        # Format the message template with replay info
                                        try:
                                            message = DiscordConstants.REPLAY_SHARE_TEMPLATE.format(
                                                player_name=player_name,
                                                score=score,
                                                game_mode=game_mode,
                                            )
                                        except Exception as e:
                                            # Fallback to a simple message if formatting fails
                                            logger.error(
                                                f"Error formatting Discord message template: {e}"
                                            )
                                            message = f"Check out this Whiffle replay from {player_name}!"

                                        payload = {
                                            "content": message,
                                            "username": DiscordConstants.BOT_USERNAME,
                                            "avatar_url": DiscordConstants.BOT_AVATAR_URL,
                                        }

                                        # Update UI status before posting
                                        if hasattr(game_state, "replay_sharing"):
                                            game_state.replay_sharing[
                                                "export_status"
                                            ] = "Uploading to Discord..."
                                            game_state.replay_sharing[
                                                "export_progress"
                                            ] = 0.5
                                            game_state.menu_cache = (
                                                None  # Force UI update
                                            )

                                        show_notification(
                                            game_state,
                                            "Uploading to Discord...",
                                            duration=3.0,
                                        )

                                        # Open the video file and post to Discord
                                        with open(video_path, "rb") as f:
                                            # Post to the webhook
                                            files = {
                                                "file": (
                                                    f"{replay_id}.mp4",
                                                    f,
                                                    "video/mp4",
                                                )
                                            }
                                            response = requests.post(
                                                DiscordConstants.WEBHOOK_URL,
                                                data=payload,
                                                files=files,
                                                timeout=DiscordConstants.REQUEST_TIMEOUT,
                                            )

                                        # Check if the request was successful
                                        if response.status_code in (200, 204):
                                            logger.info(
                                                f"Successfully shared replay to Discord: {replay_id}"
                                            )

                                            # Update UI status
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Successfully shared to Discord!"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 1.0

                                            show_notification(
                                                game_state,
                                                "Successfully shared to Discord!",
                                                duration=3.0,
                                            )
                                        else:
                                            error_message = f"Discord API error: {response.status_code} - {response.text}"
                                            logger.error(error_message)

                                            # Update UI status
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Error sharing to Discord"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.0

                                            show_notification(
                                                game_state,
                                                "Error sharing to Discord",
                                                is_error=True,
                                            )

                                    except RequestException as e:
                                        logger.error(
                                            f"Network error sharing to Discord: {e}"
                                        )

                                        # Update UI status
                                        if hasattr(game_state, "replay_sharing"):
                                            game_state.replay_sharing[
                                                "export_status"
                                            ] = f"Network error: {str(e)}"
                                            game_state.replay_sharing[
                                                "export_progress"
                                            ] = 0.0

                                        show_notification(
                                            game_state,
                                            "Network error sharing to Discord",
                                            is_error=True,
                                        )

                                    except Exception as e:
                                        logger.error(f"Error sharing to Discord: {e}")

                                        # Update UI status
                                        if hasattr(game_state, "replay_sharing"):
                                            game_state.replay_sharing[
                                                "export_status"
                                            ] = f"Error: {str(e)}"
                                            game_state.replay_sharing[
                                                "export_progress"
                                            ] = 0.0

                                        show_notification(
                                            game_state,
                                            "Error sharing to Discord",
                                            is_error=True,
                                        )
                                elif platform == "Share Link":
                                    try:
                                        # First generate video if needed
                                        video_path = None

                                        # Get the player name and score for the title
                                        replay = game_state.replay_manager.load_replay(
                                            replay_id
                                        )
                                        player_name = (
                                            replay.player_name
                                            if replay and hasattr(replay, "player_name")
                                            else "Player"
                                        )
                                        # Fix: retrieve score properly from the replay
                                        score = 0
                                        if (
                                            replay
                                            and hasattr(replay, "frames")
                                            and replay.frames
                                        ):
                                            # Get score from the last frame
                                            score = replay.frames[-1].score
                                        game_mode = (
                                            replay.game_mode
                                            if replay and hasattr(replay, "game_mode")
                                            else "classic"
                                        )

                                        # Check for existing video
                                        if hasattr(
                                            game_state, "replay_sharing"
                                        ) and game_state.replay_sharing.get(
                                            "last_export_path"
                                        ):
                                            cached_path = game_state.replay_sharing[
                                                "last_export_path"
                                            ]
                                            # Verify cached file exists
                                            if (
                                                os.path.exists(cached_path)
                                                and os.path.getsize(cached_path) > 1000
                                            ):
                                                video_path = cached_path
                                                logger.info(
                                                    f"Using previously generated video: {video_path}"
                                                )
                                            else:
                                                logger.warning(
                                                    f"Cached video not found or too small: {cached_path}"
                                                )

                                        # Generate new video if needed
                                        if not video_path:
                                            # Set status in UI
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Generating video first..."
                                                game_state.menu_cache = (
                                                    None  # Force UI update
                                                )

                                            video_path = game_state.replay_manager.generate_video(
                                                replay_id
                                            )

                                            # Update status
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "last_export_path"
                                                ] = video_path

                                        # Check if video generation was successful
                                        if not video_path or not os.path.exists(
                                            video_path
                                        ):
                                            # Update UI status if video generation failed
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Error generating video"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.0

                                            show_notification(
                                                game_state,
                                                "Error generating video",
                                                is_error=True,
                                            )
                                            return True
                                        else:
                                            # Set status in UI
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Uploading to Google Drive..."
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.3
                                                game_state.menu_cache = (
                                                    None  # Force UI update
                                                )

                                            show_notification(
                                                game_state,
                                                "Uploading to Google Drive...",
                                                duration=3.0,
                                            )

                                            # Create a title with player info
                                            title = f"Whiffle Replay - {player_name} - {score} points ({game_mode})"

                                            # Upload to Google Drive using the existing utility function
                                            success, result = (
                                                google_drive_utils.upload_video_to_drive(
                                                    video_path, title=title
                                                )
                                            )

                                            if success:
                                                shareable_link = result

                                                # Copy the shareable link to clipboard using tkinter
                                                try:
                                                    import tkinter as tk

                                                    # Create a temp hidden root window
                                                    root = tk.Tk()
                                                    root.withdraw()

                                                    # Clear clipboard and append new content
                                                    root.clipboard_clear()
                                                    root.clipboard_append(
                                                        shareable_link
                                                    )

                                                    # Display successful notification
                                                    if hasattr(
                                                        game_state, "replay_sharing"
                                                    ):
                                                        game_state.replay_sharing[
                                                            "export_status"
                                                        ] = "Video uploaded to Google Drive and link copied to clipboard!"
                                                        game_state.replay_sharing[
                                                            "export_progress"
                                                        ] = 1.0

                                                    show_notification(
                                                        game_state,
                                                        "Video uploaded to Google Drive!",
                                                        duration=2.0,
                                                    )
                                                    show_notification(
                                                        game_state,
                                                        "Link copied to clipboard!",
                                                        duration=3.0,
                                                    )

                                                    # Cleanup
                                                    root.update()
                                                    root.destroy()

                                                except (ImportError, Exception) as e:
                                                    # Fall back to showing the link if clipboard fails
                                                    if hasattr(
                                                        game_state, "replay_sharing"
                                                    ):
                                                        game_state.replay_sharing[
                                                            "export_status"
                                                        ] = f"Video uploaded: {shareable_link}"
                                                        game_state.replay_sharing[
                                                            "export_progress"
                                                        ] = 1.0

                                                    show_notification(
                                                        game_state,
                                                        "Video uploaded! Google Drive link:",
                                                        duration=2.0,
                                                    )
                                                    show_notification(
                                                        game_state,
                                                        shareable_link,
                                                        duration=5.0,
                                                    )

                                                    logger.error(
                                                        f"Clipboard error: {e}"
                                                    )
                                            else:
                                                # Failed to upload
                                                error_message = result
                                                logger.error(
                                                    f"Google Drive upload error: {error_message}"
                                                )

                                                if hasattr(
                                                    game_state, "replay_sharing"
                                                ):
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = f"Upload error: {error_message}"
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 0.0

                                                # Fall back to local path
                                                try:
                                                    import tkinter as tk

                                                    # Create a temp hidden root window
                                                    root = tk.Tk()
                                                    root.withdraw()

                                                    # Clear clipboard and append new content
                                                    root.clipboard_clear()

                                                    # Get absolute path
                                                    abs_path = os.path.abspath(
                                                        video_path
                                                    )
                                                    root.clipboard_append(abs_path)

                                                    show_notification(
                                                        game_state,
                                                        "Google Drive upload failed. Local path copied instead.",
                                                        is_error=True,
                                                        duration=3.0,
                                                    )

                                                    # Cleanup
                                                    root.update()
                                                    root.destroy()

                                                except (ImportError, Exception) as e:
                                                    # Fall back to showing path if clipboard fails
                                                    abs_path = os.path.abspath(
                                                        video_path
                                                    )

                                                    show_notification(
                                                        game_state,
                                                        "Google Drive upload failed. Local video at:",
                                                        is_error=True,
                                                        duration=3.0,
                                                    )
                                                    show_notification(
                                                        game_state,
                                                        abs_path,
                                                        duration=5.0,
                                                    )

                                                    logger.error(
                                                        f"Clipboard error: {e}"
                                                    )

                                    except Exception as e:
                                        logger.error(
                                            f"Error sharing video to Google Drive: {e}"
                                        )
                                        logger.error(traceback.format_exc())

                                        # Update UI status
                                        if hasattr(game_state, "replay_sharing"):
                                            game_state.replay_sharing[
                                                "export_status"
                                            ] = f"Error: {str(e)}"
                                            game_state.replay_sharing[
                                                "export_progress"
                                            ] = 0.0

                                        show_notification(
                                            game_state,
                                            "Error sharing video to Google Drive",
                                            is_error=True,
                                        )
                                elif platform == "YouTube":
                                    try:
                                        # First generate video if needed
                                        video_path = None

                                        # Get the player name and score for the message (moved up to initialize variables)
                                        replay = game_state.replay_manager.load_replay(
                                            replay_id
                                        )
                                        player_name = (
                                            replay.player_name
                                            if replay and hasattr(replay, "player_name")
                                            else "Player"
                                        )
                                        # Fix: retrieve score properly from the replay
                                        score = 0
                                        if (
                                            replay
                                            and hasattr(replay, "frames")
                                            and replay.frames
                                        ):
                                            # Get score from the last frame
                                            score = replay.frames[-1].score
                                        game_mode = (
                                            replay.game_mode
                                            if replay and hasattr(replay, "game_mode")
                                            else "classic"
                                        )

                                        if hasattr(
                                            game_state, "replay_sharing"
                                        ) and game_state.replay_sharing.get(
                                            "last_export_path"
                                        ):
                                            video_path = game_state.replay_sharing[
                                                "last_export_path"
                                            ]
                                        else:
                                            # Set status in UI
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Generating video first..."
                                                game_state.menu_cache = (
                                                    None  # Force UI update
                                                )

                                            video_path = game_state.replay_manager.generate_video(
                                                replay_id
                                            )

                                            # Update status
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "last_export_path"
                                                ] = video_path

                                        if not video_path:
                                            # Update UI status if video generation failed
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Error generating video"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.0

                                            show_notification(
                                                game_state,
                                                "Error generating video",
                                                is_error=True,
                                            )
                                            return True

                                        # Set status in UI
                                        if hasattr(game_state, "replay_sharing"):
                                            game_state.replay_sharing[
                                                "export_status"
                                            ] = "Uploading to YouTube..."
                                            game_state.replay_sharing[
                                                "export_progress"
                                            ] = 0.3
                                            game_state.menu_cache = (
                                                None  # Force UI update
                                            )

                                        show_notification(
                                            game_state,
                                            "Uploading to YouTube...",
                                            duration=3.0,
                                        )

                                        # Upload to YouTube
                                        success, result = (
                                            youtube_utils.upload_video_to_youtube(
                                                video_path,
                                                player_name,
                                                score,
                                                game_mode,
                                            )
                                        )

                                        if success:
                                            shareable_link = result

                                            # Copy the shareable link to clipboard using tkinter
                                            try:
                                                import tkinter as tk

                                                # Create a temp hidden root window
                                                root = tk.Tk()
                                                root.withdraw()

                                                # Clear clipboard and append new content
                                                root.clipboard_clear()
                                                root.clipboard_append(shareable_link)

                                                # Display successful notification
                                                if hasattr(
                                                    game_state, "replay_sharing"
                                                ):
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = "Video uploaded to YouTube and link copied to clipboard!"
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 1.0

                                                show_notification(
                                                    game_state,
                                                    "Video uploaded to YouTube!",
                                                    duration=2.0,
                                                )
                                                show_notification(
                                                    game_state,
                                                    "Link copied to clipboard!",
                                                    duration=3.0,
                                                )

                                                # Cleanup
                                                root.update()
                                                root.destroy()

                                            except (ImportError, Exception) as e:
                                                # Fall back to showing the link if clipboard fails
                                                if hasattr(
                                                    game_state, "replay_sharing"
                                                ):
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = f"Video uploaded: {shareable_link}"
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 1.0

                                                show_notification(
                                                    game_state,
                                                    "Video uploaded! YouTube link:",
                                                    duration=2.0,
                                                )
                                                show_notification(
                                                    game_state,
                                                    shareable_link,
                                                    duration=5.0,
                                                )

                                                logger.error(f"Clipboard error: {e}")
                                        else:
                                            # Failed to upload
                                            error_message = result
                                            logger.error(
                                                f"YouTube upload error: {error_message}"
                                            )

                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = f"Upload error: {error_message}"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.0

                                            # Fall back to local path
                                            try:
                                                import tkinter as tk

                                                # Create a temp hidden root window
                                                root = tk.Tk()
                                                root.withdraw()

                                                # Clear clipboard and append new content
                                                root.clipboard_clear()

                                                # Get absolute path
                                                abs_path = os.path.abspath(video_path)
                                                root.clipboard_append(abs_path)

                                                show_notification(
                                                    game_state,
                                                    "YouTube upload failed. Local path copied instead.",
                                                    is_error=True,
                                                    duration=3.0,
                                                )

                                                # Cleanup
                                                root.update()
                                                root.destroy()

                                            except (ImportError, Exception) as e:
                                                # Fall back to showing path if clipboard fails
                                                abs_path = os.path.abspath(video_path)

                                                show_notification(
                                                    game_state,
                                                    "YouTube upload failed. Local video at:",
                                                    is_error=True,
                                                    duration=3.0,
                                                )
                                                show_notification(
                                                    game_state, abs_path, duration=5.0
                                                )

                                                logger.error(f"Clipboard error: {e}")

                                    except Exception as e:
                                        logger.error(
                                            f"Error sharing video to YouTube: {e}"
                                        )
                                        logger.error(traceback.format_exc())

                                        # Update UI status
                                        if hasattr(game_state, "replay_sharing"):
                                            game_state.replay_sharing[
                                                "export_status"
                                            ] = f"Error: {str(e)}"
                                            game_state.replay_sharing[
                                                "export_progress"
                                            ] = 0.0

                                        show_notification(
                                            game_state,
                                            "Error sharing video to YouTube",
                                            is_error=True,
                                        )
                                else:
                                    # For other platforms
                                    # Set status in UI
                                    if hasattr(game_state, "replay_sharing"):
                                        game_state.replay_sharing["export_status"] = (
                                            f"External sharing to {platform} not implemented"
                                        )
                                        game_state.replay_sharing["export_progress"] = (
                                            0.0
                                        )

                                    show_notification(
                                        game_state,
                                        f"Sharing to {platform} is not yet implemented",
                                        is_error=True,
                                    )

                                # Update menu cache to show progress/result
                                game_state.menu_cache = None
                        return True

                    # Generate video button
                    elif action.startswith("generate_video_"):
                        if (
                            hasattr(game_state, "replay_manager")
                            and game_state.replay_manager
                        ):
                            replay_id = action[len("generate_video_") :]
                            try:
                                # Get the selected format if available
                                export_format = "MP4"  # Default
                                if hasattr(game_state, "replay_sharing"):
                                    export_format = game_state.replay_sharing.get(
                                        "selected_format", "MP4"
                                    )

                                # Set status in UI
                                if hasattr(game_state, "replay_sharing"):
                                    game_state.replay_sharing["export_status"] = (
                                        "Generating video..."
                                    )
                                    game_state.replay_sharing["export_progress"] = 0.1
                                    game_state.menu_cache = None  # Force UI update

                                show_notification(
                                    game_state, "Generating video...", duration=3.0
                                )
                                video_path = game_state.replay_manager.generate_video(
                                    replay_id
                                )

                                if video_path:
                                    # Set status in UI
                                    if hasattr(game_state, "replay_sharing"):
                                        game_state.replay_sharing["export_status"] = (
                                            f"Video saved to: {video_path}"
                                        )
                                        game_state.replay_sharing["export_progress"] = (
                                            1.0
                                        )
                                        game_state.replay_sharing[
                                            "last_export_path"
                                        ] = video_path

                                    show_notification(
                                        game_state,
                                        f"Video saved to: {video_path}",
                                        duration=5.0,
                                    )
                                else:
                                    # Set status in UI
                                    if hasattr(game_state, "replay_sharing"):
                                        game_state.replay_sharing["export_status"] = (
                                            "Error generating video"
                                        )
                                        game_state.replay_sharing["export_progress"] = (
                                            0.0
                                        )

                                    show_notification(
                                        game_state,
                                        "Error generating video",
                                        is_error=True,
                                    )
                            except Exception as e:
                                logger.error(f"Error generating video: {e}")

                                # Set status in UI
                                if hasattr(game_state, "replay_sharing"):
                                    game_state.replay_sharing["export_status"] = (
                                        f"Error: {str(e)}"
                                    )
                                    game_state.replay_sharing["export_progress"] = 0.0

                                show_notification(
                                    game_state, "Error generating video", is_error=True
                                )

                            # Update menu cache to show progress/result
                            game_state.menu_cache = None
                        return True

                    # Highlight generation
                    elif action.startswith("export_highlight_"):
                        if (
                            hasattr(game_state, "replay_manager")
                            and game_state.replay_manager
                        ):
                            parts = action.split("_")
                            if len(parts) >= 3:
                                replay_id = parts[2]
                                highlight_index = int(parts[3]) if len(parts) > 3 else 0
                                try:
                                    # Set status in UI
                                    if hasattr(game_state, "replay_sharing"):
                                        game_state.replay_sharing["export_status"] = (
                                            "Generating highlight video..."
                                        )
                                        game_state.replay_sharing["export_progress"] = (
                                            0.1
                                        )
                                        game_state.menu_cache = None  # Force UI update

                                    show_notification(
                                        game_state,
                                        "Generating highlight video...",
                                        duration=3.0,
                                    )
                                    video_path = (
                                        game_state.replay_manager.extract_highlight(
                                            replay_id, highlight_index
                                        )
                                    )
                                    if video_path:
                                        # Set status in UI
                                        if hasattr(game_state, "replay_sharing"):
                                            game_state.replay_sharing[
                                                "export_status"
                                            ] = f"Highlight saved to: {video_path}"
                                            game_state.replay_sharing[
                                                "export_progress"
                                            ] = 1.0
                                            game_state.replay_sharing[
                                                "last_export_path"
                                            ] = video_path

                                        show_notification(
                                            game_state,
                                            f"Highlight saved to: {video_path}",
                                            duration=5.0,
                                        )
                                    else:
                                        # Set status in UI
                                        if hasattr(game_state, "replay_sharing"):
                                            game_state.replay_sharing[
                                                "export_status"
                                            ] = "Error generating highlight"
                                            game_state.replay_sharing[
                                                "export_progress"
                                            ] = 0.0

                                        show_notification(
                                            game_state,
                                            "Error generating highlight",
                                            is_error=True,
                                        )
                                except Exception as e:
                                    logger.error(
                                        f"Error generating highlight video: {e}"
                                    )

                                    # Set status in UI
                                    if hasattr(game_state, "replay_sharing"):
                                        game_state.replay_sharing["export_status"] = (
                                            f"Error: {str(e)}"
                                        )
                                        game_state.replay_sharing["export_progress"] = (
                                            0.0
                                        )

                                    show_notification(
                                        game_state,
                                        "Error generating highlight",
                                        is_error=True,
                                    )

                                # Update menu cache to show progress/result
                                game_state.menu_cache = None
                        return True

                    # Toggle auto recording
                    elif action == "toggle_auto_record":
                        # Toggle the auto recording setting
                        auto_record = getattr(game_state, "auto_record_replays", False)
                        game_state.auto_record_replays = not auto_record
                        game_state.menu_cache = None  # Force menu redraw

                        # Save the setting so it persists between sessions
                        try:
                            save_settings(game_state)
                        except Exception as e:
                            logger.error(f"Error saving auto-record setting: {e}")

                        show_notification(
                            game_state,
                            f"Auto recording {'enabled' if game_state.auto_record_replays else 'disabled'}",
                        )
                        logger.info(
                            f"Auto recording toggled to: {game_state.auto_record_replays}"
                        )
                        return True

                    # Manage replay storage
                    elif action == "manage_replay_storage":
                        # Redirect to view_replays submenu which already has deletion functionality
                        game_state.submenu_active = "view_replays"
                        game_state.menu_cache = None  # Force menu redraw

                        # Show notification explaining the redirection
                        show_notification(
                            game_state,
                            "Use replay browser to manage storage - select and delete replays",
                            duration=3.0,
                        )

                        logger.info(
                            "Redirecting replay storage management to replay browser"
                        )
                        return True

                    # Leaderboard mode selection handlers
                    elif action == "leaderboard_classic":
                        game_state.leaderboard_mode = "classic"
                        game_state.menu_cache = None  # Force menu redraw
                        logger.info("Changed leaderboard display to Classic mode")
                        return True

                    elif action == "leaderboard_timed":
                        game_state.leaderboard_mode = "timed"
                        game_state.menu_cache = None  # Force menu redraw
                        logger.info("Changed leaderboard display to Timed mode")
                        return True

                    elif action == "leaderboard_survival":
                        game_state.leaderboard_mode = "survival"
                        game_state.menu_cache = None  # Force menu redraw
                        logger.info("Changed leaderboard display to Survival mode")
                        return True

                    elif action == "leaderboard_fun":
                        game_state.leaderboard_mode = "fun"
                        game_state.menu_cache = None  # Force menu redraw
                        logger.info("Changed leaderboard display to Fun mode")
                        return True

                    elif action == "leaderboard_practice":
                        game_state.leaderboard_mode = "practice"
                        game_state.menu_cache = None  # Force menu redraw
                        logger.info("Changed leaderboard display to Practice mode")
                        return True

                    elif action == "leaderboard_retro":
                        game_state.leaderboard_mode = "retro"
                        game_state.menu_cache = None  # Force menu redraw
                        logger.info("Changed leaderboard display to Retro mode")
                        return True

                    # Platform selection buttons
                    elif action.startswith("select_platform_"):
                        if hasattr(game_state, "replay_sharing"):
                            platform = action[len("select_platform_") :]
                            # Validate that this is a supported platform
                            from constants import ReplayConstants

                            if platform in ReplayConstants.SHARING_PLATFORMS:
                                game_state.replay_sharing["selected_platform"] = (
                                    platform
                                )
                                game_state.menu_cache = None  # Force UI update
                                show_notification(
                                    game_state, f"Selected platform: {platform}"
                                )
                                logger.info(f"Selected platform: {platform}")
                        return True


def _share_video_to_x(
    video_path: str, player_name: str, score: int, game_mode: str
) -> Tuple[bool, str]:
    """
    Share a video to X.com (formerly Twitter).

    Args:
        video_path: Path to the video file to share
        player_name: Name of the player
        score: Player's score
        game_mode: The game mode (e.g., "classic", "timed")

    Returns:
        Tuple of (success: bool, message: str)
    """
    from constants import XConstants

    # Check if tweepy is installed
    if "tweepy" not in globals():
        return False, "tweepy module not found. Please install with: pip install tweepy"

    # Check if API credentials are configured
    if (
        XConstants.API_KEY == "YOUR_API_KEY"
        or XConstants.API_SECRET == "YOUR_API_SECRET"
        or XConstants.ACCESS_TOKEN == "YOUR_ACCESS_TOKEN"
        or XConstants.ACCESS_TOKEN_SECRET == "YOUR_ACCESS_TOKEN_SECRET"
    ):
        return (
            False,
            "X.com API credentials not configured. Please update constants.py.",
        )

    # Check if the video file exists
    if not os.path.exists(video_path):
        return False, f"Video file not found: {video_path}"

    # Check file size
    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    if file_size_mb > XConstants.MAX_VIDEO_SIZE_MB:
        return (
            False,
            f"Video is too large for X.com upload: {file_size_mb:.1f}MB (max {XConstants.MAX_VIDEO_SIZE_MB}MB)",
        )

    try:
        # Authenticate with X.com
        auth = tweepy.OAuth1UserHandler(
            XConstants.API_KEY,
            XConstants.API_SECRET,
            XConstants.ACCESS_TOKEN,
            XConstants.ACCESS_TOKEN_SECRET,
        )
        api = tweepy.API(auth)

        # Create post message
        player_info = f" by {player_name}" if XConstants.INCLUDE_PLAYER_NAME else ""
        message = XConstants.REPLAY_SHARE_TEMPLATE.format(
            score=score,
            game_mode=game_mode,
            player=player_name if XConstants.INCLUDE_PLAYER_NAME else "",
        )

        # Upload video and post tweet
        media = api.media_upload(video_path)
        response = api.update_status(status=message, media_ids=[media.media_id])

        # If we get a response with id, it was successful
        if hasattr(response, "id"):
            tweet_id = response.id
            return True, f"Successfully shared to X.com! Tweet ID: {tweet_id}"
        else:
            return False, f"Failed to share to X.com. Unexpected response: {response}"

    except tweepy.TweepyException as e:
        error_msg = str(e)
        if "453" in error_msg:
            logging.error(f"X.com API access level error: {error_msg}")
            return False, (
                "X.com API access level error (Error 453): You need a higher API access tier to post videos.\n"
                "To fix this:\n"
                "1. Visit https://developer.x.com/en/portal/products/\n"
                "2. Upgrade to a paid API tier (Basic or higher)\n"
                "3. Ensure your app has 'Read and Write' permissions\n"
                "4. Update your API credentials in constants.py"
            )
        elif "403" in error_msg:
            logging.error(f"X.com authorization error (403 Forbidden): {error_msg}")
            return False, (
                "X.com authorization error (403 Forbidden): The API credentials don't have permission to post. "
                "To fix this:\n"
                "1. Visit https://developer.twitter.com/\n"
                "2. Create a Project and App with 'Read and Write' permissions\n"
                "3. Generate new API keys and tokens\n"
                "4. Update the credentials in constants.py"
            )
        else:
            logging.error(f"Error sharing to X.com: {e}")
            logging.error(traceback.format_exc())
            return False, f"Error sharing to X.com: {str(e)}"
    except Exception as e:
        logging.error(f"Error sharing to X.com: {e}")
        logging.error(traceback.format_exc())
        return False, f"Error sharing to X.com: {str(e)}"
