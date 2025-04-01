# game_loop.py
"""
Main game loop logic for the Whiffle Tracker project.
Handles frame capture, processing, rendering, and user input via _handle_input.
"""

import cv2
import logging
import pygame # Keep for type hints if needed by clean_exit
import numpy as np
import time

from typing import List, Tuple, Optional, Any

# Import constants and utils
from constants import UIConstants, GameConstants, ScoringConstants
from utils import clean_exit

from ui import draw_ui
from ui_elements import draw_balls
from game_state import CurrentGameState

# Import the input handler (which will use cv2.waitKey again)
from game_input import _handle_input

logger = logging.getLogger(__name__)


def _initialize_display():
    """Initializes only the OpenCV display window."""
    try:
        cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL)
        logger.info("Game window initialized (OpenCV only).")
        # --- REMOVED Pygame display init ---
    except cv2.error as e:
        logger.error(f"Failed to create OpenCV window: {e}")
        raise SystemExit("Could not create game window.")
    # Removed Pygame display init error handling


def _capture_frame(game_state: Any) -> Optional[np.ndarray]:
    """Captures a frame from the camera or uses the static frame."""
    if game_state.camera_available and game_state.cap.isOpened():
        try:
            ret, frame = game_state.cap.read()
            if not ret:
                logger.error("Camera read failed, switching to static frame.")
                game_state.camera_available = False
                return game_state.static_frame.copy() if game_state.static_frame is not None else None
            return frame
        except cv2.error as e:
            logger.error(f"Error reading frame from camera: {e}")
            game_state.camera_available = False
            return game_state.static_frame.copy() if game_state.static_frame is not None else None
    elif game_state.static_frame is not None:
        return game_state.static_frame.copy()
    else:
        logger.error("Camera unavailable and static frame is not loaded.")
        return None


def _process_frame(frame: np.ndarray, game_state: Any) -> None:
    """Detects and tracks balls in the frame."""
    try:
        white_balls, red_balls, half_balls = game_state.detector.detect_all_balls(
            frame=frame, frame_count=game_state.frame_count, game_state=game_state,
            scoring_zones=game_state.scoring_zones, debug_mode=game_state.debug_mode,
        )
    except AttributeError as e: logger.exception(f"AttrErr detect: {e}."); return
    except Exception as e: logger.exception(f"Err detect: {e}"); return
    new_balls_white_fmt = [(x, y, r) for x, y, r in white_balls]
    new_balls_red_fmt = [(x, y, r) for x, y, r in red_balls]
    new_balls_half_fmt = [(x, y, r) for x, y, r in half_balls]
    try:
        tracked_detected_balls_tuples, next_id = game_state.tracker.track_balls(
            white_balls=new_balls_white_fmt, red_balls=new_balls_red_fmt, half_balls=new_balls_half_fmt,
            tracked_balls=game_state.tracked_balls, next_ball_id=game_state.next_ball_id,
            frame_count=game_state.frame_count, scored_positions=game_state.scored_positions,
            debug_mode=game_state.debug_mode,
        )
        game_state.next_ball_id = next_id
        updated_tracked_list = []
        for x, y, r, ball_id, b_type in tracked_detected_balls_tuples:
            age = game_state.frame_count; updated_tracked_list.append((x, y, r, ball_id, age, b_type))
        game_state.tracked_balls = updated_tracked_list
    except AttributeError as e: logger.exception(f"AttrErr track: {e}.")
    except Exception as e: logger.exception(f"Err track: {e}")


def _update_ball_trails(game_state: Any) -> None:
    """Updates ball trail history."""
    for ball in game_state.tracked_balls:
        try:
            x, y, _, ball_id, _, _ = ball
            if ball_id not in game_state.ball_trails: game_state.ball_trails[ball_id] = []
            last_pos = game_state.ball_trails[ball_id][-1] if game_state.ball_trails[ball_id] else None
            current_pos = (int(x), int(y))
            if last_pos != current_pos: game_state.ball_trails[ball_id].append(current_pos)
            if len(game_state.ball_trails[ball_id]) > GameConstants.BALL_TRAIL_LENGTH: game_state.ball_trails[ball_id].pop(0)
        except (IndexError, ValueError, TypeError): logger.warning(f"Malformed ball data trail: {ball}")
        except Exception as e: logger.error(f"Error trail ball {ball}: {e}")


def _update_game_state(game_state: Any, dt: float) -> None:
    """Updates game logic like scoring, timers, and achievements."""
    # --- CHANGE: Added low time warning sound logic ---
    if ( game_state.current_state == CurrentGameState.PLAYING and game_state.game_mode == "timed" and game_state.game_timer is not None ):
        # --- Check for low time warning BEFORE decrementing timer ---
        if game_state.game_timer > 0 and game_state.game_timer <= 10.0 and not game_state.low_time_warning_played:
            logger.info("Timer below 10 seconds, playing warning sound.")
            game_state.play_sound(game_state.low_time_sound) # Assumes play_sound method exists
            game_state.low_time_warning_played = True # Set flag to prevent re-playing
        # --- End Sound Check ---

        # Now decrement timer
        game_state.game_timer -= dt
        if game_state.game_timer <= 0:
            game_state.game_timer = 0
            if game_state.current_state != CurrentGameState.GAME_OVER:
                logger.info("Timer expired! Game Over.")
                game_state.current_state = CurrentGameState.GAME_OVER
                game_state.save_score(game_state.get_current_player().name)
    # --- End Change ---

    if game_state.current_state == CurrentGameState.PLAYING:
        game_state.update_scoring(); game_state.check_achievements()
    game_state.update_achievement_notification(dt); game_state.update_notifications(dt)


def _render_frame(frame: np.ndarray, game_state: Any) -> None:
    """Renders the game frame with UI elements and balls."""
    if frame is None: logger.warning("Render None frame."); return
    if game_state.current_state != CurrentGameState.SHOWING_SPLASH:
        if game_state.current_state not in [CurrentGameState.SHOWING_SPLASH, CurrentGameState.GETTING_PLAYER_NAME]:
            draw_balls(frame, game_state)
    if game_state.current_state != CurrentGameState.SHOWING_SPLASH:
        draw_ui(frame, game_state) # This will now draw the timer if applicable
    try:
        cv2.imshow(UIConstants.WINDOW_NAME, frame)
    except cv2.error as e: logger.warning(f"imshow error: {e}")


# --- FUNCTION USING WND_PROP_AUTOSIZE CHECK ---
# This function exists in the provided code but is not called in the main loop.
# Keeping it here for reference as per the original file.
def _check_window_close(game_state: Any) -> bool:
    """ Checks if the window close button was pressed and exits cleanly if so.
    Returns True if closed."""
    try:
        window_autosize_property = cv2.getWindowProperty( UIConstants.WINDOW_NAME, cv2.WND_PROP_AUTOSIZE )
        if window_autosize_property == -1.0:
            logger.info("Window closed via red X (AUTOSIZE == -1.0).")
            clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
            return True
    except cv2.error as e:
        logger.warning(f"cv2.error checking WND_PROP_AUTOSIZE: {e}")
        clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
        return True
    except SystemExit: logger.info("SystemExit in _check_window_close."); raise
    except Exception as e: logger.error(f"Unexpected error checking window close: {e}")
    return False
# --- END FUNCTION ---


def run_game_loop(game_state: Any) -> None:
    """The main game loop."""
    _initialize_display() # Now only initializes OpenCV window
    last_time = time.time()
    if not hasattr(game_state, "frame_count"): game_state.frame_count = 0
    frame_count = game_state.frame_count

    while True: # Use internal break/return for exit
        current_time = time.time()
        dt = max(1e-6, current_time - last_time)
        last_time = current_time
        frame_count += 1
        game_state.frame_count = frame_count

        alpha = 0.1; current_fps = 1.0 / dt
        game_state.fps = alpha * current_fps + (1 - alpha) * game_state.fps

        # --- Input Handling (Reverted to calling _handle_input which uses waitKey) ---
        key_result = _handle_input(game_state)
        if key_result is None: # None signals quit request from _handle_input
            logger.debug("Received None key from _handle_input, breaking loop.")
            break

        # --- Window Close Check ---
        # Check if window was closed *after* handling input
        # This check relies on waitKey having run inside _handle_input
        # --- MODIFICATION START ---
        try:
            if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                 logger.info("Window closed via red X (WND_PROP_VISIBLE < 1). Initiating clean exit.")
                 # Call clean_exit before breaking the loop
                 clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
                 break
        except cv2.error as e:
             # Handle potential error if window property check fails after window closed
             logger.warning(f"cv2.error checking WND_PROP_VISIBLE (window likely closed): {e}. Initiating clean exit.")
             clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
             break
        # --- MODIFICATION END ---

        # --- Frame Capture ---
        frame = _capture_frame(game_state)
        if frame is None: logger.debug("Capture None frame, break."); break

        try:
            frame_resized = cv2.resize(frame, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
        except cv2.error as e: logger.error(f"Resize fail: {e}. Shape: {frame.shape}"); continue

        # --- Update Game State ---
        # Timer and sound logic moved into _update_game_state
        if game_state.current_state == CurrentGameState.PLAYING:
            run_detection_tracking = (frame_count % GameConstants.DETECTION_FRAME_INTERVAL == 0)
            if run_detection_tracking: _process_frame(frame_resized, game_state)
            _update_ball_trails(game_state)
            _update_game_state(game_state, dt) # Timer/sound logic happens here now
        elif game_state.current_state == CurrentGameState.PAUSED:
             _update_ball_trails(game_state); _update_game_state(game_state, dt) # Still update timer etc if paused? Or only notifications?
        elif game_state.current_state == CurrentGameState.GETTING_PLAYER_NAME:
             game_state.update_achievement_notification(dt); game_state.update_notifications(dt)
        elif (game_state.current_state != CurrentGameState.GAME_OVER and
              game_state.current_state != CurrentGameState.SHOWING_SPLASH):
            _update_ball_trails(game_state); _update_game_state(game_state, dt)

        # --- Render Frame ---
        _render_frame(frame_resized, game_state)

        # No separate sleep needed here as waitKey provides the delay

    # --- Cleanup after loop exit ---
    logger.info("Main game loop exited.")
    # clean_exit should be called ONLY ONCE, ideally triggered by the quit condition (q, menu, red X).
    # The logic above now ensures clean_exit is called by all intended exit paths before the loop breaks.
    # No additional call needed here unless handling unexpected loop termination without prior clean_exit.