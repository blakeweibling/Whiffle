"""
Submenu rendering and logic for the Whiffle Tracker project.

This module contains functions to render and manage the submenus within the main game menu,
including settings, help, FAQ, about, leaderboard, players, and achievements.
"""

import cv2
import numpy as np
import logging
from typing import List, Tuple, Callable, Any

from constants import UIConstants
from menu_utils import _draw_button, show_splash_on_click
from utils import mouse_callback

logger = logging.getLogger(__name__)

class ToggleItem:
    """Represents a toggleable menu item with state and action."""
    def __init__(self, label: str, get_state: Callable[[], bool], action: Callable[[], None]):
        self.label = label
        self.get_state = get_state
        self.action = action

def _draw_settings_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Settings submenu with toggle items."""
    settings_items = [
        ToggleItem("Game Sounds", lambda: game_state.game_sounds_on, 
                   lambda: setattr(game_state, 'game_sounds_on', not game_state.game_sounds_on)),
        ToggleItem("Background Music", lambda: game_state.background_music_on, 
                   lambda: [setattr(game_state, 'background_music_on', not game_state.background_music_on), 
                            game_state.toggle_background_music()]),
        ToggleItem("Enable Ball Tracking", lambda: game_state.ball_tracking_on, 
                   lambda: setattr(game_state, 'ball_tracking_on', not game_state.ball_tracking_on)),
        ToggleItem("Show Scoring Zones", lambda: game_state.show_scoring_zones, 
                   lambda: setattr(game_state, 'show_scoring_zones', not game_state.show_scoring_zones)),  # New toggle item
        ToggleItem("Calibrate White Ball", lambda: game_state.calibrating_color == "white", 
                   lambda: [setattr(game_state, 'calibrating_color', "white" if game_state.calibrating_color != "white" else None),
                            setattr(game_state, 'calibration_point', None),
                            setattr(game_state, 'calibration_hsv', None)]),
        ToggleItem("Calibrate Red Ball", lambda: game_state.calibrating_color == "red", 
                   lambda: [setattr(game_state, 'calibrating_color', "red" if game_state.calibrating_color != "red" else None),
                            setattr(game_state, 'calibration_point', None),
                            setattr(game_state, 'calibration_hsv', None)])
    ]
    y_offset = 60
    game_state.submenu_items = []
    for i, item in enumerate(settings_items):
        smx, smy = 10, y_offset + i * UIConstants.SUBMENU_Y_OFFSET
        cv2.putText(menu_frame, item.label, (smx + 5, smy + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, UIConstants.WHITE, 1)
        if item.label not in ["Calibrate White Ball", "Calibrate Red Ball"]:
            toggle_x, toggle_y = smx + 550, smy
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

def _draw_game_mode_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Game Mode submenu with Classic and Timed options."""
    cv2.putText(menu_frame, "Game Mode", (50, 80), 
                cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.FONT_THICKNESS)
    game_state.submenu_items = [
        (10, 120, UIConstants.SUBMENU_WIDTH, UIConstants.SUBMENU_HEIGHT, "Classic", lambda: game_state.set_game_mode("classic")),
        (10, 160, UIConstants.SUBMENU_WIDTH, UIConstants.SUBMENU_HEIGHT, "Timed", lambda: game_state.set_game_mode("timed"))
    ]
    for smx, smy, smw, smh, label, _ in game_state.submenu_items:
        color = UIConstants.GREEN if game_state.game_mode == label.lower() else UIConstants.CV2_BLUE
        _draw_button(menu_frame, smx, smy, smw, smh, label, color)

def _draw_help_submenu(menu_frame: np.ndarray) -> None:
    """Draw the Help submenu."""
    cv2.putText(menu_frame, "Help", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.FONT_THICKNESS)
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
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, 1)

def _draw_faq_submenu(menu_frame: np.ndarray) -> None:
    """Draw the FAQ submenu."""
    cv2.putText(menu_frame, "FAQ", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.FONT_THICKNESS)
    faq_text = [
        "Q: Why isn't my score saving?",
        "A: Check internet for online save, else saved locally.",
        "Q: How do I reset the game?",
        "A: Use 'New Game' in File menu.",
        "Q: Can I turn off sounds?",
        "A: Yes, in Settings menu.",
        "Q: Why no red ball detection?",
        "A: Red ball detection is now always enabled!"
    ]
    for i, line in enumerate(faq_text):
        cv2.putText(menu_frame, line, (50, 120 + i * 30),
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, 1)

def _draw_about_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the About submenu with logo and splash action."""
    cv2.putText(menu_frame, "Whiffle Tracker v9.4", (50, 200), 
                cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.FONT_THICKNESS)
    cv2.putText(menu_frame, "Ideas by Blake Weibling", (50, 250), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, UIConstants.WHITE, 1)
    cv2.putText(menu_frame, "Coding help from Grok", (50, 280), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, UIConstants.WHITE, 1)
    logo = cv2.imread("logo.png")
    logo_y, logo_x = 320, 50
    if logo is not None:
        logo = cv2.resize(logo, UIConstants.LOGO_SIZE)
        menu_frame[logo_y:logo_y+UIConstants.LOGO_SIZE[1], logo_x:logo_x+UIConstants.LOGO_SIZE[0]] = logo
        game_state.submenu_items = [(logo_x, logo_y, 50, 50, "Show Splash", 
                                    lambda: show_splash_on_click(menu_frame, game_state, mouse_callback, game_state))]
    else:
        logger.warning("Failed to load logo.png")
        cv2.putText(menu_frame, "Logo unavailable", (logo_x, logo_y + 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.RED, 1)

def _draw_leaderboard_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Leaderboard submenu, limiting to top 3 scores to reduce text rendering (Change 6)."""
    cv2.putText(menu_frame, "Leaderboard (Classic)", (50, 80), 
                cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.FONT_THICKNESS)
    scores, online = game_state.leaderboard.get_top_scores("classic", 5)
    if not scores:
        cv2.putText(menu_frame, "No scores yet!", (50, 150), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, UIConstants.WHITE, 1)
    else:
        # Limit to top 3 scores to reduce text rendering (Change 6)
        for i, score in enumerate(scores[:3]):  # Only show top 3 scores
            player_name = score.get('player_name', score.get('initials', 'Unknown'))
            text = f"{i + 1}. {player_name} - {score['score']}"
            cv2.putText(menu_frame, text, (50, 120 + i * 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, 1)
        if len(scores) > 3:
            cv2.putText(menu_frame, "...", (50, 120 + 3 * 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, 1)
        cv2.putText(menu_frame, f"Source: {'Online' if online else 'Local'}", 
                    (50, 120 + min(len(scores), 3) * 30 + 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, UIConstants.YELLOW, 1)

def _draw_players_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Players submenu."""
    cv2.putText(menu_frame, "Players", (50, 80), 
                cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.FONT_THICKNESS)
    game_state.submenu_items = []
    for i, player in enumerate(game_state.players):
        text = f"{i + 1}. {player.name} {'(Current)' if i == game_state.current_player_index else ''}"
        cv2.putText(menu_frame, text, (50, 120 + i * 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, 
                    UIConstants.GREEN if i == game_state.current_player_index else UIConstants.WHITE, 1)
        edit_x, edit_y = 300, 120 + i * 30
        edit_w, edit_h = 100, UIConstants.SUBMENU_HEIGHT
        _draw_button(menu_frame, edit_x, edit_y, edit_w, edit_h, "Edit Name", UIConstants.CV2_BLUE)
        game_state.submenu_items.append((edit_x, edit_y, edit_w, edit_h, f"Edit_{i}", lambda idx=i: _edit_player_name(game_state, idx)))

    y_offset = 120 + len(game_state.players) * 30
    game_state.submenu_items.extend([
        (10, y_offset, UIConstants.SUBMENU_WIDTH, UIConstants.SUBMENU_HEIGHT, 
         "Add Player", lambda: _add_player(game_state)),
        (10, y_offset + 40, UIConstants.SUBMENU_WIDTH, UIConstants.SUBMENU_HEIGHT, 
         "Switch Player", lambda: _switch_player(game_state))
    ])
    for smx, smy, smw, smh, label, _ in game_state.submenu_items[len(game_state.players):]:
        _draw_button(menu_frame, smx, smy, smw, smh, label, UIConstants.CV2_BLUE)

def _edit_player_name(game_state: Any, player_idx: int) -> None:
    """Prompt the user to edit the player's name using keyboard input."""
    if game_state.camera_available:
        ret, frame = game_state.cap.read()
        if not ret:
            logger.error("Camera read failed during name edit, using static frame")
            frame = game_state.static_frame
    else:
        frame = game_state.static_frame

    input_frame = frame.copy()
    new_name = ""
    prompt = "Enter new name (Enter to confirm, Esc to cancel): "
    input_active = True

    while input_active:
        input_frame = frame.copy()
        cv2.putText(input_frame, prompt + new_name, (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.YELLOW, UIConstants.FONT_THICKNESS)
        cv2.imshow(UIConstants.WINDOW_NAME, input_frame)

        key = cv2.waitKey(0) & 0xFF

        if key == 13:  # Enter key to confirm
            if new_name.strip():
                game_state.players[player_idx].name = new_name.strip()
                logger.info(f"Player {player_idx + 1} renamed to {new_name}")
            else:
                logger.info(f"Player {player_idx + 1} name not changed (empty input)")
            input_active = False
        elif key == 27:  # Esc key to cancel
            logger.info(f"Player {player_idx + 1} name edit cancelled")
            input_active = False
        elif key == 8 and new_name:  # Backspace to delete last character
            new_name = new_name[:-1]
        elif 32 <= key <= 126:  # Printable ASCII characters
            new_name += chr(key)

def _add_player(game_state: Any) -> None:
    """Add a new player and refresh the submenu."""
    game_state.add_player(f"Player {len(game_state.players) + 1}")
    game_state.submenu_active = "Players"

def _switch_player(game_state: Any) -> None:
    """Switch to the next player and refresh the submenu."""
    game_state.switch_player()
    game_state.submenu_active = "Players"
    game_state.achievement_notification = f"Switched to {game_state.get_current_player().name}"
    game_state.achievement_notification_timer = 3.0

def _draw_achievements_submenu(menu_frame: np.ndarray, game_state: Any) -> None:
    """Draw the Achievements submenu, limiting to first 3 achievements to reduce text rendering (Change 6)."""
    try:
        logger.debug("Drawing Achievements submenu")
        cv2.putText(menu_frame, "Achievements", (50, 80), 
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.FONT_THICKNESS)
        logger.debug(f"game_state.achievements: {game_state.achievements}")
        if not game_state.achievements:
            logger.debug("No achievements found")
            cv2.putText(menu_frame, "No achievements yet!", (50, 150), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, UIConstants.WHITE, 1)
        else:
            # Limit to first 3 achievements to reduce text rendering (Change 6)
            for i, achievement in enumerate(game_state.achievements[:3]):  # Only show first 3 achievements
                logger.debug(f"Processing achievement {i}: {achievement}")
                text = f"{achievement.name}: {achievement.description}"
                logger.debug(f"Text to display: {text}")
                color = UIConstants.GREEN if achievement.unlocked else UIConstants.WHITE
                logger.debug(f"Color: {color}")
                cv2.putText(menu_frame, text, (50, 120 + i * 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, color, 1)
            if len(game_state.achievements) > 3:
                cv2.putText(menu_frame, "...", (50, 120 + 3 * 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, 1)
    except Exception as e:
        logger.error(f"Error drawing Achievements submenu: {e}")
        raise