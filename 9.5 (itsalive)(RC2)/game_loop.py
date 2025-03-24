"""
Main game loop logic for the Whiffle Tracker project.
Handles frame capture, processing, rendering, and user input.
"""

import cv2
import logging
import pygame
import numpy as np
from typing import List, Tuple, Optional, Any  # Updated to include Any

from constants import UIConstants, GameConstants  # Import classes
from detection import detect_white_balls, detect_red_balls
from tracking import track_balls
from scoring import define_scoring_zone, is_in_scoring_zone
from utils import clean_exit
from ui import draw_ui, draw_balls

logger = logging.getLogger(__name__)

def _capture_frame(cap: cv2.VideoCapture) -> Optional[np.ndarray]:
    try:
        ret, frame = cap.read()
        if not ret:
            raise RuntimeError("Camera read failed")
        return frame
    except cv2.error as e:
        logger.error(f"Camera error: {e}")
        return None

def _detect_balls(frame: np.ndarray, game_state: Any, hsv: np.ndarray) -> List[Tuple[int, int, float]]:
    detected_balls: List[Tuple[int, int, float]] = []
    detected_red_balls: List[Tuple[int, int, float]] = []

    if game_state.white_ball_detection_on:
        detected_balls = detect_white_balls(frame, game_state.frame_count, game_state.potential_small_balls_white,
                                            game_state.excluded_positions, game_state.debug_mode, hsv_frame=hsv)
    if game_state.red_ball_detection_on:
        detected_red_balls = detect_red_balls(frame, game_state.frame_count, game_state.potential_small_balls_red,
                                              game_state.excluded_positions, game_state.debug_mode, hsv_frame=hsv)
        detected_balls.extend(detected_red_balls)
    return detected_balls, detected_red_balls

def _track_balls(detected_balls: List[Tuple[int, int, float]], game_state: Any) -> List[Tuple[int, int, float, int]]:
    tracked_detected_balls, game_state.next_ball_id = track_balls(detected_balls, game_state.tracked_balls,
                                                                 game_state.next_ball_id, game_state.frame_count,
                                                                 game_state.scored_positions, game_state.debug_mode)
    game_state.tracked_balls = [(x, y, radius, ball_id, game_state.frame_count)
                                for x, y, radius, ball_id in tracked_detected_balls]
    return tracked_detected_balls

def _update_score(frame: np.ndarray, game_state: Any, tracked_detected_balls: List[Tuple[int, int, float, int]]) -> None:
    for x, y, radius, ball_id in tracked_detected_balls:
        ball = (x, y, radius, ball_id)
        current_zone = None
        for zone in game_state.scoring_zones:
            if is_in_scoring_zone(ball, zone):
                current_zone = zone
                break

        previous_zone = game_state.balls_in_zone.get(ball_id)
        if (current_zone and
                ball_id not in game_state.scored_balls and
                previous_zone != current_zone):
            game_state.score += current_zone[4]
            game_state.scored_balls.add(ball_id)
            game_state.scored_positions[(x, y)] = ball_id
            if game_state.game_sounds_on and game_state.score_sound:
                game_state.score_sound.play()
            if game_state.debug_mode:
                logger.info(f"Ball ID {ball_id} at ({x}, {y}) scored {current_zone[4]} points in zone {current_zone}")

        game_state.balls_in_zone[ball_id] = current_zone

    game_state.balls_in_zone = {ball_id: zone for ball_id, zone in game_state.balls_in_zone.items()
                                if ball_id in {ball[3] for ball in game_state.tracked_balls}}

def _process_frame(frame: np.ndarray, game_state: Any) -> Tuple[List[Tuple[int, int, float, int]], List[Tuple[int, int, float]]]:
    game_state.update_timer()
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV) if (game_state.white_ball_detection_on or game_state.red_ball_detection_on) else None
    detected_balls, detected_red_balls = _detect_balls(frame, game_state, hsv)
    tracked_detected_balls = _track_balls(detected_balls, game_state)
    _update_score(frame, game_state, tracked_detected_balls)
    return tracked_detected_balls, detected_red_balls

def _render_frame(frame: np.ndarray, game_state: Any, tracked_detected_balls: List[Tuple[int, int, float, int]], 
                  detected_red_balls: List[Tuple[int, int, float]]) -> None:
    draw_ui(frame, game_state)
    draw_balls(frame, game_state, tracked_detected_balls, detected_red_balls)
    cv2.imshow(UIConstants.WINDOW_NAME, frame)

def _handle_input(game_state: Any) -> int:
    key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY) & 0xFF
    if game_state.debug_mode:
        logger.debug(f"Key pressed: {key}")
    if key == ord('q'):
        logger.info("Quit key 'q' pressed")
        clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on)
    elif key == ord('s'):
        game_state.drawing_mode = True
        ret, frame = game_state.cap.read()
        if ret:
            new_zone, _ = define_scoring_zone(frame, game_state.cap, False, game_state.scoring_zones)
            game_state.drawing_mode = False
            if new_zone:
                game_state.scoring_zones.append(new_zone)
                try:
                    with open("scoring_zones.json", "w") as json_file:
                        json.dump(game_state.scoring_zones, json_file)
                    if game_state.debug_mode:
                        logger.info("Scoring zones saved to scoring_zones.json")
                except Exception as e:
                    logger.error(f"Failed to save scoring zones: {e}")
    elif key == ord('d'):
        game_state.debug_mode = not game_state.debug_mode
        logger.info(f"Debug mode {'enabled' if game_state.debug_mode else 'disabled'}")
    elif key == 27:  # Escape key
        game_state.menu_state = MenuState.CLOSED
        game_state.submenu_active = None
        game_state.submenu_items = []
        if game_state.debug_mode:
            logger.info("Menu closed via Escape key")
    return key

def run_game_loop(game_state: Any) -> None:
    clock = pygame.time.Clock()
    while True:
        frame = _capture_frame(game_state.cap)
        if frame is None:
            logger.error("Camera read failed, exiting...")
            game_state.save_score()
            clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on)
            break

        tracked_detected_balls, detected_red_balls = _process_frame(frame, game_state)
        _render_frame(frame, game_state, tracked_detected_balls, detected_red_balls)
        key = _handle_input(game_state)

        try:
            visible = cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE)
            if visible <= 0:
                logger.info("Window closed via red X")
                game_state.save_score()
                clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on)
        except cv2.error as e:
            logger.info(f"Window property check failed, assuming closed: {e}")
            game_state.save_score()
            clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on)

        game_state.frame_count += 1
        if game_state.debug_mode:
            logger.debug("Frame processed")
        clock.tick(GameConstants.FRAME_RATE)