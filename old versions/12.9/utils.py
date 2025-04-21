# utils.py

import logging
from math import ceil
from typing import Any, Optional, Tuple

import cv2

# Import cleanup util
from cleanup_utils import clean_exit
# Imports needed for mouse_callback helpers
from constants import (GameConstants, MenuConstants, ScoringConstants,
                       UIConstants)
# Import GameState class and CurrentGameState enum from correct locations
from game_state import GameState  # Keep import for GameState class
# Import the necessary utility functions from CORRECT locations
from game_state_helpers import (  # Helpers that were moved to helpers
    clear_zones, load_zones, save_score, save_zones, set_special_hole,
    show_notification)
from game_state_utils import reset_game  # Correct import location
from game_state_utils import (  # Utils that remained (or need to be) in utils
    change_music_track, save_settings, set_volume, toggle_background_music,
    toggle_game_sounds)
from game_types import CurrentGameState  # Import Enum from new location
# Import Player class
from player import Player
# Import overlap check function from scoring
from scoring import _zones_overlap
# Import UI screens/modals
from ui_screens import display_modal_splash

logger = logging.getLogger(__name__)


# --- Helper: Find which handle/area of a zone is clicked ---
def _get_zone_click_location(
    x: int, y: int, zone_rect: Tuple[int, int, int, int]
) -> Optional[str]:
    """Determine if a click is on a corner, edge, or inside a zone."""
    zx, zy, zw, zh = zone_rect
    handle_size = UIConstants.ZONE_EDIT_HANDLE_SIZE; half_handle = handle_size // 2
    if abs(x - zx) < half_handle and abs(y - zy) < half_handle: return "resize_tl"
    if abs(x - (zx + zw)) < half_handle and abs(y - zy) < half_handle: return "resize_tr"
    if abs(x - zx) < half_handle and abs(y - (zy + zh)) < half_handle: return "resize_bl"
    if abs(x - (zx + zw)) < half_handle and abs(y - (zy + zh)) < half_handle: return "resize_br"
    if zx < x < zx + zw and zy < y < zy + zh: return "move"
    return None


# --- Helper: Process Interactive Zone Editing Mouse Events ---
def _process_zone_editing_event(
    event: int, x: int, y: int, game_state: GameState
) -> bool:
    """Process mouse events during interactive zone move/resize."""
    handled = False; zone_idx = game_state.selected_zone_for_edit
    if zone_idx is None or not (0 <= zone_idx < len(game_state.scoring_zones)):
        logger.warning("Zone editing event processed with invalid selected_zone_for_edit.")
        game_state.zone_editing_action = None; game_state.drag_start_pos = None
        game_state.selected_zone_for_edit = None; game_state.original_zone_on_drag_start = None
        try: game_state.current_state = (game_state.previous_state if game_state.previous_state else CurrentGameState.MENU)
        except AttributeError: game_state.current_state = CurrentGameState.MENU
        game_state.previous_state = None; return False

    current_zone = game_state.scoring_zones[zone_idx]; zx, zy, zw, zh, zp = current_zone
    min_size = ScoringConstants.MIN_ZONE_SIZE

    if event == cv2.EVENT_LBUTTONDOWN:
        click_location = _get_zone_click_location(x, y, (zx, zy, zw, zh))
        if click_location:
            game_state.zone_editing_action = click_location; game_state.drag_start_pos = (x, y)
            game_state.original_zone_on_drag_start = current_zone
            logger.debug(f"Zone editing started: Action={click_location}, Start=({x},{y})"); handled = True
        else: logger.debug("Click outside selected zone during ZONE_EDITING state.")

    elif event == cv2.EVENT_MOUSEMOVE:
        if game_state.drag_start_pos and game_state.zone_editing_action:
            drag_x_start, drag_y_start = game_state.drag_start_pos; dx, dy = x - drag_x_start, y - drag_y_start
            new_x, new_y, new_w, new_h = zx, zy, zw, zh; action = game_state.zone_editing_action
            if action == "move": new_x, new_y = zx + dx, zy + dy
            elif action == "resize_tl": new_x, new_y, new_w, new_h = zx + dx, zy + dy, zw - dx, zh - dy
            elif action == "resize_tr": new_y, new_w, new_h = zy + dy, zw + dx, zh - dy
            elif action == "resize_bl": new_x, new_w, new_h = zx + dx, zw - dx, zh + dy
            elif action == "resize_br": new_w, new_h = zw + dx, zh + dy
            if action.startswith("resize"):
                prev_w, prev_h = new_w, new_h; new_w, new_h = max(min_size, new_w), max(min_size, new_h)
                if action == "resize_tl":
                    if new_w != prev_w: new_x = (zx + zw) - new_w
                    if new_h != prev_h: new_y = (zy + zh) - new_h
                elif action == "resize_tr":
                    if new_h != prev_h: new_y = (zy + zh) - new_h
                elif action == "resize_bl":
                    if new_w != prev_w: new_x = (zx + zw) - new_w
            game_state.scoring_zones[zone_idx] = (new_x, new_y, new_w, new_h, zp); handled = True

    elif event == cv2.EVENT_LBUTTONUP:
        if game_state.drag_start_pos and game_state.zone_editing_action:
            logger.debug(f"Zone editing finished: Action={game_state.zone_editing_action}")
            final_zone = game_state.scoring_zones[zone_idx]; fx, fy, fw, fh, fp = final_zone
            if fw < min_size or fh < min_size:
                show_notification(game_state, f"Zone too small! Min size {min_size}. Reverted.", is_error=True, duration=3.0)
                if game_state.original_zone_on_drag_start: game_state.scoring_zones[zone_idx] = game_state.original_zone_on_drag_start
            else:
                other_zones = [z for i, z in enumerate(game_state.scoring_zones) if i != zone_idx]
                if _zones_overlap(final_zone[:4], other_zones):
                    show_notification(game_state, "Edit causes overlap! Reverted.", is_error=True, duration=3.0)
                    if game_state.original_zone_on_drag_start: game_state.scoring_zones[zone_idx] = game_state.original_zone_on_drag_start
                else: game_state.special_hole = set_special_hole(game_state.scoring_zones); show_notification(game_state, f"Zone {zone_idx+1} updated", duration=1.5)
            game_state.zone_editing_action = None; game_state.drag_start_pos = None; game_state.original_zone_on_drag_start = None; handled = True
    return handled


# --- Drawing Event Processing ---
def _process_drawing_event(event: int, x: int, y: int, game_state: GameState) -> None:
    """Process mouse events for drawing scoring zones."""
    if event == cv2.EVENT_LBUTTONDOWN:
        if game_state.drawing: game_state.start_x, game_state.start_y = x, y; game_state.temp_zone = None; game_state.drawing_points_input = ""; logger.debug(f"Drawing started at ({x}, {y})")
    elif event == cv2.EVENT_MOUSEMOVE:
        if (game_state.drawing and game_state.start_x is not None and game_state.start_y is not None):
            x1, y1 = min(game_state.start_x, x), min(game_state.start_y, y); w, h = abs(game_state.start_x - x), abs(game_state.start_y - y); game_state.temp_zone = (x1, y1, w, h)
    elif event == cv2.EVENT_LBUTTONUP:
        if game_state.drawing:
            logger.debug("Drawing mouse up.")
            if game_state.temp_zone:
                x1, y1, w, h = game_state.temp_zone
                if (w >= ScoringConstants.MIN_ZONE_SIZE and h >= ScoringConstants.MIN_ZONE_SIZE):
                    points_str = game_state.drawing_points_input; points = ScoringConstants.DEFAULT_POINTS
                    try:
                        if points_str: points = int(points_str)
                        if not (1 <= points <= ScoringConstants.MAX_POINTS): show_notification(game_state, f"Points must be 1-{ScoringConstants.MAX_POINTS}. Using default {ScoringConstants.DEFAULT_POINTS}.", is_error=True, duration=3.0); points = ScoringConstants.DEFAULT_POINTS
                    except ValueError:
                        if points_str: show_notification(game_state, f"Invalid points entered '{points_str}'. Using default {ScoringConstants.DEFAULT_POINTS}.", is_error=True, duration=3.0)
                        points = ScoringConstants.DEFAULT_POINTS
                    new_zone = (x1, y1, w, h, points)
                    if not _zones_overlap(new_zone[:4], game_state.scoring_zones):
                        game_state.scoring_zones.append(new_zone); game_state.special_hole = set_special_hole(game_state.scoring_zones); show_notification(game_state, f"Zone Added ({points} pts)"); logger.info(f"Added zone: {new_zone}")
                    else: show_notification(game_state, "Zone Overlaps! Not Added.", is_error=True); logger.warning("Zone overlap detected, not adding.")
                else: show_notification(game_state, f"Zone too small (Min: {ScoringConstants.MIN_ZONE_SIZE}x{ScoringConstants.MIN_ZONE_SIZE})", is_error=True); logger.warning("Drawn zone was too small.")
            game_state.drawing = False; game_state.temp_zone = None; game_state.start_x = None; game_state.start_y = None; game_state.drawing_points_input = ""


# --- Helper to reset menu editing states ---
def _reset_all_menu_editing_states(game_state: GameState) -> None:
    """Resets all flags and temporary inputs related to menu editing."""
    game_state.editing_zone_index = None; game_state.editing_zone_mode = None; game_state.editing_zone_points_input = None
    game_state.editing_player_index = None; game_state.editing_player_mode = None; game_state.editing_player_name_input = None
    game_state.selected_zone_for_edit = None; game_state.zone_editing_action = None
    game_state.drag_start_pos = None; game_state.original_zone_on_drag_start = None
    game_state.edit_zones_current_page = 1; game_state.menu_cache = None


# --- Process Menu/Game Over/CONFIRM_QUIT Click (Uses Utility Functions) ---
def _process_menu_or_modal_click(x: int, y: int, game_state: GameState) -> bool:
    """Process clicks within the menu, game over screen, or confirmation dialog."""
    if game_state.current_state not in [CurrentGameState.MENU, CurrentGameState.GAME_OVER, CurrentGameState.CONFIRM_QUIT]: return False
    if not all(hasattr(game_state, attr) for attr in ["menu_pos", "menu_width", "menu_height", "submenu_items"]): logger.warning("UI attributes missing in game_state for click processing."); return False

    menu_x, menu_y = game_state.menu_pos
    relative_x, relative_y = x - menu_x, y - menu_y

    if game_state.current_state == CurrentGameState.MENU:
        menu_w, menu_h = game_state.menu_width, game_state.menu_height
        is_outside_menu = not (0 <= relative_x < menu_w and 0 <= relative_y < menu_h)
        pad, size = UIConstants.MENU_CLOSE_BUTTON_PADDING, UIConstants.MENU_CLOSE_BUTTON_SIZE
        close_btn_rel_x1, close_btn_rel_y1 = menu_w - pad - size, pad
        close_btn_rel_x2, close_btn_rel_y2 = menu_w - pad, pad + size
        if close_btn_rel_x1 <= relative_x < close_btn_rel_x2 and close_btn_rel_y1 <= relative_y < close_btn_rel_y2:
            logger.debug("Menu close button clicked."); game_state.clicked_button_rect = (menu_x + close_btn_rel_x1, menu_y + close_btn_rel_y1, size, size)
            game_state.current_state = CurrentGameState.PLAYING; game_state.submenu_active = None
            _reset_all_menu_editing_states(game_state); return True
        if is_outside_menu: return False

    if not isinstance(game_state.submenu_items, list): logger.error("game_state.submenu_items is not a list."); return False

    known_submenu_nav_actions = {item[1] for item in MenuConstants.MAIN_MENU_ITEMS if isinstance(item[1], str)}
    known_submenu_nav_actions.update({item[1] for item in MenuConstants.ZONE_SUBMENU_ITEMS if isinstance(item[1], str)})
    non_nav_actions = {"resume", "quit", "back_to_main", "back_to_manage_zones", "save_zones", "load_zones", "clear_zones", "add_zone_info"}
    known_submenu_nav_actions -= non_nav_actions

    volume_adjusted = False

    for item_data in reversed(game_state.submenu_items):
        if not isinstance(item_data, tuple) or len(item_data) < 2: continue
        item_rect_orig, action = item_data[0], item_data[1]
        if not isinstance(item_rect_orig, tuple) or len(item_rect_orig) != 4: continue
        item_x, item_y, item_w, item_h = item_rect_orig

        if game_state.current_state != CurrentGameState.CONFIRM_QUIT:
             item_rect_abs = (item_x + menu_x, item_y + menu_y, item_w, item_h); click_x_to_check, click_y_to_check = x, y
        else: item_rect_abs = item_rect_orig; click_x_to_check, click_y_to_check = x, y

        abs_item_x, abs_item_y, abs_item_w, abs_item_h = item_rect_abs
        if (abs_item_x <= click_x_to_check < abs_item_x + abs_item_w and abs_item_y <= click_y_to_check < abs_item_y + abs_item_h):
            logger.debug(f"Click detected on item with action: {action} at rect {item_rect_abs}")
            if isinstance(action, str):
                if game_state.current_state == CurrentGameState.MENU:
                    rel_click_x = x - (menu_x + item_x)
                    if action == "adjust_sound_volume":
                        new_volume = max(0.0, min(1.0, rel_click_x / item_w if item_w > 0 else 0.0)); game_state.current_sound_volume = new_volume
                        set_volume(game_state); save_settings(game_state); game_state.menu_cache = None; volume_adjusted = True; logger.debug(f"Adjusted sound volume to {new_volume:.2f}")
                    elif action == "adjust_music_volume":
                        new_volume = max(0.0, min(1.0, rel_click_x / item_w if item_w > 0 else 0.0)); game_state.current_music_volume = new_volume
                        set_volume(game_state); save_settings(game_state); game_state.menu_cache = None; volume_adjusted = True; logger.debug(f"Adjusted music volume to {new_volume:.2f}")

                if game_state.current_state == CurrentGameState.CONFIRM_QUIT:
                    if action == "confirm_quit_yes":
                        logger.info("Quit confirmed via 'Yes' button click."); game_state.clicked_button_rect = item_rect_abs
                        clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state); return True
                    elif action == "confirm_quit_no":
                        logger.debug("Quit cancelled via 'No' button click."); game_state.clicked_button_rect = item_rect_abs
                        game_state.current_state = getattr(game_state, "previous_state_before_quit_confirm", CurrentGameState.PLAYING)
                        game_state.previous_state_before_quit_confirm = None; game_state.submenu_items = []; return True

                elif not volume_adjusted:
                    game_state.clicked_button_rect = item_rect_abs # Set feedback state
                    if action == "quit": logger.debug("Menu quit action triggered, entering CONFIRM_QUIT state."); game_state.previous_state_before_quit_confirm = CurrentGameState.MENU; game_state.current_state = CurrentGameState.CONFIRM_QUIT; _reset_all_menu_editing_states(game_state); return True

                    if game_state.current_state == CurrentGameState.MENU:
                        if action == "toggle_game_sounds": toggle_game_sounds(game_state); game_state.menu_cache = None
                        elif action == "toggle_background_music": toggle_background_music(game_state); game_state.menu_cache = None
                        elif action == "toggle_debug_overlay": game_state.show_debug_overlay = not game_state.show_debug_overlay; show_notification(game_state, f"Debug Overlay: {'ON' if game_state.show_debug_overlay else 'OFF'}"); game_state.menu_cache = None
                        elif action == "toggle_debug_mode": game_state.debug_mode = not game_state.debug_mode; log_level = logging.DEBUG if game_state.debug_mode else logging.INFO; logging.getLogger().setLevel(log_level); [h.setLevel(log_level) for h in logging.getLogger().handlers]; show_notification(game_state, f"Debug Mode: {'ON' if game_state.debug_mode else 'OFF'}"); game_state.menu_cache = None
                        elif action == "cycle_music_track":
                            total_tracks = len(GameConstants.BACKGROUND_MUSIC_TRACKS)
                            if total_tracks > 0: change_music_track(game_state, (game_state.selected_music_track_index + 1) % total_tracks); game_state.menu_cache = None
                        elif action == "show_splash": display_modal_splash(game_state, mouse_callback, game_state); game_state.menu_cache = None
                        elif action == "resume": game_state.current_state = CurrentGameState.PLAYING; game_state.submenu_active = None; _reset_all_menu_editing_states(game_state)
                        elif action == "back_to_main": _reset_all_menu_editing_states(game_state); game_state.submenu_active = None
                        elif action == "add_zone_info": show_notification(game_state, "Press 's', then click and drag to draw zone"); game_state.current_state = CurrentGameState.PLAYING; game_state.submenu_active = None; _reset_all_menu_editing_states(game_state)
                        elif action == "clear_zones": clear_zones(game_state); _reset_all_menu_editing_states(game_state)
                        elif action == "save_zones": save_zones(game_state); game_state.menu_cache = None
                        elif action == "load_zones": load_zones(game_state); _reset_all_menu_editing_states(game_state)
                        elif action.startswith("set_mode_"):
                            new_mode = action.split("set_mode_")[1]
                            valid_modes = ["classic", "timed", "fun", "practice", "survival", "retro"]
                            if new_mode in valid_modes:
                                if game_state.game_mode != new_mode:
                                    try: save_score(game_state, game_state.get_current_player().name, mode=game_state.game_mode)
                                    except Exception as e: logger.error(f"Error saving score before mode change: {e}")
                                    game_state.game_mode = new_mode; reset_game(game_state); show_notification(game_state, f"Mode set to: {new_mode.capitalize()}")
                                    game_state.current_state = CurrentGameState.PLAYING; game_state.submenu_active = None; _reset_all_menu_editing_states(game_state)
                                else: game_state.current_state = CurrentGameState.PLAYING; game_state.submenu_active = None; _reset_all_menu_editing_states(game_state)
                        elif action.startswith("select_player_"):
                            try:
                                index = int(action.split("select_player_")[1])
                                if 0 <= index < len(game_state.players):
                                    if index != game_state.current_player_index:
                                        try: save_score(game_state, game_state.get_current_player().name)
                                        except Exception as e: logger.error(f"Error saving score before player switch: {e}")
                                        game_state.current_player_index = index; logger.info(f"Switched to player: {game_state.get_current_player().name}"); reset_game(game_state)
                                    else: logger.debug("Selected current player, no change.")
                                else: logger.warning(f"Invalid player index {index} from action '{action}'")
                                _reset_all_menu_editing_states(game_state)
                            except (ValueError, IndexError) as e: logger.error(f"Error parsing player index from action '{action}': {e}"); _reset_all_menu_editing_states(game_state)
                        elif action == "add_player":
                            if len(game_state.players) < 2: game_state.players.append(Player(f"Player {len(game_state.players) + 1}")); show_notification(game_state, "Player Added")
                            else: show_notification(game_state, "Maximum 2 players supported", is_error=True)
                            _reset_all_menu_editing_states(game_state)
                        elif action == "back_to_manage_zones": _reset_all_menu_editing_states(game_state); game_state.submenu_active = "manage_zones"
                        elif action == "prev_edit_zone_page":
                            if game_state.edit_zones_current_page > 1: game_state.edit_zones_current_page -= 1; game_state.menu_cache = None
                        elif action == "next_edit_zone_page":
                            total_pages = max(1, ceil(len(game_state.scoring_zones) / game_state.edit_zones_items_per_page))
                            if game_state.edit_zones_current_page < total_pages: game_state.edit_zones_current_page += 1; game_state.menu_cache = None
                        elif action == "leaderboard_classic": game_state.leaderboard_mode = "classic"; game_state.menu_cache = None
                        elif action == "leaderboard_timed": game_state.leaderboard_mode = "timed"; game_state.menu_cache = None
                        elif action == "leaderboard_survival": game_state.leaderboard_mode = "survival"; game_state.menu_cache = None
                        elif action.startswith("edit_zone_"):
                            try:
                                index = int(action.split("edit_zone_")[1])
                                if 0 <= index < len(game_state.scoring_zones):
                                    if not (game_state.editing_zone_index == index and game_state.editing_zone_mode == "edit_points"):
                                        _reset_all_menu_editing_states(game_state); game_state.editing_zone_index = index; game_state.editing_zone_mode = "edit_points"
                                        game_state.editing_zone_points_input = str(game_state.scoring_zones[index][4]); game_state.menu_cache = None; logger.info(f"Started editing points for zone {index+1}")
                                else: logger.warning(f"Invalid zone index {index} for edit points action '{action}'"); _reset_all_menu_editing_states(game_state)
                            except (ValueError, IndexError) as e: logger.error(f"Error parsing zone index from action '{action}': {e}"); _reset_all_menu_editing_states(game_state)
                        elif action.startswith("move_zone_"):
                            try:
                                index = int(action.split("move_zone_")[1])
                                if 0 <= index < len(game_state.scoring_zones):
                                    _reset_all_menu_editing_states(game_state); game_state.selected_zone_for_edit = index; game_state.previous_state = CurrentGameState.MENU; game_state.current_state = CurrentGameState.ZONE_EDITING
                                    show_notification(game_state, "Click inside zone to move, then drag. ESC to cancel.", duration=0)
                                else: logger.warning(f"Invalid zone index {index} for move action '{action}'")
                            except (ValueError, IndexError) as e: logger.error(f"Error parsing zone index from action '{action}': {e}")
                        elif action.startswith("resize_zone_"):
                            try:
                                index = int(action.split("resize_zone_")[1])
                                if 0 <= index < len(game_state.scoring_zones):
                                    _reset_all_menu_editing_states(game_state); game_state.selected_zone_for_edit = index; game_state.previous_state = CurrentGameState.MENU; game_state.current_state = CurrentGameState.ZONE_EDITING
                                    show_notification(game_state, "Click & drag corner handles to resize. ESC to cancel.", duration=0)
                                else: logger.warning(f"Invalid zone index {index} for resize action '{action}'")
                            except (ValueError, IndexError) as e: logger.error(f"Error parsing zone index from action '{action}': {e}")
                        elif action.startswith("edit_player_name_"):
                            try:
                                index = int(action.split("edit_player_name_")[1])
                                if 0 <= index < len(game_state.players):
                                    if not (game_state.editing_player_index == index and game_state.editing_player_mode == "edit_name"):
                                        _reset_all_menu_editing_states(game_state); game_state.editing_player_index = index; game_state.editing_player_mode = "edit_name"
                                        game_state.editing_player_name_input = str(game_state.players[index].name); game_state.menu_cache = None; logger.info(f"Started editing name for player {index+1}")
                                else: logger.warning(f"Invalid player index {index} for edit name action '{action}'"); _reset_all_menu_editing_states(game_state)
                            except (ValueError, IndexError) as e: logger.error(f"Error parsing player index from action '{action}': {e}"); _reset_all_menu_editing_states(game_state)
                        elif action.startswith("delete_zone_"):
                            try:
                                index = int(action.split("delete_zone_")[1])
                                if 0 <= index < len(game_state.scoring_zones):
                                    if (game_state.editing_zone_index == index and game_state.editing_zone_mode == "confirm_delete"):
                                        logger.info(f"Confirmed deleting zone {index+1}"); del game_state.scoring_zones[index]; game_state.special_hole = set_special_hole(game_state.scoring_zones)
                                        show_notification(game_state, f"Zone {index+1} Deleted"); _reset_all_menu_editing_states(game_state)
                                    else:
                                        # <<< CORRECTED INDENTATION BLOCK START >>>
                                        _reset_all_menu_editing_states(game_state)
                                        game_state.editing_zone_index = index
                                        game_state.editing_zone_mode = "confirm_delete"
                                        game_state.menu_cache = None
                                        show_notification(
                                            game_state,
                                            f"Click Delete again for zone {index+1} to confirm",
                                            duration=4.0
                                        ) # This line was incorrectly indented
                                        # <<< CORRECTED INDENTATION BLOCK END >>>
                                else:
                                    logger.warning(f"Invalid zone index {index} for delete action '{action}'")
                                    _reset_all_menu_editing_states(game_state)
                            except (ValueError, IndexError) as e:
                                logger.error(f"Error parsing zone index from action '{action}': {e}")
                                _reset_all_menu_editing_states(game_state)
                        elif action in known_submenu_nav_actions: _reset_all_menu_editing_states(game_state); game_state.submenu_active = action
                        else: logger.warning(f"Unhandled MENU action string: {action}")

                    elif game_state.current_state == CurrentGameState.GAME_OVER:
                        if action == "new_game_from_gameover": reset_game(game_state); game_state.current_state = CurrentGameState.GETTING_PLAYER_NAME; game_state.win_condition_met = False
                        elif action == "show_leaderboard_from_gameover": game_state.current_state = CurrentGameState.MENU; game_state.submenu_active = "leaderboard"; game_state.win_condition_met = False; game_state.menu_cache = None
                        else: logger.warning(f"Unhandled GAME_OVER action string: {action}")
                    return True

            if volume_adjusted: return True
    return False


# --- Main Mouse Callback ---
def mouse_callback(event: int, x: int, y: int, flags: int, param: Any) -> None:
    """Handle mouse events for the main application window."""
    game_state: GameState = param; click_handled = False
    if game_state is None: logger.error("Mouse callback invoked with None game_state parameter."); return

    # 1. Handle interactive zone editing first
    if game_state.current_state == CurrentGameState.ZONE_EDITING and event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONUP]:
        click_handled = _process_zone_editing_event(event, x, y, game_state);
        if click_handled and event != cv2.EVENT_MOUSEMOVE: return

    # 2. Handle zone drawing
    if (not click_handled and game_state.current_state == CurrentGameState.PLAYING and getattr(game_state, "drawing", False) and event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONUP]):
        _process_drawing_event(event, x, y, game_state);
        if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP]: click_handled = True; return

    # 3. Handle clicks on menu, game over, or CONFIRM_QUIT items
    if (not click_handled and game_state.current_state in [CurrentGameState.MENU, CurrentGameState.GAME_OVER, CurrentGameState.CONFIRM_QUIT] and event == cv2.EVENT_LBUTTONDOWN):
        click_handled = _process_menu_or_modal_click(x, y, game_state);
        if click_handled: return

    # 4. Handle click on the main "Menu" button
    if (not click_handled and game_state.current_state == CurrentGameState.PLAYING and not getattr(game_state, "drawing", False) and event == cv2.EVENT_LBUTTONDOWN):
        menu_button_rect = (UIConstants.MENU_BUTTON_X, UIConstants.MENU_BUTTON_Y, UIConstants.MENU_BUTTON_WIDTH, UIConstants.MENU_BUTTON_HEIGHT)
        if (menu_button_rect[0] <= x < menu_button_rect[0] + menu_button_rect[2] and menu_button_rect[1] <= y < menu_button_rect[1] + menu_button_rect[3]):
            logger.debug("Main Menu button clicked."); game_state.clicked_button_rect = menu_button_rect
            game_state.current_state = CurrentGameState.MENU; game_state.submenu_active = None
            _reset_all_menu_editing_states(game_state); click_handled = True; return

    # 5. Log unhandled clicks (optional)
    # if not click_handled and event == cv2.EVENT_LBUTTONDOWN: logger.debug(f"Unhandled LBUTTONDOWN click at ({x},{y}) in state {game_state.current_state}")