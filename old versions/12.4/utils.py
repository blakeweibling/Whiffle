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
# Removed imports from menu for zone functions and reset_game

# Import GameState class and CurrentGameState enum from correct locations
from game_state import GameState        # Keep import for GameState class
from game_types import CurrentGameState # Import Enum from new location

# Import Player class
from player import Player
# Import cleanup util
from cleanup_utils import clean_exit
# Import UI screens/modals
from ui_screens import display_modal_splash
# Import overlap check function from scoring
from scoring import _zones_overlap

# Import the necessary utility functions from CORRECT locations
from game_state_helpers import ( # Helpers that were moved to helpers
    save_score,
    show_notification,
    set_special_hole,
    save_zones,
    load_zones,
    clear_zones,
)
from game_state_utils import ( # Utils that remained (or need to be) in utils
    reset_game,              # Correct import location
    toggle_background_music,
    toggle_game_sounds,
    change_music_track,
    set_volume,
    save_settings,
)

logger = logging.getLogger(__name__)


# --- Helper: Find which handle/area of a zone is clicked ---
def _get_zone_click_location(
    x: int, y: int, zone_rect: Tuple[int, int, int, int]
) -> Optional[str]:
    """Determine if a click is on a corner, edge, or inside a zone."""
    # (Code unchanged)
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
    # (Code unchanged, uses helpers imported above)
    handled = False; zone_idx = game_state.selected_zone_for_edit
    if zone_idx is None or not (0 <= zone_idx < len(game_state.scoring_zones)):
        game_state.zone_editing_action=None; game_state.drag_start_pos=None; game_state.selected_zone_for_edit=None; game_state.original_zone_on_drag_start=None
        try: game_state.current_state=(game_state.previous_state if game_state.previous_state else CurrentGameState.MENU)
        except AttributeError: game_state.current_state=CurrentGameState.MENU
        return False
    current_zone = game_state.scoring_zones[zone_idx]; zx, zy, zw, zh, zp = current_zone; min_size = ScoringConstants.MIN_ZONE_SIZE
    if event == cv2.EVENT_LBUTTONDOWN:
        click_location = _get_zone_click_location(x, y, (zx, zy, zw, zh))
        if click_location: game_state.zone_editing_action=click_location; game_state.drag_start_pos=(x,y); game_state.original_zone_on_drag_start=current_zone; handled=True
    elif event == cv2.EVENT_MOUSEMOVE:
        if game_state.drag_start_pos and game_state.zone_editing_action:
            drag_x_start, drag_y_start = game_state.drag_start_pos; dx=x-drag_x_start; dy=y-drag_y_start
            new_x, new_y, new_w, new_h = zx, zy, zw, zh; action=game_state.zone_editing_action
            if action=="move": new_x=zx+dx; new_y=zy+dy
            elif action=="resize_tl": new_x=zx+dx; new_y=zy+dy; new_w=zw-dx; new_h=zh-dy
            elif action=="resize_tr": new_y=zy+dy; new_w=zw+dx; new_h=zh-dy
            elif action=="resize_bl": new_x=zx+dx; new_w=zw-dx; new_h=zh+dy
            elif action=="resize_br": new_w=zw+dx; new_h=zh+dy
            if action.startswith("resize"):
                new_w=max(min_size,new_w); new_h=max(min_size,new_h)
                if action=="resize_tl": new_x=zx+zw-new_w; new_y=zy+zh-new_h
                elif action=="resize_tr": new_y=zy+zh-new_h
                elif action=="resize_bl": new_x=zx+zw-new_w
            game_state.scoring_zones[zone_idx]=(new_x,new_y,new_w,new_h,zp); game_state.drag_start_pos=(x,y); handled=True
    elif event == cv2.EVENT_LBUTTONUP:
        if game_state.drag_start_pos and game_state.zone_editing_action:
            final_zone=game_state.scoring_zones[zone_idx]; fx,fy,fw,fh,fp=final_zone
            if fw<min_size or fh<min_size:
                show_notification(game_state,"Zone too small! Reverted.",is_error=True,duration=3.0) # Use helper
                if game_state.original_zone_on_drag_start: game_state.scoring_zones[zone_idx]=game_state.original_zone_on_drag_start
            else:
                other_zones=[z for i,z in enumerate(game_state.scoring_zones) if i!=zone_idx]
                if _zones_overlap(final_zone[:4], other_zones):
                    show_notification(game_state,"Edit causes overlap! Reverted.",is_error=True,duration=3.0) # Use helper
                    if game_state.original_zone_on_drag_start: game_state.scoring_zones[zone_idx]=game_state.original_zone_on_drag_start
                else: game_state.special_hole = set_special_hole(game_state.scoring_zones) # Use helper
            game_state.zone_editing_action=None; game_state.drag_start_pos=None; game_state.original_zone_on_drag_start=None; handled=True
    return handled


# --- Drawing Event Processing ---
def _process_drawing_event(event: int, x: int, y: int, game_state: GameState) -> None:
    """Process mouse events for drawing scoring zones."""
    # (Code unchanged, uses helpers imported above)
    if event == cv2.EVENT_LBUTTONDOWN:
        if game_state.drawing: game_state.start_x, game_state.start_y=x,y; game_state.temp_zone=None; game_state.drawing_points_input=""
    elif event == cv2.EVENT_MOUSEMOVE:
        if game_state.drawing and game_state.start_x is not None and game_state.start_y is not None:
            x1=min(game_state.start_x,x); y1=min(game_state.start_y,y); w=abs(game_state.start_x-x); h=abs(game_state.start_y-y)
            game_state.temp_zone = (x1, y1, w, h)
    elif event == cv2.EVENT_LBUTTONUP:
        if game_state.drawing:
            if game_state.temp_zone:
                x1,y1,w,h=game_state.temp_zone
                if w>ScoringConstants.MIN_ZONE_SIZE and h>ScoringConstants.MIN_ZONE_SIZE:
                    points_str=game_state.drawing_points_input; points=ScoringConstants.DEFAULT_POINTS
                    try:
                        if points_str: points=int(points_str)
                        if not (1<=points<=ScoringConstants.MAX_POINTS): points=ScoringConstants.DEFAULT_POINTS; show_notification(game_state,f"Points must be 1-{ScoringConstants.MAX_POINTS}.",is_error=True,duration=3.0) # Use helper
                    except ValueError:
                        if points_str: show_notification(game_state,"Invalid points. Using default.",is_error=True,duration=3.0) # Use helper
                    new_zone=(x1,y1,w,h,points)
                    if not _zones_overlap(new_zone[:4],game_state.scoring_zones):
                        game_state.scoring_zones.append(new_zone); game_state.special_hole=set_special_hole(game_state.scoring_zones) # Use helper
                        show_notification(game_state, f"Zone Added ({points} pts)") # Use helper
                    else: show_notification(game_state,"Zone Overlaps!",is_error=True) # Use helper
                else: show_notification(game_state,"Zone too small",is_error=True) # Use helper
            game_state.drawing=False; game_state.temp_zone=None; game_state.start_x=None; game_state.start_y=None; game_state.drawing_points_input=""


# --- Helper to reset menu editing states ---
def _reset_all_menu_editing_states(game_state: GameState) -> None:
    """Resets all flags and temporary inputs related to menu editing."""
    # (Code unchanged)
    game_state.editing_zone_index=None; game_state.editing_zone_mode=None; game_state.editing_zone_points_input=None
    game_state.editing_player_index=None; game_state.editing_player_mode=None; game_state.editing_player_name_input=None
    game_state.selected_zone_for_edit=None; game_state.zone_editing_action=None; game_state.drag_start_pos=None
    game_state.original_zone_on_drag_start=None; game_state.edit_zones_current_page=1; game_state.menu_cache=None


# --- Process Menu/Game Over Click (Uses Utility Functions) ---
def _process_menu_or_gameover_click(x: int, y: int, game_state: GameState) -> bool:
    """Process clicks within the menu or game over screen, including sliders."""
    # Uses helpers imported from game_state_helpers
    # Uses utils imported from game_state_utils
    if game_state.current_state not in [CurrentGameState.MENU, CurrentGameState.GAME_OVER]: return False
    if not all(hasattr(game_state, attr) for attr in ["menu_pos", "menu_width", "menu_height"]): return False
    menu_x, menu_y = game_state.menu_pos; menu_w, menu_h = game_state.menu_width, game_state.menu_height
    if menu_w <= 0 or menu_h <= 0: return False
    # Close Button Check
    if game_state.current_state == CurrentGameState.MENU:
        pad=UIConstants.MENU_CLOSE_BUTTON_PADDING; size=UIConstants.MENU_CLOSE_BUTTON_SIZE; close_btn_x1=menu_x+menu_w-pad-size; close_btn_y1=menu_y+pad; close_btn_x2=menu_x+menu_w-pad; close_btn_y2=menu_y+pad+size
        if close_btn_x1<=x<close_btn_x2 and close_btn_y1<=y<close_btn_y2: game_state.current_state=CurrentGameState.PLAYING; game_state.submenu_active=None; _reset_all_menu_editing_states(game_state); return True
    if not (menu_x <= x < menu_x + menu_w and menu_y <= y < menu_y + menu_h): return False
    relative_x=x-menu_x; relative_y=y-menu_y
    if not hasattr(game_state,"submenu_items") or not isinstance(game_state.submenu_items, list): return False
    main_menu_actions={item[1] for item in MenuConstants.MAIN_MENU_ITEMS if isinstance(item[1],str)}; zone_submenu_actions={item[1] for item in MenuConstants.ZONE_SUBMENU_ITEMS if isinstance(item[1],str)}
    known_submenu_nav_actions = main_menu_actions.union(zone_submenu_actions) - {"resume","quit","back_to_main","back_to_manage_zones","save_zones","load_zones","clear_zones","add_zone_info"}
    volume_adjusted = False
    for item_rect, action, label in reversed(game_state.submenu_items):
        if not isinstance(item_rect, tuple) or len(item_rect)!=4: continue
        item_x, item_y, item_w, item_h = item_rect
        if (item_x <= relative_x < item_x + item_w and item_y <= relative_y < item_y + item_h):
            if isinstance(action, str):
                if action=="adjust_sound_volume": click_offset=relative_x-item_x; new_volume=max(0.0,min(1.0,click_offset/item_w)); game_state.current_sound_volume=new_volume; set_volume(game_state); save_settings(game_state); game_state.menu_cache=None; volume_adjusted=True # Uses utils
                elif action=="adjust_music_volume": click_offset=relative_x-item_x; new_volume=max(0.0,min(1.0,click_offset/item_w)); game_state.current_music_volume=new_volume; set_volume(game_state); save_settings(game_state); game_state.menu_cache=None; volume_adjusted=True # Uses utils
                elif action=="toggle_game_sounds": toggle_game_sounds(game_state); game_state.menu_cache=None; return True # Uses utils
                elif action=="toggle_background_music": toggle_background_music(game_state); game_state.menu_cache=None; return True # Uses utils
                elif not volume_adjusted:
                    if action=="quit":
                        try: save_score(game_state, game_state.get_current_player().name) # Use helper
                        except Exception as e: logger.error(f"Error saving score on quit: {e}")
                        clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state); return True
                    if game_state.current_state==CurrentGameState.MENU:
                        if action=="toggle_debug_overlay": game_state.show_debug_overlay = not game_state.show_debug_overlay; game_state.menu_cache=None
                        elif action=="toggle_debug_mode": game_state.debug_mode=not game_state.debug_mode; log_level=logging.DEBUG if game_state.debug_mode else logging.INFO; logging.getLogger().setLevel(log_level); [h.setLevel(log_level) for h in logging.getLogger().handlers]; game_state.menu_cache=None
                        elif action=="cycle_music_track": total_tracks = len(GameConstants.BACKGROUND_MUSIC_TRACKS); change_music_track(game_state, (game_state.selected_music_track_index + 1) % total_tracks) if total_tracks>0 else None; game_state.menu_cache=None # Use util
                        elif action=="show_splash": display_modal_splash(game_state, mouse_callback, game_state); game_state.menu_cache=None
                        elif action=="resume": game_state.current_state=CurrentGameState.PLAYING; game_state.submenu_active=None; _reset_all_menu_editing_states(game_state)
                        elif action=="back_to_main": _reset_all_menu_editing_states(game_state); game_state.submenu_active=None
                        elif action=="add_zone_info": show_notification(game_state,"Press 's', then click and drag"); game_state.current_state=CurrentGameState.PLAYING; game_state.submenu_active=None; _reset_all_menu_editing_states(game_state) # Use helper
                        elif action=="clear_zones": clear_zones(game_state); _reset_all_menu_editing_states(game_state) # Use helper
                        elif action=="save_zones": save_zones(game_state); game_state.menu_cache=None # Use helper
                        elif action=="load_zones": load_zones(game_state); _reset_all_menu_editing_states(game_state) # Use helper
                        elif action.startswith("set_mode_"):
                            new_mode=action.split("set_mode_")[1]; valid_modes=["classic","timed","fun","practice","survival"]
                            if new_mode in valid_modes and game_state.game_mode!=new_mode: save_score(game_state, game_state.get_current_player().name, mode=game_state.game_mode); game_state.game_mode=new_mode; reset_game(game_state); game_state.current_state=CurrentGameState.PLAYING; game_state.submenu_active=None; _reset_all_menu_editing_states(game_state) # Uses helpers/utils
                            elif game_state.game_mode==new_mode: game_state.current_state=CurrentGameState.PLAYING; game_state.submenu_active=None; _reset_all_menu_editing_states(game_state)
                        elif action.startswith("select_player_"):
                            logger.debug("Action matched: 'select_player_*'")
                            try: # Keep try block
                                index = int(action.split("select_player_")[1])
                                if 0 <= index < len(game_state.players) and index != game_state.current_player_index:
                                    save_score(game_state, game_state.get_current_player().name) # Uses helper
                                    game_state.current_player_index = index
                                    logger.info(f"Switched to player: {game_state.get_current_player().name}")
                                    reset_game(game_state) # Uses util
                                elif index == game_state.current_player_index: logger.debug("Selected current player.")
                                else: logger.warning(f"Invalid player index: {index}")
                            except Exception as e: # Add except block back
                                logger.error(f"Error processing player selection action '{action}': {e}")
                            # Reset state outside try/except
                            _reset_all_menu_editing_states(game_state)
                        elif action=="add_player":
                            if len(game_state.players)<2: game_state.players.append(Player(f"Player {len(game_state.players)+1}")); show_notification(game_state,"Player Added") # Use helper
                            else: show_notification(game_state,"Maximum 2 players",is_error=True) # Use helper
                            _reset_all_menu_editing_states(game_state)
                        elif action=="back_to_manage_zones": _reset_all_menu_editing_states(game_state); game_state.submenu_active="manage_zones"
                        elif action=="prev_edit_zone_page":
                            if game_state.edit_zones_current_page>1: game_state.edit_zones_current_page-=1; game_state.menu_cache=None
                        elif action=="next_edit_zone_page":
                            total_pages=max(1,ceil(len(game_state.scoring_zones)/game_state.edit_zones_items_per_page))
                            if game_state.edit_zones_current_page<total_pages: game_state.edit_zones_current_page+=1; game_state.menu_cache=None
                        elif action=="leaderboard_classic": game_state.leaderboard_mode="classic"; game_state.menu_cache=None
                        elif action=="leaderboard_timed": game_state.leaderboard_mode="timed"; game_state.menu_cache=None
                        elif action=="leaderboard_survival": game_state.leaderboard_mode="survival"; game_state.menu_cache=None
                        elif action.startswith("edit_zone_"):
                            logger.debug("Action matched: 'edit_zone_*' (Points)")
                            try: # Keep try block
                                index = int(action.split("edit_zone_")[1])
                                if 0 <= index < len(game_state.scoring_zones):
                                    if not (game_state.editing_zone_index==index and game_state.editing_zone_mode=="edit_points"):
                                        _reset_all_menu_editing_states(game_state)
                                        game_state.editing_zone_index=index
                                        game_state.editing_zone_mode="edit_points"
                                        game_state.editing_zone_points_input=str(game_state.scoring_zones[index][4])
                                        game_state.menu_cache=None
                                        logger.info(f"Selected zone {index+1} for points edit. Value: {game_state.scoring_zones[index][4]}")
                                else:
                                    logger.warning(f"Invalid zone index: {index}")
                                    _reset_all_menu_editing_states(game_state)
                            except Exception as e: # Add except block back
                                logger.error(f"Error processing zone points edit action '{action}': {e}")
                                _reset_all_menu_editing_states(game_state)
                        elif action.startswith("move_zone_"):
                            logger.debug("Action matched: 'move_zone_*'")
                            # --- Start CORRECTED Block ---
                            try:
                                index = int(action.split("move_zone_")[1])
                                if 0 <= index < len(game_state.scoring_zones):
                                    _reset_all_menu_editing_states(game_state)
                                    game_state.selected_zone_for_edit=index
                                    game_state.previous_state=CurrentGameState.MENU
                                    game_state.current_state=CurrentGameState.ZONE_EDITING
                                    show_notification(game_state,"Click inside zone to move, ESC cancel",duration=0) # Use helper
                                else:
                                    logger.warning(f"Invalid zone index: {index}")
                            except Exception as e: # Catch potential errors during parsing
                                logger.error(f"Error processing move zone action '{action}': {e}")
                            # --- End CORRECTED Block ---
                        elif action.startswith("resize_zone_"):
                            logger.debug("Action matched: 'resize_zone_*'")
                            # --- Start CORRECTED Block ---
                            try:
                                index = int(action.split("resize_zone_")[1])
                                if 0 <= index < len(game_state.scoring_zones):
                                    _reset_all_menu_editing_states(game_state)
                                    game_state.selected_zone_for_edit=index
                                    game_state.previous_state=CurrentGameState.MENU
                                    game_state.current_state=CurrentGameState.ZONE_EDITING
                                    show_notification(game_state,"Click corner handles to resize, ESC cancel",duration=0) # Use helper
                                else:
                                    logger.warning(f"Invalid zone index: {index}")
                            except Exception as e: # Catch potential errors during parsing
                                logger.error(f"Error processing resize zone action '{action}': {e}")
                           # --- End CORRECTED Block ---
                        elif action.startswith("edit_player_name_"):
                            # --- Start CORRECTED Block ---
                            try:
                                index = int(action.split("edit_player_name_")[1])
                                if 0 <= index < len(game_state.players):
                                    if not (game_state.editing_player_index==index and game_state.editing_player_mode=="edit_name"):
                                        _reset_all_menu_editing_states(game_state)
                                        game_state.editing_player_index=index
                                        game_state.editing_player_mode="edit_name"
                                        game_state.editing_player_name_input=str(game_state.players[index].name)
                                        game_state.menu_cache=None
                                        logger.info(f"Selected player {index+1} name edit. Value: '{game_state.players[index].name}'")
                                else:
                                    logger.warning(f"Invalid player index: {index}")
                                    _reset_all_menu_editing_states(game_state)
                            except Exception as e: # Catch potential errors during parsing
                                logger.error(f"Error processing edit player name action '{action}': {e}")
                                _reset_all_menu_editing_states(game_state)
                           # --- End CORRECTED Block ---
                        elif action.startswith("delete_zone_"):
                            # --- Start CORRECTED Block ---
                            try:
                                index = int(action.split("delete_zone_")[1])
                                if 0 <= index < len(game_state.scoring_zones):
                                    if game_state.editing_zone_index==index and game_state.editing_zone_mode=="confirm_delete":
                                        del game_state.scoring_zones[index]; game_state.special_hole=set_special_hole(game_state.scoring_zones) # Use helper
                                        show_notification(game_state,f"Zone {index+1} Deleted"); _reset_all_menu_editing_states(game_state) # Use helper
                                    else: _reset_all_menu_editing_states(game_state); game_state.editing_zone_index=index; game_state.editing_zone_mode="confirm_delete"; game_state.menu_cache=None; show_notification(game_state,f"Click Delete again for zone {index+1}",duration=4.0) # Use helper
                                else:
                                    logger.warning(f"Invalid zone index: {index}")
                                    _reset_all_menu_editing_states(game_state)
                            except Exception as e: # Catch potential errors during parsing
                                logger.error(f"Error processing delete zone action '{action}': {e}")
                                _reset_all_menu_editing_states(game_state)
                            # --- End CORRECTED Block ---
                        elif action in known_submenu_nav_actions: _reset_all_menu_editing_states(game_state); game_state.submenu_active=action
                        else: logger.warning(f"Unhandled MENU action: {action}")
                    elif game_state.current_state==CurrentGameState.GAME_OVER:
                        if action=="new_game_from_gameover": reset_game(game_state); game_state.current_state=CurrentGameState.GETTING_PLAYER_NAME; game_state.win_condition_met=False # Use util
                        elif action=="show_leaderboard_from_gameover": game_state.current_state=CurrentGameState.MENU; game_state.submenu_active="leaderboard"; game_state.win_condition_met=False; game_state.menu_cache=None
                        else: logger.warning(f"Unhandled GAME_OVER action: {action}")
                    return True
    if volume_adjusted: return True
    return False


# --- Main Mouse Callback ---
def mouse_callback(event: int, x: int, y: int, flags: int, param: Any) -> None:
    """Handle mouse events for the main application window."""
    # (Code unchanged)
    game_state: GameState = param; click_handled = False
    if game_state is None: return
    if game_state.current_state == CurrentGameState.ZONE_EDITING and event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONUP]:
        click_handled = _process_zone_editing_event(event, x, y, game_state)
        if click_handled and event != cv2.EVENT_MOUSEMOVE: return
    if not click_handled and game_state.current_state == CurrentGameState.PLAYING and getattr(game_state, "drawing", False) and event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONUP]:
        _process_drawing_event(event, x, y, game_state)
        if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP]: click_handled = True; return
    if not click_handled and game_state.current_state in [CurrentGameState.MENU, CurrentGameState.GAME_OVER] and event == cv2.EVENT_LBUTTONDOWN:
        click_handled = _process_menu_or_gameover_click(x, y, game_state)
        if click_handled: return
    if not click_handled and game_state.current_state == CurrentGameState.PLAYING and not getattr(game_state, "drawing", False) and event == cv2.EVENT_LBUTTONDOWN:
        if UIConstants.MENU_BUTTON_X <= x <= UIConstants.MENU_BUTTON_X + UIConstants.MENU_BUTTON_WIDTH and UIConstants.MENU_BUTTON_Y <= y <= UIConstants.MENU_BUTTON_Y + UIConstants.MENU_BUTTON_HEIGHT:
            game_state.current_state = CurrentGameState.MENU; game_state.submenu_active = None; _reset_all_menu_editing_states(game_state); click_handled = True; return
    # if not click_handled and event == cv2.EVENT_LBUTTONDOWN: # Log unhandled clicks
    #      if game_state.current_state not in [CurrentGameState.GETTING_PLAYER_NAME, CurrentGameState.ZONE_EDITING]: logger.debug(f"Unhandled click at ({x},{y}) in state {game_state.current_state}")