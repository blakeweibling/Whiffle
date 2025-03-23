"""
Menu management for the Whiffle Tracker project.

This module provides functions to manage the game menu, including resetting the game,
saving/loading scoring zones, and drawing the menu interface.
"""

import cv2
import numpy as np
import logging
import json
import os
from typing import List, Tuple, Dict, Callable, Optional, Any

from constants import (
    GREEN, RED, YELLOW, WHITE, BLUE,
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_NAME,
    MENU_WIDTH, MENU_HEIGHT, MENU_BUTTON_X, MENU_BUTTON_Y,
    MENU_BUTTON_WIDTH, MENU_BUTTON_HEIGHT,
    FONT_SCALE_SMALL, FONT_SCALE_MEDIUM, FONT_SCALE_LARGE,
    FONT_THICKNESS, SCORING_ZONES_FILE, LOGO_SIZE
)

# Set up logging
logger = logging.getLogger(__name__)

def _draw_button(
    frame: np.ndarray,
    x: int,
    y: int,
    width: int,
    height: int,
    label: str,
    color: Tuple[int, int, int],
    font_scale: float = FONT_SCALE_SMALL
) -> None:
    """
    Draw a button with a label on the frame.

    Args:
        frame: Frame to draw on.
        x: X-coordinate of the button's top-left corner.
        y: Y-coordinate of the button's top-left corner.
        width: Width of the button.
        height: Height of the button.
        label: Text label for the button.
        color: BGR color of the button.
        font_scale: Font scale for the label.
    """
    cv2.rectangle(frame, (x, y), (x + width, y + height), color, -1)
    cv2.putText(frame, label, (x + 5, y + 20),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, WHITE, 1)

def reset_game(game_state: Any) -> None:
    """
    Reset the game state fully.

    Args:
        game_state: Game state object to reset.
    """
    game_state.score = 0
    game_state.scoring_zones.clear()
    game_state.tracked_balls.clear()
    game_state.scored_balls.clear()
    game_state.scored_positions.clear()
    game_state.potential_small_balls.clear()
    game_state.next_ball_id = 0
    game_state.menu_active = False
    game_state.submenu_active = None
    game_state.submenu_items = []
    game_state.game_timer = None
    game_state.ball_trails.clear()
    if game_state.debug_mode:
        logger.info("Game reset: All state variables cleared, menu closed")

def save_zones(scoring_zones: List[Tuple[int, int, int, int, int]]) -> None:
    """
    Save scoring zones to a JSON file.

    Args:
        scoring_zones: List of scoring zones to save.
    """
    try:
        with open(SCORING_ZONES_FILE, "w") as f:
            json.dump(scoring_zones, f)
        logger.info(f"Scoring zones saved to {SCORING_ZONES_FILE}")
    except Exception as e:
        logger.error(f"Failed to save scoring zones to {SCORING_ZONES_FILE}: {e}")

def load_zones(scoring_zones: List[Tuple[int, int, int, int, int]]) -> List[Tuple[int, int, int, int, int]]:
    """
    Load scoring zones from a JSON file if it exists.

    Args:
        scoring_zones: Current list of scoring zones to extend.

    Returns:
        Updated list of scoring zones.
    """
    if os.path.exists(SCORING_ZONES_FILE):
        if os.path.getsize(SCORING_ZONES_FILE) == 0:
            logger.warning(f"{SCORING_ZONES_FILE} is empty, treating as if it doesn't exist")
            return scoring_zones
        try:
            with open(SCORING_ZONES_FILE, "r") as f:
                loaded_zones = json.load(f)
                scoring_zones.extend(loaded_zones)
            logger.info(f"Scoring zones loaded from {SCORING_ZONES_FILE}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to load scoring zones: Invalid JSON - {e}")
            return scoring_zones
        except Exception as e:
            logger.error(f"Failed to load scoring zones: {e}")
            return scoring_zones
    else:
        logger.info(f"{SCORING_ZONES_FILE} does not exist, starting with empty zones")
    return scoring_zones

def clear_zones(scoring_zones: List[Tuple[int, int, int, int, int]]) -> List[Tuple[int, int, int, int, int]]:
    """
    Clear saved scoring zones and reset the current zones.

    Args:
        scoring_zones: Current list of scoring zones to clear.

    Returns:
        Empty list of scoring zones.
    """
    scoring_zones.clear()
    if os.path.exists(SCORING_ZONES_FILE):
        try:
            os.remove(SCORING_ZONES_FILE)
            logger.info(f"Scoring zones file {SCORING_ZONES_FILE} removed")
        except Exception as e:
            logger.error(f"Failed to remove {SCORING_ZONES_FILE}: {e}")
    logger.info("Scoring zones cleared")
    return scoring_zones

def draw_menu(frame: np.ndarray, game_state: Any) -> None:
    """
    Draw the menu button on the main game window.

    Args:
        frame: Frame to draw on.
        game_state: Game state object (unused but kept for consistency).
    """
    _draw_button(frame, MENU_BUTTON_X, MENU_BUTTON_Y, MENU_BUTTON_WIDTH, MENU_BUTTON_HEIGHT,
                 "Click for Menu", BLUE)

def show_splash_on_click(frame: np.ndarray, game_state: Any) -> None:
    """
    Display splash screen until keypress or mouse click.

    Args:
        frame: Current frame to restore after splash screen.
        game_state: Game state object (used for debug mode).
    """
    splash = cv2.imread("splash.png")
    if splash is None:
        logger.error("Failed to load splash.png for About menu, skipping splash screen")
        return
    splash = cv2.resize(splash, (WINDOW_WIDTH, WINDOW_HEIGHT))

    while True:
        cv2.imshow(WINDOW_NAME, splash)
        key = cv2.waitKey(20) & 0xFF
        if key != 255 or cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) <= 0:
            break
    cv2.imshow(WINDOW_NAME, frame)

def draw_menu_window(frame: np.ndarray, game_state: Any) -> None:
    """
    Draw the menu as an overlay within the main game window.

    Args:
        frame: Frame to draw on.
        game_state: Game state object containing menu properties.
    """
    if game_state.debug_mode:
        logger.debug(f"draw_menu_window: menu_active={game_state.menu_active}, "
                     f"submenu_active={game_state.submenu_active}, len(submenu_items)={len(game_state.submenu_items)}")

    if not game_state.menu_active:
        return

    # Create menu overlay
    menu_frame = np.zeros((game_state.menu_height, game_state.menu_width, 3), dtype=np.uint8)
    menu_frame[:] = (50, 50, 50)  # Dark gray background
    overlay = np.ones_like(menu_frame, dtype=np.uint8) * 255
    alpha = 0.8
    menu_frame = cv2.addWeighted(menu_frame, alpha, overlay, 1 - alpha, 0)

    # Draw title bar and close button
    _draw_button(menu_frame, 0, 0, game_state.menu_width, 30, "Menu", BLUE, FONT_SCALE_MEDIUM)
    _draw_button(menu_frame, game_state.menu_width - 30, 0, 30, 30, "X", RED, FONT_SCALE_MEDIUM)

    # Draw main menu items
    for mx, my, mw, mh, label, _ in game_state.menu_items:
        _draw_button(menu_frame, mx, my - 110, mw, mh, label, BLUE)

    # Settings submenu configuration
    settings_items = [
        {
            "label": "Start Timer",
            "get_state": lambda: True,
            "action": lambda: setattr(game_state, 'game_timer', game_state.time_limit),
            "is_toggle": False
        },
        {
            "label": "Game Sounds",
            "get_state": lambda: game_state.game_sounds_on,
            "action": lambda: setattr(game_state, 'game_sounds_on', not game_state.game_sounds_on),
            "is_toggle": True
        },
        {
            "label": "Background Music",
            "get_state": lambda: game_state.background_music_on,
            "action": lambda: [
                setattr(game_state, 'background_music_on', not game_state.background_music_on),
                game_state.toggle_background_music()
            ],
            "is_toggle": True
        },
        {
            "label": "Red Ball Detection",
            "get_state": lambda: game_state.red_ball_detection_on,
            "action": lambda: setattr(game_state, 'red_ball_detection_on', not game_state.red_ball_detection_on),
            "is_toggle": True
        },
        {
            "label": "White Ball Detection",
            "get_state": lambda: game_state.white_ball_detection_on,
            "action": lambda: setattr(game_state, 'white_ball_detection_on', not game_state.white_ball_detection_on),
            "is_toggle": True
        }
    ]

    # Draw content based on submenu_active
    if game_state.submenu_active == "Settings":
        y_offset = 60
        game_state.submenu_items = []
        for i, item in enumerate(settings_items):
            smx, smy = 10, y_offset + i * 50
            smw, smh = 580, 30
            cv2.putText(menu_frame, item["label"], (smx + 5, smy + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE_SMALL, WHITE, 1)
            if item["is_toggle"]:
                toggle_x, toggle_y = smx + 400, smy
                toggle_w, toggle_h = 50, 30
                state = item["get_state"]()
                toggle_color = GREEN if state else RED
                toggle_text = "ON" if state else "OFF"
                _draw_button(menu_frame, toggle_x, toggle_y, toggle_w, toggle_h, toggle_text, toggle_color)
                game_state.submenu_items.append((smx, smy, smw, smh, item["label"], item["action"],
                                                toggle_x, toggle_y, toggle_w, toggle_h))
            else:
                _draw_button(menu_frame, smx, smy, smw, smh, item["label"], BLUE)
                game_state.submenu_items.append((smx, smy, smw, smh, item["label"], item["action"]))
    elif game_state.submenu_active == "Help":
        cv2.putText(menu_frame, "Help", (50, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE_LARGE, GREEN, FONT_THICKNESS)
        help_text = [
            "Welcome to Whiffle Tracker!",
            "How to Play:",
            "- Press 's' to draw scoring zones.",
            "- Drag to set zone size, release to set points.",
            "- Press Enter to confirm, 'c' to cancel.",
            "- Balls entering zones score points.",
            "Controls:",
            "- 'q': Quit game",
            "- 'd': Toggle debug mode",
            "- Click 'Click for Menu' for options."
        ]
        for i, line in enumerate(help_text):
            cv2.putText(menu_frame, line, (50, 120 + i * 30),
                        cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE_MEDIUM, WHITE, 1)
    elif game_state.submenu_active == "FAQ":
        cv2.putText(menu_frame, "FAQ", (50, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE_LARGE, GREEN, FONT_THICKNESS)
        faq_text = [
            "Q: Why isn't my score saving?",
            "A: Check internet for online save, else saved locally.",
            "Q: How do I reset the game?",
            "A: Use 'New Game' in File menu.",
            "Q: Can I turn off sounds?",
            "A: Yes, in Settings menu.",
            "Q: Why no red ball detection?",
            "A: Coming soon in a future update!"
        ]
        for i, line in enumerate(faq_text):
            cv2.putText(menu_frame, line, (50, 120 + i * 30),
                        cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE_MEDIUM, WHITE, 1)
    elif game_state.submenu_active == "About":
        cv2.putText(menu_frame, "Whiffle Tracker v9.4", (50, 200),
                    cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE_LARGE, GREEN, FONT_THICKNESS)
        cv2.putText(menu_frame, "Ideas by Blake Weibling", (50, 250),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, WHITE, 1)
        cv2.putText(menu_frame, "Coding help from Grok", (50, 280),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, WHITE, 1)
        logo = cv2.imread("logo.png")
        if logo is not None:
            logo = cv2.resize(logo, LOGO_SIZE)
            logo_y, logo_x = 320, 50
            menu_frame[logo_y:logo_y+LOGO_SIZE[1], logo_x:logo_x+LOGO_SIZE[0]] = logo
            game_state.submenu_items = [(logo_x, logo_y, 50, 50, "Show Splash",
                                        lambda: show_splash_on_click(frame, game_state))]
        else:
            logger.warning("Failed to load logo.png, skipping logo display")
    elif game_state.submenu_active == "Leaderboard":
        cv2.putText(menu_frame, "Leaderboard (Classic)", (50, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE_LARGE, GREEN, FONT_THICKNESS)
        scores, online = game_state.leaderboard.get_top_scores("classic", 5)
        if not scores:
            cv2.putText(menu_frame, "No scores yet!", (50, 150),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, WHITE, 1)
        else:
            for i, score in enumerate(scores):
                text = f"{i + 1}. {score['initials']} - {score['score']}"
                cv2.putText(menu_frame, text, (50, 120 + i * 30),
                            cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE_MEDIUM, WHITE, 1)
            cv2.putText(menu_frame, f"Source: {'Online' if online else 'Local'}", (50, 120 + len(scores) * 30 + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE_SMALL, YELLOW, 1)
    elif game_state.submenu_active:
        for smx, smy, smw, smh, label, _ in game_state.submenu_items:
            _draw_button(menu_frame, smx, smy, smw, smh, label, BLUE)

    # Overlay menu onto frame
    x1, y1 = game_state.menu_pos_x, game_state.menu_pos_y
    x2, y2 = x1 + game_state.menu_width, y1 + game_state.menu_height
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(frame.shape[1], x2)
    y2 = min(frame.shape[0], y2)
    menu_h, menu_w = y2 - y1, x2 - x1
    if menu_h > 0 and menu_w > 0:
        roi = frame[y1:y2, x1:x2]
        menu_frame_resized = menu_frame[:menu_h, :menu_w]
        alpha = 0.8
        beta = 1.0 - alpha
        cv2.addWeighted(menu_frame_resized, alpha, roi, beta, 0, roi)