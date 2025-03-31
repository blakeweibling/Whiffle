"""
Main game loop logic for the Whiffle Tracker project.
Handles frame capture, processing, rendering, and user input.
"""

import cv2
import logging
import pygame # Keep pygame if background_music is used directly here later
import numpy as np
import time
# Removed string import as it's used only in _handle_input
from typing import List, Tuple, Optional, Any

# Import constants and utils
from constants import UIConstants, GameConstants, ScoringConstants
from utils import clean_exit  # Ensure clean_exit is imported
# from menu import reset_game # Moved to game_input.py
from ui import draw_ui
from ui_elements import draw_balls # Import draw_balls from its new location
from game_state import CurrentGameState  # Import the Enum for states

# Import the input handler from the new file
from game_input import _handle_input

logger = logging.getLogger(__name__)


# Ensure window exists and try setting backend
def _initialize_display():
    try:
        cv2.namedWindow(
            UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL
        )  # Use normal window, allow resizing
        logger.info("Game window initialized.")
    except cv2.error as e:
        logger.error(f"Failed to create OpenCV window: {e}")
        # Exit if window fails
        raise SystemExit("Could not create game window.")


def _capture_frame(game_state: Any) -> Optional[np.ndarray]:
    """Captures a frame from the camera or uses the static frame."""
    if game_state.camera_available and game_state.cap.isOpened():
        try:
            ret, frame = game_state.cap.read()
            if not ret:
                logger.error("Camera read failed, switching to static frame.")
                game_state.camera_available = False
                return (
                    game_state.static_frame.copy()
                    if game_state.static_frame is not None
                    else None
                )
            return frame
        except cv2.error as e:
            logger.error(f"Error reading frame from camera: {e}")
            game_state.camera_available = False
            return (
                game_state.static_frame.copy()
                if game_state.static_frame is not None
                else None
            )
    elif game_state.static_frame is not None:
        return game_state.static_frame.copy()
    else:
        logger.error("Camera unavailable and static frame is not loaded.")
        return None


def _process_frame(frame: np.ndarray, game_state: Any) -> None:
    """
    Detects and tracks balls in the frame using BallDetector.detect_all_balls
    and BallTracker.track_balls. Updates game_state.tracked_balls.
    """
    try:
        white_balls, red_balls, half_balls = game_state.detector.detect_all_balls(
            frame=frame,
            frame_count=game_state.frame_count,
            game_state=game_state,
            scoring_zones=game_state.scoring_zones,
            debug_mode=game_state.debug_mode,
        )
    except AttributeError as e:
        logger.exception(
            f"AttributeError calling detection method: {e}. Check detection.py and game_loop.py."
        )
        return
    except Exception as e:
        logger.exception(f"Unexpected error during ball detection: {e}")
        return

    new_balls_white_fmt = [(x, y, r) for x, y, r in white_balls]
    new_balls_red_fmt = [(x, y, r) for x, y, r in red_balls]
    new_balls_half_fmt = [(x, y, r) for x, y, r in half_balls]

    try:
        tracked_detected_balls_tuples, next_id = game_state.tracker.track_balls(
            white_balls=new_balls_white_fmt,
            red_balls=new_balls_red_fmt,
            half_balls=new_balls_half_fmt,
            tracked_balls=game_state.tracked_balls,
            next_ball_id=game_state.next_ball_id,
            frame_count=game_state.frame_count,
            scored_positions=game_state.scored_positions,
            debug_mode=game_state.debug_mode,
        )
        game_state.next_ball_id = next_id

        updated_tracked_list = []
        for x, y, r, ball_id, b_type in tracked_detected_balls_tuples:
            age = game_state.frame_count
            updated_tracked_list.append((x, y, r, ball_id, age, b_type))
        game_state.tracked_balls = updated_tracked_list

    except AttributeError as e:
        logger.exception(
            f"AttributeError calling track_balls: {e}. Check tracking.py.")
    except Exception as e:
        logger.exception(f"Unexpected error during ball tracking: {e}")


def _update_ball_trails(game_state: Any) -> None:
    """Updates ball trail history based on current tracked ball positions."""
    for ball in game_state.tracked_balls:
        try:
            x, y, _, ball_id, _, _ = ball
            if ball_id not in game_state.ball_trails:
                game_state.ball_trails[ball_id] = []
            last_pos = (
                game_state.ball_trails[ball_id][-1]
                if game_state.ball_trails[ball_id]
                else None
            )
            current_pos = (int(x), int(y))
            if last_pos != current_pos:
                game_state.ball_trails[ball_id].append(current_pos)
            if len(game_state.ball_trails[ball_id]) > GameConstants.BALL_TRAIL_LENGTH:
                game_state.ball_trails[ball_id].pop(0)
        except (IndexError, ValueError, TypeError):
            logger.warning(f"Malformed ball data during trail update: {ball}")
        except Exception as e:
            logger.error(f"Error updating trail for ball {ball}: {e}")


def _update_game_state(game_state: Any, dt: float) -> None:
    """Updates game logic like scoring, timers, and achievements."""
    if (
        game_state.current_state == CurrentGameState.PLAYING
        and game_state.game_mode == "timed"
        and game_state.game_timer is not None
    ):
        game_state.game_timer -= dt
        if game_state.game_timer <= 0:
            game_state.game_timer = 0
            if game_state.current_state != CurrentGameState.GAME_OVER:
                logger.info("Timer expired! Game Over.")
                game_state.current_state = CurrentGameState.GAME_OVER
                game_state.save_score(game_state.get_current_player().name)

    if game_state.current_state == CurrentGameState.PLAYING:
        game_state.update_scoring()
        game_state.check_achievements()

    game_state.update_achievement_notification(dt)
    game_state.update_notifications(dt)


def _render_frame(frame: np.ndarray, game_state: Any) -> None:
    """Renders the game frame with UI elements and balls."""
    if frame is None:
        logger.warning("Attempted to render a None frame.")
        return
    if game_state.current_state != CurrentGameState.SHOWING_SPLASH:
        draw_balls(frame, game_state)
    draw_ui(frame, game_state)
    # Add a check to ensure the window still exists before showing
    try:
        # Check a property that quickly returns error if window is gone
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_AUTOSIZE) != -1:
            cv2.imshow(UIConstants.WINDOW_NAME, frame)
        else:
            logger.debug("Skipping imshow, window seems closed.")
    except cv2.error as e:
        logger.warning(
            f"cv2.error during imshow (Window '{UIConstants.WINDOW_NAME}' may already be destroyed): {e}"
        )


# --- FUNCTION USING WND_PROP_AUTOSIZE CHECK ---
def _check_window_close(game_state: Any) -> bool:
    """
    Checks if the window close button was pressed and exits cleanly if so.
    Uses WND_PROP_AUTOSIZE as the primary check.
    Returns True if the window was closed, False otherwise.
    """
    try:
        # Check WND_PROP_AUTOSIZE - often returns -1.0 if window is closed/invalid
        window_autosize_property = cv2.getWindowProperty(
            UIConstants.WINDOW_NAME, cv2.WND_PROP_AUTOSIZE
        )
        logger.debug(
            f"Window property check: cv2.WND_PROP_AUTOSIZE = {window_autosize_property}"
        )  # <-- Log this property now

        # Check if the property indicates the window is closed (-1.0)
        if window_autosize_property == -1.0:
            logger.info(
                "Window closed via red X (detected AUTOSIZE property == -1.0).")
            clean_exit(
                game_state.cap,
                game_state.background_music,
                game_state.background_music_on,
                game_state,
            )
            return True
    except cv2.error as e:
        logger.warning(
            f"cv2.error during AUTOSIZE window property check (Window '{UIConstants.WINDOW_NAME}' may already be destroyed): {e}"
        )
        # Treat error as window closed
        clean_exit(
            game_state.cap,
            game_state.background_music,
            game_state.background_music_on,
            game_state,
        )
        return True
    except SystemExit:
        logger.info(
            "SystemExit caught in _check_window_close, likely from clean_exit.")
        raise  # Re-raise SystemExit to ensure loop termination
    except Exception as e:
        logger.error(
            f"Unexpected error during AUTOSIZE window property check: {e}")
    return False


# --- END FUNCTION ---


def run_game_loop(game_state: Any) -> None:
    """The main game loop."""
    _initialize_display()
    last_time = time.time()
    if not hasattr(game_state, "frame_count"):
        game_state.frame_count = 0
    frame_count = game_state.frame_count

    while True:
        current_time = time.time()
        dt = max(1e-6, current_time - last_time)
        last_time = current_time
        frame_count += 1
        game_state.frame_count = frame_count

        alpha = 0.1
        current_fps = 1.0 / dt
        game_state.fps = alpha * current_fps + (1 - alpha) * game_state.fps

        frame = _capture_frame(game_state)
        if frame is None:
            logger.debug(
                "Received None frame from _capture_frame, breaking loop.")
            break  # Exit if frame capture fails

        try:
            frame_resized = cv2.resize(
                frame, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT)
            )
        except cv2.error as e:
            logger.error(f"Resize fail: {e}. Shape: {frame.shape}")
            continue  # Skip this frame if resize fails

        # --- LOOP ORDER CHANGE ---
        # 1. Handle Input (including cv2.waitKey to process events)
        key = _handle_input(game_state) # Call the imported function
        if key is None:
            logger.debug(
                "Received None key from _handle_input, breaking loop.")
            # Exit signal received from input handler (e.g., 'q' key, or error during waitKey)
            break

        # 2. Check for Window Close *after* processing events
        if _check_window_close(game_state):
            logger.debug(
                "Window close detected by _check_window_close, breaking loop.")
            break  # Exit the loop immediately if the window was closed

        # 3. Update Game State
        if game_state.current_state == CurrentGameState.PLAYING:
            run_detection_tracking = (
                frame_count % GameConstants.DETECTION_FRAME_INTERVAL == 0
            )
            if run_detection_tracking:
                # Pass the resized frame to processing
                _process_frame(frame_resized, game_state)
            _update_ball_trails(game_state)
            _update_game_state(game_state, dt)
        elif (
            game_state.current_state != CurrentGameState.GAME_OVER
            and game_state.current_state != CurrentGameState.SHOWING_SPLASH
        ):
            _update_ball_trails(game_state)
            _update_game_state(game_state, dt)

        # 4. Render Frame (use the resized frame)
        _render_frame(frame_resized, game_state)
        # --- END LOOP ORDER CHANGE ---