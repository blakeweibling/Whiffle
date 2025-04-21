"""
Main game loop logic for the Whiffle Tracker project.
Handles frame capture, processing, rendering, and user input.
"""

import cv2
import logging
import pygame
import numpy as np
import time
from typing import List, Tuple, Optional, Any

# Import constants and utils
# <<< Added ScoringConstants >>>
from constants import UIConstants, GameConstants, ScoringConstants
from utils import clean_exit
from ui import draw_ui, draw_balls
from game_state import CurrentGameState # Import the Enum for states

logger = logging.getLogger(__name__)

# Ensure window exists and try setting backend
def _initialize_display():
    try:
        cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL) # Use normal window, allow resizing
        logger.info("Game window initialized.")
    except cv2.error as e:
        logger.error(f"Failed to create OpenCV window: {e}")
        raise SystemExit("Could not create game window.") # Exit if window fails

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

# --- Corrected function call and arguments ---
def _process_frame(frame: np.ndarray, game_state: Any) -> None:
    """
    Detects and tracks balls in the frame using BallDetector.detect_all_balls
    and BallTracker.track_balls. Updates game_state.tracked_balls.
    """
    # Detect balls using YOLOv8 - Ensure correct method name and arguments
    try:
        # --- Making sure this call matches detection.py's detect_all_balls ---
        white_balls, red_balls, half_balls = game_state.detector.detect_all_balls(
            frame=frame,
            frame_count=game_state.frame_count, # Pass frame_count
            game_state=game_state, # Pass game_state object
            scoring_zones=game_state.scoring_zones, # Pass scoring_zones
            debug_mode=game_state.debug_mode
            # hsv_frame argument removed as it's optional and not used currently
        )
    except AttributeError as e:
         # Catch if detect_all_balls is still somehow missing or misspelled
         logger.exception(f"AttributeError calling detection method: {e}. Check detection.py and game_loop.py.")
         return # Skip tracking if detection fails
    except Exception as e:
         logger.exception(f"Unexpected error during ball detection: {e}")
         return


    # Track balls using the tracker
    # Combine detected balls into the format expected by the user's BallTracker wrapper
    new_balls_white_fmt = [(x, y, r) for x, y, r in white_balls]
    new_balls_red_fmt = [(x, y, r) for x, y, r in red_balls]
    new_balls_half_fmt = [(x, y, r) for x, y, r in half_balls]

    try:
        # Call the tracker
        tracked_detected_balls_tuples, next_id = game_state.tracker.track_balls(
            white_balls=new_balls_white_fmt,
            red_balls=new_balls_red_fmt,
            half_balls=new_balls_half_fmt,
            tracked_balls=game_state.tracked_balls, # Pass the list of tracked balls state
            next_ball_id=game_state.next_ball_id,
            frame_count=game_state.frame_count, # Pass frame_count
            scored_positions=game_state.scored_positions, # Pass scored_positions
            debug_mode=game_state.debug_mode
        )
        game_state.next_ball_id = next_id # Update next_ball_id

        # Update game_state.tracked_balls with the full tuple (x, y, r, id, age, type)
        current_tracked_map = {ball[3]: ball for ball in game_state.tracked_balls}
        updated_tracked_list = []
        for x, y, r, ball_id, b_type in tracked_detected_balls_tuples:
             # Use current frame as age - tracker should ideally manage this
             age = game_state.frame_count
             updated_tracked_list.append((x, y, r, ball_id, age, b_type))
        game_state.tracked_balls = updated_tracked_list

    except AttributeError as e:
        logger.exception(f"AttributeError calling track_balls: {e}. Check tracking.py.")
    except Exception as e:
         logger.exception(f"Unexpected error during ball tracking: {e}")


def _update_ball_trails(game_state: Any) -> None:
    """Updates ball trail history based on current tracked ball positions."""
    for ball in game_state.tracked_balls:
        try:
            x, y, _, ball_id, _, _ = ball
            if ball_id not in game_state.ball_trails: game_state.ball_trails[ball_id] = []
            last_pos = game_state.ball_trails[ball_id][-1] if game_state.ball_trails[ball_id] else None
            current_pos = (int(x), int(y))
            if last_pos != current_pos: game_state.ball_trails[ball_id].append(current_pos)
            if len(game_state.ball_trails[ball_id]) > GameConstants.BALL_TRAIL_LENGTH: game_state.ball_trails[ball_id].pop(0)
        except IndexError: logger.warning(f"Malformed ball data during trail update: {ball}")
        except Exception as e: logger.error(f"Error updating trail for ball {ball}: {e}")


def _update_game_state(game_state: Any, dt: float) -> None:
    """Updates game logic like scoring, timers, and achievements."""
    if game_state.current_state == CurrentGameState.PLAYING and game_state.game_mode == "timed" and game_state.game_timer is not None:
        game_state.game_timer -= dt
        if game_state.game_timer <= 0:
            game_state.game_timer = 0
            if game_state.current_state != CurrentGameState.GAME_OVER:
                logger.info("Timer expired! Game Over.")
                game_state.current_state = CurrentGameState.GAME_OVER
                game_state.save_score(game_state.get_current_player().name)

    # Only update scoring if playing
    if game_state.current_state == CurrentGameState.PLAYING:
        game_state.update_scoring()
        game_state.check_achievements()

    # Update notifications regardless of state (menu might show them)
    game_state.update_achievement_notification(dt)
    game_state.update_notifications(dt)


def _render_frame(frame: np.ndarray, game_state: Any) -> None:
    """Renders the game frame with UI elements and balls."""
    draw_balls(frame, game_state)
    draw_ui(frame, game_state)
    cv2.imshow(UIConstants.WINDOW_NAME, frame)


def _handle_input(game_state: Any) -> Optional[int]:
    """Handles keyboard input."""
    key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY) & 0xFF
    key_handled = False # Flag to track if the key was handled by zone editing

    # Always Active Keys
    if key == ord('q') or key == 27: logger.info("Quit key pressed."); clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state); return None
    if key == ord('d'): game_state.debug_mode = not game_state.debug_mode; logger.info(f"General Debug toggled {'ON' if game_state.debug_mode else 'OFF'}")
    if key == ord('b'): game_state.show_debug_overlay = not game_state.show_debug_overlay; logger.info(f"Visual Debug Overlay toggled {'ON' if game_state.show_debug_overlay else 'OFF'}")
    if key == ord('p'): # Pause Toggle
        if game_state.current_state == CurrentGameState.PLAYING: game_state.current_state = CurrentGameState.PAUSED; logger.info("Game Paused")
        elif game_state.current_state == CurrentGameState.PAUSED: game_state.current_state = CurrentGameState.PLAYING; logger.info("Game Resumed")

    # --- Zone Point Editing Input Handling (Priority) ---
    if game_state.current_state == CurrentGameState.MENU and \
       game_state.submenu_active == 'edit_zones' and \
       game_state.editing_zone_mode == 'edit_points' and \
       game_state.editing_zone_index is not None:

        if ord('0') <= key <= ord('9'):
            current_input = game_state.editing_zone_points_input or ""
            if len(current_input) < 3: # Limit to 3 digits
                game_state.editing_zone_points_input = current_input + chr(key)
                game_state.menu_cache = None # Redraw menu to show updated input
                logger.debug(f"Edit points input: {game_state.editing_zone_points_input}")
            else:
                 game_state.show_notification("Max 3 digits allowed", is_error=True, duration=1.5)
            key_handled = True # Indicate key was processed here

        elif key == 8: # Backspace key
            current_input = game_state.editing_zone_points_input or ""
            if current_input:
                game_state.editing_zone_points_input = current_input[:-1]
                game_state.menu_cache = None # Redraw menu
                logger.debug(f"Edit points input after backspace: {game_state.editing_zone_points_input}")
            key_handled = True # Indicate key was processed here

        elif key == 13: # Enter key
            input_str = game_state.editing_zone_points_input
            valid_points = False
            new_points = 0
            if input_str and input_str.isdigit():
                try:
                    new_points = int(input_str)
                    # Use ScoringConstants.MAX_POINTS (now 999)
                    if 1 <= new_points <= ScoringConstants.MAX_POINTS:
                         valid_points = True
                    else:
                         logger.warning(f"Entered points {new_points} out of range (1-{ScoringConstants.MAX_POINTS})")
                except ValueError:
                    logger.error(f"Could not convert input '{input_str}' to integer.")

            if valid_points:
                 try:
                     # Update the points in the specific zone tuple
                     zone_idx = game_state.editing_zone_index
                     zone_data = game_state.scoring_zones[zone_idx]
                     # Create a new tuple with updated points
                     updated_zone = (zone_data[0], zone_data[1], zone_data[2], zone_data[3], new_points)
                     game_state.scoring_zones[zone_idx] = updated_zone
                     logger.info(f"Updated Zone {zone_idx + 1} points to {new_points}")
                     game_state.show_notification(f"Zone {zone_idx + 1} points set to {new_points}")

                     # Reset editing state
                     game_state.editing_zone_points_input = None
                     game_state.editing_zone_index = None
                     game_state.editing_zone_mode = None
                     game_state.menu_cache = None # Force menu redraw

                 except IndexError:
                     logger.error(f"Error accessing scoring_zones index {zone_idx} during point update.")
                     game_state.show_notification("Error updating points!", is_error=True)
                     # Reset state even on error to avoid being stuck
                     game_state.editing_zone_points_input = None
                     game_state.editing_zone_index = None
                     game_state.editing_zone_mode = None
                     game_state.menu_cache = None
            else:
                 # Invalid input, show error but keep editing active
                 game_state.show_notification(f"Invalid points: Enter 1-{ScoringConstants.MAX_POINTS}", is_error=True)

            key_handled = True # Indicate key was processed here

    # --- State-Specific Keys (Only if not handled by point editing) ---
    if not key_handled:
        if game_state.current_state == CurrentGameState.GAME_OVER:
             if key == ord('n'): logger.info("New Game key."); from menu import reset_game; reset_game(game_state); game_state.current_state = CurrentGameState.PLAYING; game_state.win_condition_met = False
             elif key == ord('l'): logger.info("Leaderboard key."); game_state.current_state = CurrentGameState.MENU; game_state.submenu_active = "leaderboard"; game_state.menu_cache = None; game_state.win_condition_met = False

        elif game_state.current_state == CurrentGameState.MENU:
             if key == ord('m'): game_state.current_state = CurrentGameState.PLAYING; game_state.submenu_active = None; game_state.menu_cache = None; game_state.editing_zone_index = None; game_state.editing_zone_mode = None; game_state.editing_zone_points_input = None
             elif key == 8: # Backspace (Menu Navigation)
                  # If in point editing mode, Backspace is handled above. This handles menu nav backspace.
                  if game_state.submenu_active is not None:
                       previous_submenu = game_state.submenu_active
                       if game_state.submenu_active == "edit_zones": game_state.submenu_active = "manage_zones"
                       else: game_state.submenu_active = None
                       # Reset editing state when navigating back
                       game_state.editing_zone_index = None
                       game_state.editing_zone_mode = None
                       game_state.editing_zone_points_input = None
                       game_state.menu_cache = None; logger.debug(f"Backspace: back from {previous_submenu} to {game_state.submenu_active or 'main menu'}.")
                  else: # In main menu, backspace closes menu
                       game_state.current_state = CurrentGameState.PLAYING; game_state.menu_cache = None; logger.debug("Backspace: closing menu.")

        elif game_state.current_state == CurrentGameState.PLAYING:
            if key == ord('m'): game_state.current_state = CurrentGameState.MENU; game_state.submenu_active = None; game_state.menu_cache = None
            elif key == ord('s'):
                if not game_state.drawing: game_state.drawing = True; logger.info("Start drawing ('s')."); game_state.show_notification("Click and drag to draw zone")
                else: game_state.drawing = False; game_state.temp_zone = None; logger.info("Drawing cancelled ('s')."); game_state.show_notification("Drawing cancelled")

    return key


def run_game_loop(game_state: Any) -> None:
    """The main game loop."""
    _initialize_display()
    last_time = time.time()
    if not hasattr(game_state, 'frame_count'): game_state.frame_count = 0
    frame_count = game_state.frame_count

    while True:
        current_time = time.time(); dt = max(1e-6, current_time - last_time); last_time = current_time
        frame_count += 1; game_state.frame_count = frame_count

        alpha = 0.1; current_fps = 1.0 / dt; game_state.fps = alpha * current_fps + (1 - alpha) * game_state.fps

        frame = _capture_frame(game_state)
        if frame is None: break

        try: frame = cv2.resize(frame, (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT))
        except cv2.error as e: logger.error(f"Resize fail: {e}. Shape: {frame.shape}"); continue

        key = _handle_input(game_state)
        if key is None: break # Exit triggered

        # Skip game logic updates if paused, game over, or menu is active
        # Trails and state/notifications can still update in these states
        if game_state.current_state == CurrentGameState.PLAYING:
             # --- PLAYING State Logic ---
             run_detection_tracking = (frame_count % GameConstants.DETECTION_FRAME_INTERVAL == 0)
             if run_detection_tracking:
                 _process_frame(frame, game_state) # Runs detection and tracking

             _update_ball_trails(game_state) # Update trails every frame (even if detection skipped)
             _update_game_state(game_state, dt) # Update scoring, timers etc.
        else:
             # --- PAUSED / MENU / GAME_OVER ---
             # Update things that might still change visually or need timing
             _update_ball_trails(game_state) # Keep trails updated visually
             _update_game_state(game_state, dt) # Update notifications/achievement timers

        # Always render the frame and check for window close
        _render_frame(frame, game_state) # Render final frame based on current state
        _check_window_close(game_state) # Check window close


def _check_window_close(game_state: Any):
     """ Checks if the window close button was pressed and exits cleanly. """
     try:
         if cv2.getWindowProperty(UIConstants.WINDOW_NAME, 0) != -1:
              if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                   logger.info("Window closed via red X.")
                   clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
         # else: logger.debug("Window already destroyed check.") # Removed logging noise
     except cv2.error:
         # This error means the window is likely already gone.
         # Avoid calling clean_exit here as it might have already run.
         logger.info("Window property check failed, window likely closed.")
         pass