# interaction_utils.py

import logging
import time
import traceback
from typing import Dict, Optional, Tuple, Callable, TYPE_CHECKING
import os
import cv2
import requests
import sys
import subprocess

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
if TYPE_CHECKING:
    from game_state import GameState
    from utils import mouse_callback

# Import the necessary utility functions from CORRECT locations
from game_state_helpers import (
    clear_zones,
    save_zones,
    load_zones,
    save_score,
    set_special_hole,
    show_notification,
)

from game_state_utils import (
    reset_game,
    change_music_track,
    save_settings,
    set_volume,
    toggle_background_music,
    toggle_debug_mode,
    toggle_colorblind_mode,
    toggle_game_sounds,
    load_achievements,
)
from game_types import CurrentGameState

# Import submenu draw functions
import submenu_draw_functions
from submenus import _draw_game_mode_submenu, _draw_zone_submenu, _draw_layout_submenu

# Import Player class
from player import Player

# Import overlap check function from scoring
from scoring import _zones_overlap

# Import UI screens/modals
from ui_screens import display_modal_splash, display_heatmap_modal

# Import Google Drive and YouTube utils
import google_drive_utils
import youtube_utils

logger = logging.getLogger(__name__)

# Define submenu mapping for menu navigation
submenu_draw_functions_map = {
    "players": submenu_draw_functions._draw_players_submenu,
    "settings": submenu_draw_functions._draw_settings_submenu,
    "help": submenu_draw_functions._draw_help_submenu,
    "faq": submenu_draw_functions._draw_faq_submenu,
    "about": submenu_draw_functions._draw_about_submenu,
    "achievements": submenu_draw_functions._draw_achievements_submenu,
    "leaderboard": submenu_draw_functions._draw_leaderboard_submenu,
    "game_mode": _draw_game_mode_submenu,
    "layout": _draw_layout_submenu,
    "manage_zones": _draw_zone_submenu,
    "edit_zones": submenu_draw_functions._draw_edit_zones_submenu,
    "replays": submenu_draw_functions._draw_replays_submenu,
    "view_replays": submenu_draw_functions._draw_replay_browser_submenu,
    "replay_playback": submenu_draw_functions._draw_replay_playback_submenu,
    "replay_share": submenu_draw_functions._draw_replay_share_submenu,
}

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
                        game_state.last_player_name = "Player 1"
                        save_settings(game_state)
                        game_state.player_name_input_active = False
                        game_state.current_state = CurrentGameState.GETTING_PLAYFIELD
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
        cv2.EVENT_LBUTTONDOWN: username_input_handler,
        cv2.EVENT_MOUSEMOVE: lambda e, x, y, g: False  # Silently ignore mouse move events
    }
    # Register playfield selection handler (keyboard-only for now)
    handlers[CurrentGameState.GETTING_PLAYFIELD] = {
        cv2.EVENT_LBUTTONDOWN: lambda e, x, y, g: False,
        cv2.EVENT_MOUSEMOVE: lambda e, x, y, g: False,
    }

    return handlers


# Get the handlers once at module init time
EVENT_HANDLERS = _get_mouse_event_handlers()


# --- Helper: Reset score after zone edit so scoring stays accurate ---
def _reset_score_after_zone_edit(game_state: "GameState") -> None:
    """Reset game and current player score after zones are moved/resized."""
    game_state.score = 0
    game_state.final_score = 0
    if hasattr(game_state, "get_current_player"):
        try:
            player = game_state.get_current_player()
            if player is not None and hasattr(player, "score"):
                player.score = 0
        except Exception as e:
            logger.debug(f"Could not reset player score after zone edit: {e}")


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
    zones = getattr(game_state, "scoring_zones", [])
    move_all = getattr(game_state, "move_all_zones", False)

    # --- Move All Zones: click anywhere to start drag, same delta applied to every zone ---
    if move_all and zones:
        if is_dragging:
            event = cv2.EVENT_MOUSEMOVE
        if event == cv2.EVENT_LBUTTONDOWN:
            game_state.zone_editing_action = "move"
            game_state.drag_start_pos = (x, y)
            game_state.original_zones_on_drag_start = [tuple(z) for z in zones]
            logger.debug("Move-all zones: drag started.")
            return True
        if event == cv2.EVENT_MOUSEMOVE:
            if getattr(game_state, "drag_start_pos", None) and getattr(
                game_state, "original_zones_on_drag_start", None
            ):
                drag_x_start, drag_y_start = game_state.drag_start_pos
                dx, dy = x - drag_x_start, y - drag_y_start
                orig_list = game_state.original_zones_on_drag_start
                for i, (ox, oy, ow, oh, op) in enumerate(orig_list):
                    game_state.scoring_zones[i] = (ox + dx, oy + dy, ow, oh, op)
                return True
        if event == cv2.EVENT_LBUTTONUP:
            if getattr(game_state, "drag_start_pos", None) and getattr(
                game_state, "original_zones_on_drag_start", None
            ):
                min_size = getattr(ScoringConstants, "MIN_ZONE_SIZE", 10)
                valid = True
                for z in game_state.scoring_zones:
                    if z[2] < min_size or z[3] < min_size:
                        valid = False
                        break
                if valid:
                    for i, z in enumerate(game_state.scoring_zones):
                        others = [
                            game_state.scoring_zones[j]
                            for j in range(len(game_state.scoring_zones))
                            if j != i
                        ]
                        if _zones_overlap(z[:4], others):
                            valid = False
                            break
                if not valid:
                    show_notification(
                        game_state,
                        "Move causes overlap or invalid size. Reverted.",
                        is_error=True,
                        duration=3.0,
                    )
                    game_state.scoring_zones[:] = list(game_state.original_zones_on_drag_start)
                else:
                    if hasattr(game_state, "is_fivestar_playfield") and game_state.is_fivestar_playfield():
                        game_state.special_hole = None
                    else:
                        game_state.special_hole = set_special_hole(game_state.scoring_zones)
                    show_notification(game_state, "All zones moved", duration=1.5)
                    _reset_score_after_zone_edit(game_state)
                game_state.zone_editing_action = None
                game_state.drag_start_pos = None
                game_state.original_zones_on_drag_start = None
                return True
        return False

    zone_idx = getattr(game_state, "selected_zone_for_edit", None)
    if zone_idx is None or not (0 <= zone_idx < len(zones)):
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
                if hasattr(game_state, "is_fivestar_playfield"):
                    is_fivestar = game_state.is_fivestar_playfield()
                else:
                    is_fivestar = (
                        getattr(game_state, "playfield_type", "whiffle") == "fivestar"
                    )
                if is_fivestar:
                    game_state.special_hole = None
                else:
                    game_state.special_hole = set_special_hole(game_state.scoring_zones)
                show_notification(
                    game_state, f"Zone {zone_idx+1} updated", duration=1.5
                )
                _reset_score_after_zone_edit(game_state)
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
                        if hasattr(game_state, "is_fivestar_playfield"):
                            is_fivestar = game_state.is_fivestar_playfield()
                        else:
                            is_fivestar = (
                                getattr(game_state, "playfield_type", "whiffle")
                                == "fivestar"
                            )
                        if is_fivestar:
                            game_state.special_hole = None
                        else:
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
        "move_all_zones": False,
        "original_zones_on_drag_start": None,
        "confirm_clear_zones": False,
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

    # Ensure button rects exist (fallback if UI didn't populate them)
    if not game_state.game_over_buttons:
        try:
            current_width, current_height = game_state.get_current_resolution_dimensions()
            button_width, button_height, button_spacing = (200, 50, 30)
            button_y = current_height - int(0.1 * current_height) - button_height
            total_button_width = button_width * 3 + button_spacing * 2
            start_x = (current_width - total_button_width) // 2
            play_again_rect = (start_x, button_y, button_width, button_height)
            menu_rect = (
                start_x + button_width + button_spacing,
                button_y,
                button_width,
                button_height,
            )
            heatmap_rect = (
                start_x + (button_width + button_spacing) * 2,
                button_y,
                button_width,
                button_height,
            )
            game_state.game_over_buttons = {
                "play_again": play_again_rect,
                "main_menu": menu_rect,
                "heatmap": heatmap_rect,
            }
            logger.debug("Game over button rects rebuilt for click handling.")
        except Exception as e:
            logger.error(f"Failed to rebuild game over button rects: {e}")
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
            # Upload pending scores (screenshot + score) to leaderboard before starting new game
            if hasattr(game_state, "leaderboard") and game_state.leaderboard:
                if hasattr(game_state.leaderboard, "flush_pending_scores"):
                    try:
                        n = game_state.leaderboard.flush_pending_scores()
                        if n > 0:
                            show_notification(
                                game_state, "Score submitted to leaderboard", duration=2.0
                            )
                    except Exception as e:
                        logger.error(f"Error flushing leaderboard on Play Again: {e}")
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
def _process_menu_or_modal_click(
    x: int, y: int, game_state: "GameState", override_action: str = None
) -> bool:
    """Process a mouse click in menu or modal dialog."""
    # Import show_notification inside the function to avoid scope issues
    from game_state_helpers import show_notification

    # If override_action is provided, skip click detection and directly process that action
    if override_action:
        logger.info(f"Processing override action: {override_action}")

        # Special handling for player name saving and zone point editing
        if override_action == "save_zone_points":
            try:
                if hasattr(game_state, "editing_zone_index") and hasattr(
                    game_state, "editing_zone_points_input"
                ):
                    zone_index = game_state.editing_zone_index
                    points_input = game_state.editing_zone_points_input

                    # Validate points input
                    if points_input and points_input.isdigit():
                        points = int(points_input)
                        # Update the zone's points value (5th element in tuple)
                        x, y, w, h, _ = game_state.scoring_zones[zone_index]
                        game_state.scoring_zones[zone_index] = (x, y, w, h, points)

                        # Save zones to persist changes
                        save_zones(game_state)
                        game_state.has_edited_zone_points = True

                        # Reset editing state
                        game_state.editing_zone_mode = None
                        game_state.editing_zone_index = None
                        game_state.editing_zone_points_input = None

                        game_state.menu_cache = None
                        show_notification(
                            game_state,
                            f"Updated zone {zone_index + 1} points to {points}",
                        )
                    else:
                        show_notification(
                            game_state,
                            "Invalid points value, must be a number",
                            is_error=True,
                        )

                return True
            except Exception as e:
                logger.error(f"Error saving zone points: {e}")
                show_notification(game_state, "Error saving zone points", is_error=True)
                return True

        # Continue with other override actions here if needed...

    # Continue with existing code
    if getattr(game_state, "player_name_input_active", False):
        # Import here to avoid circular import
        from ui_screens import _draw_player_name_input

        # Process the username input screen X button click
        try:
            if hasattr(game_state, "username_x_button"):
                btn_x, btn_y, btn_w, btn_h = game_state.username_x_button
                if btn_x <= x <= btn_x + btn_w and btn_y <= y <= btn_y + btn_h:
                    logger.debug("Username input X button clicked")
                    # Same behavior as pressing ESC - use default name
                    if hasattr(game_state, "players") and game_state.players:
                        try:
                            game_state.players[0].name = "Player 1"  # Use default
                            game_state.last_player_name = "Player 1"
                            save_settings(game_state)
                            game_state.player_name_input_active = False
                            game_state.current_state = CurrentGameState.GETTING_PLAYFIELD
                            show_notification(
                                game_state,
                                "Using default name 'Player 1'",
                                duration=2.0,
                            )
                            return True
                        except Exception as e:
                            logger.error(
                                f"Error setting default name via X button: {e}"
                            )
            return False
        except Exception as e:
            logger.error(f"Error processing username input: {e}")
            return False

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

        # Handle versus mode End Turn button click
        if getattr(game_state, "versus_mode_active", False) and hasattr(
            game_state, "versus_end_turn_button"
        ):
            end_turn_rect = game_state.versus_end_turn_button
            btn_x, btn_y, btn_w, btn_h = end_turn_rect

            if btn_x <= x < btn_x + btn_w and btn_y <= y < btn_y + btn_h:
                logger.info("End Turn button clicked in versus mode")
                game_state.click_feedback_state = (end_turn_rect, time.time())

                # Set game state to GAME_OVER to trigger player switch
                game_state.current_state = CurrentGameState.GAME_OVER

                # Show notification
                from game_state_helpers import show_notification

                player_name = game_state.versus_players[
                    game_state.current_turn_player_index
                ].name
                show_notification(
                    game_state, f"{player_name}'s turn ended", duration=2.0
                )

                logger.info(f"Ended turn for player {player_name}")
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
                    "new_game",
                    "resume",
                    "restart_round",
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

                        # Special handling for players submenu to initialize attributes
                        if action == "players":
                            # Initialize player editing attributes to prevent AttributeError
                            if not hasattr(game_state, "editing_player_mode"):
                                game_state.editing_player_mode = None
                            if not hasattr(game_state, "editing_player_index"):
                                game_state.editing_player_index = None
                            if not hasattr(game_state, "editing_player_name_input"):
                                game_state.editing_player_name_input = None
                            logger.info(
                                "Initialized player editing attributes for players submenu"
                            )

                        game_state.submenu_active = action
                        game_state.menu_cache = None  # Force menu redraw
                        game_state.confirm_clear_zones = False  # Clear any pending clear confirmation
                        return True

                    if action == "quit":
                        game_state.previous_state_before_quit_confirm = (
                            CurrentGameState.MENU
                        )
                        game_state.current_state = CurrentGameState.CONFIRM_QUIT
                        _reset_all_menu_editing_states(game_state)
                        return True
                    elif action == "new_game":
                        # Flush pending leaderboard scores before starting new game flow
                        if hasattr(game_state, "leaderboard") and game_state.leaderboard:
                            if hasattr(game_state.leaderboard, "flush_pending_scores"):
                                try:
                                    n = game_state.leaderboard.flush_pending_scores()
                                    if n > 0:
                                        show_notification(
                                            game_state,
                                            "Score submitted to leaderboard",
                                            duration=2.0,
                                        )
                                except Exception as e:
                                    logger.error(f"Error flushing leaderboard on New Game: {e}")
                        # Reset score and all game state so the new game starts clean
                        reset_game(game_state)
                        # Then show player name + board type flow instead of going straight to PLAYING
                        game_state.submenu_active = None
                        game_state.menu_cache = None
                        game_state.current_state = CurrentGameState.GETTING_PLAYER_NAME
                        game_state.player_name_input_active = True
                        game_state.current_player_name_input = (
                            getattr(game_state, "last_player_name", "") or ""
                        )
                        game_state.player_name_cursor_pos = len(
                            game_state.current_player_name_input
                        )
                        _reset_all_menu_editing_states(game_state)
                        logger.info("New Game: returning to player name and board type flow.")
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
                        toggle_debug_mode(game_state)
                        game_state.menu_cache = None
                        return True
                    elif action == "toggle_colorblind_mode":
                        toggle_colorblind_mode(game_state)
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
                    elif action == "restart_round":
                        if hasattr(game_state, "leaderboard") and game_state.leaderboard:
                            if hasattr(game_state.leaderboard, "flush_pending_scores"):
                                try:
                                    n = game_state.leaderboard.flush_pending_scores()
                                    if n > 0:
                                        show_notification(
                                            game_state,
                                            "Score submitted to leaderboard",
                                            duration=2.0,
                                        )
                                except Exception as e:
                                    logger.error(
                                        f"Error flushing leaderboard on Restart Round: {e}"
                                    )
                        reset_game(game_state)
                        game_state.current_state = CurrentGameState.PLAYING
                        game_state.submenu_active = None
                        _reset_all_menu_editing_states(game_state)
                        show_notification(game_state, "Round restarted", duration=1.5)
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
                        if getattr(game_state, "confirm_clear_zones", False):
                            clear_zones(game_state)
                            game_state.confirm_clear_zones = False
                            _reset_all_menu_editing_states(game_state)
                            return True
                        game_state.confirm_clear_zones = True
                        show_notification(
                            game_state,
                            "Click Clear All Zones again to confirm. This cannot be undone.",
                            duration=4.0,
                        )
                        game_state.menu_cache = None
                        return True

                    elif action == "save_zones":
                        save_zones(game_state)
                        game_state.menu_cache = None
                        return True

                    elif action == "load_zones":
                        load_zones(game_state)
                        _reset_all_menu_editing_states(game_state)
                        return True

                    elif action == "back_to_manage_zones":
                        logger.info("Returning to manage zones submenu")
                        game_state.submenu_active = "manage_zones"
                        game_state.menu_cache = None
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
                            "versus",
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
                            # Upload pending scores (screenshot + score) to leaderboard when changing mode
                            if hasattr(game_state, "leaderboard") and game_state.leaderboard:
                                if hasattr(game_state.leaderboard, "flush_pending_scores"):
                                    try:
                                        n = game_state.leaderboard.flush_pending_scores()
                                        if n > 0:
                                            show_notification(
                                                game_state,
                                                "Score submitted to leaderboard",
                                                duration=2.0,
                                            )
                                    except Exception as e:
                                        logger.error(f"Error flushing leaderboard on mode change: {e}")
                            game_state.game_mode = new_mode
                            game_state.menu_cache = None
                            logger.info(f"Switched to mode: {new_mode}")

                            # Handle versus mode specially
                            if new_mode == "versus":
                                # Import versus_mode only when needed
                                try:
                                    from versus_mode import start_versus_mode

                                    start_versus_mode(game_state)
                                except Exception as e:
                                    logger.error(f"Error starting versus mode: {e}")
                                    show_notification(
                                        game_state,
                                        "Error starting versus mode",
                                        is_error=True,
                                    )
                            else:
                                # Reset the game state to start fresh with other modes
                                reset_game(game_state)

                            # Switch to retro music if retro mode is activated
                            if new_mode == "retro":
                                # Switch to the fourth track (index 3)
                                change_music_track(game_state, 3)

                            show_notification(
                                game_state, f"Mode changed to {new_mode.capitalize()}"
                            )
                        return True

                    # Layout selection
                    elif action.startswith("set_layout_"):
                        new_layout = action.split("set_layout_")[-1]
                        valid_layouts = {"whiffle", "fivestar"}
                        if new_layout in valid_layouts:
                            # Convert fivestar to "five star" for set_playfield if needed
                            layout_key = (
                                "five star" if new_layout == "fivestar" else new_layout
                            )

                            try:
                                success = game_state.set_playfield(layout_key)
                                if success:
                                    # Reset score when changing layout
                                    game_state.score = 0
                                    game_state.final_score = 0

                                    # Reset player score if there's a current player
                                    try:
                                        current_player = game_state.get_current_player()
                                        if current_player:
                                            current_player.score = 0
                                    except Exception as e:
                                        logger.debug(
                                            f"Could not reset player score: {e}"
                                        )

                                    # Reset XP when changing layout
                                    try:
                                        from xp_system import xp_system

                                        xp_system.clear_all_xp()

                                        # Refresh player XP data after clearing
                                        try:
                                            current_player = (
                                                game_state.get_current_player()
                                            )
                                            if current_player and hasattr(
                                                current_player, "refresh_xp"
                                            ):
                                                current_player.refresh_xp()
                                        except Exception as e:
                                            logger.debug(
                                                f"Could not refresh player XP: {e}"
                                            )
                                    except Exception as e:
                                        logger.error(
                                            f"Error clearing XP on layout change: {e}"
                                        )

                                    game_state.menu_cache = None
                                    layout_display = (
                                        "Five star"
                                        if new_layout == "fivestar"
                                        else "Whiffle"
                                    )
                                    show_notification(
                                        game_state, f"Layout changed to {layout_display}"
                                    )
                                    logger.info(
                                        f"Switched to layout: {new_layout}, score reset to 0"
                                    )
                                else:
                                    show_notification(
                                        game_state,
                                        "Failed to change layout",
                                        is_error=True,
                                    )
                            except Exception as e:
                                logger.error(f"Error changing layout: {e}")
                                show_notification(
                                    game_state,
                                    "Error changing layout",
                                    is_error=True,
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
                        if len(game_state.players) < 4:  # Max 4 players
                            # Use the Player class that was already imported at the top
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
                                # Reload per-player achievements for the newly selected player
                                try:
                                    load_achievements(
                                        game_state, GameConstants.ACHIEVEMENTS_FILE
                                    )
                                except Exception as ach_e:
                                    logger.error(
                                        f"Error loading achievements for selected player: {ach_e}"
                                    )
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

                                # Get the selected format if available
                                export_format = "MP4"  # Default
                                if hasattr(game_state, "replay_sharing"):
                                    export_format = game_state.replay_sharing.get(
                                        "selected_format", "MP4"
                                    )

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
                                            cached_path = game_state.replay_sharing[
                                                "last_export_path"
                                            ]
                                            # Verify cached file exists and has the correct format extension
                                            if (
                                                os.path.exists(cached_path)
                                                and os.path.getsize(cached_path) > 1000
                                                and (
                                                    # Check if the cached file matches the selected format
                                                    (
                                                        export_format == "MP4"
                                                        and cached_path.endswith(".mp4")
                                                    )
                                                    or (
                                                        export_format == "GIF"
                                                        and cached_path.endswith(".gif")
                                                    )
                                                )
                                            ):
                                                video_path = cached_path
                                                logger.info(
                                                    f"Using previously generated video: {video_path}"
                                                )
                                        else:
                                            # Safely format the log message, handling potential None for cached_path
                                            cached_path_info = (
                                                f"path: {cached_path}"
                                                if cached_path
                                                else "no cached path found"
                                            )
                                            logger.warning(
                                                f"Cached video invalid ({cached_path_info}). Regenerating..."
                                            )

                                        # If we don't have a valid cached path or it's the wrong format, generate a new one
                                        if not video_path:
                                            # Set status in UI
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = f"Generating {export_format} file..."
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.3
                                                game_state.menu_cache = (
                                                    None  # Force UI update
                                                )

                                            show_notification(
                                                game_state,
                                                f"Generating {export_format} file...",
                                                duration=2.0,
                                            )

                                            # Generate the video based on selected format
                                            video_path = game_state.replay_manager.generate_video(
                                                replay_id, format=export_format
                                            )

                                            # Update status
                                            if hasattr(game_state, "replay_sharing"):
                                                if video_path:
                                                    game_state.replay_sharing[
                                                        "last_export_path"
                                                    ] = video_path
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 0.5
                                                    game_state.menu_cache = None
                                                else:
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = f"Error generating {export_format} file"
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 0.0
                                                    game_state.menu_cache = None

                                                    show_notification(
                                                        game_state,
                                                        f"Error generating {export_format} file",
                                                        is_error=True,
                                                    )
                                                    return True

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

                                            # Now open a file save dialog to let the user choose where to save
                                            import tkinter as tk
                                            from tkinter import filedialog

                                            # Get filename and extension from the video path
                                            video_filename = os.path.basename(
                                                video_path
                                            )

                                            # Create a temporary Tkinter root window
                                            root = tk.Tk()
                                            root.withdraw()  # Hide the root window

                                            try:
                                                # Update status before dialog
                                                if hasattr(
                                                    game_state, "replay_sharing"
                                                ):
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = "Select where to save..."
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 0.5
                                                    game_state.menu_cache = None
                                            except Exception as e:
                                                logger.error(
                                                    f"Error in file save dialog: {e}"
                                                )

                                        show_notification(
                                            game_state,
                                            "Select where to save the file...",
                                            duration=2.0,
                                        )

                                        # Determine file type based on format
                                        if export_format == "MP4":
                                            file_types = [("MP4 Video", "*.mp4")]
                                            default_ext = ".mp4"
                                        else:
                                            file_types = [("GIF Animation", "*.gif")]
                                            default_ext = ".gif"

                                            # Open save dialog
                                            save_path = filedialog.asksaveasfilename(
                                                title="Save Replay",
                                                defaultextension=default_ext,
                                                filetypes=file_types,
                                                initialfile=video_filename,
                                            )

                                            # Clean up Tkinter
                                            root.destroy()

                                        if save_path:
                                            # Update status
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Saving file..."
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.7
                                                game_state.menu_cache = None

                                                # Copy the file to the selected location
                                                import shutil

                                                shutil.copy2(video_path, save_path)

                                            # Update UI with success
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = f"Saved to: {os.path.basename(save_path)}"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 1.0
                                                game_state.menu_cache = None

                                            game_state.has_shared_replay = True
                                            show_notification(
                                                game_state,
                                                f"Saved to: {os.path.basename(save_path)}",
                                                duration=3.0,
                                            )

                                            logger.info(
                                                f"Successfully shared replay locally to: {save_path}"
                                            )
                                        else:
                                            # User canceled the save dialog
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Export canceled"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.0
                                                game_state.menu_cache = None

                                            show_notification(
                                                game_state,
                                                "Export canceled",
                                                duration=2.0,
                                            )
                                    except Exception as e:
                                        logger.error(f"Error in file save dialog: {e}")

                                        # Clean up Tkinter if it failed
                                        if "root" in locals() and root:
                                            root.destroy()

                                        # Update UI with error
                                    if hasattr(game_state, "replay_sharing"):
                                        game_state.replay_sharing["export_status"] = (
                                            f"Error: {str(e)}"
                                        )
                                        game_state.replay_sharing["export_progress"] = (
                                            0.0
                                        )
                                        game_state.menu_cache = None

                                    show_notification(
                                        game_state,
                                        "Error saving file locally",
                                        is_error=True,
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
                                            cached_path = game_state.replay_sharing[
                                                "last_export_path"
                                            ]
                                            # Verify cached file exists and has the correct format extension
                                            if (
                                                os.path.exists(cached_path)
                                                and os.path.getsize(cached_path) > 1000
                                                and (
                                                    # Check if the cached file matches the selected format
                                                    (
                                                        export_format == "MP4"
                                                        and cached_path.endswith(".mp4")
                                                    )
                                                    or (
                                                        export_format == "GIF"
                                                        and cached_path.endswith(".gif")
                                                    )
                                                )
                                            ):
                                                video_path = cached_path
                                                logger.info(
                                                    f"Using previously generated video: {video_path}"
                                                )
                                            else:
                                                logger.warning(
                                                    f"Cached video not found, too small, or wrong format: {cached_path}. Regenerating..."
                                                )

                                        # Generate new video if needed
                                        if not video_path:
                                            # Set status in UI
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Generating video first..."
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.3
                                                game_state.menu_cache = (
                                                    None  # Force UI update
                                                )

                                            show_notification(
                                                game_state,
                                                f"Generating {export_format} file...",
                                                duration=2.0,
                                            )

                                            # Generate the video based on selected format
                                            video_path = game_state.replay_manager.generate_video(
                                                replay_id, format=export_format
                                            )

                                            # Update status
                                            if hasattr(game_state, "replay_sharing"):
                                                if video_path:
                                                    game_state.replay_sharing[
                                                        "last_export_path"
                                                    ] = video_path
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = "Video generated, preparing to share..."
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 0.5
                                                    game_state.menu_cache = None
                                                else:
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = f"Error generating {export_format} file"
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 0.0
                                                    game_state.menu_cache = None

                                                    show_notification(
                                                        game_state,
                                                        f"Error generating {export_format} file",
                                                        is_error=True,
                                                    )
                                                    return True

                                        # Now proceed with sharing to Discord
                                        if video_path:
                                            # Set status in UI
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Sharing to Discord..."
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.7
                                                game_state.menu_cache = None

                                            show_notification(
                                                game_state,
                                                "Sharing to Discord...",
                                                duration=2.0,
                                            )

                                            # --- Discord Webhook Implementation ---
                                            webhook_url = getattr(
                                                game_state, "discord_webhook_url", None
                                            )

                                            if not webhook_url:
                                                logger.error(
                                                    "Discord webhook URL not configured in settings."
                                                )
                                                show_notification(
                                                    game_state,
                                                    "Discord webhook URL not set!",
                                                    is_error=True,
                                                )
                                                if hasattr(
                                                    game_state, "replay_sharing"
                                                ):
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = "Discord URL missing"
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 0.0
                                                return True  # Handled the action, even though it failed

                                            try:
                                                logger.info(
                                                    f"Attempting to send {video_path} to Discord webhook."
                                                )
                                                # Construct message payload
                                                payload = {
                                                    "content": f"Check out this Whiffleball replay! ({export_format})"
                                                }
                                                # Open the file in binary read mode
                                                with open(video_path, "rb") as f:
                                                    files = {
                                                        "file": (
                                                            os.path.basename(
                                                                video_path
                                                            ),
                                                            f,
                                                            (
                                                                f"image/{export_format.lower()}"
                                                                if export_format
                                                                == "GIF"
                                                                else f"video/{export_format.lower()}"
                                                            ),
                                                        )
                                                    }
                                                    # Send the request
                                                    response = requests.post(
                                                        webhook_url,
                                                        data=payload,
                                                        files=files,
                                                    )

                                                # Check response status
                                                if (
                                                    response.status_code >= 200
                                                    and response.status_code < 300
                                                ):
                                                    logger.info(
                                                        f"Successfully posted replay {export_format} to Discord."
                                                    )
                                                    if hasattr(
                                                        game_state, "replay_sharing"
                                                    ):
                                                        game_state.replay_sharing[
                                                            "export_status"
                                                        ] = "Shared to Discord!"
                                                        game_state.replay_sharing[
                                                            "export_progress"
                                                        ] = 1.0
                                                    game_state.has_shared_replay = True
                                                    show_notification(
                                                        game_state,
                                                        "Successfully shared to Discord!",
                                                        duration=3.0,
                                                    )
                                                else:
                                                    logger.error(
                                                        f"Discord webhook failed: {response.status_code} - {response.text}"
                                                    )
                                                    if hasattr(
                                                        game_state, "replay_sharing"
                                                    ):
                                                        game_state.replay_sharing[
                                                            "export_status"
                                                        ] = f"Discord Error: {response.status_code}"
                                                        game_state.replay_sharing[
                                                            "export_progress"
                                                        ] = 0.0
                                                    show_notification(
                                                        game_state,
                                                        f"Discord share failed ({response.status_code})",
                                                        is_error=True,
                                                    )

                                            except (
                                                requests.exceptions.RequestException
                                            ) as req_err:
                                                logger.error(
                                                    f"Error sending request to Discord webhook: {req_err}"
                                                )
                                                if hasattr(
                                                    game_state, "replay_sharing"
                                                ):
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = "Network Error"
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 0.0
                                                show_notification(
                                                    game_state,
                                                    "Error connecting to Discord",
                                                    is_error=True,
                                                )
                                            except FileNotFoundError:
                                                logger.error(
                                                    f"Could not find the generated file to upload: {video_path}"
                                                )
                                                if hasattr(
                                                    game_state, "replay_sharing"
                                                ):
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = "File Not Found"
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 0.0
                                                show_notification(
                                                    game_state,
                                                    "Error: Replay file not found",
                                                    is_error=True,
                                                )
                                            except (
                                                Exception
                                            ) as inner_e:  # Catch other potential errors during upload
                                                logger.error(
                                                    f"Unexpected error during Discord upload: {inner_e}"
                                                )
                                                if hasattr(
                                                    game_state, "replay_sharing"
                                                ):
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = "Upload Error"
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 0.0
                                                show_notification(
                                                    game_state,
                                                    "Error uploading to Discord",
                                                    is_error=True,
                                                )
                                            finally:
                                                # Update menu cache regardless of success/failure to show final status
                                                game_state.menu_cache = None

                                            return True  # Action handled
                                            # --- End Discord Webhook Implementation ---

                                        else:
                                            # No video path available
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Error: No video file available"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.0
                                                game_state.menu_cache = None

                                            show_notification(
                                                game_state,
                                                "Error: No video file to share",
                                                is_error=True,
                                            )
                                            return True
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
                                        return True
                                elif platform == "Share Link":
                                    video_path = (
                                        None  # Initialize video_path for this attempt
                                    )
                                    try:
                                        # --- 1. Check for cached video ---
                                        cached_path = None
                                        export_format = "MP4"  # Default, get from state later if needed
                                        if hasattr(game_state, "replay_sharing"):
                                            export_format = (
                                                game_state.replay_sharing.get(
                                                    "selected_format", "MP4"
                                                )
                                            )
                                            cached_path = game_state.replay_sharing.get(
                                                "last_export_path"
                                            )

                                        if (
                                            cached_path
                                            and os.path.exists(cached_path)
                                            and os.path.getsize(cached_path) > 1000
                                        ):
                                            # Check if format matches
                                            correct_format = (
                                                export_format == "MP4"
                                                and cached_path.endswith(".mp4")
                                            ) or (
                                                export_format == "GIF"
                                                and cached_path.endswith(".gif")
                                            )
                                            if correct_format:
                                                video_path = cached_path
                                                logger.info(
                                                    f"Using previously generated video: {video_path}"
                                                )
                                            else:
                                                logger.warning(
                                                    f"Cached video path '{cached_path}' has wrong format (expected {export_format}). Regenerating..."
                                                )
                                        elif cached_path:
                                            logger.warning(
                                                f"Cached video path '{cached_path}' invalid (not found or too small). Regenerating..."
                                            )
                                        else:
                                            logger.warning(
                                                "No cached video path found. Regenerating..."
                                            )

                                        # --- 2. Generate video if needed ---
                                        if not video_path:
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = f"Generating {export_format}..."
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.3
                                                game_state.menu_cache = None
                                            show_notification(
                                                game_state,
                                                f"Generating {export_format} file...",
                                                duration=2.0,
                                            )

                                            # Ensure replay_id is available
                                            parts = action.split("_")
                                            if len(parts) < 4:
                                                raise ValueError(
                                                    "Could not extract replay_id from action string"
                                                )
                                            replay_id = parts[3]

                                            video_path = game_state.replay_manager.generate_video(
                                                replay_id, format=export_format
                                            )

                                            if not video_path:
                                                # Generation failed
                                                logger.error(
                                                    f"Failed to generate {export_format} for replay {replay_id}"
                                                )
                                                if hasattr(
                                                    game_state, "replay_sharing"
                                                ):
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = f"Error generating {export_format}"
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 0.0
                                                    game_state.menu_cache = None
                                                show_notification(
                                                    game_state,
                                                    f"Error generating {export_format} file",
                                                    is_error=True,
                                                )
                                                return True  # Stop processing

                                            # Generation succeeded
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "last_export_path"
                                                ] = video_path
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = f"{export_format} generated"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.5  # Halfway done
                                                game_state.menu_cache = None

                                        # --- 3. Proceed to Share Link (Google Drive) upload if video_path is valid ---
                                        if video_path:
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Sharing to Share Link..."
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.7
                                                game_state.menu_cache = None
                                            show_notification(
                                                game_state,
                                                "Sharing to Share Link...",
                                                duration=2.0,
                                            )

                                            # Get player name/score for title (ensure replay_id is defined)
                                            parts = action.split("_")
                                            replay_id = (
                                                parts[3] if len(parts) > 3 else None
                                            )
                                            if not replay_id:
                                                raise ValueError(
                                                    "Replay ID missing for upload"
                                                )  # Should not happen if video generated

                                            replay = (
                                                game_state.replay_manager.load_replay(
                                                    replay_id
                                                )
                                            )
                                            player_name = (
                                                replay.player_name
                                                if replay
                                                and hasattr(replay, "player_name")
                                                else "Player"
                                            )
                                            score = (
                                                replay.frames[-1].score
                                                if replay
                                                and hasattr(replay, "frames")
                                                and replay.frames
                                                else 0
                                            )
                                            game_mode = (
                                                replay.game_mode
                                                if replay
                                                and hasattr(replay, "game_mode")
                                                else "classic"
                                            )
                                            title = f"Whiffle Replay ({player_name} - {game_mode.capitalize()} - Score {score})"

                                            # --- Google Drive Sharing Implementation ---
                                            try:
                                                # Import necessary module with the CORRECT function name
                                                from google_drive_utils import (
                                                    upload_video_to_drive,
                                                )

                                                logger.info(
                                                    f"Attempting Google Drive upload for {video_path} with title '{title}'"
                                                )
                                                # Call the CORRECT upload function
                                                success, result_message = (
                                                    upload_video_to_drive(
                                                        video_path,
                                                        title=title,
                                                        # Mime type handling should be inside upload_video_to_drive now
                                                    )
                                                )

                                                if success:
                                                    shareable_link = result_message
                                                    logger.info(
                                                        f"Successfully uploaded to Google Drive: {shareable_link}"
                                                    )

                                                    # --- Attempt to copy link to clipboard ---
                                                    clipboard_success = False
                                                    try:
                                                        # Check system platform in a cross-platform way
                                                        system_platform = sys.platform

                                                        # Windows clipboard handling
                                                        if system_platform == "win32":
                                                            try:
                                                                # Try to use win32clipboard (from pywin32)
                                                                import win32clipboard

                                                                win32clipboard.OpenClipboard()
                                                                win32clipboard.EmptyClipboard()
                                                                win32clipboard.SetClipboardText(
                                                                    shareable_link,
                                                                    win32clipboard.CF_UNICODETEXT,
                                                                )
                                                                win32clipboard.CloseClipboard()
                                                                clipboard_success = True
                                                                logger.info(
                                                                    "Successfully copied link to clipboard using win32clipboard."
                                                                )
                                                            except ImportError:
                                                                logger.warning(
                                                                    "win32clipboard module not available. Try 'pip install pywin32'"
                                                                )
                                                                # Try fallback to ctypes for Windows
                                                                try:
                                                                    import ctypes

                                                                    CF_UNICODETEXT = 13
                                                                    GMEM_DDESHARE = (
                                                                        0x2000
                                                                    )
                                                                    d = ctypes.windll.kernel32.GlobalAlloc(
                                                                        GMEM_DDESHARE,
                                                                        len(
                                                                            shareable_link
                                                                        )
                                                                        * 2
                                                                        + 2,
                                                                    )
                                                                    p = ctypes.windll.kernel32.GlobalLock(
                                                                        d
                                                                    )
                                                                    ctypes.cdll.msvcrt.wcscpy(
                                                                        ctypes.c_wchar_p(
                                                                            p
                                                                        ),
                                                                        shareable_link,
                                                                    )
                                                                    ctypes.windll.kernel32.GlobalUnlock(
                                                                        d
                                                                    )
                                                                    ctypes.windll.user32.OpenClipboard(
                                                                        0
                                                                    )
                                                                    ctypes.windll.user32.EmptyClipboard()
                                                                    ctypes.windll.user32.SetClipboardData(
                                                                        CF_UNICODETEXT,
                                                                        d,
                                                                    )
                                                                    ctypes.windll.user32.CloseClipboard()
                                                                    clipboard_success = (
                                                                        True
                                                                    )
                                                                    logger.info(
                                                                        "Successfully copied link to clipboard using ctypes fallback."
                                                                    )
                                                                except (
                                                                    Exception
                                                                ) as ctypes_err:
                                                                    logger.error(
                                                                        f"Windows ctypes clipboard fallback failed: {ctypes_err}"
                                                                    )
                                                            except (
                                                                Exception
                                                            ) as win_clip_err:
                                                                logger.error(
                                                                    f"Windows clipboard error: {win_clip_err}"
                                                                )

                                                        # Linux clipboard handling
                                                        elif system_platform.startswith(
                                                            "linux"
                                                        ):
                                                            logger.info(
                                                                f"Attempting to copy to clipboard using xclip. DISPLAY={os.environ.get('DISPLAY')}"
                                                            )
                                                            process = subprocess.run(
                                                                [
                                                                    "xclip",
                                                                    "-selection",
                                                                    "clipboard",
                                                                ],
                                                                input=shareable_link.encode(
                                                                    "utf-8"
                                                                ),
                                                                check=True,
                                                                capture_output=True,
                                                                timeout=2,
                                                            )
                                                            clipboard_success = True
                                                            logger.info(
                                                                "Successfully copied link to clipboard using xclip."
                                                            )
                                                        else:
                                                            logger.warning(
                                                                f"No clipboard implementation for platform: {system_platform}"
                                                            )
                                                    except FileNotFoundError:
                                                        logger.warning(
                                                            "'xclip' command not found. Cannot copy to clipboard. Please install xclip."
                                                        )
                                                    except subprocess.TimeoutExpired:
                                                        logger.error(
                                                            "'xclip' command timed out after 2 seconds. Clipboard copy failed."
                                                        )
                                                    except (
                                                        subprocess.CalledProcessError
                                                    ) as e:
                                                        logger.error(
                                                            f"Failed to copy link to clipboard using xclip: {e}"
                                                        )
                                                        if hasattr(e, "stderr"):
                                                            logger.error(
                                                                f"xclip stderr: {e.stderr.decode('utf-8', errors='ignore')}"
                                                            )
                                                        if hasattr(e, "stdout"):
                                                            logger.error(
                                                                f"xclip stdout: {e.stdout.decode('utf-8', errors='ignore')}"
                                                            )
                                                    except Exception as clip_err:
                                                        logger.error(
                                                            f"Unexpected error ({type(clip_err).__name__}) copying to clipboard: {clip_err}"
                                                        )
                                                    # --- End clipboard copy attempt ---

                                                    if hasattr(
                                                        game_state, "replay_sharing"
                                                    ):
                                                        game_state.replay_sharing[
                                                            "export_status"
                                                        ] = f"Share Link Ready: {shareable_link}"
                                                        game_state.replay_sharing[
                                                            "export_progress"
                                                        ] = 1.0

                                                    game_state.has_shared_replay = True
                                                    # Update notification based on clipboard success
                                                    if clipboard_success:
                                                        notification_message = "Share Link created and copied!"
                                                    else:
                                                        notification_message = f"Link created (copy manually): {shareable_link}"
                                                    show_notification(
                                                        game_state,
                                                        notification_message,
                                                        duration=5.0,
                                                    )
                                                else:
                                                    # Upload function returned failure
                                                    error_message = result_message
                                                    raise Exception(
                                                        f"Google Drive upload failed: {error_message}"
                                                    )

                                            except Exception as upload_err:
                                                logger.error(
                                                    f"Google Drive upload failed: {upload_err}"
                                                )
                                                logger.error(
                                                    traceback.format_exc()
                                                )  # Log full traceback for upload errors
                                                if hasattr(
                                                    game_state, "replay_sharing"
                                                ):
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = f"Upload Error: {str(upload_err)[:50]}..."  # Show truncated error
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 0.0
                                                show_notification(
                                                    game_state,
                                                    "Error uploading to Google Drive",
                                                    is_error=True,
                                                )
                                            finally:
                                                game_state.menu_cache = None  # Update UI regardless of upload outcome
                                            # --- End Google Drive Sharing Implementation ---

                                        else:
                                            # This case should ideally not be reached if generation failure is handled above
                                            logger.error(
                                                f"No video path available to share after generation attempt for replay {replay_id}"
                                            )
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Error: Video unavailable"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.0
                                                game_state.menu_cache = None

                                        return True  # Action handled (successfully or with upload error)

                                    except Exception as e:
                                        # Catch errors from the entire process (loading replay, checking cache, generating, uploading)
                                        logger.error(
                                            f"Error processing 'Share Link' action: {e}"
                                        )
                                        logger.error(
                                            traceback.format_exc()
                                        )  # Log full traceback
                                        if hasattr(game_state, "replay_sharing"):
                                            game_state.replay_sharing[
                                                "export_status"
                                            ] = f"Error: {str(e)[:50]}..."
                                            game_state.replay_sharing[
                                                "export_progress"
                                            ] = 0.0
                                            game_state.menu_cache = None
                                        show_notification(
                                            game_state,
                                            "Error processing Share Link",
                                            is_error=True,
                                        )
                                        return True  # Action handled (failed)
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
                                        cached_path = None
                                        if hasattr(
                                            game_state, "replay_sharing"
                                        ) and game_state.replay_sharing.get(
                                            "last_export_path"
                                        ):
                                            cached_path = game_state.replay_sharing[
                                                "last_export_path"
                                            ]
                                            # Verify cached file exists and has the correct format extension
                                            if (
                                                os.path.exists(cached_path)
                                                and os.path.getsize(cached_path) > 1000
                                                and (
                                                    # Check if the cached file matches the selected format
                                                    (
                                                        export_format == "MP4"
                                                        and cached_path.endswith(".mp4")
                                                    )
                                                    or (
                                                        export_format == "GIF"
                                                        and cached_path.endswith(".gif")
                                                    )
                                                )
                                            ):
                                                video_path = cached_path
                                                logger.info(
                                                    f"Using previously generated video: {video_path}"
                                                )
                                            else:  # Corresponds to the 'if hasattr(...)' check
                                                # Log invalid cache state specifically if cached_path was found but invalid
                                                logger.warning(
                                                    f"Cached video path '{cached_path}' exists but is invalid (size/format). Regenerating..."
                                                )
                                        else:  # Corresponds to the 'if hasattr(game_state, "replay_sharing") and game_state.replay_sharing.get("last_export_path"):' check
                                            # Log if no cached path was found in replay_sharing at all
                                            logger.warning(
                                                "No cached video path found or replay_sharing missing. Regenerating..."
                                            )

                                        # Generate new video if needed
                                        if not video_path:
                                            # Set status in UI
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Generating video first..."
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.3
                                            game_state.menu_cache = (
                                                None  # Force UI update
                                            )

                                        show_notification(
                                            game_state,
                                            f"Generating {export_format} file...",
                                            duration=2.0,
                                        )

                                        # Generate the video based on selected format
                                        video_path = (
                                            game_state.replay_manager.generate_video(
                                                replay_id, format=export_format
                                            )
                                        )

                                        # Update status
                                        if hasattr(game_state, "replay_sharing"):
                                            if video_path:
                                                game_state.replay_sharing[
                                                    "last_export_path"
                                                ] = video_path
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.5
                                                game_state.menu_cache = None
                                            else:  # This else corresponds to the 'if video_path:' above it
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = f"Error generating {export_format} file"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.0
                                                game_state.menu_cache = None

                                                show_notification(
                                                    game_state,
                                                    f"Error generating {export_format} file",
                                                    is_error=True,
                                                )
                                                return True
                                        # Add the missing except block for the YouTube try block
                                    except Exception as e:
                                        logger.error(
                                            f"Error preparing video for YouTube: {e}"
                                        )
                                        logger.error(traceback.format_exc())

                                        # Update UI status
                                        if hasattr(game_state, "replay_sharing"):
                                            game_state.replay_sharing[
                                                "export_status"
                                            ] = f"Error preparing video: {str(e)}"
                                            game_state.replay_sharing[
                                                "export_progress"
                                            ] = 0.0
                                            game_state.menu_cache = None

                                        show_notification(
                                            game_state,
                                            "Error preparing video for YouTube",
                                            is_error=True,
                                        )
                                        # It's often good practice to return True here as the click action was handled, even if it resulted in an error.
                                        # Depending on the desired flow, you might want to change this.
                                        return True

                                        # Add the actual YouTube upload logic here, inside the try block if video_path is valid
                                    if video_path:
                                        try:
                                            # Set status in UI
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = "Uploading to YouTube..."
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.7
                                                game_state.menu_cache = None

                                            show_notification(
                                                game_state,
                                                "Uploading to YouTube...",
                                                duration=3.0,
                                            )

                                            # Call YouTube upload function using the correct name
                                            success, result_message = (
                                                youtube_utils.upload_video_to_youtube(
                                                    video_path,
                                                    player_name=player_name,
                                                    score=score,
                                                    game_mode=game_mode,
                                                    # title=f"Whiffleball Highlight: {player_name} ({score} pts - {game_mode.capitalize()})",
                                                    # description=f"Gameplay highlight from Whiffleball. Mode: {game_mode.capitalize()}",
                                                    # tags=[
                                                    #     "whiffleball",
                                                    #     "gameplay",
                                                    #     "highlight",
                                                    #     game_mode,
                                                    # ],
                                                    # privacy_status="public",  # or "private", "unlisted"
                                                )
                                            )

                                            # Update UI based on upload result
                                            if success:
                                                game_state.has_shared_replay = True
                                                video_url = result_message  # The function now returns the URL
                                                if hasattr(
                                                    game_state, "replay_sharing"
                                                ):
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = f"YouTube: {video_url}"
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 1.0
                                                show_notification(
                                                    game_state,
                                                    "Successfully uploaded to YouTube!",
                                                    duration=5.0,
                                                )
                                                logger.info(
                                                    f"Successfully uploaded video to YouTube: {video_url}"
                                                )
                                            else:
                                                if hasattr(
                                                    game_state, "replay_sharing"
                                                ):
                                                    game_state.replay_sharing[
                                                        "export_status"
                                                    ] = "YouTube upload failed"
                                                    game_state.replay_sharing[
                                                        "export_progress"
                                                    ] = 0.0
                                                show_notification(
                                                    game_state,
                                                    "Failed to upload to YouTube",
                                                    is_error=True,
                                                )
                                                logger.error("YouTube upload failed.")

                                        except Exception as e:
                                            logger.error(
                                                f"Error sharing video to YouTube: {e}"
                                            )
                                            logger.error(traceback.format_exc())

                                            # Update UI status
                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = f"YouTube Upload Error: {str(e)}"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 0.0
                                                game_state.menu_cache = None

                                            show_notification(
                                                game_state,
                                                "Error sharing video to YouTube",
                                                is_error=True,
                                            )
                                        finally:
                                            # Update the menu cache regardless of upload success/failure to reflect final status
                                            game_state.menu_cache = None

                                    return True  # Return True because the share action was processed
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
                                    replay_id, format=export_format
                                )

                                if video_path:
                                    game_state.has_exported_highlight = True
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
                                        game_state.has_exported_highlight = True
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

                    # Handle different submenu actions
                    elif action in submenu_draw_functions_map:
                        # Ensure attributes are initialized when entering players submenu
                        if action == "players":
                            # Initialize editing attributes to prevent AttributeError
                            if not hasattr(game_state, "editing_player_mode"):
                                game_state.editing_player_mode = None
                            if not hasattr(game_state, "editing_player_index"):
                                game_state.editing_player_index = None
                            if not hasattr(game_state, "editing_player_name_input"):
                                game_state.editing_player_name_input = None
                            logger.info(
                                "Initialized player editing attributes in game_state"
                            )

                        # Set submenu active to action
                        game_state.submenu_active = action
                        # Clear menu cache to redraw
                        game_state.menu_cache = None
                        logger.info(f"Switched to submenu: {action}")
                        return True

                    # Zone editing actions
                    elif action.startswith("edit_zone_"):
                        try:
                            zone_index = int(action[len("edit_zone_") :])
                            if 0 <= zone_index < len(game_state.scoring_zones):
                                logger.info(
                                    f"Setting up zone {zone_index} for points editing"
                                )
                                # Set up points editing mode instead of general editing
                                game_state.editing_zone_index = zone_index
                                game_state.editing_zone_mode = "edit_points"
                                game_state.editing_zone_points_input = str(
                                    game_state.scoring_zones[zone_index][4]
                                )
                                # Initialize text input handling if needed
                                from game_input import _handle_text_input

                                _handle_text_input(None, game_state)
                                game_state.menu_cache = None
                                show_notification(
                                    game_state,
                                    f"Editing points for zone {zone_index + 1}",
                                )
                                return True
                        except (ValueError, IndexError) as e:
                            logger.error(f"Error setting up zone points edit: {e}")
                            show_notification(
                                game_state,
                                "Error setting up points edit",
                                is_error=True,
                            )
                        return True

                    elif action == "move_all_zones":
                        if game_state.scoring_zones:
                            logger.info("Entering move-all-zones mode")
                            game_state.move_all_zones = True
                            game_state.current_state = CurrentGameState.ZONE_EDITING
                            game_state.selected_zone_for_edit = None
                            game_state.zone_editing_action = None
                            game_state.previous_state = CurrentGameState.MENU
                            show_notification(
                                game_state,
                                "Click and drag on video to move all zones. Esc to cancel.",
                                duration=3.0,
                            )
                            return True
                        return True

                    elif action.startswith("move_zone_"):
                        try:
                            zone_index = int(action[len("move_zone_") :])
                            if 0 <= zone_index < len(game_state.scoring_zones):
                                logger.info(f"Setting up zone {zone_index} for moving")
                                game_state.move_all_zones = False
                                game_state.current_state = CurrentGameState.ZONE_EDITING
                                game_state.selected_zone_for_edit = zone_index
                                game_state.zone_editing_action = "move"
                                game_state.previous_state = CurrentGameState.MENU
                                show_notification(
                                    game_state, f"Moving zone {zone_index + 1}"
                                )
                                return True
                        except (ValueError, IndexError) as e:
                            logger.error(f"Error setting up zone move: {e}")
                            show_notification(
                                game_state, "Error setting up zone move", is_error=True
                            )
                        return True

                    elif action.startswith("resize_zone_"):
                        try:
                            zone_index = int(action[len("resize_zone_") :])
                            if 0 <= zone_index < len(game_state.scoring_zones):
                                logger.info(
                                    f"Setting up zone {zone_index} for resizing"
                                )
                                game_state.move_all_zones = False
                                game_state.current_state = CurrentGameState.ZONE_EDITING
                                game_state.selected_zone_for_edit = zone_index
                                game_state.zone_editing_action = "resize"
                                game_state.previous_state = CurrentGameState.MENU
                                show_notification(
                                    game_state, f"Resizing zone {zone_index + 1}"
                                )
                                return True
                        except (ValueError, IndexError) as e:
                            logger.error(f"Error setting up zone resize: {e}")
                            show_notification(
                                game_state,
                                "Error setting up zone resize",
                                is_error=True,
                            )
                        return True

                    elif action.startswith("delete_zone_"):
                        try:
                            zone_index = int(action[len("delete_zone_") :])
                            if 0 <= zone_index < len(game_state.scoring_zones):
                                logger.info(f"Deleting zone {zone_index}")
                                # Remove the zone from the list
                                del game_state.scoring_zones[zone_index]
                                # Update special hole after zone deletion
                                if hasattr(game_state, "is_fivestar_playfield"):
                                    is_fivestar = game_state.is_fivestar_playfield()
                                else:
                                    is_fivestar = (
                                        getattr(game_state, "playfield_type", "whiffle")
                                        == "fivestar"
                                    )
                                if is_fivestar:
                                    game_state.special_hole = None
                                else:
                                    game_state.special_hole = set_special_hole(
                                        game_state.scoring_zones
                                    )
                                # Save zones to persist changes
                                save_zones(game_state)
                                # Refresh the menu display
                                game_state.menu_cache = None
                                show_notification(
                                    game_state, f"Deleted zone {zone_index + 1}"
                                )
                                return True
                        except (ValueError, IndexError) as e:
                            logger.error(f"Error deleting zone: {e}")
                            show_notification(
                                game_state, "Error deleting zone", is_error=True
                            )
                        return True

                    # Handle edit zone pagination
                    elif action == "prev_edit_zone_page":
                        if hasattr(game_state, "edit_zones_current_page"):
                            game_state.edit_zones_current_page = max(
                                1, game_state.edit_zones_current_page - 1
                            )
                            game_state.menu_cache = None
                            return True
                        return False

                    elif action == "next_edit_zone_page":
                        if hasattr(game_state, "edit_zones_current_page"):
                            # Calculate total pages
                            total_zones = len(getattr(game_state, "scoring_zones", []))
                            items_per_page = getattr(
                                game_state, "edit_zones_items_per_page", 8
                            )
                            total_pages = max(
                                1, (total_zones + items_per_page - 1) // items_per_page
                            )

                            game_state.edit_zones_current_page = min(
                                total_pages, game_state.edit_zones_current_page + 1
                            )
                            game_state.menu_cache = None
                            return True
                        return False

                    # Handle saving zone points after editing
                    elif action == "save_zone_points":
                        try:
                            if hasattr(game_state, "editing_zone_index") and hasattr(
                                game_state, "editing_zone_points_input"
                            ):
                                zone_index = game_state.editing_zone_index
                                points_input = game_state.editing_zone_points_input

                                # Validate points input
                                if points_input and points_input.isdigit():
                                    points = int(points_input)
                                    # Update the zone's points value (5th element in tuple)
                                    x, y, w, h, _ = game_state.scoring_zones[zone_index]
                                    game_state.scoring_zones[zone_index] = (
                                        x,
                                        y,
                                        w,
                                        h,
                                        points,
                                    )

                                    # Save zones to persist changes
                                    save_zones(game_state)
                                    game_state.has_edited_zone_points = True

                                    # Reset editing state
                                    game_state.editing_zone_mode = None
                                    game_state.editing_zone_index = None
                                    game_state.editing_zone_points_input = None

                                    game_state.menu_cache = None
                                    show_notification(
                                        game_state,
                                        f"Updated zone {zone_index + 1} points to {points}",
                                    )
                                else:
                                    show_notification(
                                        game_state,
                                        "Invalid points value, must be a number",
                                        is_error=True,
                                    )

                            return True
                        except Exception as e:
                            logger.error(f"Error saving zone points: {e}")
                            show_notification(
                                game_state, "Error saving zone points", is_error=True
                            )
                            return True

                    # Share highlight to platform
                    elif action.startswith("share_highlight_"):
                        if (
                            hasattr(game_state, "replay_manager")
                            and game_state.replay_manager
                        ):
                            parts = action.split("_")
                            if (
                                len(parts) >= 5
                            ):  # share_highlight_replayid_index_platform
                                replay_id = parts[2]
                                highlight_index = int(parts[3])
                                platform = parts[4]

                                # Get the selected format if available
                                export_format = game_state.replay_sharing.get(
                                    "selected_format", "MP4"
                                )  # Indentation fixed

                                # Correctly indent the try block for highlight sharing
                                try:
                                    # Set status in UI
                                    if hasattr(game_state, "replay_sharing"):
                                        game_state.replay_sharing["export_status"] = (
                                            f"Preparing highlight for {platform}..."
                                        )
                                        game_state.replay_sharing["export_progress"] = (
                                            0.1
                                        )
                                        game_state.menu_cache = None  # Force UI update

                                    show_notification(
                                        game_state,
                                        f"Preparing highlight for {platform}...",
                                        duration=2.0,
                                    )  # Indentation fixed

                                    # First extract the highlight
                                    video_path = (
                                        game_state.replay_manager.extract_highlight(
                                            replay_id, highlight_index
                                        )
                                    )

                                    if video_path:
                                        # Update UI
                                        if hasattr(game_state, "replay_sharing"):
                                            game_state.replay_sharing[
                                                "export_status"
                                            ] = f"Sharing highlight to {platform}..."
                                            game_state.replay_sharing[
                                                "export_progress"
                                            ] = 0.5
                                            game_state.replay_sharing[
                                                "last_export_path"
                                            ] = video_path
                                            game_state.menu_cache = None

                                        show_notification(
                                            game_state,
                                            f"Sharing highlight to {platform}...",
                                            duration=2.0,
                                        )

                                        # Now use the appropriate sharing method for the platform
                                        if platform == "Discord":
                                            # Handle Discord sharing
                                            # Similar to share_to_Discord code but for highlights
                                            pass
                                        elif platform == "Share Link":
                                            # Handle Google Drive sharing
                                            # Similar to share_to_Share_Link code but for highlights
                                            pass
                                        elif platform == "YouTube":
                                            # Handle YouTube sharing
                                            # Similar to share_to_YouTube code but for highlights
                                            pass
                                        else:
                                            # Local sharing
                                            show_notification(
                                                game_state,
                                                f"Highlight saved to: {video_path}",
                                                duration=3.0,
                                            )

                                            if hasattr(game_state, "replay_sharing"):
                                                game_state.replay_sharing[
                                                    "export_status"
                                                ] = f"Highlight saved: {video_path}"
                                                game_state.replay_sharing[
                                                    "export_progress"
                                                ] = 1.0
                                    else:  # This else corresponds to 'if video_path:'
                                        # Failed to extract highlight
                                        if hasattr(game_state, "replay_sharing"):
                                            game_state.replay_sharing[
                                                "export_status"
                                            ] = "Error extracting highlight"
                                            game_state.replay_sharing[
                                                "export_progress"
                                            ] = 0.0
                                            game_state.menu_cache = (
                                                None  # Update cache on error too
                                            )

                                        show_notification(
                                            game_state,
                                            "Error extracting highlight",
                                            is_error=True,
                                        )
                                # Ensure this except block matches the try block above
                                except Exception as e:
                                    logger.error(f"Error sharing highlight: {e}")

                                    if hasattr(game_state, "replay_sharing"):
                                        game_state.replay_sharing["export_status"] = (
                                            f"Error: {str(e)}"
                                        )
                                        game_state.replay_sharing["export_progress"] = (
                                            0.0
                                        )
                                        game_state.menu_cache = (
                                            None  # Update cache on error
                                        )

                                    show_notification(
                                        game_state,
                                        "Error sharing highlight",
                                        is_error=True,
                                    )
                        # This return should be outside the 'if len(parts) >= 5' block but inside the outer 'if'
                        return True  # Return True because the action was processed

            # If click wasn't handled by any item after the loop
            if (
                not volume_adjusted
            ):  # Only reset feedback if not a volume slider interaction
                # Check if click feedback state exists before attempting to reset
                if hasattr(game_state, "click_feedback_state"):
                    game_state.click_feedback_state = None
            # Break the loop as the click has been processed (or determined not to be on an item)
            break  # Exit the loop once a click is processed on an item

        else:  # Click is outside the current item bounds, continue checking other items
            # Optional: Log that this specific item was not clicked
            # logger.debug(f"Click outside item {action}")
            pass  # Continue to the next item in the reversed list

    # Restore the logic that was previously misplaced
    # If the loop completes without finding a clicked item within the menu bounds
    if 0 <= relative_x < menu_w and 0 <= relative_y < menu_h:
        # Click was inside the menu area but not on any interactive element checked
        logger.debug("Click inside menu bounds, but no specific item was hit.")
        # Optionally reset feedback state here if needed
        # if hasattr(game_state, 'click_feedback_state'):
        #     game_state.click_feedback_state = None
    else:
        # Click was outside the menu bounds entirely
        logger.debug("Click outside menu bounds.")
        if hasattr(game_state, "click_feedback_state"):
            game_state.click_feedback_state = None

    # Return False if the click was not handled by any menu item or specific action button
    return False
