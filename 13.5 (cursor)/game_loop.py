# game_loop.py
"""
Main game loop logic for the Whiffle Tracker project.
Handles frame capture, processing, rendering, and user input via _handle_input.
"""

import logging
import time
from typing import Optional, Dict, Tuple

import cv2
import numpy as np

# Import cleanup and utility functions
from cleanup_utils import clean_exit

# Import constants and UI elements
# [MODIFY] Import ResolutionConstants
from constants import GameConstants, UIConstants, ResolutionConstants

# Import input handling
from game_input import _handle_input

# Import GameState class and CurrentGameState enum from NEW location
from game_state import GameState

# Import the necessary refactored utility functions
from game_state_utils import update_scoring, update_timers_and_state
from game_types import CurrentGameState
from ui import draw_ui

logger = logging.getLogger(__name__)

# Cache for retro mode processing to avoid recomputing for static frames
retro_frame_cache: Dict[Tuple[int, int, int], np.ndarray] = {}
MAX_CACHE_SIZE = 5


def _initialize_display():
    """Initializes only the main OpenCV display window."""
    try:
        # [FIX] Use ResolutionConstants here for initial setup
        initial_width = ResolutionConstants.RESOLUTIONS[ResolutionConstants.DEFAULT_RESOLUTION][0]
        initial_height = ResolutionConstants.RESOLUTIONS[ResolutionConstants.DEFAULT_RESOLUTION][1]
        cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(UIConstants.WINDOW_NAME, initial_width, initial_height)
        logger.info(f"Game window initialized with initial size {initial_width}x{initial_height}.")
    except cv2.error as e:
        logger.error(f"Failed create or resize window: {e}")
        raise SystemExit("Could not create game window.")


# (Function unchanged)
def _capture_frame(game_state: GameState) -> Optional[np.ndarray]:
    """Captures a frame from the camera or uses the static frame."""
    if game_state.camera_available and game_state.cap and game_state.cap.isOpened():
        try:
            ret, frame = game_state.cap.read()
            if not ret or frame is None: logger.error("Camera read failed."); game_state.camera_available = False; return (game_state.static_frame.copy() if game_state.static_frame is not None else None)
            return frame
        except cv2.error as e: logger.error(f"Camera read cv2.error: {e}"); game_state.camera_available = False; return (game_state.static_frame.copy() if game_state.static_frame is not None else None)
    elif game_state.static_frame is not None: return game_state.static_frame.copy()
    else: logger.error("Camera unavailable and static frame missing."); return None


# Optimized retro mode processing
def _apply_retro_effects(frame: np.ndarray, game_state: GameState) -> np.ndarray:
    """Apply retro mode effects (pixelation and sepia) with caching for static frames."""
    global retro_frame_cache
    
    # For static frames, use cached version if available
    if not game_state.camera_available and game_state.static_frame is not None:
        # Create cache key from frame dimensions and current timestamp (rounded to seconds)
        # This ensures cache is refreshed periodically even for static frames
        h, w = frame.shape[:2]
        cache_key = (w, h, int(time.time()) // 5)  # Cache for 5 seconds
        
        if cache_key in retro_frame_cache:
            return retro_frame_cache[cache_key].copy()
    
        # If cache is too large, remove oldest entries
        if len(retro_frame_cache) >= MAX_CACHE_SIZE:
            # Remove an arbitrary key (first one)
            for k in list(retro_frame_cache.keys())[:1]:
                del retro_frame_cache[k]
    
    try:
        # Pixelation
        h, w = frame.shape[:2]
        factor = GameConstants.RETRO_PIXEL_FACTOR
        small_h, small_w = max(1, h // factor), max(1, w // factor)
        
        # Apply pixelation effect by resizing down and back up
        temp = cv2.resize(frame, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
        pixelated = cv2.resize(temp, (w, h), interpolation=cv2.INTER_NEAREST)
        
        # Ensure frame is in BGR format
        if len(pixelated.shape) == 2:  # Grayscale
            pixelated = cv2.cvtColor(pixelated, cv2.COLOR_GRAY2BGR)
        elif pixelated.shape[2] == 4:  # RGBA
            pixelated = cv2.cvtColor(pixelated, cv2.COLOR_BGRA2BGR)
        
        # Apply sepia effect using pre-computed kernel
        sepia_canvas = cv2.transform(pixelated, GameConstants.RETRO_SEPIA_KERNEL)
        retro_frame = np.clip(sepia_canvas, 0, 255).astype(np.uint8)
        
        # Cache result for static frames
        if not game_state.camera_available and game_state.static_frame is not None:
            h, w = frame.shape[:2]
            cache_key = (w, h, int(time.time()) // 5)
            retro_frame_cache[cache_key] = retro_frame.copy()
            
        return retro_frame
        
    except Exception as e:
        logger.error(f"Error applying retro effects: {e}")
        return frame  # Return original frame on error


# (Function unchanged)
def _process_frame(frame: np.ndarray, game_state: GameState) -> None:
    """Processes a frame for ball detection and tracking."""
    try:
        white_balls, red_balls, half_balls = game_state.detector.detect_all_balls(frame=frame, frame_count=game_state.frame_count, game_state=game_state, scoring_zones=game_state.scoring_zones, debug_mode=game_state.debug_mode,)
    except Exception as e: logger.exception(f"Ball detection error: {e}"); return
    new_balls_white_fmt = [(int(x), int(y), float(r)) for x, y, r in white_balls];
    new_balls_red_fmt = [(int(x), int(y), float(r)) for x, y, r in red_balls];
    new_balls_half_fmt = [(int(x), int(y), float(r)) for x, y, r in half_balls]
    try:
        if hasattr(game_state, "tracker") and game_state.tracker:
            tracked_detected_balls_tuples, next_id = game_state.tracker.track_balls(white_balls=new_balls_white_fmt, red_balls=new_balls_red_fmt, half_balls=new_balls_half_fmt, tracked_balls=game_state.tracked_balls, next_ball_id=game_state.next_ball_id, frame_count=game_state.frame_count, scored_positions=game_state.scored_positions, debug_mode=game_state.debug_mode,)
            game_state.next_ball_id = next_id
            updated_tracked_list = []; current_ages = { b[3]: b[4] for b in game_state.tracked_balls if len(b) >= 6 }
            for x, y, r, ball_id, b_type in tracked_detected_balls_tuples:
                age = current_ages.get(ball_id, game_state.frame_count); updated_tracked_list.append((int(x), int(y), float(r), int(ball_id), int(age), str(b_type)))
            game_state.tracked_balls = updated_tracked_list
        else: logger.error("Ball tracker not initialized in game_state.")
    except Exception as e: logger.exception(f"Ball tracking error: {e}")


# (Function unchanged)
def _render_frame(draw_canvas: np.ndarray, game_state: GameState) -> None:
    """Renders the game frame with UI elements, balls, and effects onto the draw_canvas."""
    if draw_canvas is None: logger.warning("Render received None draw_canvas."); return
    draw_ui(draw_canvas, game_state)
    try:
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 1: cv2.imshow(UIConstants.WINDOW_NAME, draw_canvas)
        else: pass
    except cv2.error as e:
        if "window not found" not in str(e).lower(): logger.warning(f"cv2.imshow error: {e}")
    except Exception as e: logger.exception(f"Display error during rendering: {e}")


# (Loop logic updated to use optimized retro mode)
def run_game_loop(game_state: GameState) -> None:
    """The main game loop."""
    _initialize_display()
    last_time = time.time()
    if not hasattr(game_state, "frame_count"): game_state.frame_count = 0
    try:
        while True:
            current_time = time.time(); dt = max(1e-6, current_time - last_time); last_time = current_time; game_state.frame_count += 1
            if dt > 0: current_fps = 1.0 / dt; alpha = 0.1; game_state.fps = alpha * current_fps + (1 - alpha) * game_state.fps
            key_result = _handle_input(game_state)
            if key_result is None: logger.info("Quit signaled from input handler."); break
            try:
                if (cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1): logger.info("Window closed by user."); break
            except Exception as e: logger.error(f"Window property check error: {e}."); break

            # Frame capture and resizing (using game_state dimensions)
            frame = _capture_frame(game_state)
            if frame is None: logger.error("Frame capture failed. Exiting loop."); break
            target_width, target_height = game_state.get_current_resolution_dimensions()
            if frame.shape[1] != target_width or frame.shape[0] != target_height:
                logger.debug(f"Resizing frame from {frame.shape[1]}x{frame.shape[0]} to {target_width}x{target_height}")
                try: frame_resized = cv2.resize(frame, (target_width, target_height))
                except Exception as e: logger.exception(f"Frame resize error: {e}. Frame shape: {frame.shape}, Target: {target_width}x{target_height}"); continue
            else: frame_resized = frame
            draw_canvas = frame_resized.copy()

            # Apply retro mode effects if enabled
            if game_state.game_mode == "retro":
                draw_canvas = _apply_retro_effects(draw_canvas, game_state)

            update_timers_and_state(game_state, dt)

            if game_state.current_state == CurrentGameState.PLAYING:
                 run_detection_tracking = (game_state.frame_count % GameConstants.DETECTION_FRAME_INTERVAL == 0)
                 if run_detection_tracking: _process_frame(draw_canvas, game_state)

            update_scoring(game_state)
            _render_frame(draw_canvas, game_state)
            
            # Trim history collections every 30 frames to prevent memory bloat
            if game_state.frame_count % 30 == 0 and hasattr(game_state, "trim_history_collections"):
                try:
                    game_state.trim_history_collections()
                except Exception as e:
                    logger.error(f"Error trimming history collections: {e}")

    except SystemExit: logger.info("SystemExit caught in main loop.")
    except Exception as e: logger.exception(f"Unexpected error in main game loop: {e}")
    finally:
        logger.info("Main game loop exited. Initiating cleanup sequence.")
        clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state,)