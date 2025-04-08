# utils.py

import logging
import time
from math import ceil
from typing import Any, Optional, Tuple

import cv2

# Import cleanup util
from cleanup_utils import clean_exit

# Imports needed for mouse_callback helpers
from constants import GameConstants, MenuConstants, ScoringConstants, UIConstants

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

logger = logging.getLogger(__name__)


# --- Helper: Find which handle/area of a zone is clicked ---
def _get_zone_click_location(
        x: int, y: int, zone_rect: Tuple[int, int, int, int]) -> Optional[str]:
    """Determine if a click is on a corner, edge, or inside a zone."""
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
def _process_zone_editing_event(event: int, x: int, y: int,
                                game_state: "GameState") -> bool:
    """Process mouse events during interactive zone move/resize."""
    handled = False
    zone_idx = getattr(game_state, "selected_zone_for_edit", None)

    if zone_idx is None or not (0 <= zone_idx < len(
            getattr(game_state, "scoring_zones", []))):
        if game_state.current_state == CurrentGameState.ZONE_EDITING:
            logger.warning(
                "Zone editing event processed with invalid/no selected zone index. Reverting state."
            )
        if hasattr(game_state, "current_state"):
            try:
                prev_state = getattr(game_state, "previous_state", None)
                game_state.current_state = (prev_state if prev_state else
                                            CurrentGameState.MENU)
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
                game_state, "zone_editing_action", None):
            drag_x_start, drag_y_start = game_state.drag_start_pos
            dx, dy = x - drag_x_start, y - drag_y_start
            new_x, new_y, new_w, new_h = zx, zy, zw, zh
            action = game_state.zone_editing_action
            orig_zone = getattr(game_state, "original_zone_on_drag_start",
                                None)
            if not orig_zone:
                logger.error(
                    "Original zone state missing during drag move/resize.")
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

            game_state.scoring_zones[zone_idx] = (new_x, new_y, new_w, new_h,
                                                  zp)
            handled = True

    elif event == cv2.EVENT_LBUTTONUP:
        if getattr(game_state, "drag_start_pos", None) and getattr(
                game_state, "zone_editing_action", None):
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
                    z for i, z in enumerate(game_state.scoring_zones)
                    if i != zone_idx
                ]
                if _zones_overlap(final_zone[:4], other_zones):
                    error_message = "Edit causes overlap! Reverted."
                    valid_edit = False

            if not valid_edit:
                show_notification(game_state,
                                  error_message,
                                  is_error=True,
                                  duration=3.0)
                if game_state.original_zone_on_drag_start:
                    game_state.scoring_zones[zone_idx] = (
                        game_state.original_zone_on_drag_start)
                else:
                    logger.error(
                        "Cannot revert zone edit, original state was None.")
            else:
                game_state.special_hole = set_special_hole(
                    game_state.scoring_zones)
                show_notification(game_state,
                                  f"Zone {zone_idx+1} updated",
                                  duration=1.5)

            game_state.zone_editing_action = None
            game_state.drag_start_pos = None
            game_state.original_zone_on_drag_start = None
            handled = True
    return handled


# --- Drawing Event Processing ---
def _process_drawing_event(event: int, x: int, y: int,
                           game_state: "GameState") -> None:
    """Process mouse events for drawing scoring zones."""
    if event == cv2.EVENT_LBUTTONDOWN:
        if game_state.drawing:
            game_state.start_x, game_state.start_y = x, y
            game_state.temp_zone = None
            game_state.drawing_points_input = ""
            logger.debug(f"Drawing started at ({x}, {y})")

    elif event == cv2.EVENT_MOUSEMOVE:
        if (game_state.drawing and game_state.start_x is not None
                and game_state.start_y is not None):
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
                            max_pts = getattr(ScoringConstants, "MAX_POINTS",
                                              999)
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
                            new_zone[:4],
                            getattr(game_state, "scoring_zones", [])):
                        game_state.scoring_zones.append(new_zone)
                        game_state.special_hole = set_special_hole(
                            game_state.scoring_zones)
                        show_notification(game_state,
                                          f"Zone Added ({points} pts)")
                        logger.info(f"Added zone: {new_zone}")
                    else:
                        show_notification(game_state,
                                          "Zone Overlaps! Not Added.",
                                          is_error=True)
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
    """Resets all flags and temporary inputs related to menu editing."""
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


# --- Process Menu/Game Over/CONFIRM_QUIT Click ---
def _process_menu_or_modal_click(x: int, y: int,
                                 game_state: "GameState") -> bool:
    """Process clicks within the menu, game over screen, or confirmation dialog."""
    current_state = getattr(game_state, "current_state", None)
    if current_state not in [
            CurrentGameState.MENU,
            CurrentGameState.GAME_OVER,
            CurrentGameState.CONFIRM_QUIT,
    ]:
        return False
    required_attrs = ["menu_pos", "menu_width", "menu_height", "submenu_items"]
    if not all(hasattr(game_state, attr) for attr in required_attrs):
        logger.warning(
            "UI attributes missing in game_state for menu/modal click processing."
        )
        return False

    menu_x, menu_y = game_state.menu_pos
    relative_x, relative_y = x - menu_x, y - menu_y
    menu_w, menu_h = game_state.menu_width, game_state.menu_height

    if current_state == CurrentGameState.MENU:
        pad = getattr(UIConstants, "MENU_CLOSE_BUTTON_PADDING", 10)
        size = getattr(UIConstants, "MENU_CLOSE_BUTTON_SIZE", 40)
        close_btn_rel_x1, close_btn_rel_y1 = menu_w - pad - size, pad
        close_btn_rel_x2, close_btn_rel_y2 = menu_w - pad, pad + size
        if (close_btn_rel_x1 <= relative_x < close_btn_rel_x2
                and close_btn_rel_y1 <= relative_y < close_btn_rel_y2):
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
    if not isinstance(submenu_items_list, list):
        logger.error("game_state.submenu_items is not a list.")
        return False
    volume_adjusted = False

    for item_data in reversed(submenu_items_list):
        if not isinstance(item_data, tuple) or len(item_data) < 2:
            continue
        item_rect_orig, action = item_data[0], item_data[1]
        if not isinstance(item_rect_orig, tuple) or len(item_rect_orig) != 4:
            continue
        item_x, item_y, item_w, item_h = item_rect_orig

        if current_state != CurrentGameState.CONFIRM_QUIT:
            item_rect_abs = (item_x + menu_x, item_y + menu_y, item_w, item_h)
            click_x_to_check, click_y_to_check = x, y
        else:
            item_rect_abs = item_rect_orig
            click_x_to_check, click_y_to_check = x, y

        abs_item_x, abs_item_y, abs_item_w, abs_item_h = item_rect_abs
        if (abs_item_x <= click_x_to_check < abs_item_x + abs_item_w
                and abs_item_y <= click_y_to_check < abs_item_y + abs_item_h):
            logger.debug(
                f"Click detected on item with action: {action} at rect {item_rect_abs}"
            )
            if isinstance(action, str):
                if current_state == CurrentGameState.MENU:
                    rel_click_x_in_item = click_x_to_check - (abs_item_x)
                    if action == "adjust_sound_volume":
                        new_volume = max(
                            0.0,
                            min(
                                1.0,
                                (rel_click_x_in_item /
                                 abs_item_w if abs_item_w > 0 else 0.0),
                            ),
                        )
                        if (abs(
                                getattr(game_state, "current_sound_volume", 0)
                                - new_volume) > 0.01):
                            game_state.current_sound_volume = new_volume
                            set_volume(game_state)
                            save_settings(game_state)
                            game_state.menu_cache = None
                            volume_adjusted = True
                            logger.debug(
                                f"Adjusted sound volume to {new_volume:.2f}")
                        return True
                    elif action == "adjust_music_volume":
                        new_volume = max(
                            0.0,
                            min(
                                1.0,
                                (rel_click_x_in_item /
                                 abs_item_w if abs_item_w > 0 else 0.0),
                            ),
                        )
                        if (abs(
                                getattr(game_state, "current_music_volume", 0)
                                - new_volume) > 0.01):
                            game_state.current_music_volume = new_volume
                            set_volume(game_state)
                            save_settings(game_state)
                            game_state.menu_cache = None
                            volume_adjusted = True
                            logger.debug(
                                f"Adjusted music volume to {new_volume:.2f}")
                        return True

                if current_state == CurrentGameState.CONFIRM_QUIT:
                    if action == "confirm_quit_yes":
                        logger.info("Quit confirmed via 'Yes' button click.")
                        game_state.click_feedback_state = (item_rect_abs,
                                                           time.time())
                        cap = getattr(game_state, "cap", None)
                        music = getattr(game_state, "background_music", None)
                        music_on = getattr(game_state, "background_music_on",
                                           False)
                        clean_exit(cap, music, music_on, game_state)
                        return True
                    elif action == "confirm_quit_no":
                        logger.debug("Quit cancelled via 'No' button click.")
                        game_state.click_feedback_state = (item_rect_abs,
                                                           time.time())
                        prev_state = getattr(
                            game_state,
                            "previous_state_before_quit_confirm",
                            CurrentGameState.PLAYING,
                        )
                        game_state.current_state = prev_state
                        game_state.previous_state_before_quit_confirm = None
                        game_state.submenu_items = []
                        if prev_state == CurrentGameState.MENU:
                            game_state.menu_cache = None
                        return True

                if not volume_adjusted:
                    game_state.click_feedback_state = (item_rect_abs,
                                                       time.time())
                    known_submenu_nav_actions = {
                        item[1]
                        for item in MenuConstants.MAIN_MENU_ITEMS
                        if isinstance(item[1], str)
                    }
                    known_submenu_nav_actions.update({
                        item[1]
                        for item in MenuConstants.ZONE_SUBMENU_ITEMS
                        if isinstance(item[1], str)
                    })
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
                        if action == "quit":
                            logger.debug(
                                "Menu 'Quit Game' action triggered...")
                            game_state.previous_state_before_quit_confirm = (
                                CurrentGameState.MENU)
                            game_state.current_state = CurrentGameState.CONFIRM_QUIT
                            _reset_all_menu_editing_states(game_state)
                        elif action == "toggle_game_sounds":
                            toggle_game_sounds(game_state)
                            game_state.menu_cache = None
                        elif action == "toggle_background_music":
                            toggle_background_music(game_state)
                            game_state.menu_cache = None
                        elif action == "toggle_debug_overlay":
                            game_state.show_debug_overlay = not getattr(
                                game_state, "show_debug_overlay", False)
                            show_notification(
                                game_state,
                                f"Debug Overlay: {'ON' if game_state.show_debug_overlay else 'OFF'}",
                            )
                            game_state.menu_cache = None
                        elif action == "toggle_debug_mode":
                            game_state.debug_mode = not getattr(
                                game_state, "debug_mode", False)
                            log_level = (logging.DEBUG if game_state.debug_mode
                                         else logging.INFO)
                            logging.getLogger().setLevel(log_level)
                            [
                                h.setLevel(log_level)
                                for h in logging.getLogger().handlers
                            ]
                            show_notification(
                                game_state,
                                f"Debug Mode: {'ON' if game_state.debug_mode else 'OFF'}",
                            )
                            game_state.menu_cache = None
                        elif action == "cycle_music_track":
                            available_tracks = getattr(
                                GameConstants, "BACKGROUND_MUSIC_TRACKS", [])
                            if available_tracks:
                                change_music_track(
                                    game_state,
                                    (getattr(game_state,
                                             "selected_music_track_index", 0) +
                                     1) % len(available_tracks),
                                )
                            game_state.menu_cache = None
                        elif action == "show_splash":
                            display_modal_splash(game_state, mouse_callback,
                                                 game_state)
                            game_state.menu_cache = None
                        elif action == "resume":
                            game_state.current_state = CurrentGameState.PLAYING
                            game_state.submenu_active = None
                            _reset_all_menu_editing_states(game_state)
                        elif action == "back_to_main":
                            _reset_all_menu_editing_states(game_state)
                            game_state.submenu_active = None
                        elif action == "add_zone_info":
                            show_notification(
                                game_state,
                                "Press 's', then click and drag to draw zone",
                            )
                            game_state.current_state = CurrentGameState.PLAYING
                            game_state.submenu_active = None
                            _reset_all_menu_editing_states(game_state)
                        elif action == "clear_zones":
                            clear_zones(game_state)
                            _reset_all_menu_editing_states(game_state)
                        elif action == "save_zones":
                            save_zones(game_state)
                            game_state.menu_cache = None
                        elif action == "load_zones":
                            load_zones(game_state)
                            _reset_all_menu_editing_states(game_state)
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
                            if new_mode in valid_modes:
                                if (getattr(game_state, "game_mode", "classic")
                                        != new_mode):
                                    try:
                                        player_name = (
                                            game_state.get_current_player(
                                            ).name)
                                        save_score(
                                            game_state,
                                            player_name,
                                            mode=game_state.game_mode,
                                        )
                                    except Exception as e:
                                        logger.error(
                                            f"Error saving score before mode change: {e}"
                                        )
                                    game_state.game_mode = new_mode
                                    reset_game(game_state)
                                    show_notification(
                                        game_state,
                                        f"Mode set to: {new_mode.capitalize()}",
                                    )
                                game_state.current_state = CurrentGameState.PLAYING
                                game_state.submenu_active = None
                                _reset_all_menu_editing_states(game_state)
                        elif action.startswith("select_player_"):
                            try:
                                index = int(action.split("select_player_")[-1])
                                if 0 <= index < len(
                                        getattr(game_state, "players", [])):
                                    if index != getattr(
                                            game_state, "current_player_index",
                                            0):
                                        try:
                                            player_name = (
                                                game_state.get_current_player(
                                                ).name)
                                            save_score(game_state, player_name)
                                        except Exception as e:
                                            logger.error(
                                                f"Error saving score before player switch: {e}"
                                            )
                                        game_state.current_player_index = index
                                        logger.info(
                                            f"Switched to player: {game_state.get_current_player().name}"
                                        )
                                        reset_game(game_state)
                                    _reset_all_menu_editing_states(game_state)
                                else:
                                    logger.warning(
                                        f"Invalid player index {index} from action '{action}'"
                                    )
                            except Exception as e:
                                logger.error(
                                    f"Error processing select_player action '{action}': {e}"
                                )
                        elif action == "add_player":
                            if len(getattr(game_state, "players", [])) < 2:
                                game_state.players.append(
                                    Player(
                                        f"Player {len(game_state.players) + 1}"
                                    ))
                                show_notification(game_state, "Player Added")
                            else:
                                show_notification(game_state,
                                                  "Maximum players reached",
                                                  is_error=True)
                            _reset_all_menu_editing_states(game_state)
                        elif action == "back_to_manage_zones":
                            _reset_all_menu_editing_states(game_state)
                            game_state.submenu_active = "manage_zones"
                        elif action == "prev_edit_zone_page":
                            if getattr(game_state, "edit_zones_current_page",
                                       1) > 1:
                                game_state.edit_zones_current_page -= 1
                                game_state.menu_cache = None
                        elif action == "next_edit_zone_page":
                            total_pages = max(
                                1,
                                ceil(
                                    len(
                                        getattr(game_state, "scoring_zones",
                                                [])) /
                                    getattr(game_state,
                                            "edit_zones_items_per_page", 8)),
                            )
                            if (getattr(game_state, "edit_zones_current_page",
                                        1) < total_pages):
                                game_state.edit_zones_current_page += 1
                                game_state.menu_cache = None
                        elif action == "leaderboard_classic":
                            game_state.leaderboard_mode = "classic"
                            game_state.menu_cache = None
                        elif action == "leaderboard_timed":
                            game_state.leaderboard_mode = "timed"
                            game_state.menu_cache = None
                        elif action == "leaderboard_survival":
                            game_state.leaderboard_mode = "survival"
                            game_state.menu_cache = None
                        elif action.startswith("edit_zone_"):
                            try:
                                index = int(action.split("edit_zone_")[-1])
                                if (0 <= index < len(
                                        getattr(game_state, "scoring_zones",
                                                []))):
                                    if not (getattr(game_state,
                                                    "editing_zone_index", None)
                                            == index and getattr(
                                                game_state,
                                                "editing_zone_mode", None)
                                            == "edit_points"):
                                        _reset_all_menu_editing_states(
                                            game_state)
                                        game_state.editing_zone_index = index
                                        game_state.editing_zone_mode = "edit_points"
                                        game_state.editing_zone_points_input = str(
                                            game_state.scoring_zones[index][4])
                                        game_state.menu_cache = None
                                        logger.info(
                                            f"Started editing points for zone {index+1}"
                                        )
                                else:
                                    logger.warning(
                                        f"Invalid zone index {index} for edit action '{action}'"
                                    )
                            except Exception as e:
                                logger.error(
                                    f"Error processing edit_zone action '{action}': {e}"
                                )
                        elif action.startswith("move_zone_"):
                            try:
                                index = int(action.split("move_zone_")[-1])
                                if (0 <= index < len(
                                        getattr(game_state, "scoring_zones",
                                                []))):
                                    _reset_all_menu_editing_states(game_state)
                                    game_state.selected_zone_for_edit = index
                                    game_state.previous_state = CurrentGameState.MENU
                                    game_state.current_state = (
                                        CurrentGameState.ZONE_EDITING)
                                    show_notification(
                                        game_state,
                                        "Click inside zone to move, drag. ESC=Cancel.",
                                        duration=0,
                                    )
                                else:
                                    logger.warning(
                                        f"Invalid zone index {index} for move action '{action}'"
                                    )
                            except Exception as e:
                                logger.error(
                                    f"Error processing move_zone action '{action}': {e}"
                                )
                        elif action.startswith("resize_zone_"):
                            try:
                                index = int(action.split("resize_zone_")[-1])
                                if (0 <= index < len(
                                        getattr(game_state, "scoring_zones",
                                                []))):
                                    _reset_all_menu_editing_states(game_state)
                                    game_state.selected_zone_for_edit = index
                                    game_state.previous_state = CurrentGameState.MENU
                                    game_state.current_state = (
                                        CurrentGameState.ZONE_EDITING)
                                    show_notification(
                                        game_state,
                                        "Click & drag corner handles. ESC=Cancel.",
                                        duration=0,
                                    )
                                else:
                                    logger.warning(
                                        f"Invalid zone index {index} for resize action '{action}'"
                                    )
                            except Exception as e:
                                logger.error(
                                    f"Error processing resize_zone action '{action}': {e}"
                                )
                        elif action.startswith("edit_player_name_"):
                            try:
                                index = int(
                                    action.split("edit_player_name_")[-1])
                                if 0 <= index < len(
                                        getattr(game_state, "players", [])):
                                    if not (getattr(
                                            game_state, "editing_player_index",
                                            None) == index and getattr(
                                                game_state,
                                                "editing_player_mode", None)
                                            == "edit_name"):
                                        _reset_all_menu_editing_states(
                                            game_state)
                                        game_state.editing_player_index = index
                                        game_state.editing_player_mode = "edit_name"
                                        game_state.editing_player_name_input = str(
                                            game_state.players[index].name)
                                        game_state.menu_cache = None
                                        logger.info(
                                            f"Started editing name for player {index+1}"
                                        )
                                else:
                                    logger.warning(
                                        f"Invalid player index {index} for edit name action '{action}'"
                                    )
                            except Exception as e:
                                logger.error(
                                    f"Error processing edit_player_name action '{action}': {e}"
                                )
                        elif action.startswith("delete_zone_"):
                            try:
                                index = int(action.split("delete_zone_")[-1])
                                if (0 <= index < len(
                                        getattr(game_state, "scoring_zones",
                                                []))):
                                    # --- Corrected Indentation Block Start ---
                                    if (getattr(game_state,
                                                "editing_zone_index", None)
                                            == index and getattr(
                                                game_state,
                                                "editing_zone_mode", None)
                                            == "confirm_delete"):
                                        logger.info(
                                            f"Confirmed deleting zone {index+1}"
                                        )
                                        del game_state.scoring_zones[index]
                                        game_state.special_hole = set_special_hole(
                                            game_state.scoring_zones)
                                        show_notification(
                                            game_state,
                                            f"Zone {index+1} Deleted")
                                        _reset_all_menu_editing_states(
                                            game_state
                                        )  # Resets mode, index, cache
                                    else:  # Otherwise, enter confirm delete mode
                                        _reset_all_menu_editing_states(
                                            game_state)
                                        game_state.editing_zone_index = index
                                        game_state.editing_zone_mode = "confirm_delete"
                                        game_state.menu_cache = None  # Force redraw to show confirmation state
                                        # This line's indentation is now fixed:
                                        show_notification(
                                            game_state,
                                            f"Click Delete again for zone {index+1} to confirm",
                                            duration=4.0,
                                        )
                                    # --- Corrected Indentation Block End ---
                                else:
                                    logger.warning(
                                        f"Invalid zone index {index} for delete action '{action}'"
                                    )
                                    _reset_all_menu_editing_states(game_state)
                            except Exception as e:
                                logger.error(
                                    f"Error processing delete_zone action '{action}': {e}"
                                )
                                _reset_all_menu_editing_states(game_state)

                        elif action in known_submenu_nav_actions:
                            _reset_all_menu_editing_states(game_state)
                            game_state.submenu_active = action
                        else:
                            logger.warning(
                                f"Unhandled MENU action string: {action}")

                    elif current_state == CurrentGameState.GAME_OVER:
                        if action == "new_game_from_gameover":
                            reset_game(game_state)
                            game_state.current_state = (
                                CurrentGameState.GETTING_PLAYER_NAME)
                            game_state.win_condition_met = False
                        elif action == "show_leaderboard_from_gameover":
                            game_state.current_state = CurrentGameState.MENU
                            game_state.submenu_active = "leaderboard"
                            game_state.win_condition_met = False
                            game_state.menu_cache = None
                        else:
                            logger.warning(
                                f"Unhandled GAME_OVER action string: {action}")
                    return True
            if volume_adjusted:
                return True
    return False


# --- Main Mouse Callback ---
def mouse_callback(event: int, x: int, y: int, flags: int, param: Any) -> None:
    """Handle mouse events for the main application window."""
    if not isinstance(param, object) or not hasattr(param, "current_state"):
        logger.error("Mouse callback invoked with invalid 'param'.")
        return
    game_state: "GameState" = param
    click_handled = False

    # Order of Processing Click Events:
    # 1. Zone Editing (if active)
    # 2. Zone Drawing (if active)
    # 3. Menu/Modal Clicks (Menu, Game Over, Confirm Quit)
    # 4. Heatmap Button Click (If Menu/Paused)
    # 5. Main Menu Button Click (If Playing)

    # 1. Interactive Zone Editing
    if game_state.current_state == CurrentGameState.ZONE_EDITING and event in [
            cv2.EVENT_LBUTTONDOWN,
            cv2.EVENT_MOUSEMOVE,
            cv2.EVENT_LBUTTONUP,
    ]:
        click_handled = _process_zone_editing_event(event, x, y, game_state)
        if click_handled and event != cv2.EVENT_MOUSEMOVE:
            logger.debug(f"Zone editing event {event} handled.")
            return

    # 2. Zone Drawing
    if (not click_handled
            and game_state.current_state == CurrentGameState.PLAYING
            and getattr(game_state, "drawing", False) and event in [
                cv2.EVENT_LBUTTONDOWN, cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONUP
            ]):
        _process_drawing_event(event, x, y, game_state)
        if event in [cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP]:
            logger.debug(f"Zone drawing event {event} handled.")
            click_handled = True
            return

    # 3. Menu Items / Modal Dialog Buttons
    if (not click_handled and game_state.current_state in [
            CurrentGameState.MENU,
            CurrentGameState.GAME_OVER,
            CurrentGameState.CONFIRM_QUIT,
    ] and event == cv2.EVENT_LBUTTONDOWN):
        click_handled = _process_menu_or_modal_click(x, y, game_state)
        if click_handled:
            logger.debug(
                f"Menu/Modal item click handled in state {game_state.current_state}."
            )
            return

    # 4. "Show Heatmap" Button Click
    if (not click_handled and game_state.current_state
            in [CurrentGameState.MENU, CurrentGameState.PAUSED]
            and event == cv2.EVENT_LBUTTONDOWN):
        # Calculate heatmap button position (must match ui.py)
        menu_x, menu_y = getattr(game_state, "menu_pos", (0, 0))
        menu_w = getattr(game_state, "menu_width", 600)
        menu_h = getattr(game_state, "menu_height", 450)
        panel_width = 350
        stats_content_height = 230
        button_height = 35
        panel_padding_bottom = 15
        total_content_height = (stats_content_height + button_height +
                                panel_padding_bottom)
        panel_height = max(total_content_height + 40, menu_h)
        padding = 20
        panel_x = menu_x + menu_w + padding
        panel_y = menu_y
        if panel_x + panel_width > UIConstants.WINDOW_WIDTH - padding:
            panel_x = menu_x - panel_width - padding
        if panel_x < padding:
            panel_x = (UIConstants.WINDOW_WIDTH - panel_width) // 2
            panel_y = menu_y + menu_h + padding
            panel_height = total_content_height + 40
        panel_x = max(
            padding,
            min(panel_x, UIConstants.WINDOW_WIDTH - panel_width - padding))
        panel_y = max(
            padding,
            min(panel_y, UIConstants.WINDOW_HEIGHT - panel_height - padding))
        text_x_offset = 15
        button_y_pos = panel_y + panel_height - button_height - panel_padding_bottom
        button_x_pos = panel_x + text_x_offset
        button_width = panel_width - (2 * text_x_offset)
        heatmap_button_rect = (button_x_pos, button_y_pos, button_width,
                               button_height)

        bx, by, bw, bh = heatmap_button_rect
        if bx <= x < bx + bw and by <= y < by + bh:
            logger.info("Show Heatmap button clicked.")
            game_state.click_feedback_state = (heatmap_button_rect,
                                               time.time())
            try:
                # Call the imported function directly
                display_heatmap_modal(game_state, mouse_callback, game_state)
            except Exception as e:
                # Catch potential errors during modal display
                logger.exception(
                    f"Error occurred when trying to display heatmap: {e}")
                if hasattr(game_state, "notification_text"):
                    show_notification(game_state,
                                      "Error displaying heatmap",
                                      is_error=True)
            click_handled = True
            return  # Click handled

    # 5. Main "Menu" Button Click
    if (not click_handled
            and game_state.current_state == CurrentGameState.PLAYING
            and not getattr(game_state, "drawing", False)
            and event == cv2.EVENT_LBUTTONDOWN):
        menu_button_rect = (
            getattr(UIConstants, "MENU_BUTTON_X", 10),
            getattr(UIConstants, "MENU_BUTTON_Y", 80),
            getattr(UIConstants, "MENU_BUTTON_WIDTH", 100),
            getattr(UIConstants, "MENU_BUTTON_HEIGHT", 40),
        )
        mbx, mby, mbw, mbh = menu_button_rect
        if mbx <= x < mbx + mbw and mby <= y < mby + mbh:
            logger.debug("Main Menu button clicked.")
            game_state.click_feedback_state = (menu_button_rect, time.time())
            game_state.current_state = CurrentGameState.MENU
            game_state.submenu_active = None
            _reset_all_menu_editing_states(game_state)
            click_handled = True
            return
