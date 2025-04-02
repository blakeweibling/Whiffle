# utils_zone_helpers.py

import cv2
import logging
import numpy as np # Import numpy for calculations
import math # Import math for page calculation if needed later
from typing import Tuple, Optional

# Imports needed for zone helpers
from constants import UIConstants, ScoringConstants
from game_state import GameState, CurrentGameState
from scoring import _zones_overlap
from game_state_utils import set_special_hole # Used after adding/editing zones

logger = logging.getLogger(__name__)

# --- Helper: Find which handle/area of a zone is clicked ---
def _get_zone_click_location(x: int, y: int, zone_rect: Tuple[int, int, int, int]) -> Optional[str]:
    """Determine if a click is on a corner, edge, or inside a zone."""
    zx, zy, zw, zh = zone_rect
    handle_size = UIConstants.ZONE_EDIT_HANDLE_SIZE
    half_handle = handle_size // 2

    # Check corners first (priority)
    if abs(x - zx) < half_handle and abs(y - zy) < half_handle: return "resize_tl" #
    if abs(x - (zx + zw)) < half_handle and abs(y - zy) < half_handle: return "resize_tr" #
    if abs(x - zx) < half_handle and abs(y - (zy + zh)) < half_handle: return "resize_bl" #
    if abs(x - (zx + zw)) < half_handle and abs(y - (zy + zh)) < half_handle: return "resize_br" #

    # Check if inside
    if zx < x < zx + zw and zy < y < zy + zh: return "move" #

    return None #


# --- Helper: Process Interactive Zone Editing Mouse Events ---
def _process_zone_editing_event(event: int, x: int, y: int, game_state: GameState) -> bool: #
    """Process mouse events during interactive zone move/resize."""
    handled = False
    zone_idx = game_state.selected_zone_for_edit

    if zone_idx is None or not (0 <= zone_idx < len(game_state.scoring_zones)): #
        logger.warning("Zone editing event called with invalid selected_zone_for_edit.")
        # Reset state just in case
        game_state.zone_editing_action = None
        game_state.drag_start_pos = None
        game_state.selected_zone_for_edit = None #
        game_state.original_zone_on_drag_start = None #
        game_state.current_state = game_state.previous_state or CurrentGameState.MENU # Revert state
        return False #

    current_zone = game_state.scoring_zones[zone_idx] #
    zx, zy, zw, zh, zp = current_zone # Unpack including points

    min_size = ScoringConstants.MIN_ZONE_SIZE # Minimum width/height

    if event == cv2.EVENT_LBUTTONDOWN: #
        click_location = _get_zone_click_location(x, y, (zx, zy, zw, zh)) #
        if click_location: #
            game_state.zone_editing_action = click_location #
            game_state.drag_start_pos = (x, y) #
            game_state.original_zone_on_drag_start = current_zone # Store original state
            logger.info(f"Starting zone edit action: {click_location} for zone {zone_idx} at ({x},{y})") #
            handled = True #
        else: #
            # Click outside the selected zone while in editing mode could perhaps cancel?
            logger.debug("Click outside selected zone during ZONE_EDITING state.") #
            pass # Currently, clicking outside does nothing, requires ESC

    elif event == cv2.EVENT_MOUSEMOVE: #
        if game_state.drag_start_pos and game_state.zone_editing_action: #
            drag_x_start, drag_y_start = game_state.drag_start_pos #
            dx = x - drag_x_start #
            dy = y - drag_y_start #

            new_x, new_y, new_w, new_h = zx, zy, zw, zh #
            action = game_state.zone_editing_action #

            if action == "move": #
                new_x = zx + dx #
                new_y = zy + dy #
            elif action == "resize_tl": #
                new_x = zx + dx #
                new_y = zy + dy #
                new_w = zw - dx #
                new_h = zh - dy #
            elif action == "resize_tr": #
                new_y = zy + dy #
                new_w = zw + dx #
                new_h = zh - dy #
            elif action == "resize_bl": #
                new_x = zx + dx #
                new_w = zw - dx #
                new_h = zh + dy #
            elif action == "resize_br": #
                new_w = zw + dx #
                new_h = zh + dy #

            # Enforce minimum size during resize
            if action.startswith("resize"): #
                new_w = max(min_size, new_w) #
                new_h = max(min_size, new_h) #
                # Adjust position if width/height change affected top-left corner
                if action == "resize_tl": #
                    new_x = zx + zw - new_w #
                    new_y = zy + zh - new_h #
                elif action == "resize_tr": #
                    new_y = zy + zh - new_h #
                elif action == "resize_bl": #
                    new_x = zx + zw - new_w #

            # Update the zone in the list *directly* for immediate feedback
            game_state.scoring_zones[zone_idx] = (new_x, new_y, new_w, new_h, zp) #
            # Update drag start position for next move event
            game_state.drag_start_pos = (x, y) #
            handled = True # Mouse move during drag is handled

    elif event == cv2.EVENT_LBUTTONUP: #
        if game_state.drag_start_pos and game_state.zone_editing_action: #
            logger.info(f"Finished zone edit action: {game_state.zone_editing_action} for zone {zone_idx}") #

            # Final validation and overlap check
            final_zone = game_state.scoring_zones[zone_idx] #
            fx, fy, fw, fh, fp = final_zone #

            # Check for overlap with OTHER zones
            other_zones = [z for i, z in enumerate(game_state.scoring_zones) if i != zone_idx] #
            if _zones_overlap(final_zone[:4], other_zones): #
                logger.warning(f"Edited zone {zone_idx} overlaps with another zone. Reverting.") #
                game_state.show_notification("Edit causes overlap! Reverted.", is_error=True, duration=3.0) #
                # Revert to original state
                if game_state.original_zone_on_drag_start: #
                    game_state.scoring_zones[zone_idx] = game_state.original_zone_on_drag_start #
                else: #
                     # Should not happen, but maybe delete if revert fails? Risky.
                     logger.error("Cannot revert overlapping zone, original state missing!") #
            else: #
                logger.debug(f"Zone {zone_idx} updated to: {final_zone}") #
                # Update special hole if necessary
                game_state.special_hole = set_special_hole(game_state.scoring_zones) #
                # Consider auto-saving here?
                # save_zones(game_state)
                # game_state.show_notification(f"Zone {zone_idx+1} Updated")

            # Reset editing state
            game_state.zone_editing_action = None #
            game_state.drag_start_pos = None #
            game_state.original_zone_on_drag_start = None #
            # Stay in ZONE_EDITING state until user explicitly exits via ESC or menu
            handled = True #

    return handled #


# --- Drawing Event Processing ---
def _process_drawing_event(event: int, x: int, y: int, game_state: GameState) -> None: #
    """Process mouse events for drawing scoring zones."""
    if event == cv2.EVENT_LBUTTONDOWN: #
        if game_state.drawing: #
            game_state.start_x, game_state.start_y = x, y #
            game_state.temp_zone = None #
            game_state.drawing_points_input = "" #
            logger.info(f"Drawing started at ({x}, {y}). Points input reset.") #

    elif event == cv2.EVENT_MOUSEMOVE: #
        if game_state.drawing and game_state.start_x is not None and game_state.start_y is not None: #
            x1 = min(game_state.start_x, x) #
            y1 = min(game_state.start_y, y) #
            w = abs(game_state.start_x - x) #
            h = abs(game_state.start_y - y) #
            game_state.temp_zone = (x1, y1, w, h) #

    elif event == cv2.EVENT_LBUTTONUP: #
        if game_state.drawing: #
            if game_state.temp_zone: #
                x1, y1, w, h = game_state.temp_zone #
                if ( #
                    w > ScoringConstants.MIN_ZONE_SIZE #
                    and h > ScoringConstants.MIN_ZONE_SIZE #
                ):
                    points_str = game_state.drawing_points_input #
                    try: #
                        points = int(points_str) #
                        if not (1 <= points <= ScoringConstants.MAX_POINTS): #
                            logger.warning(f"Entered points {points} out of range (1-{ScoringConstants.MAX_POINTS}). Using default {ScoringConstants.DEFAULT_POINTS}.") #
                            points = ScoringConstants.DEFAULT_POINTS #
                            game_state.show_notification(f"Points must be 1-{ScoringConstants.MAX_POINTS}. Using default.", is_error=True, duration=3.0) #
                        else: #
                            logger.info(f"Using entered points: {points}") #
                    except ValueError: #
                        logger.warning(f"Invalid points input '{points_str}'. Using default {ScoringConstants.DEFAULT_POINTS}.") #
                        points = ScoringConstants.DEFAULT_POINTS #
                        if points_str: #
                             game_state.show_notification(f"Invalid points input. Using default.", is_error=True, duration=3.0) #

                    new_zone = (x1, y1, w, h, points) #
                    if not _zones_overlap(new_zone[:4], game_state.scoring_zones): #
                        game_state.scoring_zones.append(new_zone) #
                        game_state.special_hole = set_special_hole(game_state.scoring_zones) #
                        logger.info(f"Added scoring zone: {new_zone}") #
                        game_state.show_notification(f"Zone Added ({points} pts)") #
                    else: #
                        logger.warning(f"Drawn zone overlaps existing zone. Not adding.") #
                        game_state.show_notification("Zone Overlaps!", is_error=True) #
                else: #
                    logger.warning(f"Ignoring drawn zone with width/height <= {ScoringConstants.MIN_ZONE_SIZE}.") #
                    game_state.show_notification("Zone too small", is_error=True) #
            else: #
                logger.debug("LBUTTONUP received but no temp_zone defined (likely just a click).") #

            game_state.drawing = False #
            game_state.temp_zone = None #
            game_state.start_x = None #
            game_state.start_y = None #
            game_state.drawing_points_input = "" #
            logger.info("Drawing finished.") #