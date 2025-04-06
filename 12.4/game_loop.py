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

# Import constants and UI elements
from constants import UIConstants, GameConstants, ScoringConstants
from ui import draw_ui
from ui_elements import draw_balls

# Import GameState class and CurrentGameState enum from NEW location
from game_state import GameState # Keep import for GameState
from game_types import CurrentGameState # Import from new location

# Import input handling
from game_input import _handle_input

# Import cleanup and utility functions
from cleanup_utils import clean_exit
# Import the necessary refactored utility functions
from game_state_utils import (
    update_scoring,
    update_timers_and_state,
    # check_achievements is called within update_timers_and_state now
)


logger = logging.getLogger(__name__)


def _initialize_display():
    """Initializes only the main OpenCV display window."""
    # (Code unchanged)
    try: cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL); logger.info("Game window initialized.")
    except cv2.error as e: logger.error(f"Failed create window: {e}"); raise SystemExit("Could not create game window.")


def _capture_frame(game_state: GameState) -> Optional[np.ndarray]:
    """Captures a frame from the camera or uses the static frame."""
    # (Code unchanged)
    if game_state.camera_available and game_state.cap and game_state.cap.isOpened():
        try:
            ret, frame = game_state.cap.read()
            if not ret or frame is None: logger.error("Cam read fail"); game_state.camera_available=False; return game_state.static_frame.copy() if game_state.static_frame is not None else None
            return frame
        except cv2.error as e: logger.error(f"Cam read error: {e}"); game_state.camera_available=False; return game_state.static_frame.copy() if game_state.static_frame is not None else None
    elif game_state.static_frame is not None: return game_state.static_frame.copy()
    else: logger.error("Camera unavailable and static frame missing."); return None


def _process_frame(frame: np.ndarray, game_state: GameState) -> None:
    """Processes a frame for ball detection and tracking."""
    try:
        white_balls, red_balls, half_balls = game_state.detector.detect_all_balls(
            frame=frame, frame_count=game_state.frame_count, game_state=game_state,
            scoring_zones=game_state.scoring_zones, debug_mode=game_state.debug_mode,
        )
    except Exception as e: logger.exception(f"Detection error: {e}"); return

    new_balls_white_fmt=[(int(x),int(y),float(r)) for x,y,r in white_balls]
    new_balls_red_fmt=[(int(x),int(y),float(r)) for x,y,r in red_balls]
    new_balls_half_fmt=[(int(x),int(y),float(r)) for x,y,r in half_balls]

    try:
        if hasattr(game_state, "tracker") and game_state.tracker:
            tracked_detected_balls_tuples, next_id = game_state.tracker.track_balls(
                white_balls=new_balls_white_fmt, red_balls=new_balls_red_fmt, half_balls=new_balls_half_fmt,
                tracked_balls=game_state.tracked_balls, next_ball_id=game_state.next_ball_id,
                frame_count=game_state.frame_count, scored_positions=game_state.scored_positions,
                debug_mode=game_state.debug_mode,
            )
            game_state.next_ball_id = next_id
            updated_tracked_list = []
            # --- Start CORRECTED Block ---
            # Get current ages to preserve them across tracking updates
            # Iterate with a named variable for the tuple
            current_ages = {}
            for ball_tuple in game_state.tracked_balls:
                # Check length before unpacking
                if len(ball_tuple) >= 6:
                    _, _, _, ball_id, age, _ = ball_tuple[:6] # Unpack known part
                    current_ages[ball_id] = age
                else:
                    logger.warning(f"Skipping malformed ball_tuple in age calculation: {ball_tuple}")

            for x, y, r, ball_id, b_type in tracked_detected_balls_tuples:
                 age = current_ages.get(ball_id, game_state.frame_count)
                 updated_tracked_list.append(
                      (int(x), int(y), float(r), int(ball_id), int(age), str(b_type))
                 )
            # --- End CORRECTED Block ---
            game_state.tracked_balls = updated_tracked_list
        else: logger.error("Ball tracker not initialized.")
    except Exception as e: logger.exception(f"Tracking error: {e}") # Keep generic exception


def _render_frame(draw_canvas: np.ndarray, game_state: GameState) -> None:
    """Renders the game frame with UI elements, balls, and effects onto the draw_canvas."""
    # (Code unchanged)
    if draw_canvas is None: logger.warning("Render received None draw_canvas."); return
    draw_ui(draw_canvas, game_state) # draw_ui handles drawing elements based on state
    try:
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 1: cv2.imshow(UIConstants.WINDOW_NAME, draw_canvas)
        else: pass
    except cv2.error as e:
        if "window not found" not in str(e).lower(): logger.warning(f"cv2.imshow error: {e}")
    except Exception as e: logger.exception(f"Display error: {e}")


def run_game_loop(game_state: GameState) -> None:
    """The main game loop."""
    # (Code unchanged)
    _initialize_display(); last_time=time.time()
    if not hasattr(game_state,"frame_count"): game_state.frame_count=0
    try:
        while True:
            current_time=time.time(); dt=max(1e-6,current_time-last_time); last_time=current_time; game_state.frame_count+=1
            if dt>0: current_fps=1.0/dt; alpha=0.1; game_state.fps=alpha*current_fps+(1-alpha)*game_state.fps
            key_result=_handle_input(game_state)
            if key_result is None: logger.info("Quit signaled from input."); break
            try:
                if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE)<1: logger.info("Window closed."); break
            except Exception as e: logger.error(f"Window check err: {e}."); break
            frame=_capture_frame(game_state)
            if frame is None: logger.error("Capture fail."); break
            try:
                if frame is None or frame.shape[0]==0 or frame.shape[1]==0: logger.error("Invalid frame for resize."); continue
                frame_resized = cv2.resize(frame,(UIConstants.WINDOW_WIDTH,UIConstants.WINDOW_HEIGHT))
            except Exception as e: logger.exception(f"Resize error: {e}."); continue
            draw_canvas=frame_resized.copy()
            # Update State using Utils
            update_timers_and_state(game_state, dt)
            if game_state.current_state == CurrentGameState.PLAYING:
                 run_detection_tracking = (game_state.frame_count%GameConstants.DETECTION_FRAME_INTERVAL==0)
                 if run_detection_tracking: _process_frame(frame_resized, game_state)
                 update_scoring(game_state) # Update scoring AFTER processing frame
            _render_frame(draw_canvas, game_state)
    except SystemExit: logger.info("SystemExit caught.")
    except Exception as e: logger.exception(f"Unexpected main loop error: {e}")
    finally:
        logger.info("Main loop exited. Cleanup.")
        clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)