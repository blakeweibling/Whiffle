# game_loop.py
"""
Main game loop logic for the Whiffle Tracker project.
Handles frame capture, processing, rendering, and user input via _handle_input.
"""

import cv2
import logging
import pygame  # Keep for type hints if needed by clean_exit
import numpy as np
import time

from typing import List, Tuple, Optional, Any

# Import constants and utils
from constants import UIConstants, GameConstants, ScoringConstants

# Import clean_exit from the correct location
from cleanup_utils import clean_exit

from ui import draw_ui
from ui_elements import draw_balls  # Keep draw_balls import
from game_state import CurrentGameState

# Import the input handler
from game_input import _handle_input

logger = logging.getLogger(__name__)


def _initialize_display():
    """Initializes only the OpenCV display window."""
    try:
        cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL)
        logger.info("Game window initialized (OpenCV only).")
    except cv2.error as e:
        logger.error(f"Failed to create OpenCV window: {e}")
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
    """Detects and tracks balls in the frame."""
    try:
        white_balls, red_balls, half_balls = game_state.detector.detect_all_balls(
            frame=frame,
            frame_count=game_state.frame_count,
            game_state=game_state,
            scoring_zones=game_state.scoring_zones,
            debug_mode=game_state.debug_mode,
        )
    except AttributeError as e:
        logger.exception(f"AttrErr detect: {e}.")
    except Exception as e:
        logger.exception(f"Err detect: {e}")
        return

    # Ensure ball data is in the expected format (x, y, radius) before passing to tracker
    new_balls_white_fmt = [(int(x), int(y), float(r)) for x, y, r in white_balls]
    new_balls_red_fmt = [(int(x), int(y), float(r)) for x, y, r in red_balls]
    new_balls_half_fmt = [(int(x), int(y), float(r)) for x, y, r in half_balls]

    try:
        # Pass formatted lists to track_balls
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
        # Update the tracked_balls list in game_state with the full tuple format
        # (x, y, radius, ball_id, frame_count, ball_type)
        updated_tracked_list = []
        # Map current tracked balls by ID to get their age (frame_count)
        current_ages = {
            ball_id: age for _, _, _, ball_id, age, _ in game_state.tracked_balls
        }
        for x, y, r, ball_id, b_type in tracked_detected_balls_tuples:
            # Use existing age if ball was matched, otherwise use current frame_count for new balls
            age = current_ages.get(ball_id, game_state.frame_count)
            updated_tracked_list.append((x, y, r, ball_id, age, b_type))
        game_state.tracked_balls = updated_tracked_list

    except AttributeError as e:
        logger.exception(f"AttrErr track: {e}.")
    except Exception as e:
        logger.exception(f"Err track: {e}")


def _update_ball_trails(game_state: Any) -> None:
    """Updates ball trail history."""
    if not hasattr(game_state, "ball_trails") or not hasattr(
        game_state, "tracked_balls"
    ):
        return  # Cannot update trails if attributes are missing

    tracked_ids = {ball[3] for ball in game_state.tracked_balls if len(ball) >= 4}

    # Remove trails for balls that are no longer tracked
    for ball_id in list(game_state.ball_trails.keys()):
        if ball_id not in tracked_ids:
            del game_state.ball_trails[ball_id]

    # Add new positions for currently tracked balls
    for ball in game_state.tracked_balls:
        try:
            # Ensure ball tuple has enough elements
            if len(ball) >= 6:
                x, y, _, ball_id, _, _ = ball[:6]  # Unpack first 6
                if ball_id not in game_state.ball_trails:
                    game_state.ball_trails[ball_id] = []
                current_pos = (int(x), int(y))
                last_pos = (
                    game_state.ball_trails[ball_id][-1]
                    if game_state.ball_trails[ball_id]
                    else None
                )

                # Add position if it's different from the last one
                if last_pos != current_pos:
                    game_state.ball_trails[ball_id].append(current_pos)

                # Limit trail length
                if (
                    len(game_state.ball_trails[ball_id])
                    > GameConstants.BALL_TRAIL_LENGTH
                ):
                    game_state.ball_trails[ball_id].pop(0)
            else:
                logger.warning(
                    f"Skipping trail update for malformed ball data (length < 6): {ball}"
                )

        except (IndexError, ValueError, TypeError) as e:
            logger.warning(
                f"Error processing ball data for trail update: {ball}. Error: {e}"
            )
        except Exception as e:
            logger.error(f"Unexpected error updating trail for ball {ball}: {e}")


def _update_game_state(game_state: Any, dt: float) -> None:
    """Updates game logic like scoring, timers, and achievements."""
    # Update Timed Mode Timer
    if (
        game_state.current_state == CurrentGameState.PLAYING
        and game_state.game_mode == "timed"
        and game_state.game_timer is not None
    ):
        # Check for low time warning BEFORE decrementing timer
        if (
            game_state.game_timer > 0
            and game_state.game_timer <= 10.0
            and not game_state.low_time_warning_played
        ):
            logger.info("Timer below 10 seconds, playing warning sound.")
            game_state.play_sound(
                game_state.low_time_sound
            )  # Assumes play_sound method exists
            game_state.low_time_warning_played = True  # Set flag to prevent re-playing

        # Decrement timer
        game_state.game_timer -= dt
        if game_state.game_timer <= 0:
            game_state.game_timer = 0
            # Check if already Game Over to prevent multiple saves
            if game_state.current_state != CurrentGameState.GAME_OVER:
                logger.info("Timer expired! Game Over.")
                game_state.current_state = CurrentGameState.GAME_OVER
                # Save score immediately when timer runs out
                if hasattr(game_state, "save_score") and hasattr(
                    game_state, "get_current_player"
                ):
                    player = game_state.get_current_player()
                    if player and hasattr(player, "name"):
                        game_state.save_score(player.name)

    # Update Scoring and Achievements only when Playing
    if game_state.current_state == CurrentGameState.PLAYING:
        if hasattr(game_state, "update_scoring"):
            game_state.update_scoring()
        if hasattr(game_state, "check_achievements"):
            game_state.check_achievements()

    # Update Notifications and Achievement Popups (regardless of playing state, except maybe name input?)
    if game_state.current_state != CurrentGameState.GETTING_PLAYER_NAME:
        if hasattr(game_state, "update_achievement_notification"):
            game_state.update_achievement_notification(dt)
        if hasattr(game_state, "update_notifications"):
            game_state.update_notifications(dt)


# --- CORRECTED FUNCTION ---
def _render_frame(frame: np.ndarray, game_state: Any) -> None:
    """Renders the game frame with UI elements and balls."""
    if frame is None:
        logger.warning("Render received None frame.")
        return

    # Decide when to draw balls (e.g., during active gameplay states, maybe dimmed in menu)
    if game_state.current_state in [CurrentGameState.PLAYING, CurrentGameState.PAUSED]:
        # We could potentially add MENU here and dim them in draw_balls if desired
        draw_balls(frame, game_state)

    # Always call draw_ui, as it contains the internal logic
    # to draw the correct elements based on the current game_state.
    # It handles drawing the name input screen, menu, game over screen,
    # playing UI, paused overlay, notifications, etc.
    draw_ui(frame, game_state)

    # Display the final frame
    try:
        cv2.imshow(UIConstants.WINDOW_NAME, frame)
    except cv2.error as e:
        logger.warning(f"cv2.imshow error (window might be closed): {e}")


# --- END CORRECTED FUNCTION ---


# Function using WND_PROP_AUTOSIZE check (unused in main loop, kept for reference)
def _check_window_close(game_state: Any) -> bool:
    """Checks if the window close button was pressed and exits cleanly if so. Returns True if closed."""
    try:
        # Check using WND_PROP_VISIBLE which is more reliable across backends
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
            logger.info(
                "Window closed via red X (WND_PROP_VISIBLE < 1). Initiating clean exit."
            )
            clean_exit(
                game_state.cap,
                game_state.background_music,
                game_state.background_music_on,
                game_state,
            )
            return True
    except cv2.error as e:
        # This error often means the window is already gone
        logger.warning(
            f"cv2.error checking WND_PROP_VISIBLE (window likely closed): {e}. Initiating clean exit."
        )
        clean_exit(
            game_state.cap,
            game_state.background_music,
            game_state.background_music_on,
            game_state,
        )
        return True
    except SystemExit:  # Propagate SystemExit from clean_exit
        logger.info("SystemExit caught in _check_window_close.")
        raise
    except Exception as e:
        logger.error(f"Unexpected error checking window close: {e}")
        # Attempt clean exit even on unexpected error
        clean_exit(
            game_state.cap,
            game_state.background_music,
            game_state.background_music_on,
            game_state,
        )
        return True  # Assume closed / trying to exit
    return False


def run_game_loop(game_state: Any) -> None:
    """The main game loop."""
    _initialize_display()  # Now only initializes OpenCV window
    last_time = time.time()
    if not hasattr(game_state, "frame_count"):
        game_state.frame_count = 0
    frame_count = game_state.frame_count

    while True:  # Use internal break/return/SystemExit for exit
        current_time = time.time()
        # Calculate dt, ensuring it's positive and non-zero
        dt = max(1e-6, current_time - last_time)
        last_time = current_time
        frame_count += 1
        game_state.frame_count = frame_count  # Update frame count in game_state

        # Calculate FPS (smoothed)
        if dt > 0:
            current_fps = 1.0 / dt
            alpha = 0.1  # Smoothing factor
            game_state.fps = alpha * current_fps + (1 - alpha) * game_state.fps

        # --- Input Handling ---
        key_result = _handle_input(game_state)
        if key_result is None:  # None signals quit request from _handle_input
            logger.info("Received None key from _handle_input, breaking loop.")
            break  # Exit loop cleanly

        # --- Window Close Check (using WND_PROP_VISIBLE) ---
        try:
            if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                logger.info(
                    "Window closed via red X (WND_PROP_VISIBLE < 1). Breaking loop."
                )
                # No need to call clean_exit here, the finally block will handle it
                break
        except cv2.error as e:
            logger.warning(
                f"cv2.error checking WND_PROP_VISIBLE (window likely closed): {e}. Breaking loop."
            )
            break
        except Exception as e:  # Catch other potential errors
            logger.error(f"Error checking window property: {e}. Breaking loop.")
            break

        # --- Frame Capture ---
        frame = _capture_frame(game_state)
        if frame is None:
            logger.error("Failed to capture frame, breaking loop.")
            break  # Exit loop if frame capture fails

        # --- Frame Resizing ---
        try:
            frame_resized = cv2.resize(
                frame, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT)
            )
        except cv2.error as e:
            logger.error(
                f"Frame resize failed: {e}. Frame shape: {frame.shape}. Skipping frame."
            )
            continue  # Skip processing/rendering this frame

        # --- Update Game State based on Current State ---
        current_state = game_state.current_state  # Get current state for clarity
        if current_state == CurrentGameState.PLAYING:
            # Process detection/tracking periodically
            run_detection_tracking = (
                frame_count % GameConstants.DETECTION_FRAME_INTERVAL == 0
            )
            if run_detection_tracking:
                _process_frame(frame_resized, game_state)
            # Update trails and game logic every frame
            _update_ball_trails(game_state)
            _update_game_state(game_state, dt)
        elif current_state == CurrentGameState.PAUSED:
            # Update trails visually, but don't advance game logic timers/scoring
            _update_ball_trails(game_state)
            # Update notifications even when paused
            _update_game_state(
                game_state, dt
            )  # Still call this to handle notifications/achievements popups
        elif current_state == CurrentGameState.GETTING_PLAYER_NAME:
            # Only update notifications/popups
            _update_game_state(game_state, dt)
        elif current_state == CurrentGameState.MENU:
            # Update trails for background visual effect? Optional.
            _update_ball_trails(game_state)
            # Update notifications/popups
            _update_game_state(game_state, dt)
        elif current_state == CurrentGameState.GAME_OVER:
            # Update trails for background visual effect? Optional.
            _update_ball_trails(game_state)
            # Update notifications/popups
            _update_game_state(game_state, dt)
        # Add elif for other states as needed

        # --- Render Frame ---
        _render_frame(frame_resized, game_state)  # This calls draw_ui internally

        # The loop delay is handled by cv2.waitKey inside _handle_input

    # --- Cleanup after loop exit ---
    logger.info("Main game loop exited. Performing final cleanup.")
    # Ensure clean_exit is called when the loop breaks for any reason
    clean_exit(
        game_state.cap,
        game_state.background_music,
        game_state.background_music_on,
        game_state,
    )
