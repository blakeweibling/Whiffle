"""
Utility functions for the Whiffle Tracker project.

This module provides helper functions for mouse event handling and resource cleanup.
"""

import cv2
import numpy as np
import logging
import pygame
from typing import Any, Tuple, Optional

from constants import UIConstants  # Updated to class-based import
from menu import reset_game, save_zones, clear_zones
from leaderboard import Leaderboard  # For type hinting

# Use existing logger
logger = logging.getLogger(__name__)

def _process_drawing_event(event: int, x: int, y: int, game_state: Any) -> None:
    """Process mouse events for drawing scoring zones."""
    if event == cv2.EVENT_LBUTTONDOWN:
        game_state.drawing = True
        game_state.start_x, game_state.start_y = x, y
        if game_state.debug_mode:
            logger.info(f"Drawing started at ({x}, {y})")
    elif event == cv2.EVENT_MOUSEMOVE and game_state.drawing:
        game_state.temp_zone = (game_state.start_x, game_state.start_y, x - game_state.start_x, y - game_state.start_y)
    elif event == cv2.EVENT_LBUTTONUP:
        game_state.drawing = False
        if game_state.temp_zone:
            x1, y1, w, h = game_state.temp_zone
            x = min(x1, x1 + w)
            y = min(y1, y1 + h)
            w = abs(w)
            h = abs(h)
            game_state.temp_zone = (x, y, w, h)
            if game_state.debug_mode:
                logger.info(f"Drawing ended, zone created: ({x}, {y}, {w}, {h})")

def _check_menu_button_click(x: int, y: int, game_state: Any) -> bool:
    """Check if the menu button was clicked and activate the menu."""
    if (UIConstants.MENU_BUTTON_X <= x <= UIConstants.MENU_BUTTON_X + UIConstants.MENU_BUTTON_WIDTH and  # Updated
        UIConstants.MENU_BUTTON_Y <= y <= UIConstants.MENU_BUTTON_Y + UIConstants.MENU_BUTTON_HEIGHT):  # Updated
        game_state.menu_active = True
        game_state.menu_pos_x = (UIConstants.WINDOW_WIDTH - game_state.menu_width) // 2  # Updated
        game_state.menu_pos_y = (UIConstants.WINDOW_HEIGHT - game_state.menu_height) // 2  # Updated
        if game_state.debug_mode:
            logger.info("Menu button clicked, opening menu")
        return True
    return False

def _handle_menu_close_click(menu_x: int, menu_y: int, game_state: Any) -> bool:
    """Handle clicking the close button on the menu."""
    if (game_state.menu_width - 30 <= menu_x <= game_state.menu_width and 
        0 <= menu_y <= 30):
        game_state.menu_active = False
        game_state.submenu_active = None
        game_state.submenu_items = []
        game_state.dragging_menu = False  # Reset dragging state
        if game_state.debug_mode:
            logger.info("Close button clicked, closing menu")
        return True
    return False

def _start_menu_drag(menu_x: int, menu_y: int, x: int, y: int, game_state: Any) -> bool:
    """Start dragging the menu if the title bar is clicked."""
    if 0 <= menu_x <= game_state.menu_width and 0 <= menu_y <= 30:
        game_state.dragging_menu = True
        game_state.drag_start_x = x
        game_state.drag_start_y = y
        if game_state.debug_mode:
            logger.info(f"Started dragging menu at ({x}, {y})")
        return True
    return False

def _handle_menu_item_click(menu_x: int, menu_y: int, game_state: Any) -> None:
    """Handle clicks on main menu items."""
    if not game_state.menu_items:
        logger.warning("No menu items defined in game state")
        return
    my_offset = -110  # Pre-compute adjustment
    for mx, my, mw, mh, label, _ in game_state.menu_items:
        adjusted_my = my + my_offset
        if mx <= menu_x <= mx + mw and adjusted_my <= menu_y <= adjusted_my + mh:
            if game_state.debug_mode:
                logger.info(f"Menu item clicked: {label} at ({mx}, {adjusted_my})")
            game_state.submenu_active = label
            if label == "File":
                game_state.submenu_items = [
                    (10, 60, UIConstants.SUBMENU_WIDTH, UIConstants.SUBMENU_HEIGHT, "New Game", lambda: reset_game(game_state)),  # Updated
                    (10, 100, UIConstants.SUBMENU_WIDTH, UIConstants.SUBMENU_HEIGHT, "Save Zones", lambda: save_zones(game_state.scoring_zones)),  # Updated
                    (10, 140, UIConstants.SUBMENU_WIDTH, UIConstants.SUBMENU_HEIGHT, "Clear Zones", lambda: clear_zones(game_state.scoring_zones)),  # Updated
                    (10, 180, UIConstants.SUBMENU_WIDTH, UIConstants.SUBMENU_HEIGHT, "Exit", lambda: clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on))  # Updated
                ]
            elif label == "Players":
                game_state.submenu_items = []  # Populated in draw_menu_window
            elif label == "Settings":
                game_state.submenu_items = []  # Populated in draw_menu_window
            elif label in ["Help", "FAQ", "About", "Leaderboard", "Achievements"]:
                game_state.submenu_items = []
            break

def _handle_submenu_item_click(menu_x: int, menu_y: int, game_state: Any) -> None:
    """Handle clicks on submenu items."""
    if not game_state.submenu_items:
        return
    for item in game_state.submenu_items:
        if len(item) == 6:  # Non-toggle items
            smx, smy, smw, smh, label, action = item
            if smx <= menu_x <= smx + smw and smy <= menu_y <= smy + smh:
                if game_state.debug_mode:
                    logger.info(f"Submenu item clicked: {label} at ({smx}, {smy})")
                result = action()
                if label == "Clear Zones":
                    game_state.scoring_zones = result
                game_state.menu_active = False
                game_state.submenu_active = None
                game_state.submenu_items = []
                if game_state.debug_mode:
                    logger.info("Menu closed after submenu action")
                break
        else:  # Toggle items
            smx, smy, smw, smh, label, action, toggle_x, toggle_y, toggle_w, toggle_h = item
            if toggle_x <= menu_x <= toggle_x + toggle_w and smy <= menu_y <= smy + smh:
                if game_state.debug_mode:
                    logger.info(f"Toggle button clicked: {label} at ({toggle_x}, {smy})")
                action()
                break

def _process_menu_event(event: int, x: int, y: int, game_state: Any) -> None:
    """Process mouse events for menu interactions."""
    if event == cv2.EVENT_LBUTTONDOWN:
        if not game_state.menu_active and _check_menu_button_click(x, y, game_state):
            return
        if not hasattr(game_state, 'menu_active') or not game_state.menu_active:
            return
        menu_x = x - game_state.menu_pos_x
        menu_y = y - game_state.menu_pos_y
        if _handle_menu_close_click(menu_x, menu_y, game_state) or _start_menu_drag(menu_x, menu_y, x, y, game_state):
            return
        _handle_menu_item_click(menu_x, menu_y, game_state)
        if game_state.submenu_active:
            _handle_submenu_item_click(menu_x, menu_y, game_state)
    elif event in (cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONUP):
        _handle_menu_dragging(event, x, y, game_state)

def _handle_menu_dragging(event: int, x: int, y: int, game_state: Any) -> None:
    """Handle mouse events for dragging the menu window."""
    if event == cv2.EVENT_MOUSEMOVE and game_state.dragging_menu:
        dx = x - game_state.drag_start_x
        dy = y - game_state.drag_start_y
        new_x = game_state.menu_pos_x + dx
        new_y = game_state.menu_pos_y + dy
        game_state.menu_pos_x = max(0, min(new_x, UIConstants.WINDOW_WIDTH - game_state.menu_width))  # Updated
        game_state.menu_pos_y = max(0, min(new_y, UIConstants.WINDOW_HEIGHT - game_state.menu_height))  # Updated
        if game_state.menu_pos_x in (0, UIConstants.WINDOW_WIDTH - game_state.menu_width) or \
           game_state.menu_pos_y in (0, UIConstants.WINDOW_HEIGHT - game_state.menu_height):  # Updated
            logger.debug(f"Menu hit boundary at ({game_state.menu_pos_x}, {game_state.menu_pos_y})")
        game_state.drag_start_x = x
        game_state.drag_start_y = y
        if game_state.debug_mode:
            logger.debug(f"Dragging menu to ({game_state.menu_pos_x}, {game_state.menu_pos_y})")
    elif event == cv2.EVENT_LBUTTONUP:
        game_state.dragging_menu = False
        if game_state.debug_mode:
            logger.info("Stopped dragging menu")

def mouse_callback(event: int, x: int, y: int, flags: int, game_state: Any) -> None:
    """
    Handle mouse events for drawing scoring zones or interacting with the main game window.
    """
    if game_state.debug_mode:
        logger.debug(f"Mouse event: {event} at ({x}, {y})")
    if not hasattr(game_state, 'drawing_mode') or not hasattr(game_state, 'menu_active'):
        logger.warning("Invalid game state for mouse handling")
        return
    if game_state.drawing_mode:
        _process_drawing_event(event, x, y, game_state)
    else:
        if event == cv2.EVENT_LBUTTONDOWN and game_state.debug_mode:
            logger.info(f"Main window click at ({x}, {y})")
        _process_menu_event(event, x, y, game_state)

def clean_exit(
    cap: cv2.VideoCapture,
    background_music: Optional[pygame.mixer.Sound] = None,
    background_music_on: bool = False
) -> None:
    """
    Cleanly exit the game by releasing resources.
    """
    logger.info("Cleaning up and exiting game...")
    if cap and hasattr(cap, 'isOpened') and cap.isOpened():
        try:
            cap.release()
            logger.debug("Camera released")
        except cv2.error as e:
            logger.error(f"Failed to release camera: {e}")
    if background_music and background_music_on:
        try:
            background_music.stop()
            logger.debug("Background music stopped")
        except pygame.error as e:
            logger.error(f"Failed to stop background music: {e}")
    try:
        cv2.destroyAllWindows()
        logger.debug("All windows destroyed")
    except cv2.error as e:
        logger.error(f"Failed to destroy windows: {e}")
    try:
        pygame.mixer.quit()
        logger.debug("Pygame mixer quit")
    except pygame.error as e:
        logger.error(f"Failed to quit Pygame mixer: {e}")
    logger.info("Resources released, exiting program.")
    raise SystemExit