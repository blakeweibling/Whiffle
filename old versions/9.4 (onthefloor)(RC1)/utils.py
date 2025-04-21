"""
Utility functions for the Whiffle Tracker project.

This module provides helper functions for mouse event handling and resource cleanup.
"""

import cv2
import numpy as np
import logging
import pygame
from typing import Any, Tuple, Optional

from constants import WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_NAME
from menu import reset_game, save_zones, clear_zones
from leaderboard import Leaderboard  # For type hinting

# Use existing logger
logger = logging.getLogger(__name__)

# Menu button configuration (from menu.py)
MENU_BUTTON_X: int = 10
MENU_BUTTON_Y: int = 70
MENU_BUTTON_WIDTH: int = 140
MENU_BUTTON_HEIGHT: int = 30

def _handle_drawing(event: int, x: int, y: int, game_state: Any) -> None:
    """
    Handle mouse events for drawing scoring zones.

    Args:
        event: OpenCV mouse event type.
        x: X-coordinate of the mouse event.
        y: Y-coordinate of the mouse event.
        game_state: Game state object.
    """
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

def _handle_menu_click(x: int, y: int, game_state: Any) -> None:
    """
    Handle mouse clicks for menu interactions.

    Args:
        x: X-coordinate of the mouse event.
        y: Y-coordinate of the mouse event.
        game_state: Game state object.
    """
    if not game_state.menu_active:
        if MENU_BUTTON_X <= x <= MENU_BUTTON_X + MENU_BUTTON_WIDTH and MENU_BUTTON_Y <= y <= MENU_BUTTON_Y + MENU_BUTTON_HEIGHT:
            game_state.menu_active = True
            game_state.menu_pos_x = (WINDOW_WIDTH - game_state.menu_width) // 2
            game_state.menu_pos_y = (WINDOW_HEIGHT - game_state.menu_height) // 2
            if game_state.debug_mode:
                logger.info("Click for Menu button clicked, opening menu")
        return

    menu_x = x - game_state.menu_pos_x
    menu_y = y - game_state.menu_pos_y
    if game_state.debug_mode:
        logger.debug(f"Adjusted menu coordinates: menu_x={menu_x}, menu_y={menu_y}")

    # Check for close button click
    if (game_state.menu_width - 30 <= menu_x <= game_state.menu_width) and (0 <= menu_y <= 30):
        game_state.menu_active = False
        game_state.submenu_active = None
        game_state.submenu_items = []
        if game_state.debug_mode:
            logger.info("Close button clicked, closing menu")
        return

    # Check for dragging the menu
    if 0 <= menu_x <= game_state.menu_width and 0 <= menu_y <= 30:
        game_state.dragging_menu = True
        game_state.drag_start_x = x
        game_state.drag_start_y = y
        if game_state.debug_mode:
            logger.info(f"Started dragging menu at ({x}, {y})")
        return

    # Check for main menu item clicks
    for i, (mx, my, mw, mh, label, _) in enumerate(game_state.menu_items):
        adjusted_my = my - 110
        if mx <= menu_x <= mx + mw and adjusted_my <= menu_y <= adjusted_my + mh:
            if game_state.debug_mode:
                logger.info(f"Menu item clicked: {label} at ({mx}, {adjusted_my})")
            game_state.submenu_active = label
            if label == "File":
                game_state.submenu_items = [
                    (10, 60, 580, 30, "New Game", lambda: reset_game(game_state)),
                    (10, 100, 580, 30, "Save Zones", lambda: save_zones(game_state.scoring_zones)),
                    (10, 140, 580, 30, "Clear Zones", lambda: clear_zones(game_state.scoring_zones)),
                    (10, 180, 580, 30, "Exit", lambda: clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on))
                ]
            elif label == "Settings":
                game_state.submenu_items = []  # Populated in draw_menu_window
            elif label in ["Help", "FAQ", "About", "Leaderboard"]:
                game_state.submenu_items = []
            break

    # Check for submenu item clicks
    if game_state.submenu_active and game_state.submenu_items:
        for item in game_state.submenu_items:
            if len(item) == 6:  # Non-toggle items (e.g., File, About)
                smx, smy, smw, smh, label, action = item
                # Adjust smy to match the drawing offset in draw_menu_window
                adjusted_smy = smy  # Remove the -110 offset to match draw_menu_window
                if game_state.debug_mode:
                    logger.debug(f"Checking submenu item: {label} at ({smx}, {adjusted_smy}) to ({smx + smw}, {adjusted_smy + smh})")
                    logger.debug(f"Mouse click at: menu_x={menu_x}, menu_y={menu_y}")
                if smx <= menu_x <= smx + smw and adjusted_smy <= menu_y <= adjusted_smy + smh:
                    if game_state.debug_mode:
                        logger.info(f"Submenu item clicked: {label} at ({smx}, {adjusted_smy})")
                    result = action()
                    if label == "New Game":
                        if game_state.debug_mode:
                            logger.info("New Game action executed")
                    elif label == "Save Zones":
                        if game_state.debug_mode:
                            logger.info("Save Zones action executed")
                    elif label == "Clear Zones":
                        game_state.scoring_zones = result  # clear_zones returns the cleared list
                        if game_state.debug_mode:
                            logger.info("Clear Zones action executed")
                    elif label == "Exit":
                        if game_state.debug_mode:
                            logger.info("Exit action executed")
                    elif label == "Show Splash":
                        result  # Execute splash screen display
                        if game_state.debug_mode:
                            logger.info("Show Splash action executed")
                    # Close the menu after the action
                    game_state.menu_active = False
                    game_state.submenu_active = None
                    game_state.submenu_items = []
                    if game_state.debug_mode:
                        logger.info("Menu closed after submenu action")
                    break
            else:  # Toggle items (e.g., Settings)
                smx, smy, smw, smh, label, action, toggle_x, toggle_y, toggle_w, toggle_h = item
                if toggle_x <= menu_x <= toggle_x + toggle_w and smy <= menu_y <= smy + smh:
                    if game_state.debug_mode:
                        logger.info(f"Toggle button clicked: {label} at ({toggle_x}, {smy})")
                    action()
                    break

def _handle_menu_dragging(event: int, x: int, y: int, game_state: Any) -> None:
    """
    Handle mouse events for dragging the menu window.

    Args:
        event: OpenCV mouse event type.
        x: X-coordinate of the mouse event.
        y: Y-coordinate of the mouse event.
        game_state: Game state object.
    """
    if event == cv2.EVENT_MOUSEMOVE and game_state.dragging_menu:
        dx = x - game_state.drag_start_x
        dy = y - game_state.drag_start_y
        game_state.menu_pos_x += dx
        game_state.menu_pos_y += dy
        game_state.menu_pos_x = max(0, min(game_state.menu_pos_x, WINDOW_WIDTH - game_state.menu_width))
        game_state.menu_pos_y = max(0, min(game_state.menu_pos_y, WINDOW_HEIGHT - game_state.menu_height))
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

    Args:
        event: OpenCV mouse event type.
        x: X-coordinate of the mouse event.
        y: Y-coordinate of the mouse event.
        flags: OpenCV mouse event flags.
        game_state: Game state object.
    """
    if game_state.debug_mode:
        logger.debug(f"main_mouse_callback: Initial menu_active={game_state.menu_active}, "
                     f"submenu_active={game_state.submenu_active}, len(submenu_items)={len(game_state.submenu_items)}")

    if game_state.drawing_mode:
        _handle_drawing(event, x, y, game_state)
    else:
        if event == cv2.EVENT_LBUTTONDOWN:
            if game_state.debug_mode:
                logger.info(f"Main window click at ({x}, {y})")
            _handle_menu_click(x, y, game_state)
        else:
            _handle_menu_dragging(event, x, y, game_state)

    if game_state.debug_mode:
        logger.debug(f"main_mouse_callback: Final menu_active={game_state.menu_active}, "
                     f"submenu_active={game_state.submenu_active}, len(submenu_items)={len(game_state.submenu_items)}")

def clean_exit(
    cap: cv2.VideoCapture,
    background_music: Optional[pygame.mixer.Sound] = None,
    background_music_on: bool = False
) -> None:
    """
    Cleanly exit the game by releasing resources.

    Args:
        cap: Video capture object to release.
        background_music: Background music sound object to stop.
        background_music_on: Flag indicating if background music is playing.

    Raises:
        SystemExit: To signal the program to exit.
    """
    logger.info("Cleaning up and exiting game...")
    if cap and cap.isOpened():
        cap.release()
        logger.debug("Camera released")
    if background_music and background_music_on:
        background_music.stop()
        logger.debug("Background music stopped")
    cv2.destroyAllWindows()
    logger.debug("All windows destroyed")
    pygame.mixer.quit()
    logger.debug("Pygame mixer quit")
    logger.info("Resources released, exiting program.")
    raise SystemExit