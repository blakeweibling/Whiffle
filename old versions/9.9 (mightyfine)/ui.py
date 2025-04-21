"""
UI rendering functions for the Whiffle Tracker project.
Manages drawing of UI elements, balls, and splash screen.
"""

import cv2
import numpy as np
import logging
import time
from typing import List, Tuple, Any, Optional

from constants import UIConstants, GameConstants
from scoring import draw_scoring_zones
from menu import draw_menu, draw_menu_window
from menu_utils import show_splash_on_click
from utils import clean_exit
from game_state import GameState

logger = logging.getLogger(__name__)

def draw_ui(frame: np.ndarray, game_state: Any) -> None:
    """
    Draw the user interface elements on the frame.

    Args:
        frame (np.ndarray): The frame to draw on.
        game_state (Any): The current game state.
    """
    logger.debug("Drawing UI")
    # Display current player's name and score
    current_player = game_state.get_current_player()
    cv2.putText(frame, f"Player: {current_player.name}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.WHITE, UIConstants.FONT_THICKNESS)
    cv2.putText(frame, f"Score: {current_player.score}  High: {game_state.high_score}", (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.FONT_THICKNESS)

    if game_state.game_timer is not None:
        timer_display = int(max(0, game_state.game_timer))
        color = UIConstants.YELLOW if game_state.game_timer > 10 else UIConstants.RED
        cv2.putText(frame, f"Time: {timer_display}", (10, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, color, UIConstants.FONT_THICKNESS)

    # Display achievement notification
    if game_state.achievement_notification:
        cv2.putText(frame, game_state.achievement_notification, (UIConstants.WINDOW_WIDTH // 2 - 200, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.GREEN, UIConstants.FONT_THICKNESS)

    # Display a warning if running with static image
    if not game_state.camera_available:
        cv2.putText(frame, "Camera unavailable - Using static image", (10, UIConstants.WINDOW_HEIGHT - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.RED, UIConstants.FONT_THICKNESS)

    # Only draw scoring zones if the toggle is enabled
    if game_state.show_scoring_zones:
        draw_scoring_zones(frame, game_state.scoring_zones, game_state.special_hole)

    if game_state.temp_zone and game_state.drawing:
        x, y, w, h = game_state.temp_zone
        cv2.putText(frame, "Drawing zone...", (10, UIConstants.WINDOW_HEIGHT - 60),
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.YELLOW, UIConstants.FONT_THICKNESS)
        cv2.rectangle(frame, (x, y), (x + w, y + h), UIConstants.YELLOW, UIConstants.FONT_THICKNESS)

    draw_menu(frame, game_state)
    draw_menu_window(frame, game_state)

def draw_balls(frame: np.ndarray, game_state: Any, tracked_detected_balls: List[Tuple[int, int, float, int, str, int]]) -> None:
    """
    Handle tracked balls without drawing them (highlighting removed).

    Args:
        frame (np.ndarray): The frame to draw on.
        game_state (Any): The current game state.
        tracked_detected_balls (List[Tuple[int, int, float, int, str, int]]): List of tracked balls as (x, y, radius, ball_id, ball_type, zone_frames).
    """
    logger.debug("Drawing balls (highlighting disabled)")
    try:
        # Get the camera frame resolution
        if game_state.camera_available:
            camera_width = int(game_state.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            camera_height = int(game_state.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if camera_width == 0 or camera_height == 0:
                logger.warning("Camera resolution could not be retrieved, assuming frame dimensions")
                camera_width, camera_height = frame.shape[1], frame.shape[0]
        else:
            camera_width, camera_height = frame.shape[1], frame.shape[0]  # Use static frame dimensions if camera unavailable

        logger.debug(f"Camera resolution: {camera_width}x{camera_height}, Display resolution: {UIConstants.WINDOW_WIDTH}x{UIConstants.WINDOW_HEIGHT}")

        # Calculate scaling factors to map camera coordinates to display window coordinates
        scale_x = UIConstants.WINDOW_WIDTH / camera_width
        scale_y = UIConstants.WINDOW_HEIGHT / camera_height
        logger.debug(f"Scaling factors: scale_x={scale_x}, scale_y={scale_y}")

        # Removed all drawing logic for balls, trails, and IDs
        # The balls will still be detected and scored, but no visual highlighting will be drawn
        pass

    except Exception as e:
        logger.error(f"Error drawing balls: {e}")
        raise

def show_splash_screen(supabase_url: str, supabase_key: str) -> Optional[GameState]:
    """
    Display the splash screen with a fade effect.

    Args:
        supabase_url (str): The Supabase URL.
        supabase_key (str): The Supabase API key.

    Returns:
        Optional[GameState]: The initialized game state, or None if the splash screen is skipped.
    """
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