"""
Main game loop logic for the Whiffle Tracker project.
Handles frame capture, processing, rendering, and user input.
"""

import cv2
import logging
import pygame
import numpy as np
import json
import time
import os
from typing import List, Tuple, Optional, Any

from constants import UIConstants, GameConstants
from detection import BallDetector
from tracking import BallTracker
from scoring import define_scoring_zone, is_in_scoring_zone
from utils import clean_exit
from ui import draw_ui, draw_balls
from game_state import MenuState

logger = logging.getLogger(__name__)

# Check if Qt backend is available
try:
    cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_GUI_NORMAL)  # Try to use Qt if available
    logger.info("Attempted to use Qt backend for display (WINDOW_GUI_NORMAL).")
except cv2.error as e:
    logger.warning(f"Failed to set Qt backend: {e}. Falling back to default backend.")
    cv2.namedWindow(UIConstants.WINDOW_NAME, cv2.WINDOW_NORMAL)

def _capture_frame(cap: cv2.VideoCapture, game_state: Any) -> Optional[np.ndarray]:
    if game_state.camera_available:
        try:
            ret, frame = cap.read()
            if not ret:
                logger.error("Camera read failed, switching to static frame")
                game_state.camera_available = False
                frame = game_state.static_frame
        except cv2.error as e:
            logger.error(f"Camera error: {e}, switching to static frame")
            game_state.camera_available = False
            frame = game_state.static_frame
    else:
        frame = game_state.static_frame
    if frame is None:
        logger.error("Frame is None after capture")
        return None
    return frame

def _detect_balls(frame: np.ndarray, game_state: Any, hsv: np.ndarray) -> Tuple[List[Tuple[int, int, float]], List[Tuple[int, int, float]], List[Tuple[int, int, float]]]:
    detector = BallDetector()
    white_balls, red_balls, half_balls = detector.detect_all_balls(
        frame, game_state.frame_count, game_state, scoring_zones=game_state.scoring_zones, hsv_frame=hsv, debug_mode=game_state.debug_mode
    )
    return white_balls, red_balls, half_balls

def _track_balls(white_balls: List[Tuple[int, int, float]], red_balls: List[Tuple[int, int, float]], half_balls: List[Tuple[int, int, float]], game_state: Any) -> List[Tuple[int, int, float, int, str]]:
    tracker = BallTracker()
    tracked_detected_balls, game_state.next_ball_id = tracker.track_balls(
        white_balls, red_balls, half_balls, game_state.tracked_balls, game_state.next_ball_id,
        game_state.frame_count, game_state.scored_positions, game_state.debug_mode
    )
    game_state.tracked_balls = [(x, y, radius, ball_id, game_state.frame_count, ball_type)
                                for x, y, radius, ball_id, ball_type in tracked_detected_balls]
    return tracked_detected_balls

def _process_frame(frame: np.ndarray, game_state: Any) -> List[Tuple[int, int, float, int, str]]:
    game_state.update_timer()

    # If ball tracking is disabled, return an empty list to skip detection and tracking
    if not game_state.ball_tracking_on:
        return []

    # Run detection every frame
    DETECTION_INTERVAL = 1
    if game_state.frame_count % DETECTION_INTERVAL == 0:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        white_balls, red_balls, half_balls = _detect_balls(frame, game_state, hsv)
        tracked_detected_balls = _track_balls(white_balls, red_balls, half_balls, game_state)
    else:
        # Use the last known positions for tracking
        tracked_detected_balls = [(x, y, radius, ball_id, ball_type) 
                                  for x, y, radius, ball_id, _, ball_type in game_state.tracked_balls]

    game_state.update_score(frame, tracked_detected_balls)
    return tracked_detected_balls

def _render_calibration_overlay(frame: np.ndarray, game_state: Any) -> None:
    """
    Render an overlay for HSV calibration mode, showing the selected point and instructions.
    """
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT), (50, 50, 50), -1)
    alpha = 0.5
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    color_type = game_state.calibrating_color
    instruction = f"Click a {color_type} ball pixel, then press Enter to confirm or 'c' to cancel"
    cv2.putText(frame, instruction, (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_MEDIUM, UIConstants.YELLOW, UIConstants.FONT_THICKNESS)

    if game_state.calibration_point and game_state.calibration_hsv:
        x, y = game_state.calibration_point
        h, s, v = game_state.calibration_hsv
        cv2.line(frame, (x - 10, y), (x + 10, y), UIConstants.RED, 2)
        cv2.line(frame, (x, y - 10), (x, y + 10), UIConstants.RED, 2)
        hsv_text = f"HSV: ({h}, {s}, {v})"
        cv2.putText(frame, hsv_text, (x + 20, y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, UIConstants.FONT_SCALE_SMALL, UIConstants.RED, 1)

def _render_frame(frame: np.ndarray, game_state: Any, tracked_detected_balls: List[Tuple[int, int, float, int, str]], render_balls: bool = True) -> None:
    draw_ui(frame, game_state)
    if render_balls:
        draw_balls(frame, game_state, tracked_detected_balls)
    if game_state.calibrating_color is not None:
        _render_calibration_overlay(frame, game_state)

    try:
        cv2.imshow(UIConstants.WINDOW_NAME, frame)
    except cv2.error as e:
        logger.error(f"Failed to display frame with cv2.imshow: {e}")

def _update_hsv_ranges(game_state: Any) -> None:
    """
    Update the HSV ranges in GameState based on the selected pixel's HSV value and save them to a file.
    """
    if not game_state.calibration_hsv:
        logger.warning("No HSV value selected for calibration")
        return

    h, s, v = [int(val) for val in game_state.calibration_hsv]
    h_range = 10
    s_range = 50
    v_range = 50

    if game_state.calibrating_color == "white":
        game_state.white_hsv_min = (0, 0, max(0, v - v_range))
        game_state.white_hsv_max = (179, min(255, s + s_range), 255)
        logger.info(f"Updated white ball HSV range: min={game_state.white_hsv_min}, max={game_state.white_hsv_max}")
    elif game_state.calibrating_color == "red":
        h_lower = max(0, h - h_range)
        h_upper = min(179, h + h_range)
        s_lower = max(0, s - s_range)
        s_upper = min(255, s + s_range)
        v_lower = max(0, v - v_range)
        v_upper = min(255, v + v_range)
        if h < 90:
            game_state.red_hsv_min = (h_lower, s_lower, v_lower)
            game_state.red_hsv_max = (h_upper, s_upper, v_upper)
            game_state.red_hsv_min2 = (170, s_lower, v_lower)
            game_state.red_hsv_max2 = (179, s_upper, v_upper)
        else:
            game_state.red_hsv_min = (0, s_lower, v_lower)
            game_state.red_hsv_max = (10, s_upper, v_upper)
            game_state.red_hsv_min2 = (h_lower, s_lower, v_lower)
            game_state.red_hsv_max2 = (h_upper, s_upper, v_upper)
        logger.info(f"Updated red ball HSV ranges: min={game_state.red_hsv_min}, max={game_state.red_hsv_max}, "
                    f"min2={game_state.red_hsv_min2}, max2={game_state.red_hsv_max2}")

    game_state._save_hsv_ranges()

def _handle_input(game_state: Any) -> int:
    try:
        key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY) & 0xFF
    except Exception as e:
        logger.error(f"Error in cv2.waitKey: {e}")
        raise
    if key == ord('q'):
        logger.info("Quit key 'q' pressed")
        clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
    elif key == ord('s'):
        game_state.drawing_mode = True
        if game_state.camera_available:
            ret, frame = game_state.cap.read()
            if not ret:
                logger.error("Camera read failed during scoring zone definition, using static frame")
                frame = game_state.static_frame
        else:
            frame = game_state.static_frame
        if frame is not None:
            new_zone, _ = define_scoring_zone(frame, game_state.cap, False, game_state.scoring_zones)
            game_state.drawing_mode = False
            if new_zone:
                game_state.scoring_zones.append(new_zone)
                try:
                    with open("scoring_zones.json", "w") as json_file:
                        json.dump(game_state.scoring_zones, json_file)
                except Exception as e:
                    logger.error(f"Failed to save scoring zones: {e}")
                # Update the special hole after adding a new zone
                game_state._set_special_hole()
    elif key == ord('d'):
        game_state.debug_mode = not game_state.debug_mode
        logger.info(f"Debug mode {'enabled' if game_state.debug_mode else 'disabled'}")
    elif key == 27:  # Escape key
        game_state.menu_state = MenuState.CLOSED
        game_state.menu_active = False
        game_state.submenu_active = None
        game_state.submenu_items = []
    elif game_state.calibrating_color is not None:
        if key == 13:  # Enter key to confirm calibration
            if game_state.calibration_hsv:
                _update_hsv_ranges(game_state)
            game_state.calibrating_color = None
            game_state.calibration_point = None
            game_state.calibration_hsv = None
            logger.info("Calibration confirmed and applied")
        elif key == ord('c'):  # 'c' key to cancel calibration
            game_state.calibrating_color = None
            game_state.calibration_point = None
            game_state.calibration_hsv = None
            logger.info("Calibration cancelled")
    return key

def run_game_loop(game_state: Any) -> None:
    clock = pygame.time.Clock()
    tracked_detected_balls: List[Tuple[int, int, float, int, str]] = []

    while True:
        frame = _capture_frame(game_state.cap, game_state)
        if frame is None:
            logger.error("No frame available (camera and static frame both failed), exiting...")
            game_state.save_score(game_state.get_current_player().name)
            clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
            break

        # Skip frame processing when menu is active
        if not game_state.menu_active:
            tracked_detected_balls = _process_frame(frame, game_state)

        # Check if the timer has reached 0 in timed mode
        if game_state.game_mode == "timed" and game_state.game_timer is not None and game_state.game_timer <= 0:
            logger.info("Time's up in timed mode! Saving score and resetting game.")
            game_state.save_score(game_state.get_current_player().name, mode="timed")
            # Reset game state for a new timed game
            game_state.set_game_mode("timed")  # Resets timer to 120 seconds
            game_state.get_current_player().reset_score()
            game_state.scored_balls.clear()
            game_state.scored_positions.clear()
            game_state.tracked_balls.clear()
            game_state.balls_in_zone.clear()
            game_state.ball_trails.clear()
            game_state.potential_small_balls_white.clear()
            game_state.potential_small_balls_red.clear()
            game_state.scored_cooldown.clear()
            game_state.red_ball_scored = False
            game_state.ball_states.clear()
            game_state.previous_ball_states.clear()
            game_state.special_hole_scored = False
            game_state.achievement_notification = "Time's Up! Game Reset."
            game_state.achievement_notification_timer = 3.0

        game_state.check_achievements()
        game_state.update_achievement_notification(1.0 / GameConstants.FRAME_RATE)
        _render_frame(frame, game_state, tracked_detected_balls, render_balls=not game_state.menu_active)
        key = _handle_input(game_state)

        try:
            visible = cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE)
            if visible <= 0:
                logger.info("Window closed via red X")
                game_state.save_score(game_state.get_current_player().name)
                clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
        except cv2.error as e:
            logger.info(f"Window property check failed, assuming closed: {e}")
            game_state.save_score(game_state.get_current_player().name)
            clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)

        if not game_state.menu_active:
            game_state.frame_count += 1
        clock.tick(GameConstants.FRAME_RATE)