"""
Constants for the Whiffle Tracker project.

This file defines constants used throughout the project, including color values
in BGR format (for OpenCV) and game configuration settings. Constants are grouped
into classes for organization and can be partially configured via environment variables.
"""

import os
import cv2
import logging
import string  # Import string for player name characters
from typing import Tuple, List, Optional, Dict

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Validation function to ensure positive values
def _assert_positive(value, name):
    assert value > 0, f"{name} must be positive"
    return value


# Validation function to ensure non-negative values
def _assert_non_negative(value, name):
    assert value >= 0, f"{name} must be non-negative"
    return value


# Validation function for range [0.0, 1.0]
def _assert_fractional(value, name):
    assert 0.0 <= value <= 1.0, f"{name} must be between 0.0 and 1.0"
    return value


class UIConstants:
    """Constants for user interface and display settings."""

    # Colors in BGR format for OpenCV (Blue, Green, Red)
    GREEN: Tuple[int, int, int] = (0, 255, 0)
    RED: Tuple[int, int, int] = (0, 0, 255)
    YELLOW: Tuple[int, int, int] = (0, 255, 255)
    WHITE: Tuple[int, int, int] = (255, 255, 255)
    CV2_BLUE: Tuple[int, int, int] = (255, 0, 0)
    BLACK: Tuple[int, int, int] = (0, 0, 0)
    GREY_BG: Tuple[int, int, int] = (100, 100, 100)

    # Window and Display
    WINDOW_NAME: str = "Whiffle Tracker"
    WINDOW_WIDTH: int = _assert_positive(1280, "WINDOW_WIDTH")
    WINDOW_HEIGHT: int = _assert_positive(720, "WINDOW_HEIGHT")

    # Font Sizes
    FONT_SCALE_SMALL: float = _assert_positive(0.5, "FONT_SCALE_SMALL")
    FONT_SCALE_MEDIUM: float = _assert_positive(0.7, "FONT_SCALE_MEDIUM")
    FONT_SCALE_LARGE: float = _assert_positive(1.0, "FONT_SCALE_LARGE")
    FONT_SCALE_XLARGE: float = _assert_positive(2.0, "FONT_SCALE_XLARGE")
    FONT_THICKNESS: int = _assert_positive(1, "FONT_THICKNESS")  # Base thickness

    # Text Positioning
    TEXT_OFFSET_X: int = _assert_non_negative(5, "TEXT_OFFSET_X")
    TEXT_OFFSET_Y: int = _assert_non_negative(15, "TEXT_OFFSET_Y")
    TEXT_SAFE_DISTANCE: int = _assert_non_negative(10, "TEXT_SAFE_DISTANCE")

    # Menu Button
    MENU_BUTTON_WIDTH: int = _assert_positive(100, "MENU_BUTTON_WIDTH")
    MENU_BUTTON_HEIGHT: int = _assert_positive(40, "MENU_BUTTON_HEIGHT")
    MENU_BUTTON_X: int = 10
    MENU_BUTTON_Y: int = 80

    # --- NEW: Menu Close Button ---
    MENU_CLOSE_BUTTON_SIZE: int = _assert_positive(
        40, "MENU_CLOSE_BUTTON_SIZE"
    )  # Size of the square button
    MENU_CLOSE_BUTTON_PADDING: int = _assert_non_negative(
        10, "MENU_CLOSE_BUTTON_PADDING"
    )  # Padding from menu corner
    MENU_CLOSE_BUTTON_COLOR: Tuple[int, int, int] = RED  # Color of the 'X'
    MENU_CLOSE_BUTTON_THICKNESS: int = _assert_positive(
        2, "MENU_CLOSE_BUTTON_THICKNESS"
    )  # Thickness of the 'X'
    # --- END NEW ---

    # Zone Editing Visuals
    ZONE_EDIT_HANDLE_SIZE: int = 8
    ZONE_EDIT_HANDLE_COLOR: Tuple[int, int, int] = (255, 165, 0)  # Orange
    ZONE_EDIT_LINE_COLOR: Tuple[int, int, int] = (255, 165, 0)  # Orange
    ZONE_EDIT_SELECTED_COLOR: Tuple[int, int, int] = (0, 255, 255)  # Yellow highlight
    ZONE_EDIT_MOVE_COLOR: Tuple[int, int, int] = (0, 165, 255)  # Orange-Red for move
    ZONE_EDIT_RESIZE_COLOR: Tuple[int, int, int] = (255, 0, 255)  # Magenta for resize


class CameraConfig:
    """Configuration for camera index and backend selection."""

    # Possible camera indices to try
    CAMERA_INDICES: List[int] = [0, 1, -1]  # -1 for auto-select

    # Supported OpenCV backends
    CAMERA_BACKENDS: Dict[str, int] = {
        "default": cv2.CAP_ANY,  # Let OpenCV choose the backend
        "dshow": cv2.CAP_DSHOW,  # DirectShow (Windows)
        "msmf": cv2.CAP_MSMF,  # Microsoft Media Foundation (Windows)
    }

    # Default backend (set to DirectShow since it worked)
    DEFAULT_BACKEND: str = "dshow"

    @staticmethod
    def get_camera_config() -> Tuple[Optional[int], Optional[int], bool]:
        """
        Determine the best camera index and backend to use, prioritizing DirectShow.
        Returns:
            Tuple of (camera_index, backend, use_camera):
            - camera_index: The selected camera index, or None if no camera is available.
            - backend: The selected backend, or None if no camera is available.
            - use_camera: True if a camera should be used, False if fallback to static frame is needed.
        """
        # Check environment variables for overrides
        env_index = os.getenv("WHIFFLE_CAMERA_INDEX")
        env_backend = os.getenv("WHIFFLE_CAMERA_BACKEND", CameraConfig.DEFAULT_BACKEND)

        # Validate environment variables
        if env_index is not None:
            try:
                preferred_index = int(env_index)
                if preferred_index < -1:
                    logger.warning(
                        f"Invalid camera index from WHIFFLE_CAMERA_INDEX: {env_index}. Ignoring."
                    )
                    preferred_index = None
            except ValueError:
                logger.warning(
                    f"Invalid WHIFFLE_CAMERA_INDEX value: {env_index}. Must be an integer. Ignoring."
                )
                preferred_index = None
        else:
            preferred_index = None

        if env_backend not in CameraConfig.CAMERA_BACKENDS:
            logger.warning(
                f"Invalid backend from WHIFFLE_CAMERA_BACKEND: {env_backend}. Using default: {CameraConfig.DEFAULT_BACKEND}"
            )
            env_backend = CameraConfig.DEFAULT_BACKEND

        # If a specific index is provided via environment variable, prioritize it
        indices_to_try = (
            [preferred_index]
            if preferred_index is not None
            else CameraConfig.CAMERA_INDICES
        )

        # Prioritize the specified or default backend (DirectShow)
        backend = CameraConfig.CAMERA_BACKENDS[env_backend]
        backend_name = env_backend

        # Try each index with the selected backend
        for index in indices_to_try:
            logger.info(
                f"Trying camera index {index} with backend {backend_name} ({backend})..."
            )
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                logger.info(
                    f"Successfully opened camera at index {index} with backend {backend_name}"
                )
                # Test capturing a frame to ensure the camera is functional
                ret, _ = cap.read()
                if ret:
                    logger.info(
                        f"Camera at index {index} with backend {backend_name} is functional"
                    )
                    cap.release()
                    return index, backend, True
                else:
                    logger.warning(
                        f"Camera at index {index} with backend {backend_name} opened but failed to capture a frame"
                    )
            else:
                logger.warning(
                    f"Failed to open camera at index {index} with backend {backend_name}"
                )
            cap.release()

        # If no camera is found with DirectShow, try other backends as a fallback
        if env_backend == CameraConfig.DEFAULT_BACKEND:
            other_backends = [
                name
                for name in CameraConfig.CAMERA_BACKENDS.keys()
                if name != CameraConfig.DEFAULT_BACKEND
            ]
            for backend_name in other_backends:
                backend = CameraConfig.CAMERA_BACKENDS[backend_name]
                for index in indices_to_try:
                    logger.info(
                        f"Trying camera index {index} with fallback backend {backend_name} ({backend})..."
                    )
                    cap = cv2.VideoCapture(index, backend)
                    if cap.isOpened():
                        logger.info(
                            f"Successfully opened camera at index {index} with backend {backend_name}"
                        )
                        ret, _ = cap.read()
                        if ret:
                            logger.info(
                                f"Camera at index {index} with backend {backend_name} is functional"
                            )
                            cap.release()
                            return index, backend, True
                        else:
                            logger.warning(
                                f"Camera at index {index} with backend {backend_name} opened but failed to capture a frame"
                            )
                    else:
                        logger.warning(
                            f"Failed to open camera at index {index} with backend {backend_name}"
                        )
                    cap.release()

        # If no camera is found, fall back to static frame
        logger.warning("No working camera found. Falling back to static frame.")
        return None, None, False


class GameConstants:
    """Constants for general game configuration and timing."""

    # Performance
    FRAME_RATE: int = _assert_positive(30, "FRAME_RATE")
    WAIT_KEY_DELAY: int = max(1, int(1000 / FRAME_RATE) // 3)
    DETECTION_FRAME_INTERVAL: int = _assert_positive(2, "DETECTION_FRAME_INTERVAL")

    # File Paths
    ZONES_FILE: str = "scoring_zones.json"
    ACHIEVEMENTS_FILE: str = "achievements_status.json"
    HSV_RANGES_FILE: str = "hsv_ranges.json"
    HIGH_SCORE_FILE: str = "high_scores.json"
    SPLASH_SCREEN_FILE: str = "splash.png"
    SPLASH_SCREEN_FILE2: str = "splash2.png"
    GAME_OVER_SPLASH_FILE: str = "game_over.png"
    STATIC_FRAME_FILE: str = "last_frame.png"
    SOUND_EFFECTS_PATH: str = "sounds/"

    # Splash Screen
    SPLASH_DURATION: float = _assert_non_negative(2.0, "SPLASH_DURATION")
    FADE_DURATION: float = _assert_non_negative(1.0, "FADE_DURATION")

    # Game Modes
    TIMED_MODE_DURATION: float = _assert_positive(90.0, "TIMED_MODE_DURATION")
    TIMED_MODE_WIN_SCORE: int = _assert_positive(500, "TIMED_MODE_WIN_SCORE")

    # Scoring Logic
    POSITION_HISTORY_LENGTH: int = _assert_positive(5, "POSITION_HISTORY_LENGTH")
    REST_THRESHOLD_DISTANCE: float = _assert_non_negative(
        10.0, "REST_THRESHOLD_DISTANCE"
    )
    ZONE_STABILITY_FRAMES: int = _assert_positive(45, "ZONE_STABILITY_FRAMES")
    SCORE_COOLDOWN_DURATION: float = _assert_non_negative(
        9000.0, "SCORE_COOLDOWN_DURATION"
    )

    # Ball Tracking / Trail
    # BALL_TRAIL_LENGTH: int = _assert_non_negative(15, "BALL_TRAIL_LENGTH") # Removed

    # Camera Configuration
    CAMERA_INDEX, CAMERA_BACKEND, USE_CAMERA = CameraConfig.get_camera_config()

    # Audio
    DEFAULT_SOUND_VOLUME: float = _assert_fractional(0.7, "DEFAULT_SOUND_VOLUME")
    DEFAULT_MUSIC_VOLUME: float = _assert_fractional(0.5, "DEFAULT_MUSIC_VOLUME")


class MenuConstants:
    """Constants defining menu structures."""

    MAIN_MENU_ITEMS: List[Tuple[str, str]] = [
        ("Resume", "resume"),
        ("Settings", "settings"),
        ("Game Mode", "game_mode"),
        ("Manage Zones", "manage_zones"),
        ("Players", "players"),
        ("Leaderboard", "leaderboard"),
        ("Achievements", "achievements"),
        ("Help", "help"),
        ("FAQ", "faq"),
        ("About", "about"),
        ("Quit Game", "quit"),
    ]
    ZONE_SUBMENU_ITEMS: List[Tuple[str, str]] = [
        ("Add Zone (Start 's')", "add_zone_info"),
        ("Clear All Zones", "clear_zones"),
        ("Edit Zones", "edit_zones"),
        ("Save Zones", "save_zones"),
        ("Load Zones", "load_zones"),
        ("Back", "back_to_main"),
    ]


class GameSpecificConstants:
    """Constants specific to the Whiffle ball game physics or rules."""

    EXCLUDED_POSITIONS: List[Tuple[int, int, int]] = []


# --- NEW Player Constants ---
class PlayerConstants:
    """Constants related to player configuration."""

    MAX_PLAYER_NAME_LENGTH: int = _assert_positive(15, "MAX_PLAYER_NAME_LENGTH")
    ALLOWED_PLAYER_NAME_CHARS: str = (
        string.ascii_letters + string.digits + " _-"
    )  # Allow letters, digits, space, underscore, hyphen


class DetectionConstants:
    """Constants for ball detection parameters."""

    YOLO_CONFIDENCE_THRESHOLD: float = _assert_non_negative(
        0.5, "YOLO_CONFIDENCE_THRESHOLD"
    )
    SMALL_BALL_CONFIRM_THRESHOLD: int = _assert_positive(
        3, "SMALL_BALL_CONFIRM_THRESHOLD"
    )
    KERNEL_SIZE: Tuple[int, int] = (5, 5)
    ERODE_ITERATIONS: int = _assert_positive(1, "ERODE_ITERATIONS")
    DILATE_ITERATIONS: int = _assert_positive(2, "DILATE_ITERATIONS")
    # Add exclusion distance constant if needed, e.g.:
    # EXCLUSION_DISTANCE: float = _assert_non_negative(50.0, "EXCLUSION_DISTANCE")


class TrackingConstants:
    """Constants for ball tracking parameters."""

    TRACKING_DISTANCE_THRESHOLD: float = _assert_positive(
        100.0, "TRACKING_DISTANCE_THRESHOLD"
    )
    SCORED_DISTANCE_THRESHOLD: float = _assert_positive(
        100.0, "SCORED_DISTANCE_THRESHOLD"
    )
    MAX_AGE_FRAMES: int = _assert_positive(30000, "MAX_AGE_FRAMES")


class ScoringConstants:
    """Constants for scoring logic."""

    DEFAULT_POINTS: int = _assert_positive(100, "DEFAULT_POINTS")
    MAX_POINTS: int = _assert_positive(999, "MAX_POINTS")
    MIN_ZONE_SIZE: int = _assert_positive(10, "MIN_ZONE_SIZE")


class LeaderboardConstants:
    """Constants for leaderboard management."""

    LEADERBOARD_FILE: str = "whiffle_leaderboard.json"
    TABLE_NAME: str = "whifflescores"
    BATCH_SIZE: int = _assert_positive(10, "BATCH_SIZE")
    FLUSH_INTERVAL: float = _assert_positive(60.0, "FLUSH_INTERVAL")
