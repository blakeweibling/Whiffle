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

def _assert_non_negative(value, name):
    assert value >= 0, f"{name} must be non-negative"
    return value

class UIConstants:
    """Constants for user interface and display settings."""
    # Colors in BGR format for OpenCV (Blue, Green, Red)
    GREEN: Tuple[int, int, int] = (0, 255, 0)  # Bright green for scoring zones
    RED: Tuple[int, int, int] = (0, 0, 255)    # Red for white balls and errors
    YELLOW: Tuple[int, int, int] = (255, 255, 0)  # Yellow for temporary zones and timer
    WHITE: Tuple[int, int, int] = (255, 255, 255)  # White for text
    CV2_BLUE: Tuple[int, int, int] = (255, 0, 0)   # Blue in BGR for red balls (not RGB!)

    # Window settings (configurable via env vars)
    WINDOW_WIDTH: int = _assert_positive(int(os.getenv("WHIFFLE_WINDOW_WIDTH", 1280)), "WINDOW_WIDTH")  # Default 1280px
    WINDOW_HEIGHT: int = _assert_positive(int(os.getenv("WHIFFLE_WINDOW_HEIGHT", 720)), "WINDOW_HEIGHT")  # Default 720px
    WINDOW_NAME: str = "Whiffle"  # Name of the OpenCV window

    # Menu settings
    MENU_WIDTH: int = 750  # Increased from 600 to 750 to accommodate more menu items
    MENU_HEIGHT: int = 600  # Height of the menu overlay in pixels
    MENU_BUTTON_X: int = 10  # X-position of the "Click for Menu" button
    MENU_BUTTON_Y: int = 70  # Y-position of the "Click for Menu" button
    MENU_BUTTON_WIDTH: int = 140  # Width of the "Click for Menu" button
    MENU_BUTTON_HEIGHT: int = 30  # Height of the "Click for Menu" button

    # Submenu settings (moved from menu.py)
    SUBMENU_WIDTH: int = _assert_positive(730, "SUBMENU_WIDTH")  # Increased from 580 to 730 to match MENU_WIDTH
    SUBMENU_HEIGHT: int = _assert_positive(30, "SUBMENU_HEIGHT")  # Height of submenu items
    SUBMENU_Y_OFFSET: int = _assert_positive(50, "SUBMENU_Y_OFFSET")  # Vertical spacing between submenu items

    # Font settings
    FONT_SCALE_SMALL: float = 0.5  # Small font scale for ball IDs
    FONT_SCALE_MEDIUM: float = 0.6  # Medium font scale for menu text
    FONT_SCALE_LARGE: float = 1.0  # Large font scale for score/timer
    FONT_THICKNESS: int = 2  # Thickness of font lines

    # Scoring UI settings
    TEXT_OFFSET_X: int = 10  # X-offset for text labels next to zones
    TEXT_OFFSET_Y: int = 20  # Y-offset for text labels below zones
    TEXT_SAFE_DISTANCE: int = int(WINDOW_WIDTH * 0.1)  # Min distance from edge to keep text visible

    # File and asset settings
    SCORING_ZONES_FILE: str = "scoring_zones.json"  # File to store scoring zones
    LOGO_SIZE: Tuple[int, int] = (50, 50)  # Size of the logo in the About menu

class GameConstants:
    """Constants for game logic and timing."""
    DEFAULT_TIME_LIMIT: int = _assert_positive(60, "DEFAULT_TIME_LIMIT")  # Default game time in seconds
    DEFAULT_MUSIC_VOLUME: float = _assert_non_negative(0.5, "DEFAULT_MUSIC_VOLUME")  # Volume for background music (0.0-1.0)
    FRAME_RATE: float = _assert_positive(30.0, "FRAME_RATE")  # Target frames per second
    SPLASH_DURATION: float = _assert_positive(10.0, "SPLASH_DURATION")  # Duration of splash screen in seconds
    FADE_DURATION: float = _assert_positive(1.0, "FADE_DURATION")  # Duration of splash fade in seconds
    WAIT_KEY_DELAY: int = _assert_positive(int(1000 / FRAME_RATE), "WAIT_KEY_DELAY")  # Milliseconds, tuned for FRAME_RATE

class DetectionConstants:
    """Constants for ball detection parameters."""
    MIN_CONTOUR_AREA: int = _assert_positive(50, "MIN_CONTOUR_AREA")  # Min contour area to consider as a ball
    STANDARD_BALL_AREA: int = _assert_positive(100, "STANDARD_BALL_AREA")  # Min area for a standard-sized ball
    MIN_CIRCULARITY: float = _assert_positive(0.5, "MIN_CIRCULARITY")  # Min circularity for standard balls
    MIN_SMALL_CIRCULARITY: float = _assert_positive(0.3, "MIN_SMALL_CIRCULARITY")  # Min circularity for small balls
    MIN_RADIUS: int = _assert_positive(5, "MIN_RADIUS")  # Min radius for standard balls
    MIN_SMALL_RADIUS: int = _assert_positive(3, "MIN_SMALL_RADIUS")  # Min radius for small balls
    EXCLUSION_DISTANCE: int = _assert_positive(10, "EXCLUSION_DISTANCE")  # Distance to exclude nearby detections
    ASPECT_RATIO_MIN: float = _assert_positive(1.5, "ASPECT_RATIO_MIN")  # Min aspect ratio for merged contours
    ASPECT_RATIO_MAX: float = _assert_positive(3.0, "ASPECT_RATIO_MAX")  # Max aspect ratio for merged contours
    MERGED_CONTOUR_AREA: int = _assert_positive(200, "MERGED_CONTOUR_AREA")  # Min area for merged contour splitting
    SMALL_BALL_FRAME_THRESHOLD: int = _assert_positive(5, "SMALL_BALL_FRAME_THRESHOLD")  # Frames to confirm small balls
    SMALL_BALL_COUNT_THRESHOLD: int = _assert_positive(3, "SMALL_BALL_COUNT_THRESHOLD")  # Detections to confirm small balls
    KERNEL_SIZE: Tuple[int, int] = (5, 5)  # Kernel size for morphological operations
    ERODE_ITERATIONS: int = _assert_positive(2, "ERODE_ITERATIONS")  # Iterations for erosion
    DILATE_ITERATIONS: int = _assert_positive(3, "DILATE_ITERATIONS")  # Iterations for dilation

class TrackingConstants:
    """Constants for ball tracking parameters."""
    TRACKING_DISTANCE_THRESHOLD: float = _assert_positive(50.0, "TRACKING_DISTANCE_THRESHOLD")  # Max distance to match balls
    SCORED_DISTANCE_THRESHOLD: float = _assert_positive(20.0, "SCORED_DISTANCE_THRESHOLD")  # Distance to consider scored
    MAX_AGE_FRAMES: int = _assert_positive(30, "MAX_AGE_FRAMES")  # Frames before a tracked ball is dropped

class ScoringConstants:
    """Constants for scoring logic."""
    DEFAULT_POINTS: int = _assert_positive(100, "DEFAULT_POINTS")  # Default points for a scoring zone
    MAX_POINTS: int = _assert_positive(300, "MAX_POINTS")  # Maximum points allowed for a zone

class LeaderboardConstants:
    """Constants for leaderboard management."""
    LEADERBOARD_FILE: str = "whiffle_leaderboard.json"  # Local file for leaderboard scores
    TABLE_NAME: str = "whifflescores"  # Supabase table name for online scores

class GameSpecificConstants:
    """Constants specific to game mechanics."""
    EXCLUDED_POSITIONS: List[Tuple[int, int]] = [
        (1272, 169), (82, 9), (1244, 176)
    ]  # Known false-positive detection spots (e.g., bright lights, reflections)