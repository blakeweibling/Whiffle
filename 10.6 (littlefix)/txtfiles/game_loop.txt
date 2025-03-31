"""
Main game loop logic for the Whiffle Tracker project.
Handles frame capture, processing, rendering, and user input.
"""

import cv2
import logging
import pygame
import numpy as np
import time
import string # <<< Added for valid characters check
from typing import List, Tuple, Optional, Any

# Import constants and utils
from constants import UIConstants, GameConstants, ScoringConstants
from utils import clean_exit # <<< Ensure clean_exit is imported
# <<< Ensure reset_game is imported if needed within this file >>>
from menu import reset_game
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
    # ...(process_frame remains the same)...
    try:
        white_balls, red_balls, half_balls = game_state.detector.detect_all_balls(
            frame=frame, frame_count=game_state.frame_count, game_state=game_state,
            scoring_zones=game_state.scoring_zones, debug_mode=game_state.debug_mode
        )
    except AttributeError as e:
         logger.exception(f"AttributeError calling detection method: {e}. Check detection.py and game_loop.py.")
         return
    except Exception as e:
         logger.exception(f"Unexpected error during ball detection: {e}")
         return

    new_balls_white_fmt = [(x, y, r) for x, y, r in white_balls]
    new_balls_red_fmt = [(x, y, r) for x, y, r in red_balls]
    new_balls_half_fmt = [(x, y, r) for x, y, r in half_balls]

    try:
        tracked_detected_balls_tuples, next_id = game_state.tracker.track_balls(
            white_balls=new_balls_white_fmt, red_balls=new_balls_red_fmt, half_balls=new_balls_half_fmt,
            tracked_balls=game_state.tracked_balls, next_ball_id=game_state.next_ball_id,
            frame_count=game_state.frame_count, scored_positions=game_state.scored_positions,
            debug_mode=game_state.debug_mode
        )
        game_state.next_ball_id = next_id

        updated_tracked_list = []
        for x, y, r, ball_id, b_type in tracked_detected_balls_tuples:
             age = game_state.frame_count
             updated_tracked_list.append((x, y, r, ball_id, age, b_type))
        game_state.tracked_balls = updated_tracked_list

    except AttributeError as e:
        logger.exception(f"AttributeError calling track_balls: {e}. Check tracking.py.")
    except Exception as e:
         logger.exception(f"Unexpected error during ball tracking: {e}")


def _update_ball_trails(game_state: Any) -> None:
    """Updates ball trail history based on current tracked ball positions."""
    # ...(update_ball_trails remains the same)...
    for ball in game_state.tracked_balls:
        try:
            x, y, _, ball_id, _, _ = ball
            if ball_id not in game_state.ball_trails: game_state.ball_trails[ball_id] = []
            last_pos = game_state.ball_trails[ball_id][-1] if game_state.ball_trails[ball_id] else None
            current_pos = (int(x), int(y))
            if last_pos != current_pos: game_state.ball_trails[ball_id].append(current_pos)
            if len(game_state.ball_trails[ball_id]) > GameConstants.BALL_TRAIL_LENGTH: game_state.ball_trails[ball_id].pop(0)
        except (IndexError, ValueError, TypeError): logger.warning(f"Malformed ball data during trail update: {ball}")
        except Exception as e: logger.error(f"Error updating trail for ball {ball}: {e}")


def _update_game_state(game_state: Any, dt: float) -> None:
    """Updates game logic like scoring, timers, and achievements."""
    # ...(update_game_state remains the same)...
    if game_state.current_state == CurrentGameState.PLAYING and game_state.game_mode == "timed" and game_state.game_timer is not None:
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
    # ...(render_frame remains the same)...
    if game_state.current_state != CurrentGameState.SHOWING_SPLASH:
        draw_balls(frame, game_state)
    draw_ui(frame, game_state)
    cv2.imshow(UIConstants.WINDOW_NAME, frame)


def _handle_input(game_state: Any) -> Optional[int]:
    """Handles keyboard input."""
    key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY) & 0xFF
    key_handled = False
    # Define allowed characters for player names (alphanumeric + space)
    allowed_name_chars = string.ascii_letters + string.digits + ' '
    max_name_length = 15 # Max length for player name

    # --- Quit Key ('q') ---
    if key == ord('q'):
        logger.info("Quit key ('q') pressed.")
        clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
        return None # Signal exit

    # --- State-Specific Input Handling ---

    # Handle input for SHOWING_SPLASH state
    if game_state.current_state == CurrentGameState.SHOWING_SPLASH:
        if key != 255 and key != -1: # Any key press
            logger.info("Key press detected during splash, returning to previous state.")
            if game_state.previous_state: game_state.current_state = game_state.previous_state
            else: game_state.current_state = CurrentGameState.MENU; logger.warning("Previous state was None...")
            game_state.previous_state = None
            game_state.menu_cache = None
            key_handled = True

    # Handle input for MENU state
    elif game_state.current_state == CurrentGameState.MENU:
        # Priority for Zone Point Editing Input
        if game_state.submenu_active == 'edit_zones' and \
           game_state.editing_zone_mode == 'edit_points' and \
           game_state.editing_zone_index is not None:
            # ...(Zone Point Editing remains the same)...
            if ord('0') <= key <= ord('9'):
                current_input = game_state.editing_zone_points_input or ""
                if len(current_input) < 3:
                    game_state.editing_zone_points_input = current_input + chr(key)
                    game_state.menu_cache = None
                    logger.debug(f"Edit points input: {game_state.editing_zone_points_input}")
                else: game_state.show_notification("Max 3 digits allowed", is_error=True, duration=1.5)
                key_handled = True
            elif key == 8: # Backspace
                current_input = game_state.editing_zone_points_input or ""
                if current_input:
                    game_state.editing_zone_points_input = current_input[:-1]
                    game_state.menu_cache = None
                    logger.debug(f"Edit points input after backspace: {game_state.editing_zone_points_input}")
                key_handled = True
            elif key == 13: # Enter
                input_str = game_state.editing_zone_points_input; valid_points = False; new_points = 0
                if input_str and input_str.isdigit():
                    try:
                        new_points = int(input_str)
                        if 1 <= new_points <= ScoringConstants.MAX_POINTS: valid_points = True
                        else: logger.warning(f"Entered points {new_points} out of range (1-{ScoringConstants.MAX_POINTS})")
                    except ValueError: logger.error(f"Could not convert input '{input_str}' to integer.")
                if valid_points:
                     try:
                         zone_idx = game_state.editing_zone_index; zone_data = game_state.scoring_zones[zone_idx]
                         updated_zone = (zone_data[0], zone_data[1], zone_data[2], zone_data[3], new_points)
                         game_state.scoring_zones[zone_idx] = updated_zone
                         logger.info(f"Updated Zone {zone_idx + 1} points to {new_points}")
                         game_state.show_notification(f"Zone {zone_idx + 1} points set to {new_points}")
                         game_state.editing_zone_points_input = None; game_state.editing_zone_index = None; game_state.editing_zone_mode = None
                         game_state.menu_cache = None
                     except IndexError:
                         logger.error(f"Error accessing scoring_zones index {zone_idx} during point update.")
                         game_state.show_notification("Error updating points!", is_error=True)
                         game_state.editing_zone_points_input = None; game_state.editing_zone_index = None; game_state.editing_zone_mode = None
                         game_state.menu_cache = None
                else: game_state.show_notification(f"Invalid points: Enter 1-{ScoringConstants.MAX_POINTS}", is_error=True)
                key_handled = True
            elif key == 27: # ESC cancels editing
                logger.info("ESC pressed during point edit, cancelling edit.")
                game_state.editing_zone_points_input = None; game_state.editing_zone_index = None; game_state.editing_zone_mode = None
                game_state.menu_cache = None; game_state.show_notification("Point editing cancelled")
                key_handled = True

        # <<< Added: Player Name Editing Input Handling >>>
        elif game_state.submenu_active == 'players' and \
             game_state.editing_player_mode == 'edit_name' and \
             game_state.editing_player_index is not None:

            char = chr(key) if key < 256 else None # Get character if it's a standard key

            # Append allowed characters (letters, digits, space)
            if char is not None and char in allowed_name_chars:
                current_input = game_state.editing_player_name_input or ""
                if len(current_input) < max_name_length:
                    game_state.editing_player_name_input = current_input + char
                    game_state.menu_cache = None # Redraw menu
                    logger.debug(f"Edit name input: {game_state.editing_player_name_input}")
                else:
                    game_state.show_notification(f"Max name length {max_name_length} reached", is_error=True, duration=1.5)
                key_handled = True

            elif key == 8: # Backspace
                current_input = game_state.editing_player_name_input or ""
                if current_input:
                    game_state.editing_player_name_input = current_input[:-1]
                    game_state.menu_cache = None # Redraw menu
                    logger.debug(f"Edit name input after backspace: {game_state.editing_player_name_input}")
                key_handled = True

            elif key == 13: # Enter - Save Name
                new_name = (game_state.editing_player_name_input or "").strip() # Remove leading/trailing whitespace
                if new_name: # Check if name is not empty
                    try:
                        player_idx = game_state.editing_player_index
                        game_state.players[player_idx].name = new_name
                        logger.info(f"Updated Player {player_idx + 1} name to '{new_name}'")
                        game_state.show_notification(f"Player {player_idx + 1} name updated")
                        # Reset editing state
                        game_state.editing_player_index = None; game_state.editing_player_mode = None; game_state.editing_player_name_input = None
                        game_state.menu_cache = None
                    except IndexError:
                        logger.error(f"Error accessing players index {player_idx} during name update.")
                        game_state.show_notification("Error updating name!", is_error=True)
                        game_state.editing_player_index = None; game_state.editing_player_mode = None; game_state.editing_player_name_input = None
                        game_state.menu_cache = None
                else:
                    # Invalid name (empty)
                    game_state.show_notification("Player name cannot be empty", is_error=True)
                key_handled = True

            elif key == 27: # ESC - Cancel Edit
                logger.info("ESC pressed during name edit, cancelling edit.")
                game_state.editing_player_index = None; game_state.editing_player_mode = None; game_state.editing_player_name_input = None
                game_state.menu_cache = None # Redraw menu
                game_state.show_notification("Name editing cancelled")
                key_handled = True
            # --- End of Player Name Editing Input Handling ---

        # General Menu Input (if not editing points/name or key wasn't handled)
        if not key_handled:
            if key == ord('m'):
                logger.debug("Menu key ('m') pressed, closing menu.")
                game_state.current_state = CurrentGameState.PLAYING; game_state.submenu_active = None; game_state.menu_cache = None
                game_state.editing_zone_index = None; game_state.editing_zone_mode = None; game_state.editing_zone_points_input = None
                game_state.editing_player_index = None; game_state.editing_player_mode = None; game_state.editing_player_name_input = None
                key_handled = True
            elif key == 8: # Backspace (Menu Navigation)
                 if game_state.submenu_active is not None:
                      previous_submenu = game_state.submenu_active
                      if game_state.submenu_active == "edit_zones": game_state.submenu_active = "manage_zones"
                      elif game_state.submenu_active == "players": game_state.submenu_active = None # Go back to main from players
                      else: game_state.submenu_active = None
                      game_state.editing_zone_index = None; game_state.editing_zone_mode = None; game_state.editing_zone_points_input = None
                      game_state.editing_player_index = None; game_state.editing_player_mode = None; game_state.editing_player_name_input = None
                      game_state.menu_cache = None; logger.debug(f"Backspace: back from {previous_submenu} to {game_state.submenu_active or 'main menu'}.")
                 else:
                      game_state.current_state = CurrentGameState.PLAYING; game_state.menu_cache = None; logger.debug("Backspace: closing menu.")
                 key_handled = True
            elif key == 27: # ESC key (Menu Navigation)
                 if game_state.submenu_active is not None:
                      previous_submenu = game_state.submenu_active
                      if game_state.submenu_active == "edit_zones": game_state.submenu_active = "manage_zones"
                      else: game_state.submenu_active = None # Go to main menu
                      game_state.editing_zone_index = None; game_state.editing_zone_mode = None; game_state.editing_zone_points_input = None
                      game_state.editing_player_index = None; game_state.editing_player_mode = None; game_state.editing_player_name_input = None
                      game_state.menu_cache = None; logger.debug(f"ESC: back from {previous_submenu} to {game_state.submenu_active or 'main menu'}.")
                 else:
                      logger.debug("ESC pressed in main menu, closing menu.")
                      game_state.current_state = CurrentGameState.PLAYING; game_state.menu_cache = None
                      game_state.editing_zone_index = None; game_state.editing_zone_mode = None; game_state.editing_zone_points_input = None
                      game_state.editing_player_index = None; game_state.editing_player_mode = None; game_state.editing_player_name_input = None
                 key_handled = True

    # Handle input for PLAYING state
    elif game_state.current_state == CurrentGameState.PLAYING:
        if key == ord('m'): game_state.current_state = CurrentGameState.MENU; game_state.submenu_active = None; game_state.menu_cache = None; key_handled = True
        elif key == ord('s'):
            if not game_state.drawing: game_state.drawing = True; logger.info("Start drawing ('s')."); game_state.show_notification("Click and drag to draw zone")
            else: game_state.drawing = False; game_state.temp_zone = None; logger.info("Drawing cancelled ('s')."); game_state.show_notification("Drawing cancelled")
            key_handled = True
        elif key == ord('p'): game_state.current_state = CurrentGameState.PAUSED; logger.info("Game Paused"); key_handled = True
        elif key == 27: # ESC quits
             logger.info("ESC key pressed while playing, exiting."); clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state); return None

    # Handle input for PAUSED state
    elif game_state.current_state == CurrentGameState.PAUSED:
        if key == ord('p'): game_state.current_state = CurrentGameState.PLAYING; logger.info("Game Resumed"); key_handled = True
        elif key == 27: # ESC quits
             logger.info("ESC key pressed while paused, exiting."); clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state); return None

    # Handle input for GAME_OVER state
    elif game_state.current_state == CurrentGameState.GAME_OVER:
         if key == ord('n'):
             logger.info("New Game key ('n') from game over.");
             try: from menu import reset_game; reset_game(game_state); game_state.current_state = CurrentGameState.PLAYING; game_state.win_condition_met = False
             except ImportError: logger.error("Failed to import reset_game function in _handle_input.")
             key_handled = True
         elif key == ord('l'): logger.info("Leaderboard key ('l') from game over."); game_state.current_state = CurrentGameState.MENU; game_state.submenu_active = "leaderboard"; game_state.menu_cache = None; game_state.win_condition_met = False; key_handled = True
         elif key == 27: # ESC quits
             logger.info("ESC key pressed on game over screen, exiting."); clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state); return None

    # Handle global keys if not handled by state-specific logic
    if not key_handled:
        if key == ord('d'): game_state.debug_mode = not game_state.debug_mode; logger.info(f"General Debug toggled {'ON' if game_state.debug_mode else 'OFF'}"); key_handled = True
        elif key == ord('b'): game_state.show_debug_overlay = not game_state.show_debug_overlay; logger.info(f"Visual Debug Overlay toggled {'ON' if game_state.show_debug_overlay else 'OFF'}"); key_handled = True

    return key # Return key code (or None if exit was triggered)


def run_game_loop(game_state: Any) -> None:
    """The main game loop."""
    # ...(run_game_loop structure remains the same)...
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
        if key is None: break # Exit signal received

        # Update game logic based on state
        if game_state.current_state == CurrentGameState.PLAYING:
             run_detection_tracking = (frame_count % GameConstants.DETECTION_FRAME_INTERVAL == 0)
             if run_detection_tracking:
                 _process_frame(frame, game_state)
             _update_ball_trails(game_state)
             _update_game_state(game_state, dt)

        elif game_state.current_state != CurrentGameState.GAME_OVER and game_state.current_state != CurrentGameState.SHOWING_SPLASH:
             _update_ball_trails(game_state)
             _update_game_state(game_state, dt) # Update notifications etc.

        # Always render and check window
        _render_frame(frame, game_state)
        _check_window_close(game_state) # Calls clean_exit if needed


def _check_window_close(game_state: Any):
     """ Checks if the window close button was pressed and exits cleanly. """
     # ...(check_window_close remains the same)...
     try:
         if UIConstants.WINDOW_NAME and cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 0:
              if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                   logger.info("Window closed via red X.")
                   clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
     except cv2.error:
         logger.info("Window property check failed (cv2.error), window likely closed.")
         pass
     except SystemExit:
         logger.info("SystemExit caught in _check_window_close, likely from clean_exit.")
         raise