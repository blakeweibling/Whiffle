# menu.py
"""
Menu rendering and utility functions for the Whiffle Tracker project.

This module provides functions to manage the main game menu, including rendering the menu button,
overlaying the menu on the game window, and handling game state utilities like resetting the game
and managing scoring zones.
"""

import cv2
import numpy as np
import logging
import json
import os
from typing import List, Tuple, Any

# Import constants, including the new MenuConstants
from constants import UIConstants, GameConstants, ScoringConstants, MenuConstants
from menu_utils import _draw_button

# Import submenu functions here to avoid circular imports within _draw_menu_content
from submenus import draw_submenu

# Import GameState directly for type hinting if needed, but avoid direct use that causes cycles
from game_state import GameState, CurrentGameState

# Set up logging
logger = logging.getLogger(__name__)


def reset_game(game_state: GameState) -> None:
    """
    Reset the game state fully. Includes resetting effects lists.
    """
    logger.info("Resetting game state...")
    game_state.score = 0
    game_state.tracked_balls.clear()
    game_state.scored_balls.clear()
    game_state.scored_positions.clear()
    game_state.next_ball_id = 0
    game_state.submenu_active = None
    game_state.submenu_items = []
    game_state.game_timer = None
    # game_state.ball_trails.clear() # Removed this line
    game_state.ball_states.clear()
    game_state.previous_ball_states.clear()
    game_state.achievement_notification = None
    game_state.achievement_notification_timer = 0.0
    game_state.balls_in_zone.clear()
    game_state.ball_scored_zones.clear()
    game_state.ball_positions_history.clear()
    game_state.ball_zone_history.clear()
    game_state.zone_cooldown.clear()
    game_state.win_condition_met = False
    game_state.edit_zones_current_page = 1

    # Reset menu editing states
    game_state.editing_zone_index = None
    game_state.editing_zone_mode = None
    game_state.editing_zone_points_input = None
    game_state.editing_player_index = None
    game_state.editing_player_mode = None
    game_state.editing_player_name_input = None
    game_state.selected_zone_for_edit = None
    game_state.zone_editing_action = None
    game_state.drag_start_pos = None
    game_state.original_zone_on_drag_start = None

    # Reset session flags
    game_state.special_hole_hit_this_session = False
    game_state.low_time_warning_played = False

    # --- CORRECTED: Reset Fun Mode effects ---
    if hasattr(game_state, "active_trails"):
        game_state.active_trails.clear()
    if hasattr(game_state, "active_explosions"):
        game_state.active_explosions.clear()
    # --- END CORRECTION ---

    if game_state.players and 0 <= game_state.current_player_index < len(
        game_state.players
    ):
        game_state.players[game_state.current_player_index].reset_score()
    else:
        logger.warning("Player index out of bounds or no players during reset.")

    if game_state.game_mode == "timed":
        game_state.game_timer = GameConstants.TIMED_MODE_DURATION
        logger.info(
            f"Timed mode selected. Timer set to {game_state.game_timer} seconds."
        )
    elif game_state.game_mode == "survival": # <-- Added this block
        game_state.game_timer = GameConstants.SURVIVAL_MODE_START_TIME
        logger.info(
            f"Survival mode reset. Timer set to {game_state.game_timer} seconds."
        )
    else:
        game_state.game_timer = None

    if hasattr(game_state, "_load_initial_state") and callable(
        game_state._load_initial_state
    ):
        game_state._load_initial_state()  # Reload zones and high score
    else:
        logger.warning(
            "Cannot reload initial state during reset, _load_initial_state not found."
        )

    logger.info(
        f"Game state reset for player: {game_state.get_current_player().name}, Mode: {game_state.game_mode}"
    )


def save_zones(game_state: GameState) -> None:
    """Save the current scoring zones to a JSON file."""
    # ... (function unchanged) ...
    try:
        with open(GameConstants.ZONES_FILE, "w") as f:
            json.dump(game_state.scoring_zones, f, indent=4)
        logger.info(f"Scoring zones saved to {GameConstants.ZONES_FILE}")
        game_state.show_notification("Zones Saved")
    except IOError as e:
        logger.error(f"Error saving scoring zones: {e}")
        game_state.show_notification("Error Saving Zones", is_error=True)


def load_zones(game_state: GameState) -> None:
    """Load scoring zones from a JSON file."""
    # ... (function unchanged) ...
    if os.path.exists(GameConstants.ZONES_FILE):
        try:
            if os.path.getsize(GameConstants.ZONES_FILE) == 0:
                logger.warning(f"{GameConstants.ZONES_FILE} is empty. Clearing zones.")
                game_state.scoring_zones = []
                game_state.special_hole = None
                return

            with open(GameConstants.ZONES_FILE, "r") as f:
                loaded_data = json.load(f)
            if isinstance(loaded_data, list) and all(
                isinstance(z, list) and len(z) == 5 for z in loaded_data
            ):
                game_state.scoring_zones = [
                    (int(z[0]), int(z[1]), int(z[2]), int(z[3]), int(z[4]))
                    for z in loaded_data
                ]
                logger.info(f"Scoring zones loaded from {GameConstants.ZONES_FILE}")
                game_state.show_notification("Zones Loaded")
                from game_state_utils import set_special_hole

                game_state.special_hole = set_special_hole(game_state.scoring_zones)
            else:
                logger.error(
                    "Invalid format in zones file. Expected list of [x, y, w, h, points]."
                )
                game_state.show_notification("Invalid Zone File Format", is_error=True)
                game_state.scoring_zones = []
                game_state.special_hole = None

        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Error loading scoring zones: {e}")
            game_state.show_notification("Error Loading Zones", is_error=True)
            game_state.scoring_zones = []
            game_state.special_hole = None
    else:
        logger.warning(f"Scoring zones file '{GameConstants.ZONES_FILE}' not found.")
        game_state.scoring_zones = []
        game_state.special_hole = None


def clear_zones(game_state: GameState) -> None:
    """Clear all scoring zones."""
    # ... (function unchanged) ...
    game_state.scoring_zones.clear()
    game_state.special_hole = None
    if hasattr(game_state, "scoring_zones_cache"):
        game_state.scoring_zones_cache = []
    if os.path.exists(GameConstants.ZONES_FILE):
        try:
            os.remove(GameConstants.ZONES_FILE)
        except OSError as e:
            logger.error(f"Failed to remove zones file: {e}")
    logger.info("All scoring zones cleared.")
    game_state.show_notification("All Zones Cleared")


def flush_scoring_zones(game_state: GameState) -> None:
    """Writes current scoring zones to disk (used by clean_exit)."""
    # ... (function unchanged) ...
    logger.debug("Flushing scoring zones (calling save_zones)...")
    save_zones(game_state)


def draw_menu(frame: np.ndarray, game_state: GameState) -> None:
    """Draw the menu button on the frame."""
    # ... (function unchanged) ...
    if game_state.current_state == CurrentGameState.PLAYING:
        _draw_button(
            frame,
            UIConstants.MENU_BUTTON_X,
            UIConstants.MENU_BUTTON_Y,
            UIConstants.MENU_BUTTON_WIDTH,
            UIConstants.MENU_BUTTON_HEIGHT,
            "Menu",
            UIConstants.CV2_BLUE,
        )


def _draw_menu_content(menu_frame: np.ndarray, game_state: GameState) -> None:
    """Draw the actual content of the menu or submenu onto the menu_frame."""
    # ... (function unchanged) ...
    if game_state.submenu_active:
        draw_submenu(menu_frame, game_state)
    else:
        cv2.putText(
            menu_frame,
            "Main Menu",
            (30, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            UIConstants.FONT_SCALE_LARGE,
            UIConstants.WHITE,
            UIConstants.FONT_THICKNESS,
        )
        game_state.submenu_items.clear()
        y_offset = 80
        item_height = 35
        for label, action_key in MenuConstants.MAIN_MENU_ITEMS:
            item_rect = (20, y_offset, game_state.menu_width - 40, item_height)
            _draw_button(
                menu_frame,
                item_rect[0],
                item_rect[1],
                item_rect[2],
                item_rect[3],
                label,
                UIConstants.CV2_BLUE,
                font_scale=UIConstants.FONT_SCALE_MEDIUM,
            )
            game_state.submenu_items.append((item_rect, action_key, label))
            y_offset += item_height + 5


def draw_menu_window(frame: np.ndarray, game_state: GameState) -> None:
    """Draw the menu as an overlay, using caching."""
    # ... (function largely unchanged, ensuring dynamic height calculation logic remains) ...
    if game_state.current_state != CurrentGameState.MENU:
        return

    default_height = 450
    if game_state.submenu_active == "edit_zones":
        items_per_page = game_state.edit_zones_items_per_page
        list_item_height = 30 + 5
        header_height = 80
        pagination_controls_height = 35 + 5
        back_button_height = 35 + 20
        content_height = (
            header_height
            + (items_per_page * list_item_height)
            + pagination_controls_height
            + back_button_height
        )
        game_state.menu_height = max(300, min(default_height, int(content_height)))
    elif not game_state.submenu_active:
        game_state.menu_height = 60 + len(MenuConstants.MAIN_MENU_ITEMS) * 40 + 20
    elif not hasattr(game_state, "menu_height") or game_state.menu_height < 100:
        game_state.menu_height = default_height  # Fallback if submenu doesn't set it

    game_state.menu_width = 600  # Keep consistent width

    # Cache key generation...
    current_item_actions_tuple = tuple(
        item[1] if len(item) > 1 else None for item in game_state.submenu_items
    )
    cache_key_parts = [
        game_state.submenu_active,
        current_item_actions_tuple,
        game_state.editing_zone_index,
        game_state.editing_zone_mode,
        game_state.editing_zone_points_input,
        game_state.editing_player_index,
        game_state.editing_player_mode,
        game_state.editing_player_name_input,
        game_state.current_player_index,
    ]
    if game_state.submenu_active == "edit_zones":
        cache_key_parts.append(game_state.edit_zones_current_page)
    cache_key = tuple(cache_key_parts)

    menu_frame = None
    # Cache check...
    if (
        hasattr(game_state, "menu_cache")
        and game_state.menu_cache is not None
        and game_state.menu_cache_key == cache_key
        and game_state.menu_cache.shape[0] == game_state.menu_height
        and game_state.menu_cache.shape[1] == game_state.menu_width
    ):
        menu_frame = game_state.menu_cache
        # if game_state.debug_mode: logger.debug("Using cached menu frame.") # Optional debug
    else:
        # if game_state.debug_mode: logger.debug("Redrawing menu content.") # Optional debug
        menu_frame = None  # Ensure redraw if cache is invalid

    # Redraw if needed...
    if menu_frame is None:
        menu_height_to_use = max(100, game_state.menu_height)
        menu_frame = np.zeros(
            (menu_height_to_use, game_state.menu_width, 3), dtype=np.uint8
        )
        game_state.menu_height = menu_height_to_use
        _draw_menu_content(menu_frame, game_state)  # Draw content

        # Draw close button onto the menu frame *before* caching
        try:
            pad = UIConstants.MENU_CLOSE_BUTTON_PADDING
            size = UIConstants.MENU_CLOSE_BUTTON_SIZE
            btn_x1 = game_state.menu_width - pad - size
            btn_y1 = pad
            btn_x2 = game_state.menu_width - pad
            btn_y2 = pad + size
            line_pad = size // 4
            cv2.line(
                menu_frame,
                (btn_x1 + line_pad, btn_y1 + line_pad),
                (btn_x2 - line_pad, btn_y2 - line_pad),
                UIConstants.MENU_CLOSE_BUTTON_COLOR,
                UIConstants.MENU_CLOSE_BUTTON_THICKNESS,
            )
            cv2.line(
                menu_frame,
                (btn_x1 + line_pad, btn_y2 - line_pad),
                (btn_x2 - line_pad, btn_y1 + line_pad),
                UIConstants.MENU_CLOSE_BUTTON_COLOR,
                UIConstants.MENU_CLOSE_BUTTON_THICKNESS,
            )
        except Exception as e:
            logger.error(f"Error drawing menu close button: {e}")

        if menu_frame is not None:
            game_state.menu_cache = (
                menu_frame  # Cache the newly drawn frame with close button
            )
            game_state.menu_cache_key = cache_key
        else:
            logger.error("Failed to create menu_frame during redraw.")
            return

    # Blending menu onto main frame...
    start_x = (frame.shape[1] - game_state.menu_width) // 2
    start_y = (frame.shape[0] - game_state.menu_height) // 2
    game_state.menu_pos = (start_x, start_y)
    x1, y1 = game_state.menu_pos
    menu_h, menu_w = menu_frame.shape[0], menu_frame.shape[1]
    x2, y2 = x1 + menu_w, y1 + menu_h
    x1c, y1c = max(0, x1), max(0, y1)
    x2c, y2c = min(frame.shape[1], x2), min(frame.shape[0], y2)
    roi_h, roi_w = y2c - y1c, x2c - x1c
    menu_start_y, menu_start_x = max(0, -y1), max(0, -x1)
    menu_end_y, menu_end_x = menu_start_y + roi_h, menu_start_x + roi_w

    if roi_h > 0 and roi_w > 0 and menu_end_y <= menu_h and menu_end_x <= menu_w:
        try:
            roi = frame[y1c:y2c, x1c:x2c]
            menu_frame_slice = menu_frame[
                menu_start_y:menu_end_y, menu_start_x:menu_end_x
            ]
            if roi.shape == menu_frame_slice.shape:
                alpha = 0.85
                cv2.addWeighted(menu_frame_slice, alpha, roi, 1.0 - alpha, 0, roi)
                cv2.rectangle(
                    frame, (x1c, y1c), (x2c, y2c), UIConstants.WHITE, 2
                )  # Border
            else:
                logger.warning(
                    f"ROI shape {roi.shape} mismatch menu slice {menu_frame_slice.shape}. Fallback draw."
                )
                cv2.rectangle(frame, (x1c, y1c), (x2c, y2c), (50, 50, 50), -1)
        except Exception as e:
            logger.exception(f"Error blending menu: {e}")
            cv2.rectangle(
                frame, (x1c, y1c), (x2c, y2c), (50, 0, 0), -1
            )  # Error fallback
    # ... (rest of blending checks unchanged) ...
    elif roi_h <= 0 or roi_w <= 0:
        logger.debug("Menu overlay ROI has zero or negative size, skipping overlay.")
    else:
        logger.warning(f"Menu slice calculation out-of-bounds, skipping overlay.")
