"""
UI rendering functions for the Whiffle Tracker project.
Manages drawing of UI elements, balls, and splash screen.
"""

import cv2
import numpy as np
import logging
import time
from typing import List, Tuple, Any, Optional

from constants import UIConstants, GameConstants  # Import classes
from scoring import draw_scoring_zones
from menu import draw_menu, draw_menu_window
from utils import clean_exit
from game_state import GameState

logger = logging.getLogger(__name__)

def draw_ui(frame: np.ndarray, game_state: Any) -> None:
    # Display current player's name and score
    current_player = game_state.get_current_player()
    cv2.putText(frame, f"Player: {current_player.name}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, UIConstants.FONT_THICKNESS)
    cv2.putText(frame, f"Score: {current_player.score}  High: {game_state.high_score}", (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.FONT_THICKNESS)

    if game_state.game_timer is not None:
        timer_display = int(max(0, game_state.game_timer))
        cv2.putText(frame, f"Time: {timer_display}", (10, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.YELLOW, UIConstants.FONT_THICKNESS)

    # Display achievement notification
    if game_state.achievement_notification:
        cv2.putText(frame, game_state.achievement_notification, (UIConstants.WINDOW_WIDTH // 2 - 200, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.GREEN, UIConstants.FONT_THICKNESS)

    # Display a warning if running with static image
    if not game_state.camera_available:
        cv2.putText(frame, "Camera unavailable - Using static image", (10, UIConstants.WINDOW_HEIGHT - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.RED, UIConstants.FONT_THICKNESS)

    draw_scoring_zones(frame, game_state.scoring_zones)

    if game_state.temp_zone and game_state.drawing:
        x, y, w, h = game_state.temp_zone
        cv2.rectangle(frame, (x, y), (x + w, y + h), UIConstants.YELLOW, UIConstants.FONT_THICKNESS)

    draw_menu(frame, game_state)
    draw_menu_window(frame, game_state)

def draw_balls(frame: np.ndarray, game_state: Any, tracked_detected_balls: List[Tuple[int, int, float, int]],
               detected_red_balls: List[Tuple[int, int, float]]) -> None:
    for ball_id in list(game_state.ball_trails.keys()):
        game_state.ball_trails[ball_id] = [(x, y, a + 1) for x, y, a in game_state.ball_trails[ball_id] if a < 20]
        if not game_state.ball_trails[ball_id]:
            del game_state.ball_trails[ball_id]

    for x, y, radius, ball_id in tracked_detected_balls:
        is_red = any((x, y, radius) in detected_red_balls for _ in [detected_red_balls]
                     if game_state.red_ball_detection_on)
        game_state.ball_trails.setdefault(ball_id, []).append((x, y, 0))
        for tx, ty, age in game_state.ball_trails.get(ball_id, []):
            alpha = 1 - (age / 20)
            color = UIConstants.CV2_BLUE if is_red else UIConstants.RED
            cv2.circle(frame, (tx, ty), int(radius * (1 - age / 40)), color, 2)

        color = UIConstants.CV2_BLUE if is_red else UIConstants.RED
        cv2.circle(frame, (x, y), int(radius), color, 2)
        cv2.putText(frame, f"ID: {ball_id}", (x + 20, y),
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, color, 1)

def show_splash_screen(supabase_url: str, supabase_key: str) -> Optional[GameState]:
    splash = cv2.imread("splash.png")
    if splash is None:
        logger.error("Failed to load splash.png, skipping splash screen")
        return None

    splash = cv2.resize(splash, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
    cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL)

    start_time = time.time()
    game_state = GameState(supabase_url, supabase_key)

    # Attempt to read the first frame, or use static frame if camera is unavailable
    if game_state.camera_available:
        ret, first_frame = game_state.cap.read()
        if not ret:
            logger.error("Camera failed during splash screen, exiting...")
            clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on)
            return None
    else:
        first_frame = game_state.static_frame
        logger.info("Camera unavailable, using static frame for splash screen transition")

    while time.time() - start_time < GameConstants.SPLASH_DURATION + GameConstants.FADE_DURATION:
        elapsed = time.time() - start_time
        if elapsed < GameConstants.SPLASH_DURATION:
            cv2.imshow(UIConstants.WINDOW_NAME, splash)
        else:
            alpha = 1 - (elapsed - GameConstants.SPLASH_DURATION) / GameConstants.FADE_DURATION
            beta = 1 - alpha
            blended = cv2.addWeighted(splash, alpha, first_frame, beta, 0)
            cv2.imshow(UIConstants.WINDOW_NAME, blended)

        if cv2.waitKey(GameConstants.WAIT_KEY_DELAY) & 0xFF == ord('q'):
            clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on)
            return None

    return game_state