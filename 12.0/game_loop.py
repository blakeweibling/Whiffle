# game_loop.py
"""
Main game loop logic for the Whiffle Tracker project.
Handles frame capture, processing, rendering, and user input via _handle_input.
"""

import cv2
import logging
import pygame
import numpy as np
import time

from typing import List, Tuple, Optional, Any

from constants import UIConstants, GameConstants, ScoringConstants
from cleanup_utils import clean_exit
from ui import draw_ui
from ui_elements import draw_balls
from game_state import CurrentGameState, GameState
from game_input import _handle_input

logger = logging.getLogger(__name__)

# RAW_FRAME_WINDOW_NAME = "Raw Frame Input" # REMOVED

def _initialize_display():
    """Initializes only the main OpenCV display window.""" # Modified comment
    try:
        cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL)
        # cv2.namedWindow(RAW_FRAME_WINDOW_NAME, cv2.WINDOW_NORMAL) # REMOVED
        logger.info("Game window initialized.") # Modified log
    except cv2.error as e:
        logger.error(f"Failed to create OpenCV window: {e}")
        raise SystemExit("Could not create game window.")


def _capture_frame(game_state: GameState) -> Optional[np.ndarray]:
    # ... (function unchanged) ...
    if game_state.camera_available and game_state.cap and game_state.cap.isOpened():
        try:
            ret, frame = game_state.cap.read()
            if not ret: logger.error("Camera read failed..."); game_state.camera_available = False; return game_state.static_frame.copy() if game_state.static_frame is not None else None
            return frame
        except cv2.error as e: logger.error(f"Error reading camera: {e}"); game_state.camera_available = False; return game_state.static_frame.copy() if game_state.static_frame is not None else None
    elif game_state.static_frame is not None: return game_state.static_frame.copy()
    else: logger.error("Camera unavailable and static frame missing."); return None


def _process_frame(frame: np.ndarray, game_state: GameState) -> None:
    # ... (function unchanged) ...
    try:
        white_balls, red_balls, half_balls = game_state.detector.detect_all_balls(frame=frame, frame_count=game_state.frame_count, game_state=game_state, scoring_zones=game_state.scoring_zones, debug_mode=game_state.debug_mode)
    except AttributeError as e: logger.exception(f"AttrErr detect: {e}."); return
    except Exception as e: logger.exception(f"Err detect: {e}"); return
    new_balls_white_fmt = [(int(x), int(y), float(r)) for x, y, r in white_balls]; new_balls_red_fmt = [(int(x), int(y), float(r)) for x, y, r in red_balls]; new_balls_half_fmt = [(int(x), int(y), float(r)) for x, y, r in half_balls]
    try:
        if hasattr(game_state, 'tracker') and game_state.tracker:
            tracked_detected_balls_tuples, next_id = game_state.tracker.track_balls(white_balls=new_balls_white_fmt, red_balls=new_balls_red_fmt, half_balls=new_balls_half_fmt, tracked_balls=game_state.tracked_balls, next_ball_id=game_state.next_ball_id, frame_count=game_state.frame_count, scored_positions=game_state.scored_positions, debug_mode=game_state.debug_mode)
            game_state.next_ball_id = next_id; updated_tracked_list = []
            current_ages = {ball_id: age for _, _, _, ball_id, age, _ in game_state.tracked_balls}
            for x, y, r, ball_id, b_type in tracked_detected_balls_tuples: age = current_ages.get(ball_id, game_state.frame_count); updated_tracked_list.append((int(x), int(y), float(r), int(ball_id), int(age), str(b_type)))
            game_state.tracked_balls = updated_tracked_list
        else: logger.error("Ball tracker not initialized.")
    except AttributeError as e: logger.exception(f"AttrErr track: {e}.")
    except Exception as e: logger.exception(f"Err track: {e}")


def _update_game_state(game_state: GameState, dt: float) -> None:
    # ... (function unchanged) ...
    if ( game_state.current_state == CurrentGameState.PLAYING and game_state.game_mode == "timed" and game_state.game_timer is not None):
        if ( game_state.game_timer > 0 and game_state.game_timer <= 10.0 and not game_state.low_time_warning_played ): logger.info("Timer low."); game_state.play_sound(game_state.low_time_sound); game_state.low_time_warning_played = True
        game_state.game_timer -= dt
        if game_state.game_timer <= 0:
            game_state.game_timer = 0
            if game_state.current_state != CurrentGameState.GAME_OVER: logger.info("Timer expired."); game_state.current_state = CurrentGameState.GAME_OVER;
            if hasattr(game_state, "save_score") and hasattr(game_state, "get_current_player"): player = game_state.get_current_player();
            if player and hasattr(player, "name"): game_state.save_score(player.name)
    if game_state.current_state == CurrentGameState.PLAYING:
        if hasattr(game_state, "update_scoring"): game_state.update_scoring()
        if hasattr(game_state, "check_achievements"): game_state.check_achievements()
        if game_state.game_mode == "fun":
            if hasattr(game_state, 'active_explosions'):
                for explosion in game_state.active_explosions: explosion.update(dt)
                game_state.active_explosions = [exp for exp in game_state.active_explosions if exp.is_active()]
            else: logger.warning("Missing 'active_explosions'.")
    if game_state.current_state != CurrentGameState.GETTING_PLAYER_NAME:
        if hasattr(game_state, "update_achievement_notification"): game_state.update_achievement_notification(dt)
        if hasattr(game_state, "update_notifications"): game_state.update_notifications(dt)


def _render_frame(draw_canvas: np.ndarray, game_state: GameState) -> None:
    """Renders the game frame with UI elements, balls, and effects onto the draw_canvas."""
    if draw_canvas is None:
        logger.warning("Render received None draw_canvas.")
        return

    # Draw balls and trails (if applicable)
    if game_state.current_state in [CurrentGameState.PLAYING, CurrentGameState.PAUSED, CurrentGameState.MENU]:
        draw_balls(draw_canvas, game_state)

    # Draw UI, zones, explosions (if applicable), text, menu etc.
    draw_ui(draw_canvas, game_state)

    # Display the final canvas
    try:
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 1:
            cv2.imshow(UIConstants.WINDOW_NAME, draw_canvas)
        else:
            logger.debug("Skipping imshow, main window seems closed.")
    except cv2.error as e:
        logger.warning(f"cv2.imshow error (window might be closed): {e}")
    except Exception as e:
        logger.exception(f"Unexpected error during frame display: {e}")


def run_game_loop(game_state: GameState) -> None:
    """The main game loop."""
    _initialize_display() # Now only initializes main window
    last_time = time.time()
    if not hasattr(game_state, "frame_count"): game_state.frame_count = 0
    frame_count = game_state.frame_count

    try:
        while True:
            current_time = time.time()
            dt = max(1e-6, current_time - last_time)
            last_time = current_time
            frame_count += 1
            game_state.frame_count = frame_count

            if dt > 0:
                current_fps = 1.0 / dt; alpha = 0.1
                game_state.fps = alpha * current_fps + (1 - alpha) * game_state.fps

            key_result = _handle_input(game_state)
            if key_result is None: logger.info("Received None key, breaking loop."); break

            try: # Window close check (Main window only)
                if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    logger.info("Main game window closed via red X. Breaking loop.")
                    break
            except cv2.error as e: logger.warning(f"Window property check error: {e}. Breaking."); break
            except Exception as e: logger.error(f"Error checking window property: {e}. Breaking."); break

            frame = _capture_frame(game_state)
            if frame is None: logger.error("Failed capture, breaking loop."); break

            try: # Resize
                if frame is None: logger.error("Cannot resize None frame."); continue
                frame_resized = cv2.resize(frame, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
            except cv2.error as e: logger.error(f"Resize failed: {e}. Skipping."); continue
            except Exception as e: logger.exception(f"Unexpected error resizing: {e}. Skipping."); continue

            # --- REMOVED: Show Raw Frame in Debug Window ---
            # try:
            #      cv2.imshow(RAW_FRAME_WINDOW_NAME, frame_resized)
            # except cv2.error as e:
            #      logger.warning(f"Could not show raw frame window: {e}")
            # --- END REMOVAL ---

            draw_canvas = frame_resized.copy()
            _update_game_state(game_state, dt)

            if game_state.current_state == CurrentGameState.PLAYING:
                run_detection_tracking = (frame_count % GameConstants.DETECTION_FRAME_INTERVAL == 0)
                if run_detection_tracking:
                    _process_frame(frame_resized, game_state) # Process original resized

            _render_frame(draw_canvas, game_state) # Render all elements


            # Loop delay handled by cv2.waitKey in _handle_input

    except SystemExit:
         logger.info("SystemExit caught in game loop, performing cleanup.")
    except Exception as e:
         logger.exception(f"Unexpected error in main game loop: {e}")
    finally:
        logger.info("Main loop exited. Cleaning up.")
        # --- REMOVED: Destroy the debug window ---
        # try:
        #     cv2.destroyWindow(RAW_FRAME_WINDOW_NAME)
        # except cv2.error: pass
        # --- END REMOVAL ---
        clean_exit(
            game_state.cap, game_state.background_music,
            game_state.background_music_on, game_state,
        )