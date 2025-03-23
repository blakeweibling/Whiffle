"""
Constants for the Whiffle Tracker project.

This file defines constants used throughout the project, including color values
in BGR format (for OpenCV) and game configuration settings.
"""

from typing import Tuple, List

# Color constants in BGR format for OpenCV (Blue, Green, Red)
GREEN: Tuple[int, int, int] = (0, 255, 0)
RED: Tuple[int, int, int] = (0, 0, 255)
YELLOW: Tuple[int, int, int] = (255, 255, 0)
WHITE: Tuple[int, int, int] = (255, 255, 255)
BLUE: Tuple[int, int, int] = (255, 0, 0)

# Game configuration constants
WINDOW_WIDTH: int = 1280
WINDOW_HEIGHT: int = 720
WINDOW_NAME: str = "Whiffle"
DEFAULT_TIME_LIMIT: int = 60
DEFAULT_MUSIC_VOLUME: float = 0.5
FRAME_RATE: float = 30.0
SPLASH_DURATION: float = 10.0
FADE_DURATION: float = 1.0

# Detection configuration constants (from detection.py)
MIN_CONTOUR_AREA: int = 50
STANDARD_BALL_AREA: int = 100
MIN_CIRCULARITY: float = 0.5
MIN_SMALL_CIRCULARITY: float = 0.3
MIN_RADIUS: int = 5
MIN_SMALL_RADIUS: int = 3
EXCLUSION_DISTANCE: int = 10
ASPECT_RATIO_MIN: float = 1.5
ASPECT_RATIO_MAX: float = 3.0
MERGED_CONTOUR_AREA: int = 200
SMALL_BALL_FRAME_THRESHOLD: int = 5
SMALL_BALL_COUNT_THRESHOLD: int = 3
KERNEL_SIZE: Tuple[int, int] = (5, 5)
ERODE_ITERATIONS: int = 2
DILATE_ITERATIONS: int = 3

# Tracking configuration constants (from tracking.py)
TRACKING_DISTANCE_THRESHOLD: float = 50.0
SCORED_DISTANCE_THRESHOLD: float = 20.0
MAX_AGE_FRAMES: int = 30

# Scoring configuration constants (from scoring.py)
DEFAULT_POINTS: int = 100
MAX_POINTS: int = 300
FONT_SCALE: float = 0.6
FONT_THICKNESS: int = 2
TEXT_OFFSET_X: int = 10
TEXT_OFFSET_Y: int = 20
TEXT_SAFE_DISTANCE: int = 100

# Menu configuration constants (from menu.py)
MENU_WIDTH: int = 600
MENU_HEIGHT: int = 600
MENU_BUTTON_X: int = 10
MENU_BUTTON_Y: int = 70
MENU_BUTTON_WIDTH: int = 140
MENU_BUTTON_HEIGHT: int = 30
FONT_SCALE_SMALL: float = 0.5
FONT_SCALE_MEDIUM: float = 0.6
FONT_SCALE_LARGE: float = 1.0
SCORING_ZONES_FILE: str = "scoring_zones.json"
LOGO_SIZE: Tuple[int, int] = (50, 50)

# Leaderboard configuration constants (from leaderboard.py)
LEADERBOARD_FILE: str = "whiffle_leaderboard.json"
TABLE_NAME: str = "whifflescores"

# Game UI constants (from game.py)
EXCLUDED_POSITIONS: List[Tuple[int, int]] = [(1272, 169), (82, 9), (1244, 176)]