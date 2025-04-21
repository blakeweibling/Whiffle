"""
Constants for the Whiffle Tracker project.

This file defines constants used throughout the project, including color values
in BGR format (for OpenCV) and game configuration settings. Constants are grouped
into classes for organization and can be partially configured via environment variables.
"""

import os
from typing import Tuple, List

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
    # <<< Added semi-transparent grey for text background >>>
    GREY_BG: Tuple[int, int, int] = (100, 100, 100)

    # Window and Display
    WINDOW_NAME: str = "Whiffle Tracker"
    WINDOW_WIDTH: int = _assert_positive(1280, "WINDOW_WIDTH")
    WINDOW_HEIGHT: int = _assert_positive(720, "WINDOW_HEIGHT")

    # Font Sizes
    FONT_SCALE_SMALL: float = _assert_positive(0.5, "FONT_SCALE_SMALL")
    FONT_SCALE_MEDIUM: float = _assert_positive(0.7, "FONT_SCALE_MEDIUM")
    FONT_SCALE_LARGE: float = _assert_positive(1.0, "FONT_SCALE_LARGE")
    FONT_SCALE_XLARGE: float = _assert_positive(2.0, "FONT_SCALE_XLARGE") # For Game Over etc.
    FONT_THICKNESS: int = _assert_positive(1, "FONT_THICKNESS")

    # Text Positioning
    TEXT_OFFSET_X: int = _assert_non_negative(5, "TEXT_OFFSET_X")
    TEXT_OFFSET_Y: int = _assert_non_negative(15, "TEXT_OFFSET_Y")
    TEXT_SAFE_DISTANCE: int = _assert_non_negative(10, "TEXT_SAFE_DISTANCE")

    # Menu Button (<<< MOVED TO TOP LEFT >>>)
    MENU_BUTTON_WIDTH: int = _assert_positive(100, "MENU_BUTTON_WIDTH")
    MENU_BUTTON_HEIGHT: int = _assert_positive(40, "MENU_BUTTON_HEIGHT")
    MENU_BUTTON_X: int = 10 # Moved to left
    MENU_BUTTON_Y: int = 80 # Moved below Mode text (previously 10)


class GameConstants:
    """Constants for general game configuration and timing."""
    # Performance
    FRAME_RATE: int = _assert_positive(30, "FRAME_RATE") # Target FPS (Increased from 15)
    WAIT_KEY_DELAY: int = max(1, int(1000 / FRAME_RATE) // 3) # Delay for cv2.waitKey() based on FRAME_RATE
    DETECTION_FRAME_INTERVAL: int = _assert_positive(2, "DETECTION_FRAME_INTERVAL") # Run detection every N frames (1 = every frame)

    # File Paths
    ZONES_FILE: str = "scoring_zones.json"
    ACHIEVEMENTS_FILE: str = "achievements_status.json"
    HSV_RANGES_FILE: str = "hsv_ranges.json"
    HIGH_SCORE_FILE: str = "high_scores.json"
    SPLASH_SCREEN_FILE: str = "splash.png"
    GAME_OVER_SPLASH_FILE: str = "game_over.png"
    STATIC_FRAME_FILE: str = "static_frame.png" # Fallback if camera fails
    SOUND_EFFECTS_PATH: str = "sounds/" # Path to sound effects directory

    # Splash Screen
    SPLASH_DURATION: float = _assert_non_negative(2.0, "SPLASH_DURATION") # Seconds to show splash
    FADE_DURATION: float = _assert_non_negative(1.0, "FADE_DURATION") # Seconds to fade splash

    # Game Modes
    TIMED_MODE_DURATION: float = _assert_positive(60.0, "TIMED_MODE_DURATION") # Seconds for timed mode
    TIMED_MODE_WIN_SCORE: int = _assert_positive(500, "TIMED_MODE_WIN_SCORE") # Score needed to win timed mode

    # Scoring Logic
    POSITION_HISTORY_LENGTH: int = _assert_positive(5, "POSITION_HISTORY_LENGTH") # Frames for position stability check
    REST_THRESHOLD_DISTANCE: float = _assert_non_negative(5.0, "REST_THRESHOLD_DISTANCE") # Max distance moved to be considered at rest
    ZONE_STABILITY_FRAMES: int = _assert_positive(5, "ZONE_STABILITY_FRAMES") # Frames needed in same zone for stability
    SCORE_COOLDOWN_DURATION: float = _assert_non_negative(1.0, "SCORE_COOLDOWN_DURATION") # Seconds before a ball can score again

    # Ball Tracking / Trail
    BALL_TRAIL_LENGTH: int = _assert_non_negative(15, "BALL_TRAIL_LENGTH") # Max points in ball trail

    # Camera
    CAMERA_INDEX: int = _assert_non_negative(0, "CAMERA_INDEX") # Default camera index

    # --- Audio ---
    DEFAULT_SOUND_VOLUME: float = _assert_fractional(0.7, "DEFAULT_SOUND_VOLUME") # Default volume for sound effects
    DEFAULT_MUSIC_VOLUME: float = _assert_fractional(0.5, "DEFAULT_MUSIC_VOLUME") # Default volume for background music


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
        ("Quit Game", "quit")
    ]
    ZONE_SUBMENU_ITEMS: List[Tuple[str, str]] = [
        ("Add Zone (Start 's')", "add_zone_info"),
        ("Clear All Zones", "clear_zones"),
        ("Edit Zones", "edit_zones"),
        ("Save Zones", "save_zones"),
        ("Load Zones", "load_zones"),
        ("Back", "back_to_main")
    ]

class GameSpecificConstants:
    """Constants specific to the Whiffle ball game physics or rules."""
    EXCLUDED_POSITIONS: List[Tuple[int, int, int]] = []

class DetectionConstants:
    """Constants for ball detection parameters."""
    YOLO_CONFIDENCE_THRESHOLD: float = _assert_non_negative(0.5, "YOLO_CONFIDENCE_THRESHOLD")
    SMALL_BALL_CONFIRM_THRESHOLD: int = _assert_positive(3, "SMALL_BALL_CONFIRM_THRESHOLD")
    KERNEL_SIZE: Tuple[int, int] = (5, 5)
    ERODE_ITERATIONS: int = _assert_positive(1, "ERODE_ITERATIONS")
    DILATE_ITERATIONS: int = _assert_positive(2, "DILATE_ITERATIONS")

class TrackingConstants:
    """Constants for ball tracking parameters."""
    TRACKING_DISTANCE_THRESHOLD: float = _assert_positive(100.0, "TRACKING_DISTANCE_THRESHOLD")
    SCORED_DISTANCE_THRESHOLD: float = _assert_positive(20.0, "SCORED_DISTANCE_THRESHOLD")
    MAX_AGE_FRAMES: int = _assert_positive(30, "MAX_AGE_FRAMES")

class ScoringConstants:
    """Constants for scoring logic."""
    DEFAULT_POINTS: int = _assert_positive(100, "DEFAULT_POINTS")
    MAX_POINTS: int = _assert_positive(999, "MAX_POINTS") # Updated from 300
    MIN_ZONE_SIZE: int = _assert_positive(10, "MIN_ZONE_SIZE")

class LeaderboardConstants:
    """Constants for leaderboard management."""
    LEADERBOARD_FILE: str = "whiffle_leaderboard.json"
    TABLE_NAME: str = "whifflescores"
    BATCH_SIZE: int = _assert_positive(10, "BATCH_SIZE")
    FLUSH_INTERVAL: float = _assert_positive(60.0, "FLUSH_INTERVAL")