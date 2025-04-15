# utils.py

import logging
import time
from math import ceil
from typing import Any, Dict, Optional, Tuple, Callable

import cv2

# Import cleanup util
from cleanup_utils import clean_exit

# Imports needed for mouse_callback helpers
from constants import (
    GameConstants,
    MenuConstants,
    ScoringConstants,
    UIConstants,
    ResolutionConstants,
)

# Import GameState class and CurrentGameState enum from correct locations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game_state import GameState

# Import the necessary utility functions from CORRECT locations
from game_state_helpers import (
    clear_zones,
    load_zones,
    save_score,
    save_zones,
    set_special_hole,
    show_notification,
)
# --- START CHANGE: Import reset_game explicitly ---
from game_state_utils import reset_game
# --- END CHANGE ---
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
    
    # Game over handler that uses our specialized function
    def game_over_handler(event: int, x: int, y: int, game_state: "GameState") -> bool:
        """Specialized handler for game over screen"""
        return _process_game_over_click(x, y, game_state, mouse_callback)
    
    # State-specific handlers
    handlers[CurrentGameState.PLAYING] = {
        cv2.EVENT_LBUTTONDOWN: lambda e, x, y, g: (_process_drawing_event(e, x, y, g) 
                                                  if getattr(g, "drawing", False) 
                                                  else _process_menu_or_modal_click(x, y, g)),
        cv2.EVENT_MOUSEMOVE: lambda e, x, y, g: _process_drawing_event(e, x, y, g) if getattr(g, "drawing", False) else False,
        cv2.EVENT_LBUTTONUP: lambda e, x, y, g: _process_drawing_event(e, x, y, g) if getattr(g, "drawing", False) else False,
    }
    
    handlers[CurrentGameState.ZONE_EDITING] = {
        cv2.EVENT_LBUTTONDOWN: lambda e, x, y, g: _process_zone_editing_event(e, x, y, g),
        cv2.EVENT_MOUSEMOVE: lambda e, x, y, g: _process_zone_editing_event(e, x, y, g),
        cv2.EVENT_LBUTTONUP: lambda e, x, y, g: _process_zone_editing_event(e, x, y, g),
    }
    
    # GAME_OVER has its own specialized handler
    handlers[CurrentGameState.GAME_OVER] = {
        cv2.EVENT_LBUTTONDOWN: game_over_handler
    }
    
    # For states that just handle menu clicks
    for state in [CurrentGameState.MENU, CurrentGameState.PAUSED, CurrentGameState.CONFIRM_QUIT]:
        handlers[state] = {
            cv2.EVENT_LBUTTONDOWN: menu_handler
        }
    
    return handlers

# Get the handlers once at module init time
EVENT_HANDLERS = _get_mouse_event_handlers()

# Mouse callback function
def mouse_callback(event: int, x: int, y: int, flags: int, param: Any) -> None:
    """Global mouse event handler that delegates to the appropriate function based on game state."""
    try:
        # Add debug logging for mouse clicks
        if event == cv2.EVENT_LBUTTONDOWN:
            logger.debug(f"Mouse click detected at coordinates: ({x}, {y})")
            
        game_state = param
        if game_state is None:
            logger.warning("Mouse callback received None game_state.")
            return

        current_state = getattr(game_state, "current_state", None)
        if current_state is None:
            logger.warning("game_state has no current_state attribute in mouse callback.")
            return
            
        # Get the appropriate event handlers for the current state
        state_handlers = EVENT_HANDLERS.get(current_state, {})
        
        # Get the handler for this specific event
        handler = state_handlers.get(event)
        
        # Call the handler if one exists
        if handler:
            handler(event, x, y, game_state)
            return

    except Exception as e:
        logger.exception(f"Error in mouse_callback: {e}")

# --- Helper: Find which handle/area of a zone is clicked ---
# (Content of _get_zone_click_location remains unchanged)
def _get_zone_click_location(x: int, y: int, zone_rect: Tuple[int, int, int, int]) -> Optional[str]:
    zx, zy, zw, zh = zone_rect
    handle_size = UIConstants.ZONE_EDIT_HANDLE_SIZE
    half_handle = handle_size // 2
    if abs(x - zx) < half_handle and abs(y - zy) < half_handle: return "resize_tl"
    if abs(x - (zx + zw)) < half_handle and abs(y - zy) < half_handle: return "resize_tr"
    if abs(x - zx) < half_handle and abs(y - (zy + zh)) < half_handle: return "resize_bl"
    if abs(x - (zx + zw)) < half_handle and abs(y - (zy + zh)) < half_handle: return "resize_br"
    if zx <= x < zx + zw and zy <= y < zy + zh: return "move"
    return None


# --- Helper: Process Interactive Zone Editing Mouse Events ---
# (Content of _process_zone_editing_event remains unchanged)
def _process_zone_editing_event(event: int, x: int, y: int, game_state: "GameState") -> bool:
    handled = False
    zone_idx = getattr(game_state, "selected_zone_for_edit", None)
    if zone_idx is None or not (0 <= zone_idx < len(getattr(game_state, "scoring_zones", []))):
        if game_state.current_state == CurrentGameState.ZONE_EDITING: logger.warning("Zone editing event processed with invalid/no selected zone index. Reverting state.")
        if hasattr(game_state, "current_state"):
            try:
                prev_state = getattr(game_state, "previous_state", None)
                game_state.current_state = (prev_state if prev_state else CurrentGameState.MENU)
                game_state.previous_state = None
            except AttributeError: game_state.current_state = CurrentGameState.MENU
            game_state.selected_zone_for_edit = None
            game_state.zone_editing_action = None
            game_state.drag_start_pos = None
            game_state.original_zone_on_drag_start = None
        return False
    current_zone = game_state.scoring_zones[zone_idx]
    zx, zy, zw, zh, zp = current_zone
    min_size = getattr(ScoringConstants, "MIN_ZONE_SIZE", 10)
    if event == cv2.EVENT_LBUTTONDOWN:
        click_location = _get_zone_click_location(x, y, (zx, zy, zw, zh))
        if click_location:
            game_state.zone_editing_action = click_location
            game_state.drag_start_pos = (x, y)
            game_state.original_zone_on_drag_start = current_zone
            logger.debug(f"Zone editing started: Action={click_location}, Start=({x},{y})")
            handled = True
        else: logger.debug("Click outside selected zone handles during ZONE_EDITING state.")
    elif event == cv2.EVENT_MOUSEMOVE:
        if getattr(game_state, "drag_start_pos", None) and getattr(game_state, "zone_editing_action", None):
            drag_x_start, drag_y_start = game_state.drag_start_pos
            dx, dy = x - drag_x_start, y - drag_y_start
            new_x, new_y, new_w, new_h = zx, zy, zw, zh
            action = game_state.zone_editing_action
            orig_zone = getattr(game_state, "original_zone_on_drag_start", None)
            if not orig_zone:
                 logger.error("Original zone state missing during drag move/resize.")
                 game_state.zone_editing_action = None; game_state.drag_start_pos = None; return False
            orig_x, orig_y, orig_w, orig_h, _ = orig_zone
            if action == "move": new_x, new_y = orig_x + dx, orig_y + dy
            elif action.startswith("resize"):
                if action == "resize_tl": new_x, new_y, new_w, new_h = (orig_x + dx, orig_y + dy, orig_w - dx, orig_h - dy,)
                elif action == "resize_tr": new_x, new_y, new_w, new_h = (orig_x, orig_y + dy, orig_w + dx, orig_h - dy,)
                elif action == "resize_bl": new_x, new_y, new_w, new_h = (orig_x + dx, orig_y, orig_w - dx, orig_h + dy,)
                elif action == "resize_br": new_x, new_y, new_w, new_h = (orig_x, orig_y, orig_w + dx, orig_h + dy,)
                new_w = max(min_size, new_w)
                new_h = max(min_size, new_h)
                if action == "resize_tl": new_x = (orig_x + orig_w) - new_w; new_y = (orig_y + orig_h) - new_h
                elif action == "resize_tr": new_y = (orig_y + orig_h) - new_h
                elif action == "resize_bl": new_x = (orig_x + orig_w) - new_w
            game_state.scoring_zones[zone_idx] = (new_x, new_y, new_w, new_h, zp)
            handled = True
    elif event == cv2.EVENT_LBUTTONUP:
        if getattr(game_state, "drag_start_pos", None) and getattr(game_state, "zone_editing_action", None):
            logger.debug(f"Zone editing finished: Action={game_state.zone_editing_action}")
            final_zone = game_state.scoring_zones[zone_idx]
            fx, fy, fw, fh, fp = final_zone
            valid_edit = True
            error_message = None
            if fw < min_size or fh < min_size: error_message = f"Zone too small! Min size {min_size}. Reverted."; valid_edit = False
            else:
                other_zones = [z for i, z in enumerate(game_state.scoring_zones) if i != zone_idx]
                if _zones_overlap(final_zone[:4], other_zones): error_message = "Edit causes overlap! Reverted."; valid_edit = False
            if not valid_edit:
                show_notification(game_state, error_message, is_error=True, duration=3.0)
                if game_state.original_zone_on_drag_start: game_state.scoring_zones[zone_idx] = (game_state.original_zone_on_drag_start)
                else: logger.error("Cannot revert zone edit, original state was None.")
            else:
                game_state.special_hole = set_special_hole(game_state.scoring_zones)
                show_notification(game_state, f"Zone {zone_idx+1} updated", duration=1.5)
            game_state.zone_editing_action = None
            game_state.drag_start_pos = None
            game_state.original_zone_on_drag_start = None
            handled = True
    return handled


# --- Drawing Event Processing ---
# (Content of _process_drawing_event remains unchanged)
def _process_drawing_event(event: int, x: int, y: int, game_state: "GameState") -> None:
    if event == cv2.EVENT_LBUTTONDOWN:
        if game_state.drawing:
            game_state.start_x, game_state.start_y = x, y
            game_state.temp_zone = None
            game_state.drawing_points_input = ""
            logger.debug(f"Drawing started at ({x}, {y})")
    elif event == cv2.EVENT_MOUSEMOVE:
        if (game_state.drawing and game_state.start_x is not None and game_state.start_y is not None):
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
                                show_notification(game_state, f"Points must be 1-{max_pts}. Using default {ScoringConstants.DEFAULT_POINTS}.", is_error=True, duration=3.0,)
                                points = ScoringConstants.DEFAULT_POINTS
                    except ValueError:
                        if points_str: show_notification(game_state, f"Invalid points '{points_str}'. Using default {ScoringConstants.DEFAULT_POINTS}.", is_error=True, duration=3.0,)
                        points = ScoringConstants.DEFAULT_POINTS
                    new_zone = (x1, y1, w, h, points)
                    if not _zones_overlap(new_zone[:4], getattr(game_state, "scoring_zones", [])):
                        game_state.scoring_zones.append(new_zone)
                        game_state.special_hole = set_special_hole(game_state.scoring_zones)
                        show_notification(game_state, f"Zone Added ({points} pts)")
                        logger.info(f"Added zone: {new_zone}")
                    else:
                        show_notification(game_state, "Zone Overlaps! Not Added.", is_error=True)
                        logger.warning("Zone overlap detected, not adding.")
                else:
                    show_notification(game_state, f"Zone too small (Min: {min_size}x{min_size})", is_error=True,)
                    logger.warning("Drawn zone was too small.")
            game_state.drawing = False
            game_state.temp_zone = None
            game_state.start_x = None
            game_state.start_y = None
            game_state.drawing_points_input = ""


# --- Helper to reset menu editing states ---
# (Content of _reset_all_menu_editing_states remains unchanged)
def _reset_all_menu_editing_states(game_state: "GameState") -> None:
    attrs_to_reset = {
        "editing_zone_index": None, "editing_zone_mode": None, "editing_zone_points_input": None,
        "editing_player_index": None, "editing_player_mode": None, "editing_player_name_input": None,
        "selected_zone_for_edit": None, "zone_editing_action": None, "drag_start_pos": None,
        "original_zone_on_drag_start": None, "edit_zones_current_page": 1, "menu_cache": None,
        "click_feedback_state": None,
    }
    for attr, value in attrs_to_reset.items():
        if hasattr(game_state, attr): setattr(game_state, attr, value)


# --- Process Menu / CONFIRM_QUIT Click ---
# --- START CHANGE: Excluded GAME_OVER state ---
def _process_menu_or_modal_click(x: int, y: int, game_state: "GameState") -> bool:
    """Handles clicks ONLY for MENU and CONFIRM_QUIT states."""
    current_state = getattr(game_state, "current_state", None)
    # Check for PLAYING state to handle menu button click
    if current_state == CurrentGameState.PLAYING:
        # Handle menu button click
        menu_button_rect = (UIConstants.MENU_BUTTON_X, UIConstants.MENU_BUTTON_Y, 
                           UIConstants.MENU_BUTTON_WIDTH, UIConstants.MENU_BUTTON_HEIGHT)
        menu_btn_x, menu_btn_y, menu_btn_w, menu_btn_h = menu_button_rect
        if menu_btn_x <= x < menu_btn_x + menu_btn_w and menu_btn_y <= y < menu_btn_y + menu_btn_h:
            logger.debug(f"Menu button clicked at ({x}, {y})")
            game_state.click_feedback_state = (menu_button_rect, time.time())
            game_state.current_state = CurrentGameState.MENU
            return True
    
    # Exclude GAME_OVER from this function's responsibility
    if current_state not in [CurrentGameState.MENU, CurrentGameState.CONFIRM_QUIT, CurrentGameState.PAUSED]:
         return False
    # --- END CHANGE ---

    # Check for stats panel heatmap button click (in MENU or PAUSED state)
    if current_state in [CurrentGameState.MENU, CurrentGameState.PAUSED]:
        # Calculate stats panel dimensions and position - using the same calculations as _draw_stats_display in ui.py
        current_width, current_height = game_state.get_current_resolution_dimensions()
        menu_x, menu_y = getattr(game_state, "menu_pos", (0, 0))
        menu_w = getattr(game_state, "menu_width", 600)
        stats_content_height = 230
        button_height = 35
        panel_padding_bottom = 15
        total_content_height = stats_content_height + button_height + panel_padding_bottom
        panel_width = 350
        panel_height = max(total_content_height + 40, getattr(game_state, "menu_height", 450))
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
        heatmap_button_rect = (button_x_pos, button_y_pos, heatmap_button_width, button_height)
        bx, by, bw, bh = heatmap_button_rect
        
        if bx <= x < bx + bw and by <= y < by + bh:
            logger.info("Stats panel heatmap button clicked.")
            game_state.click_feedback_state = (heatmap_button_rect, time.time())
            try:
                # Call the heatmap display function
                display_heatmap_modal(game_state, mouse_callback, game_state)
                return True
            except Exception as e:
                logger.exception(f"Error displaying heatmap from stats panel: {e}")
                show_notification(game_state, "Error displaying heatmap", is_error=True)
                return True
    
    # Rest of the function remains largely unchanged, but actions related to GAME_OVER are now unreachable
    required_attrs = ["menu_pos", "menu_width", "menu_height", "submenu_items"]
    if not all(hasattr(game_state, attr) for attr in required_attrs): logger.warning("UI attributes missing in game_state for menu/modal click processing."); return False
    menu_x, menu_y = game_state.menu_pos
    relative_x, relative_y = x - menu_x, y - menu_y
    menu_w, menu_h = game_state.menu_width, game_state.menu_height

    # Handle resolution button click (outside of menu window)
    res_button_rect = (UIConstants.RESOLUTION_BUTTON_X, UIConstants.RESOLUTION_BUTTON_Y, 
                      UIConstants.RESOLUTION_BUTTON_WIDTH, UIConstants.RESOLUTION_BUTTON_HEIGHT)
    res_x, res_y, res_w, res_h = res_button_rect
    if res_x <= x < res_x + res_w and res_y <= y < res_y + res_h:
        logger.debug(f"Resolution button clicked at ({x}, {y})")
        game_state.click_feedback_state = (res_button_rect, time.time())

        # Toggle between available resolutions
        if hasattr(game_state, "set_resolution") and hasattr(game_state, "current_resolution_key"):
            available_resolutions = list(ResolutionConstants.RESOLUTIONS.keys())
            current_index = available_resolutions.index(game_state.current_resolution_key)
            new_index = (current_index + 1) % len(available_resolutions)
            new_resolution = available_resolutions[new_index]
            
            logger.info(f"Changing resolution from {game_state.current_resolution_key} to {new_resolution}")
            game_state.set_resolution(new_resolution)
        
        # Return True to indicate the click was handled
        return True

    if current_state == CurrentGameState.MENU:
        pad = getattr(UIConstants, "MENU_CLOSE_BUTTON_PADDING", 10)
        size = getattr(UIConstants, "MENU_CLOSE_BUTTON_SIZE", 40)
        close_btn_rel_x1, close_btn_rel_y1 = menu_w - pad - size, pad
        close_btn_rel_x2, close_btn_rel_y2 = menu_w - pad, pad + size
        if (close_btn_rel_x1 <= relative_x < close_btn_rel_x2 and close_btn_rel_y1 <= relative_y < close_btn_rel_y2):
            logger.debug("Menu close 'X' button clicked.")
            close_btn_abs_rect = (menu_x + close_btn_rel_x1, menu_y + close_btn_rel_y1, size, size,)
            game_state.click_feedback_state = (close_btn_abs_rect, time.time())
            game_state.current_state = CurrentGameState.PLAYING
            game_state.submenu_active = None
            _reset_all_menu_editing_states(game_state)
            return True

    submenu_items_list = getattr(game_state, "submenu_items", [])
    if not isinstance(submenu_items_list, list): logger.error("game_state.submenu_items is not a list."); return False

    volume_adjusted = False
    for item_data in reversed(submenu_items_list):
        if not isinstance(item_data, tuple) or len(item_data) < 2: continue
        item_rect_orig, action = item_data[0], item_data[1]
        if not isinstance(item_rect_orig, tuple) or len(item_rect_orig) != 4: continue
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

        if (abs_item_x <= click_x_to_check < abs_item_x + abs_item_w and abs_item_y <= click_y_to_check < abs_item_y + abs_item_h):
            logger.debug(f"Click detected on item with action: {action} at rect {item_rect_abs}")
            if isinstance(action, str):
                # Volume slider checks
                if current_state == CurrentGameState.MENU:
                    rel_click_x_in_item = click_x_to_check - (abs_item_x)
                    if action == "adjust_sound_volume":
                        new_volume = max(0.0, min(1.0,(rel_click_x_in_item / abs_item_w if abs_item_w > 0 else 0.0),),)
                        if (abs(getattr(game_state, "current_sound_volume", 0)- new_volume) > 0.01):
                            game_state.current_sound_volume = new_volume; set_volume(game_state); save_settings(game_state); game_state.menu_cache = None; volume_adjusted = True; logger.debug(f"Adjusted sound volume to {new_volume:.2f}"); return True
                    elif action == "adjust_music_volume":
                        new_volume = max(0.0,min(1.0,(rel_click_x_in_item / abs_item_w if abs_item_w > 0 else 0.0),),)
                        if (abs(getattr(game_state, "current_music_volume", 0) - new_volume) > 0.01):
                            game_state.current_music_volume = new_volume; set_volume(game_state); save_settings(game_state); game_state.menu_cache = None; volume_adjusted = True; logger.debug(f"Adjusted music volume to {new_volume:.2f}"); return True

                # Confirm Quit checks
                if current_state == CurrentGameState.CONFIRM_QUIT:
                    if action == "confirm_quit_yes":
                        logger.info("Quit confirmed via 'Yes' button click.")
                        game_state.click_feedback_state = (item_rect_abs,time.time()); cap = getattr(game_state, "cap", None); music = getattr(game_state, "background_music", None); music_on = getattr(game_state, "background_music_on", False)
                        clean_exit(cap, music, music_on, game_state); return True
                    elif action == "confirm_quit_no":
                        logger.debug("Quit cancelled via 'No' button click.")
                        game_state.click_feedback_state = (item_rect_abs,time.time()); prev_state = getattr(game_state,"previous_state_before_quit_confirm",CurrentGameState.PLAYING,); game_state.current_state = prev_state; game_state.previous_state_before_quit_confirm = None; game_state.submenu_items = []; game_state.menu_cache = None; return True

                # Set feedback state if not a volume adjustment
                if not volume_adjusted: game_state.click_feedback_state = (item_rect_abs, time.time())

                # General menu action handling (only for MENU state now)
                known_submenu_nav_actions = {item[1] for item in MenuConstants.MAIN_MENU_ITEMS if isinstance(item[1], str)} | {item[1] for item in MenuConstants.ZONE_SUBMENU_ITEMS if isinstance(item[1], str)}
                non_nav_actions = {"resume","quit","back_to_main","back_to_manage_zones","save_zones","load_zones","clear_zones","add_zone_info",}
                known_submenu_nav_actions -= non_nav_actions

                if current_state == CurrentGameState.MENU:
                    if action == "quit": game_state.previous_state_before_quit_confirm = (CurrentGameState.MENU); game_state.current_state = CurrentGameState.CONFIRM_QUIT; _reset_all_menu_editing_states(game_state)
                    elif action == "toggle_game_sounds": toggle_game_sounds(game_state); game_state.menu_cache = None
                    elif action == "toggle_background_music": toggle_background_music(game_state); game_state.menu_cache = None
                    elif action == "toggle_debug_overlay": game_state.show_debug_overlay = not getattr(game_state, "show_debug_overlay", False); show_notification(game_state,f"Debug Overlay: {'ON' if game_state.show_debug_overlay else 'OFF'}",); game_state.menu_cache = None
                    elif action == "toggle_debug_mode": game_state.debug_mode = not getattr(game_state, "debug_mode", False); log_level = (logging.DEBUG if game_state.debug_mode else logging.INFO); logging.getLogger().setLevel(log_level); [h.setLevel(log_level) for h in logging.getLogger().handlers]; show_notification(game_state,f"Debug Mode: {'ON' if game_state.debug_mode else 'OFF'}",); game_state.menu_cache = None
                    elif action == "cycle_music_track": available_tracks = getattr(GameConstants, "BACKGROUND_MUSIC_TRACKS", []); change_music_track(game_state,(getattr(game_state, "selected_music_track_index", 0) + 1) % len(available_tracks)) if available_tracks else None; game_state.menu_cache = None
                    elif action == "show_splash": display_modal_splash(game_state, mouse_callback, game_state); game_state.menu_cache = None
                    elif action == "resume": game_state.current_state = CurrentGameState.PLAYING; game_state.submenu_active = None; _reset_all_menu_editing_states(game_state)
                    elif action == "back_to_main": _reset_all_menu_editing_states(game_state); game_state.submenu_active = None
                    elif action == "add_zone_info": show_notification(game_state,"Press 's', then click and drag to draw zone",); game_state.current_state = CurrentGameState.PLAYING; game_state.submenu_active = None; _reset_all_menu_editing_states(game_state)
                    elif action == "clear_zones": clear_zones(game_state); _reset_all_menu_editing_states(game_state)
                    elif action == "save_zones": save_zones(game_state); game_state.menu_cache = None
                    elif action == "load_zones": load_zones(game_state); _reset_all_menu_editing_states(game_state)
                    elif action.startswith("set_mode_"):
                         new_mode = action.split("set_mode_")[-1]
                         valid_modes = {"classic","timed","fun","practice","survival","retro",}
                         if new_mode in valid_modes and getattr(game_state, "game_mode", "classic") != new_mode:
                              try: save_score(game_state, game_state.get_current_player().name, mode=game_state.game_mode)
                              except Exception as e: logger.error(f"Error saving score before mode change: {e}")
                              game_state.game_mode = new_mode;
                              game_state.menu_cache = None  # Clear menu cache when changing modes
                              if new_mode == "retro":
                                   available_tracks = getattr(GameConstants, "BACKGROUND_MUSIC_TRACKS", [])
                                   try:
                                       target_track = "background_music4.mp3"
                                       retro_track_index = available_tracks.index(target_track)
                                       logger.info(f"Explicitly changing music for Retro mode switch to: {retro_track_index} ({target_track})")
                                       change_music_track(game_state, retro_track_index)
                                   except ValueError: logger.error(f"Could not find '{target_track}' for retro mode switch. Music will be randomized by reset_game.")
                                   except Exception as e_music: logger.error(f"Error changing music track during retro mode switch: {e_music}")
                              reset_game(game_state)  # Reset game state after all mode-specific changes
                              show_notification(game_state, f"Mode set to: {new_mode.capitalize()}")
                              game_state.current_state = CurrentGameState.PLAYING  # Ensure we're in playing state
                              game_state.submenu_active = None  # Clear any active submenu
                              _reset_all_menu_editing_states(game_state)  # Reset all menu states
                    elif action.startswith("select_player_"):
                         try:
                              index = int(action.split("select_player_")[-1])
                              if 0 <= index < len(getattr(game_state, "players", [])) and index != getattr(game_state, "current_player_index", 0):
                                   try: save_score(game_state, game_state.get_current_player().name)
                                   except Exception as e: logger.error(f"Error saving score before player switch: {e}")
                                   game_state.current_player_index = index; logger.info(f"Switched to player: {game_state.get_current_player().name}"); reset_game(game_state); _reset_all_menu_editing_states(game_state)
                         except Exception as e: logger.error(f"Error processing select_player action '{action}': {e}")
                    elif action == "add_player":
                         if len(getattr(game_state, "players", [])) < 2: game_state.players.append(Player(f"Player {len(game_state.players) + 1}")); show_notification(game_state, "Player Added")
                         else: show_notification(game_state,"Maximum players reached",is_error=True)
                         _reset_all_menu_editing_states(game_state)
                    elif action == "back_to_manage_zones": _reset_all_menu_editing_states(game_state); game_state.submenu_active = "manage_zones"
                    elif action == "prev_edit_zone_page":
                         if getattr(game_state, "edit_zones_current_page", 1) > 1: game_state.edit_zones_current_page -= 1; game_state.menu_cache = None
                    elif action == "next_edit_zone_page":
                         total_pages = max(1, ceil(len(getattr(game_state, "scoring_zones",[])) / getattr(game_state,"edit_zones_items_per_page", 8)),)
                         if getattr(game_state, "edit_zones_current_page", 1) < total_pages: game_state.edit_zones_current_page += 1; game_state.menu_cache = None
                    elif action == "leaderboard_classic": game_state.leaderboard_mode = "classic"; game_state.menu_cache = None
                    elif action == "leaderboard_timed": game_state.leaderboard_mode = "timed"; game_state.menu_cache = None
                    elif action == "leaderboard_survival": game_state.leaderboard_mode = "survival"; game_state.menu_cache = None
                    elif action.startswith("edit_zone_"):
                         try:
                              index = int(action.split("edit_zone_")[-1])
                              if 0 <= index < len(getattr(game_state, "scoring_zones", [])) and not (getattr(game_state, "editing_zone_index", None) == index and getattr(game_state,"editing_zone_mode", None) == "edit_points"):
                                   _reset_all_menu_editing_states(game_state); game_state.editing_zone_index = index; game_state.editing_zone_mode = "edit_points"; game_state.editing_zone_points_input = str(game_state.scoring_zones[index][4]); game_state.menu_cache = None; logger.info(f"Started editing points for zone {index+1}")
                         except Exception as e: logger.error(f"Error processing edit_zone action '{action}': {e}")
                    elif action.startswith("move_zone_"):
                         try:
                              index = int(action.split("move_zone_")[-1])
                              if 0 <= index < len(getattr(game_state, "scoring_zones", [])):
                                   _reset_all_menu_editing_states(game_state); game_state.selected_zone_for_edit = index; game_state.previous_state = CurrentGameState.MENU; game_state.current_state = CurrentGameState.ZONE_EDITING; show_notification(game_state,"Click inside zone to move, drag. ESC=Cancel.",duration=0,)
                         except Exception as e: logger.error(f"Error processing move_zone action '{action}': {e}")
                    elif action.startswith("resize_zone_"):
                         try:
                              index = int(action.split("resize_zone_")[-1])
                              if 0 <= index < len(getattr(game_state, "scoring_zones", [])):
                                   _reset_all_menu_editing_states(game_state); game_state.selected_zone_for_edit = index; game_state.previous_state = CurrentGameState.MENU; game_state.current_state = CurrentGameState.ZONE_EDITING; show_notification(game_state,"Click & drag corner handles. ESC=Cancel.",duration=0,)
                         except Exception as e: logger.error(f"Error processing resize_zone action '{action}': {e}")
                    elif action.startswith("edit_player_name_"):
                         try:
                              index = int(action.split("edit_player_name_")[-1])
                              if 0 <= index < len(getattr(game_state, "players", [])) and not (getattr(game_state, "editing_player_index", None) == index and getattr(game_state,"editing_player_mode", None) == "edit_name"):
                                   _reset_all_menu_editing_states(game_state); game_state.editing_player_index = index; game_state.editing_player_mode = "edit_name"; game_state.editing_player_name_input = str(game_state.players[index].name); game_state.menu_cache = None; logger.info(f"Started editing name for player {index+1}")
                         except Exception as e: logger.error(f"Error processing edit_player_name action '{action}': {e}")
                    elif action.startswith("delete_zone_"):
                         try:
                              index = int(action.split("delete_zone_")[-1])
                              if 0 <= index < len(getattr(game_state, "scoring_zones", [])):
                                   if (getattr(game_state,"editing_zone_index", None) == index and getattr(game_state,"editing_zone_mode", None) == "confirm_delete"):
                                        logger.info(f"Confirmed deleting zone {index+1}"); del game_state.scoring_zones[index]; game_state.special_hole = set_special_hole(game_state.scoring_zones); show_notification(game_state,f"Zone {index+1} Deleted"); _reset_all_menu_editing_states(game_state)
                                   else: _reset_all_menu_editing_states(game_state); game_state.editing_zone_index = index; game_state.editing_zone_mode = "confirm_delete"; game_state.menu_cache = None; show_notification(game_state,f"Click Delete again for zone {index+1} to confirm",duration=4.0,)
                         except Exception as e: logger.error(f"Error processing delete_zone action '{action}': {e}"); _reset_all_menu_editing_states(game_state)
                    # Navigation to submenus
                    elif action in known_submenu_nav_actions: _reset_all_menu_editing_states(game_state); game_state.submenu_active = action
                    else: logger.warning(f"Unhandled MENU action string: {action}")

                # --- REMOVED GAME_OVER block ---

                return True # Indicate click was handled
            # --- End isinstance(action, str) block ---

    # If loop completes without handling click on an item
    if volume_adjusted: return True # Indicate click was handled by volume adjustment
    return False # Click was not handled by menu/modal logic

# === ADD NEW FUNCTION: Process Game Over Screen Clicks ===
def _process_game_over_click(x: int, y: int, game_state: "GameState", mouse_callback: Callable) -> bool:
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
                display_heatmap_modal(game_state, mouse_callback, game_state)
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