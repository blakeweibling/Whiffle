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

# Constants for ball visualization
BALL_COLORS = {
    "white": (255, 255, 255),  # White in BGR
    "red": (0, 0, 255),        # Red in BGR
    "half": (255, 0, 255)      # Magenta for half red/half white
}
TRAIL_LENGTH = 10  # Number of past positions to draw in the trail
TRAIL_THICKNESS = 2  # Thickness of the trail lines
TRAIL_FADE_STEP = 0.1  # Alpha decrease per trail segment (for fading effect)

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
    # Display score and high score
    score_text = f"Score: {current_player.score}  High: {game_state.high_score}"
    cv2.putText(frame, score_text, (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_LARGE, UIConstants.GREEN, UIConstants.FONT_THICKNESS)

    # Display timer in timed mode, positioned below the score
    if game_state.game_mode == "timed" and game_state.game_timer is not None:
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

def draw_balls(frame: np.ndarray, game_state: Any, tracked_detected_balls: List[Tuple[int, int, float, int, str]]) -> None:
    """
    Draw tracked balls and their trails on the frame.

    Args:
        frame (np.ndarray): The frame to draw on.
        game_state (Any): The current game state.
        tracked_detected_balls (List[Tuple[int, int, float, int, str]]): List of tracked balls as (x, y, radius, ball_id, ball_type).
    """
    logger.debug(f"Drawing {len(tracked_detected_balls)} balls")
    start_time = time.time()

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

        # Update ball trails and draw balls
        for x, y, radius, ball_id, ball_type in tracked_detected_balls:
            # Scale coordinates and radius to display resolution
            scaled_x = int(x * scale_x)
            scaled_y = int(y * scale_y)
            scaled_radius = int(radius * (scale_x + scale_y) / 2)  # Average scaling for radius

            # Update ball trails
            if ball_id not in game_state.ball_trails:
                game_state.ball_trails[ball_id] = []
            # Add current position with frame count
            game_state.ball_trails[ball_id].append((scaled_x, scaled_y, game_state.frame_count))
            # Keep only the last TRAIL_LENGTH positions and remove old entries
            game_state.ball_trails[ball_id] = [
                pos for pos in game_state.ball_trails[ball_id]
                if game_state.frame_count - pos[2] < TRAIL_LENGTH * GameConstants.FRAME_RATE  # Adjust for frame rate
            ][-TRAIL_LENGTH:]

            # Draw the trail with fading effect
            trail = game_state.ball_trails[ball_id]
            if len(trail) > 1:
                for i in range(len(trail) - 1):
                    alpha = 1.0 - (TRAIL_FADE_STEP * (len(trail) - 1 - i))  # Fade older segments
                    if alpha <= 0:
                        continue
                    # Create a temporary overlay for the trail to apply transparency
                    overlay = frame.copy()
                    start_pos = (trail[i][0], trail[i][1])
                    end_pos = (trail[i + 1][0], trail[i + 1][1])
                    cv2.line(overlay, start_pos, end_pos, BALL_COLORS[ball_type], TRAIL_THICKNESS)
                    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

            # Draw the ball
            color = BALL_COLORS.get(ball_type, (128, 128, 128))  # Default to gray if type unknown
            cv2.circle(frame, (scaled_x, scaled_y), scaled_radius, color, 2)

            # Optionally draw the ball ID (for debugging)
            if game_state.debug_mode:
                cv2.putText(frame, str(ball_id), (scaled_x + 15, scaled_y),
                            cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, color, 1)

        # Clean up trails for balls that are no longer tracked
        current_ball_ids = {ball[3] for ball in tracked_detected_balls}
        game_state.ball_trails = {
            ball_id: trail for ball_id, trail in game_state.ball_trails.items()
            if ball_id in current_ball_ids
        }

    except Exception as e:
        logger.error(f"Error drawing balls: {e}")
        raise
    finally:
        render_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        logger.debug(f"Ball rendering took {render_time:.2f} ms")

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