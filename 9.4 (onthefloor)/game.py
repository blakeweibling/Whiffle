"""
Main game loop for the Whiffle Tracker project.

This module initializes the game state, displays a splash screen, and runs the main game loop,
integrating ball detection, tracking, scoring, and menu functionality.
"""

import cv2
import logging
import pygame
import numpy as np
import time
import os
from dotenv import load_dotenv
from typing import Optional, List, Tuple, Dict, Any

from constants import (
    GREEN, RED, YELLOW, WHITE, BLUE,
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_NAME,
    DEFAULT_TIME_LIMIT, DEFAULT_MUSIC_VOLUME
)
from detection import detect_white_balls, detect_red_balls
from tracking import track_balls
from scoring import define_scoring_zone, is_in_scoring_zone, draw_scoring_zones
from menu import draw_menu, draw_menu_window, load_zones, show_splash_on_click
from utils import mouse_callback, clean_exit
from leaderboard import Leaderboard

# Load environment variables from .env file
load_dotenv()

# Game configuration constants
FRAME_RATE: float = 30.0  # Frames per second
SPLASH_DURATION: float = 10.0  # Seconds
FADE_DURATION: float = 1.0  # Seconds
FONT_SCALE_LARGE: float = 1.0
FONT_SCALE_SMALL: float = 0.5
FONT_THICKNESS: int = 2
EXCLUDED_POSITIONS: List[Tuple[int, int]] = [(1272, 169), (82, 9), (1244, 176)]

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GameState:
    """
    Manages the state of the Whiffle Tracker game.

    Attributes:
        cap: Video capture object.
        score: Current player score.
        high_score: Highest score achieved.
        scoring_zones: List of scoring zones as (x, y, w, h, points) tuples.
        tracked_balls: List of tracked balls as (x, y, radius, ball_id, age) tuples.
        scored_balls: Set of ball IDs that have already scored.
        scored_positions: Dictionary of (x, y) positions that have scored, mapping to ball IDs.
        potential_small_balls: Dictionary tracking potential small balls across frames.
        next_ball_id: Next available ball ID.
        frame_count: Current frame number.
        balls_in_zone: Dictionary mapping ball IDs to the scoring zone they’re in.
        time_limit: Game time limit in seconds.
        game_timer: Current game timer value, or None if not active.
        ball_trails: Dictionary mapping ball IDs to their trails as (x, y, age) tuples.
        score_sound: Sound played when a ball scores.
        background_music: Background music sound object.
        leaderboard: Leaderboard object for managing scores.
        game_sounds_on: Flag indicating if game sounds are enabled.
        background_music_on: Flag indicating if background music is enabled.
        red_ball_detection_on: Flag indicating if red ball detection is enabled.
        white_ball_detection_on: Flag indicating if white ball detection is enabled.
        drawing: Flag indicating if a scoring zone is being drawn.
        start_x: X-coordinate where drawing started.
        start_y: Y-coordinate where drawing started.
        temp_zone: Temporary scoring zone being drawn as (x, y, w, h).
        drawing_mode: Flag indicating if drawing mode is active.
        menu_active: Flag indicating if the menu is active.
        submenu_active: Name of the active submenu, or None.
        menu_items: List of main menu items as (x, y, w, h, label, action) tuples.
        submenu_items: List of submenu items.
        menu_width: Width of the menu window.
        menu_height: Height of the menu window.
        menu_pos_x: X-coordinate of the menu window.
        menu_pos_y: Y-coordinate of the menu window.
        dragging_menu: Flag indicating if the menu is being dragged.
        drag_start_x: X-coordinate where dragging started.
        drag_start_y: Y-coordinate where dragging started.
        debug_mode: Flag indicating if debug mode is enabled.
    """
    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        self.cap: cv2.VideoCapture = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, WINDOW_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WINDOW_HEIGHT)
        width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        logger.info(f"Camera resolution: {width}x{height}")

        if not self.cap.isOpened():
            logger.error("Failed to open camera")
            raise RuntimeError("Camera initialization failed")

        self.score: int = 0
        self.high_score: int = 0
        self.scoring_zones: List[Tuple[int, int, int, int, int]] = []
        self.tracked_balls: List[Tuple[int, int, float, int, int]] = []  # (x, y, radius, ball_id, age)
        self.scored_balls: set = set()
        self.scored_positions: Dict[Tuple[int, int], int] = {}
        self.potential_small_balls: Dict[Tuple[int, int], Tuple[int, int]] = {}
        self.next_ball_id: int = 0
        self.frame_count: int = 0
        self.balls_in_zone: Dict[int, Optional[Tuple[int, int, int, int, int]]] = {}
        self.time_limit: int = DEFAULT_TIME_LIMIT
        self.game_timer: Optional[float] = None
        self.ball_trails: Dict[int, List[Tuple[int, int, int]]] = {}

        # Initialize sounds
        pygame.mixer.init()
        try:
            self.score_sound: pygame.mixer.Sound = pygame.mixer.Sound("ding.wav")
        except pygame.error as e:
            logger.error(f"Failed to load score sound (ding.wav): {e}")
            self.score_sound = None
        try:
            self.background_music: pygame.mixer.Sound = pygame.mixer.Sound("background_music.mp3")
            self.background_music.set_volume(DEFAULT_MUSIC_VOLUME)
        except pygame.error as e:
            logger.error(f"Failed to load background music (background_music.mp3): {e}")
            self.background_music = None

        self.leaderboard: Leaderboard = Leaderboard(supabase_url, supabase_key)

        self.game_sounds_on: bool = True
        self.background_music_on: bool = True
        self.red_ball_detection_on: bool = False
        self.white_ball_detection_on: bool = True

        self.toggle_background_music()

        self.drawing: bool = False
        self.start_x: int = -1
        self.start_y: int = -1
        self.temp_zone: Optional[Tuple[int, int, int, int]] = None
        self.drawing_mode: bool = False

        self.menu_active: bool = False
        self.submenu_active: Optional[str] = None
        self.menu_items: List[Tuple[int, int, int, int, str, Optional[Callable[[], None]]]] = [
            (10, 140, 60, 30, "File", None),
            (70, 140, 80, 30, "Settings", None),
            (150, 140, 60, 30, "Help", None),
            (210, 140, 60, 30, "About", None),
            (270, 140, 80, 30, "Leaderboard", None)
        ]
        self.submenu_items: List[Any] = []
        self.menu_width: int = 600
        self.menu_height: int = 600
        self.menu_pos_x: int = (WINDOW_WIDTH - self.menu_width) // 2
        self.menu_pos_y: int = (WINDOW_HEIGHT - self.menu_height) // 2
        self.dragging_menu: bool = False
        self.drag_start_x: int = 0
        self.drag_start_y: int = 0

        self.debug_mode: bool = False
        self.excluded_positions: List[Tuple[int, int]] = EXCLUDED_POSITIONS

        self.scoring_zones = load_zones(self.scoring_zones)
        self._initialize_balls_in_zone()

    def _initialize_balls_in_zone(self) -> None:
        """Initialize the balls_in_zone dictionary by detecting balls in the first frame."""
        ret, frame = self.cap.read()
        if not ret:
            logger.error("Failed to read initial frame for ball initialization")
            return
        detected_balls = detect_white_balls(frame, self.frame_count, self.potential_small_balls,
                                            self.excluded_positions, self.debug_mode)
        tracked_detected_balls, self.next_ball_id = track_balls(detected_balls, self.tracked_balls,
                                                               self.next_ball_id, self.frame_count,
                                                               self.scored_positions, self.debug_mode)
        self.tracked_balls = [(x, y, radius, ball_id, self.frame_count)
                              for x, y, radius, ball_id in tracked_detected_balls]
        for x, y, radius, ball_id, _ in self.tracked_balls:
            ball = (x, y, radius, ball_id)
            for zone in self.scoring_zones:
                if is_in_scoring_zone(ball, zone):
                    self.balls_in_zone[ball_id] = zone
                    if self.debug_mode:
                        logger.info(f"Ball ID {ball_id} at ({x}, {y}) already in zone {zone} at startup")
                    break
            if ball_id not in self.balls_in_zone:
                self.balls_in_zone[ball_id] = None

    def load_high_score(self) -> None:
        """Load the high score from the leaderboard."""
        scores, _ = self.leaderboard.get_top_scores("classic", 1)
        self.high_score = scores[0]["score"] if scores else 0

    def save_score(self, initials: str = "ANON", mode: str = "classic") -> None:
        """
        Save the current score to the leaderboard.

        Args:
            initials: Player initials (default: "ANON").
            mode: Game mode (default: "classic").
        """
        self.leaderboard.submit_score(initials, self.score, mode)
        if self.score > self.high_score:
            self.high_score = self.score

    def toggle_background_music(self) -> None:
        """Toggle background music on or off."""
        if self.background_music is None:
            return
        if self.background_music_on:
            if not pygame.mixer.get_busy():
                self.background_music.play(-1)
        else:
            self.background_music.stop()

def _draw_ui(frame: np.ndarray, game_state: GameState) -> None:
    """
    Draw the UI elements (score, timer, scoring zones, menu) on the frame.

    Args:
        frame: Frame to draw on.
        game_state: Game state object.
    """
    # Draw score and high score
    cv2.putText(frame, f"Score: {game_state.score}  High: {game_state.high_score}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE_LARGE, GREEN, FONT_THICKNESS)

    # Draw timer
    if game_state.game_timer is not None:
        game_state.game_timer -= 1 / FRAME_RATE
        timer_display = int(max(0, game_state.game_timer))
        cv2.putText(frame, f"Time: {timer_display}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE_LARGE, YELLOW, FONT_THICKNESS)
        if game_state.game_timer <= 0:
            game_state.game_timer = 0

    # Draw scoring zones
    draw_scoring_zones(frame, game_state.scoring_zones)

    # Draw temporary scoring zone
    if game_state.temp_zone and game_state.drawing:
        x, y, w, h = game_state.temp_zone
        cv2.rectangle(frame, (x, y), (x + w, y + h), YELLOW, FONT_THICKNESS)
        # Note: Points are now handled in define_scoring_zone, no need for trackbar here

    # Draw menu
    draw_menu(frame, game_state)
    draw_menu_window(frame, game_state)

def _detect_and_track_balls(frame: np.ndarray, game_state: GameState) -> List[Tuple[int, int, float, int]]:
    """
    Detect and track balls in the frame.

    Args:
        frame: Input frame.
        game_state: Game state object.

    Returns:
        Tuple of (tracked_detected_balls, detected_red_balls), where tracked_detected_balls is a list
        of (x, y, radius, ball_id) tuples, and detected_red_balls is a list of detected red balls.
    """
    # Convert to HSV once for both white and red ball detection
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV) if (game_state.white_ball_detection_on or
                                                     game_state.red_ball_detection_on) else None

    detected_balls: List[Tuple[int, int, float]] = []
    detected_red_balls: List[Tuple[int, int, float]] = []

    if game_state.white_ball_detection_on:
        detected_balls = detect_white_balls(frame, game_state.frame_count, game_state.potential_small_balls,
                                            game_state.excluded_positions, game_state.debug_mode, hsv_frame=hsv)
    if game_state.red_ball_detection_on:
        detected_red_balls = detect_red_balls(frame, game_state.frame_count, game_state.potential_small_balls,
                                              game_state.excluded_positions, game_state.debug_mode, hsv_frame=hsv)
        detected_balls.extend(detected_red_balls)

    tracked_detected_balls, game_state.next_ball_id = track_balls(detected_balls, game_state.tracked_balls,
                                                                 game_state.next_ball_id, game_state.frame_count,
                                                                 game_state.scored_positions, game_state.debug_mode)
    # Update tracked_balls with the age (frame_count) for tracking purposes
    game_state.tracked_balls = [(x, y, radius, ball_id, game_state.frame_count)
                                for x, y, radius, ball_id in tracked_detected_balls]
    return tracked_detected_balls, detected_red_balls

def _draw_balls(frame: np.ndarray, game_state: GameState, tracked_detected_balls: List[Tuple[int, int, float, int]],
                detected_red_balls: List[Tuple[int, int, float]]) -> None:
    """
    Draw tracked balls and their trails on the frame.

    Args:
        frame: Frame to draw on.
        game_state: Game state object.
        tracked_detected_balls: List of tracked balls as (x, y, radius, ball_id) tuples.
        detected_red_balls: List of detected red balls.
    """
    # Update and draw ball trails
    for ball_id in list(game_state.ball_trails.keys()):
        game_state.ball_trails[ball_id] = [(x, y, a + 1) for x, y, a in game_state.ball_trails[ball_id] if a < 20]
        if not game_state.ball_trails[ball_id]:
            del game_state.ball_trails[ball_id]

    for x, y, radius, ball_id in tracked_detected_balls:  # Unpack 4 elements
        is_red = any((x, y, radius) in detected_red_balls for _ in [detected_red_balls]
                     if game_state.red_ball_detection_on)
        game_state.ball_trails.setdefault(ball_id, []).append((x, y, 0))
        for tx, ty, age in game_state.ball_trails.get(ball_id, []):
            alpha = 1 - (age / 20)
            color = BLUE if is_red else RED
            cv2.circle(frame, (tx, ty), int(radius * (1 - age / 40)), color, 2)

        # Draw the ball
        color = BLUE if is_red else RED
        cv2.circle(frame, (x, y), int(radius), color, 2)
        cv2.putText(frame, f"ID: {ball_id}", (x + 20, y),
                    cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE_SMALL, color, 1)

def _update_score(frame: np.ndarray, game_state: GameState, tracked_detected_balls: List[Tuple[int, int, float, int]]) -> None:
    """
    Update the score based on balls entering scoring zones.

    Args:
        frame: Input frame.
        game_state: Game state object.
        tracked_detected_balls: List of tracked balls as (x, y, radius, ball_id) tuples.
    """
    for x, y, radius, ball_id in tracked_detected_balls:  # Unpack 4 elements
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

def show_splash_screen(supabase_url: str, supabase_key: str) -> Optional['GameState']:
    """
    Display the splash screen with a fade effect and initialize the game state.

    Args:
        supabase_url: Supabase URL for the leaderboard.
        supabase_key: Supabase API key for the leaderboard.

    Returns:
        Initialized GameState object, or None if the splash screen is skipped.
    """
    splash = cv2.imread("splash.png")
    if splash is None:
        logger.error("Failed to load splash.png, skipping splash screen")
        return None

    splash = cv2.resize(splash, (WINDOW_WIDTH, WINDOW_HEIGHT))
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    start_time = time.time()
    game_state = GameState(supabase_url, supabase_key)
    ret, first_frame = game_state.cap.read()
    if not ret:
        logger.error("Camera failed during splash screen, exiting...")
        clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on)
        return None

    while time.time() - start_time < SPLASH_DURATION + FADE_DURATION:
        elapsed = time.time() - start_time
        if elapsed < SPLASH_DURATION:
            cv2.imshow(WINDOW_NAME, splash)
        else:
            alpha = 1 - (elapsed - SPLASH_DURATION) / FADE_DURATION
            beta = 1 - alpha
            blended = cv2.addWeighted(splash, alpha, first_frame, beta, 0)
            cv2.imshow(WINDOW_NAME, blended)

        if cv2.waitKey(20) & 0xFF == ord('q'):
            clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on)
            return None

    return game_state

def main() -> None:
    """
    Run the main game loop for Whiffle Tracker.
    """
    # Load Supabase credentials from environment variables
    supabase_url = os.getenv("SUPABASE_URL", "https://default-supabase-url.supabase.co")
    supabase_key = os.getenv("SUPABASE_KEY", "default-supabase-api-key")

    # Warn if default Supabase URL is used
    if supabase_url == "https://default-supabase-url.supabase.co":
        logger.warning("Supabase URL not set in .env file. Using default URL, which will fail. Please set SUPABASE_URL and SUPABASE_KEY in .env file.")

    game_state = show_splash_screen(supabase_url, supabase_key)
    if game_state is None:
        return

    cv2.setMouseCallback(WINDOW_NAME, mouse_callback, game_state)

    print("Press 'q' to quit, 's' to start drawing a scoring zone, 'd' to toggle debug mode")

    ret, frame = game_state.cap.read()
    if ret:
        cv2.imshow(WINDOW_NAME, frame)
        cv2.waitKey(100)

    try:
        while True:
            ret, frame = game_state.cap.read()
            if not ret:
                logger.error("Camera read failed, exiting...")
                clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on)
                break

            _draw_ui(frame, game_state)

            tracked_detected_balls, detected_red_balls = _detect_and_track_balls(frame, game_state)
            _draw_balls(frame, game_state, tracked_detected_balls, detected_red_balls)
            _update_score(frame, game_state, tracked_detected_balls)

            cv2.imshow(WINDOW_NAME, frame)

            key = cv2.waitKey(20) & 0xFF
            if game_state.debug_mode:
                logger.debug(f"Key pressed: {key}")
                try:
                    visible = cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE)
                    logger.debug(f"Window visible property: {visible}")
                except cv2.error as e:
                    logger.warning(f"Failed to get window property: {e}")
                    clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on)
                    break

            if key == ord('q'):
                logger.info("Quit key 'q' pressed")
                clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on)
            elif key == ord('s'):
                game_state.drawing_mode = True
                new_zone, _ = define_scoring_zone(frame, game_state.cap, False, game_state.scoring_zones)
                game_state.drawing_mode = False
                if new_zone:
                    game_state.scoring_zones.append(new_zone)
                    try:
                        with open("scoring_zones.json", "w") as f:
                            json.dump(game_state.scoring_zones, f)
                        if game_state.debug_mode:
                            logger.info("Scoring zones saved to scoring_zones.json")
                    except Exception as e:
                        logger.error(f"Failed to save scoring zones: {e}")
            elif key == ord('d'):
                game_state.debug_mode = not game_state.debug_mode
                logger.info(f"Debug mode {'enabled' if game_state.debug_mode else 'disabled'}")
            elif key == 27:  # Escape key
                game_state.menu_active = False
                game_state.submenu_active = None
                game_state.submenu_items = []
                if game_state.debug_mode:
                    logger.info("Menu closed via Escape key")

            try:
                visible = cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE)
                if visible <= 0:
                    logger.info(f"Window closed via red X detected (visible={visible})")
                    clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on)
            except cv2.error as e:
                logger.info(f"Window property check failed, assuming closed: {e}")
                clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on)

            game_state.frame_count += 1
            if game_state.debug_mode:
                logger.debug(f"Frame processed")

    except SystemExit:
        logger.info("Program exited via clean_exit")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
        clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on)

if __name__ == "__main__":
    main()