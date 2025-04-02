# game_constants.py

import cv2
import numpy as np
import string # Added for PlayerConstants
import os # Added for CameraConfig logic
import logging # Added for CameraConfig logic
from typing import Tuple, List, Optional, Dict, Any # Added Any/Dict/Optional for CameraConfig

logger = logging.getLogger(__name__) # Added for CameraConfig logic

# --- Validation Helpers (from original constants.py) ---
def _assert_positive(value, name):
    assert value > 0, f"{name} must be positive"
    return value

def _assert_non_negative(value, name):
    assert value >= 0, f"{name} must be non-negative"
    return value

def _assert_fractional(value, name):
    assert 0.0 <= value <= 1.0, f"{name} must be between 0.0 and 1.0"
    return value

# --- CameraConfig (from original constants.py) ---
class CameraConfig:
    """Configuration for camera index and backend selection."""
    CAMERA_INDICES: List[int] = [0, 1, -1]
    CAMERA_BACKENDS: Dict[str, int] = {
        "default": cv2.CAP_ANY,
        "dshow": cv2.CAP_DSHOW,
        "msmf": cv2.CAP_MSMF,
    }
    DEFAULT_BACKEND: str = "dshow"

    @staticmethod
    def get_camera_config() -> Tuple[Optional[int], Optional[int], bool]:
        """Determine the best camera index and backend to use."""
        env_index = os.getenv("WHIFFLE_CAMERA_INDEX")
        env_backend = os.getenv("WHIFFLE_CAMERA_BACKEND", CameraConfig.DEFAULT_BACKEND)
        preferred_index = None
        if env_index is not None:
            try:
                preferred_index = int(env_index)
                if preferred_index < -1: preferred_index = None
            except ValueError: preferred_index = None
        if env_backend not in CameraConfig.CAMERA_BACKENDS:
            env_backend = CameraConfig.DEFAULT_BACKEND

        indices_to_try = [preferred_index] if preferred_index is not None else CameraConfig.CAMERA_INDICES
        backend = CameraConfig.CAMERA_BACKENDS[env_backend]
        backend_name = env_backend

        for index in indices_to_try:
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                ret, _ = cap.read()
                cap.release()
                if ret:
                    logger.info(f"Using camera index {index} with backend {backend_name}")
                    return index, backend, True
            else:
                cap.release()

        # Fallback logic (simplified for brevity, ensure full logic if needed)
        if env_backend == CameraConfig.DEFAULT_BACKEND:
            other_backends = [n for n in CameraConfig.CAMERA_BACKENDS if n != env_backend]
            for bk_name in other_backends:
                bk = CameraConfig.CAMERA_BACKENDS[bk_name]
                for index in indices_to_try:
                    cap = cv2.VideoCapture(index, bk)
                    if cap.isOpened():
                        ret, _ = cap.read()
                        cap.release()
                        if ret:
                             logger.info(f"Using camera index {index} with fallback backend {bk_name}")
                             return index, bk, True
                    else:
                        cap.release()

        logger.warning("No working camera found. Falling back to static frame assumption.")
        return None, None, False # Indicate fallback needed

# --- UI Constants (Merged) ---
class UIConstants:
    """Constants for user interface and display settings."""
    GREEN: tuple[int, int, int] = (0, 255, 0)
    RED: tuple[int, int, int] = (0, 0, 255)
    YELLOW: tuple[int, int, int] = (0, 255, 255)
    WHITE: tuple[int, int, int] = (255, 255, 255)
    CV2_BLUE: tuple[int, int, int] = (255, 0, 0)
    BLACK: tuple[int, int, int] = (0, 0, 0)
    GREY_BG: tuple[int, int, int] = (100, 100, 100)
    LIGHT_GRAY: tuple[int, int, int] = (200, 200, 200)
    DARK_GRAY: tuple[int, int, int] = (100, 100, 100)

    WINDOW_NAME: str = "Whiffle Tracker"
    # Use consistent Window dimensions (e.g., from original constants.txt or adjusted game_state usage)
    # Let's use the values from the original constants.txt as the primary source for now
    WINDOW_WIDTH: int = _assert_positive(1280, "WINDOW_WIDTH")
    WINDOW_HEIGHT: int = _assert_positive(720, "WINDOW_HEIGHT")

    # Font Sizes
    FONT_SCALE_SMALL: float = _assert_positive(0.5, "FONT_SCALE_SMALL")
    FONT_SCALE_MEDIUM: float = _assert_positive(0.7, "FONT_SCALE_MEDIUM")
    FONT_SCALE_LARGE: float = _assert_positive(1.0, "FONT_SCALE_LARGE")
    FONT_SCALE_XLARGE: float = _assert_positive(2.0, "FONT_SCALE_XLARGE")
    FONT_THICKNESS: int = _assert_positive(1, "FONT_THICKNESS")

    # Text Positioning
    TEXT_OFFSET_X: int = _assert_non_negative(5, "TEXT_OFFSET_X")
    TEXT_OFFSET_Y: int = _assert_non_negative(15, "TEXT_OFFSET_Y")
    TEXT_SAFE_DISTANCE: int = _assert_non_negative(10, "TEXT_SAFE_DISTANCE")

    # Menu Button (from original constants.txt)
    MENU_BUTTON_WIDTH: int = _assert_positive(100, "MENU_BUTTON_WIDTH")
    MENU_BUTTON_HEIGHT: int = _assert_positive(40, "MENU_BUTTON_HEIGHT")
    MENU_BUTTON_X: int = 10
    MENU_BUTTON_Y: int = 80

    # Menu Window Dimensions (Using values from original constants.txt analysis)
    MENU_WIDTH: int = 600 # Default width used in menu.py
    MENU_HEIGHT: int = 450 # Default height used in menu.py

    # Zone Editing Visuals (from original constants.txt)
    ZONE_EDIT_HANDLE_SIZE: int = 8
    ZONE_EDIT_HANDLE_COLOR: Tuple[int, int, int] = (255, 165, 0) # Orange
    ZONE_EDIT_LINE_COLOR: Tuple[int, int, int] = (255, 165, 0) # Orange
    ZONE_EDIT_SELECTED_COLOR: Tuple[int, int, int] = (0, 255, 255) # Yellow highlight
    ZONE_EDIT_MOVE_COLOR: Tuple[int, int, int] = (0, 165, 255) # Orange-Red for move
    ZONE_EDIT_RESIZE_COLOR: Tuple[int, int, int] = (255, 0, 255) # Magenta for resize

    # Notification Durations
    NOTIFICATION_DURATION: float = 2.0
    NOTIFICATION_ERROR_DURATION: float = 3.0

# --- Game Constants (Merged) ---
class GameConstants:
    """Constants for general game configuration and timing."""
    # Camera Configuration (Determined at runtime now)
    CAMERA_INDEX, CAMERA_BACKEND, USE_CAMERA = CameraConfig.get_camera_config()

    # Performance
    FRAME_RATE: int = _assert_positive(30, "FRAME_RATE")
    WAIT_KEY_DELAY: int = max(1, int(1000 / FRAME_RATE) // 3)
    DETECTION_FRAME_INTERVAL: int = _assert_positive(2, "DETECTION_FRAME_INTERVAL")

    # File Paths (from original constants.txt)
    ZONES_FILE: str = "scoring_zones.json"
    ACHIEVEMENTS_FILE: str = "achievements_status.json"
    HSV_RANGES_FILE: str = "hsv_ranges.json"
    HIGH_SCORE_FILE: str = "high_scores.json"
    SPLASH_SCREEN_FILE: str = "splash.png"
    SPLASH_SCREEN_FILE2: str = "splash2.png" # Keep if used
    GAME_OVER_SPLASH_FILE: str = "game_over.png"
    STATIC_FRAME_FILE: str = "last_frame.png" # Fallback image
    SOUND_EFFECTS_PATH: str = "sounds/"
    LEADERBOARD_FILE: str = "whiffle_leaderboard.json" # Moved from LeaderboardConstants

    # Splash Screen (from original constants.txt)
    SPLASH_DURATION: float = _assert_non_negative(2.0, "SPLASH_DURATION")
    FADE_DURATION: float = _assert_non_negative(1.0, "FADE_DURATION")

    # Game Modes & Timing (Using values from original constants.txt)
    TIMED_MODE_DURATION: float = _assert_positive(90.0, "TIMED_MODE_DURATION")
    TIMED_MODE_WIN_SCORE: int = _assert_positive(500, "TIMED_MODE_WIN_SCORE")
    LOW_TIME_WARNING: float = 10.0 # Seconds remaining

    # Ball State / Scoring Logic (Using values from original constants.txt)
    POSITION_HISTORY_LENGTH: int = _assert_positive(5, "POSITION_HISTORY_LENGTH")
    REST_THRESHOLD_DISTANCE: float = _assert_non_negative(10.0, "REST_THRESHOLD_DISTANCE") # Keep original name
    ZONE_STABILITY_FRAMES: int = _assert_positive(45, "ZONE_STABILITY_FRAMES") # Keep original name
    SCORE_COOLDOWN_DURATION: float = _assert_non_negative(9000.0, "SCORE_COOLDOWN_DURATION") # Keep original float ms

    # Ball Tracking / Trail (from original constants.txt)
    BALL_TRAIL_LENGTH: int = _assert_non_negative(15, "BALL_TRAIL_LENGTH")

    # Audio (from original constants.txt)
    DEFAULT_SOUND_VOLUME: float = _assert_fractional(0.7, "DEFAULT_SOUND_VOLUME")
    DEFAULT_MUSIC_VOLUME: float = _assert_fractional(0.5, "DEFAULT_MUSIC_VOLUME")

    # Renamed from game_constants ZONE_HISTORY_LENGTH, REST_THRESHOLD_PIXELS, ZONE_STABILITY_THRESHOLD
    # Keep original names from constants.txt for consistency unless refactoring is done everywhere
    ZONE_HISTORY_LENGTH: int = _assert_positive(5, "ZONE_HISTORY_LENGTH") # Value from game_state analysis
    # REST_THRESHOLD_PIXELS is derived from REST_THRESHOLD_DISTANCE, no separate constant needed?
    # ZONE_STABILITY_THRESHOLD is ZONE_STABILITY_FRAMES

# --- Scoring Constants (Merged) ---
class ScoringConstants:
    """Constants for scoring logic."""
    DEFAULT_POINTS: int = _assert_positive(100, "DEFAULT_POINTS")
    MAX_POINTS: int = _assert_positive(999, "MAX_POINTS")
    MIN_ZONE_SIZE: int = _assert_positive(10, "MIN_ZONE_SIZE")
    # Values from game_state analysis/original game_constants
    SPECIAL_HOLE_POINTS: int = 100
    SPECIAL_HOLE_BONUS_MULTIPLIER: int = 2
    # Ball Type Multipliers (Example - ensure these match intended logic)
    MULTIPLIER_RED_BALL: float = 2.0
    MULTIPLIER_HALF_BALL: float = 1.5
    MULTIPLIER_DEFAULT: float = 1.0
    # SCORE_COOLDOWN_DURATION is now in GameConstants

# --- MenuConstants (from original constants.py) ---
class MenuConstants:
    """Constants defining menu structures."""
    MAIN_MENU_ITEMS: List[Tuple[str, str]] = [
        ("Resume", "resume"), ("Settings", "settings"), ("Game Mode", "game_mode"),
        ("Manage Zones", "manage_zones"), ("Players", "players"), ("Leaderboard", "leaderboard"),
        ("Achievements", "achievements"), ("Help", "help"), ("FAQ", "faq"),
        ("About", "about"), ("Quit Game", "quit"),
    ]
    ZONE_SUBMENU_ITEMS: List[Tuple[str, str]] = [
        ("Add Zone (Start 's')", "add_zone_info"), ("Clear All Zones", "clear_zones"),
        ("Edit Zones", "edit_zones"), ("Save Zones", "save_zones"),
        ("Load Zones", "load_zones"), ("Back", "back_to_main"),
    ]

# --- GameSpecificConstants (from original constants.py) ---
class GameSpecificConstants:
    """Constants specific to the Whiffle ball game physics or rules."""
    EXCLUDED_POSITIONS: List[Tuple[int, int, int]] = [] # Ensure format matches usage

# --- PlayerConstants (from original constants.py) ---
class PlayerConstants:
    """Constants related to player configuration."""
    MAX_PLAYER_NAME_LENGTH: int = _assert_positive(15, "MAX_PLAYER_NAME_LENGTH")
    ALLOWED_PLAYER_NAME_CHARS: str = (
        string.ascii_letters + string.digits + " _-"
    )

# --- DetectionConstants (from original constants.py) ---
class DetectionConstants:
    """Constants for ball detection parameters."""
    YOLO_CONFIDENCE_THRESHOLD: float = _assert_non_negative(0.5, "YOLO_CONFIDENCE_THRESHOLD")
    SMALL_BALL_CONFIRM_THRESHOLD: int = _assert_positive(3, "SMALL_BALL_CONFIRM_THRESHOLD")
    KERNEL_SIZE: Tuple[int, int] = (5, 5)
    ERODE_ITERATIONS: int = _assert_positive(1, "ERODE_ITERATIONS")
    DILATE_ITERATIONS: int = _assert_positive(2, "DILATE_ITERATIONS")
    # Add exclusion distance constant if needed, matching usage in detection.py
    EXCLUSION_DISTANCE: float = _assert_non_negative(50.0, "EXCLUSION_DISTANCE") # Value assumed, verify

# --- TrackingConstants (from original constants.py) ---
class TrackingConstants:
    """Constants for ball tracking parameters."""
    TRACKING_DISTANCE_THRESHOLD: float = _assert_positive(100.0, "TRACKING_DISTANCE_THRESHOLD")
    SCORED_DISTANCE_THRESHOLD: float = _assert_positive(100.0, "SCORED_DISTANCE_THRESHOLD")
    MAX_AGE_FRAMES: int = _assert_positive(30000, "MAX_AGE_FRAMES")

# --- LeaderboardConstants (from original constants.py) ---
class LeaderboardConstants:
    """Constants for leaderboard management."""
    LEADERBOARD_FILE: str = "whiffle_leaderboard.json"
    TABLE_NAME: str = "whifflescores"
    BATCH_SIZE: int = _assert_positive(10, "BATCH_SIZE")
    FLUSH_INTERVAL: float = _assert_positive(60.0, "FLUSH_INTERVAL") # Flush interval in seconds