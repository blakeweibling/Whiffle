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

from constants import UIConstants  # Updated to class-based import

# Set up logging
logger = logging.getLogger(__name__)

class ToggleItem:
    """Represents a toggleable menu item with state and action."""
    def __init__(self, label: str, get_state: Callable[[], bool], action: Callable[[], None]):
        self.label = label
        self.get_state = get_state
        self.action = action

def _draw_button(
    frame: np.ndarray,
    x: int,
    y: int,
    width: int,
    height: int,
    label: str,
    color: Tuple[int, int, int],
    font_scale: float = UIConstants.FONT_SCALE_SMALL  # Updated
) -> None:
    """
    Draw a button with a label on the frame.
    """
    cv2.rectangle(frame, (x, y), (x + width, y + height), color, -1)
    cv2.putText(frame, label, (x + 5, y + 20),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, UIConstants.WHITE, 1)  # Updated

def reset_game(game_state: Any) -> None:
    """
    Reset the game state fully.
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
    # Note: high_score and time_limit not reset to preserve game settings
    if game_state.debug_mode:
        logger.info("Game reset: All state variables cleared, menu closed")

def save_zones(scoring_zones: List[Tuple[int, int, int, int, int]]) -> bool:
    """
    Save scoring zones to a JSON file.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        with open(UIConstants.SCORING_ZONES_FILE, "w", encoding='utf-8') as f:
            json.dump(scoring_zones, f)
        logger.info(f"Scoring zones saved to {UIConstants.SCORING_ZONES_FILE}")
        return True
    except (IOError, PermissionError) as e:
        logger.error(f"Failed to save scoring zones to {UIConstants.SCORING_ZONES_FILE}: {e}")
        return False

def load_zones(scoring_zones: List[Tuple[int, int, int, int, int]]) -> List[Tuple[int, int, int, int, int]]:
    """
    Load scoring zones from a JSON file if it exists.

    Returns:
        Updated list of scoring zones.
    """
    if os.path.exists(UIConstants.SCORING_ZONES_FILE):
        if os.path.getsize(UIConstants.SCORING_ZONES_FILE) == 0:
            logger.warning(f"{UIConstants.SCORING_ZONES_FILE} is empty, treating as if it doesn't exist")
            return scoring_zones
        try:
            with open(UIConstants.SCORING_ZONES_FILE, "r", encoding='utf-8') as f:
                loaded_zones = json.load(f)
                scoring_zones.extend(loaded_zones)
            logger.info(f"Scoring zones loaded from {UIConstants.SCORING_ZONES_FILE}")
        except (json.JSONDecodeError, IOError, PermissionError) as e:
            logger.error(f"Failed to load scoring zones: {e}")
    else:
        logger.info(f"{UIConstants.SCORING_ZONES_FILE} does not exist, starting with empty zones")
    return scoring_zones

def clear_zones(scoring_zones: List[Tuple[int, int, int, int, int]]) -> List[Tuple[int, int, int, int, int]]:
    """
    Clear saved scoring zones and reset the current zones.

    Returns:
        Empty list of scoring zones.
    """
    scoring_zones.clear()
    if os.path.exists(UIConstants.SCORING_ZONES_FILE):
        try:
            os.remove(UIConstants.SCORING_ZONES_FILE)
            logger.info(f"Scoring zones file {UIConstants.SCORING_ZONES_FILE} removed")
        except (IOError, PermissionError) as e:
            logger.error(f"Failed to remove {UIConstants.SCORING_ZONES_FILE}: {e}")
    logger.info("Scoring zones cleared")
    return scoring_zones

def draw_menu(frame: np.ndarray, game_state: Any) -> None:
    """
    Draw the menu button on the main game window.
    """
    _draw_button(frame, UIConstants.MENU_BUTTON_X, UIConstants.MENU_BUTTON_Y,
                 UIConstants.MENU_BUTTON_WIDTH, UIConstants.MENU_BUTTON_HEIGHT,
                 "Click for Menu", UIConstants.CV2_BLUE)  # Updated to use CV2_BLUE

def show_splash_on_click(frame: np.ndarray, game_state: Any) -> None:
    """
    Display splash screen until keypress or mouse click.
    """
    splash = cv2.imread("splash.png")
    if splash is None:
        logger.error("Failed to load splash.png for About menu, skipping splash screen")
        cv2.putText(frame, "Splash unavailable", (50, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.RED, UIConstants.FONT_THICKNESS)  # Updated
        cv2.imshow(UIConstants.WINDOW_NAME, frame)
        cv2.waitKey(1000)  # Show error briefly
        return
    splash = cv2.resize(splash, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))

    while True:
        cv2.imshow(UIConstants.WINDOW_NAME, splash)
        key = cv2.waitKey(20) & 0xFF
        if key != 255 or cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) <= 0:
            break
    cv2.imshow(UIConstants.WINDOW_NAME, frame)

def _create_menu_base(game_state: Any) -> np.ndarray:
    """Create the static base of the menu frame."""
    menu_frame = np.zeros((game_state.menu_height, game_state.menu_width, 3), dtype=np.uint8)
    menu_frame[:] = (50, 50, 50)  # Dark gray background
    overlay = np.ones_like(menu_frame, dtype=np.uint8) * 255
    alpha = 0.8
    menu_frame = cv2.addWeighted(menu_frame, alpha, overlay, 1 - alpha, 0)
    _draw_button(menu_frame, 0, 0, game_state.menu_width, 30, "Menu", UIConstants.CV2_BLUE, UIConstants.FONT_SCALE_MEDIUM)  # Updated
    _draw_button(menu_frame, game_state.menu_width - 30, 0, 30, 30, "X", UIConstants.RED, UIConstants.FONT_SCALE_MEDIUM)  # Updated
    for mx, my, mw, mh, label, _ in game_state.menu_items:
        _draw_button(menu_frame, mx, my - 110, mw, mh, label, UIConstants.CV2_BLUE)  # Updated
    return menu_frame

def _draw_settings_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Settings submenu with toggle items."""
    settings_items = [
        ToggleItem("Start Timer", lambda: True, lambda: setattr(game_state, 'game_timer', game_state.time_limit)),
        ToggleItem("Game Sounds", lambda: game_state.game_sounds_on, 
                   lambda: setattr(game_state, 'game_sounds_on', not game_state.game_sounds_on)),
        ToggleItem("Background Music", lambda: game_state.background_music_on, 
                   lambda: [setattr(game_state, 'background_music_on', not game_state.background_music_on), 
                            game_state.toggle_background_music()]),
        ToggleItem("Red Ball Detection", lambda: game_state.red_ball_detection_on, 
                   lambda: setattr(game_state, 'red_ball_detection_on', not game_state.red_ball_detection_on)),
        ToggleItem("White Ball Detection", lambda: game_state.white_ball_detection_on, 
                   lambda: setattr(game_state, 'white_ball_detection_on', not game_state.white_ball_detection_on))
    ]
    y_offset = 60
    game_state.submenu_items = []
    for i, item in enumerate(settings_items):
        smx, smy = 10, y_offset + i * UIConstants.SUBMENU_Y_OFFSET
        cv2.putText(menu_frame, item.label, (smx + 5, smy + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, UIConstants.WHITE, 1)
        if item.label != "Start Timer":
            toggle_x, toggle_y = smx + 550, smy  # Adjusted from 400 to 550 to fit new menu width
            toggle_w, toggle_h = 50, UIConstants.SUBMENU_HEIGHT
            state = item.get_state()
            toggle_color = UIConstants.GREEN if state else UIConstants.RED
            toggle_text = "ON" if state else "OFF"
            _draw_button(menu_frame, toggle_x, toggle_y, toggle_w, toggle_h, toggle_text, toggle_color)
            game_state.submenu_items.append((smx, smy, UIConstants.SUBMENU_WIDTH, UIConstants.SUBMENU_HEIGHT, item.label, item.action,
                                            toggle_x, toggle_y, toggle_w, toggle_h))
        else:
            _draw_button(menu_frame, smx, smy, UIConstants.SUBMENU_WIDTH, UIConstants.SUBMENU_HEIGHT, item.label, UIConstants.CV2_BLUE)
            game_state.submenu_items.append((smx, smy, UIConstants.SUBMENU_WIDTH, UIConstants.SUBMENU_HEIGHT, item.label, item.action))

def _draw_help_submenu(menu_frame: np.ndarray) -> None:
    """Draw the Help submenu."""
    cv2.putText(menu_frame, "Help", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.FONT_THICKNESS)  # Updated
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
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, 1)  # Updated

def _draw_faq_submenu(menu_frame: np.ndarray) -> None:
    """Draw the FAQ submenu."""
    cv2.putText(menu_frame, "FAQ", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.FONT_THICKNESS)  # Updated
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
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, 1)  # Updated

def _draw_about_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the About submenu with logo and splash action."""
    cv2.putText(menu_frame, "Whiffle Tracker v9.4", (50, 200), 
                cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.FONT_THICKNESS)  # Updated
    cv2.putText(menu_frame, "Ideas by Blake Weibling", (50, 250), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, UIConstants.WHITE, 1)  # Updated
    cv2.putText(menu_frame, "Coding help from Grok", (50, 280), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, UIConstants.WHITE, 1)  # Updated
    logo = cv2.imread("logo.png")
    logo_y, logo_x = 320, 50
    if logo is not None:
        logo = cv2.resize(logo, UIConstants.LOGO_SIZE)
        menu_frame[logo_y:logo_y+UIConstants.LOGO_SIZE[1], logo_x:logo_x+UIConstants.LOGO_SIZE[0]] = logo
        game_state.submenu_items = [(logo_x, logo_y, 50, 50, "Show Splash", 
                                    lambda: show_splash_on_click(menu_frame, game_state))]
    else:
        logger.warning("Failed to load logo.png")
        cv2.putText(menu_frame, "Logo unavailable", (logo_x, logo_y + 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.RED, 1)  # Updated

def _draw_leaderboard_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Leaderboard submenu."""
    cv2.putText(menu_frame, "Leaderboard (Classic)", (50, 80), 
                cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.FONT_THICKNESS)
    scores, online = game_state.leaderboard.get_top_scores("classic", 5)
    if not scores:
        cv2.putText(menu_frame, "No scores yet!", (50, 150), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, UIConstants.WHITE, 1)
    else:
        for i, score in enumerate(scores):
            player_name = score.get('player_name', score.get('initials', 'Unknown'))
            text = f"{i + 1}. {player_name} - {score['score']}"
            cv2.putText(menu_frame, text, (50, 120 + i * 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, 1)
        cv2.putText(menu_frame, f"Source: {'Online' if online else 'Local'}", 
                    (50, 120 + len(scores) * 30 + 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, UIConstants.YELLOW, 1)

def _draw_players_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Players submenu."""
    cv2.putText(menu_frame, "Players", (50, 80), 
                cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.FONT_THICKNESS)
    # Display current players
    for i, player in enumerate(game_state.players):
        text = f"{i + 1}. {player.name}"
        cv2.putText(menu_frame, text, (50, 120 + i * 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, 1)
    # Add buttons
    game_state.submenu_items = [
        (10, 120 + len(game_state.players) * 30, UIConstants.SUBMENU_WIDTH, UIConstants.SUBMENU_HEIGHT, 
         "Add Player", lambda: game_state.add_player(f"Player {len(game_state.players) + 1}")),
        (10, 160 + len(game_state.players) * 30, UIConstants.SUBMENU_WIDTH, UIConstants.SUBMENU_HEIGHT, 
         "Switch Player", lambda: game_state.switch_player())
    ]
    for smx, smy, smw, smh, label, _ in game_state.submenu_items:
        _draw_button(menu_frame, smx, smy, smw, smh, label, UIConstants.CV2_BLUE)

def _draw_achievements_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Achievements submenu."""
    cv2.putText(menu_frame, "Achievements", (50, 80), 
                cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.FONT_THICKNESS)
    if not game_state.achievements:
        cv2.putText(menu_frame, "No achievements yet!", (50, 150), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, UIConstants.WHITE, 1)
    else:
        for i, achievement in enumerate(game_state.achievements):
            text = f"{achievement.name}: {achievement.description}"
            color = UIConstants.GREEN if achievement.unlocked else UIConstants.WHITE
            cv2.putText(menu_frame, text, (50, 120 + i * 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, color, 1)

def _draw_menu_content(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the dynamic content of the menu based on the active submenu."""
    if game_state.submenu_active == "Settings":
        _draw_settings_submenu(menu_frame, game_state)
    elif game_state.submenu_active == "Help":
        _draw_help_submenu(menu_frame)
    elif game_state.submenu_active == "FAQ":
        _draw_faq_submenu(menu_frame)
    elif game_state.submenu_active == "About":
        _draw_about_submenu(menu_frame, game_state)
    elif game_state.submenu_active == "Leaderboard":
        _draw_leaderboard_submenu(menu_frame, game_state)
    elif game_state.submenu_active == "Players":
        _draw_players_submenu(menu_frame, game_state)
    elif game_state.submenu_active == "Achievements":
        _draw_achievements_submenu(menu_frame, game_state)
    elif game_state.submenu_active:
        for smx, smy, smw, smh, label, _ in game_state.submenu_items:
            _draw_button(menu_frame, smx, smy, smw, smh, label, UIConstants.CV2_BLUE)  # Updated

def _overlay_menu(frame: np.ndarray, menu_frame: np.ndarray, game_state: Any) -> None:
    """Overlay the menu onto the main frame."""
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

def draw_menu_window(frame: np.ndarray, game_state: Any) -> None:
    """
    Draw the menu as an overlay within the main game window.
    """
    if game_state.debug_mode:
        logger.debug(f"draw_menu_window: menu_active={game_state.menu_active}, "
                     f"submenu_active={game_state.submenu_active}, len(submenu_items)={len(game_state.submenu_items)}")
    if not game_state.menu_active:
        return
    menu_frame = _create_menu_base(game_state)
    _draw_menu_content(menu_frame, game_state)
    _overlay_menu(frame, menu_frame, game_state)