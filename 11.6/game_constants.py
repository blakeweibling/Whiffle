# game_constants.py

import cv2
import numpy as np

# --- UI Constants ---
# Values based on the provided constants.txt
class UIConstants:
    """Constants for user interface and display settings."""

    # Colors in BGR format for OpenCV (Blue, Green, Red)
    GREEN: tuple[int, int, int] = (0, 255, 0) # [cite: 2, 56]
    RED: tuple[int, int, int] = (0, 0, 255) # [cite: 2, 56]
    YELLOW: tuple[int, int, int] = (0, 255, 255) # [cite: 2, 57]
    WHITE: tuple[int, int, int] = (255, 255, 255) # [cite: 3, 57]
    CV2_BLUE: tuple[int, int, int] = (255, 0, 0) # [cite: 3, 57] - Used in scoring.py
    BLACK: tuple[int, int, int] = (0, 0, 0) # [cite: 3, 57]
    GREY_BG: tuple[int, int, int] = (100, 100, 100) # [cite: 3, 57]
    LIGHT_GRAY: tuple[int, int, int] = (200, 200, 200) # Added for consistency if needed elsewhere
    DARK_GRAY: tuple[int, int, int] = (100, 100, 100) # Same as GREY_BG

    # Window and Display
    WINDOW_NAME: str = "Whiffle Tracker" # [cite: 3, 57] - Needed by game.py, scoring.py
    WINDOW_WIDTH: int = 1024 # Adjusted based on game_state.py usage, original was 1280 [cite: 3, 57]
    WINDOW_HEIGHT: int = 768 # Adjusted based on game_state.py usage, original was 720 [cite: 3, 57]

    # Menu/UI Element Dimensions (Add if needed, based on original constants.txt)
    MENU_WIDTH: int = 400 # From previous game_state.py analysis
    MENU_HEIGHT: int = 450 # From previous game_state.py analysis
    MENU_BUTTON_WIDTH: int = 100 # [cite: 4, 58]
    MENU_BUTTON_HEIGHT: int = 40 # [cite: 4, 58]
    MENU_BUTTON_X: int = 10 # [cite: 4, 58]
    MENU_BUTTON_Y: int = 80 # [cite: 4, 58]


    # Font Sizes (Used by scoring.py)
    FONT_SCALE_SMALL: float = 0.5 # [cite: 3, 57]
    FONT_SCALE_MEDIUM: float = 0.7 # [cite: 3, 58]
    FONT_SCALE_LARGE: float = 1.0 # [cite: 4, 58]
    FONT_SCALE_XLARGE: float = 2.0 # [cite: 4, 58]
    FONT_THICKNESS: int = 1 # [cite: 4, 58]

    # Text Positioning (Used by scoring.py)
    TEXT_OFFSET_X: int = 5 # [cite: 4, 58]
    TEXT_OFFSET_Y: int = 15 # [cite: 4, 58]
    TEXT_SAFE_DISTANCE: int = 10 # [cite: 4, 58]

    # Zone Editing Visuals (Add if zone editing UI uses them)
    ZONE_EDIT_HANDLE_SIZE: int = 8 # [cite: 5, 59]
    ZONE_EDIT_HANDLE_COLOR: tuple[int, int, int] = (255, 165, 0) # Orange [cite: 5, 59]
    ZONE_EDIT_LINE_COLOR: tuple[int, int, int] = (255, 165, 0) # Orange [cite: 5, 59]
    ZONE_EDIT_SELECTED_COLOR: tuple[int, int, int] = (0, 255, 255) # Yellow highlight [cite: 5, 59]
    ZONE_EDIT_MOVE_COLOR: tuple[int, int, int] = (0, 165, 255) # Orange-Red for move [cite: 5, 59]
    ZONE_EDIT_RESIZE_COLOR: tuple[int, int, int] = (255, 0, 255) # Magenta for resize [cite: 5, 59]

    # Notification Durations
    NOTIFICATION_DURATION: float = 2.0 # Default notification display time in seconds
    NOTIFICATION_ERROR_DURATION: float = 3.0 # Duration for error notifications


# --- Game Constants ---
# Values based on the provided constants.txt and game_state.py analysis
class GameConstants:
    """Constants for general game configuration and timing."""

    # Camera Configuration (Simplified - using values determined by game_state init)
    # Complex logic from CameraConfig is omitted here.
    # These values should ideally match what GameState's init determines.
    USE_CAMERA: bool = True # Default, can be overridden by GameState init logic
    CAMERA_INDEX: int = 0 # Default, GameState init logic might change this [cite: 32, 86]
    CAMERA_BACKEND = cv2.CAP_DSHOW # Default, GameState init logic might change this [cite: 32, 86]
    STATIC_FRAME_FILE: str = "last_frame.png" # [cite: 31, 85] Fallback image

    # Performance
    FRAME_RATE: int = 30 # [cite: 30, 84]
    WAIT_KEY_DELAY: int = max(1, int(1000 / FRAME_RATE) // 3) # [cite: 30, 84]
    DETECTION_FRAME_INTERVAL: int = 2 # [cite: 30, 84]

    # File Paths
    ZONES_FILE: str = "scoring_zones.json" # [cite: 30, 84]
    ACHIEVEMENTS_FILE: str = "achievements_status.json" # [cite: 30, 84]
    HSV_RANGES_FILE: str = "hsv_ranges.json" # [cite: 30, 84]
    HIGH_SCORE_FILE: str = "high_scores.json" # [cite: 30, 85]
    SPLASH_SCREEN_FILE: str = "splash.png" # [cite: 31, 85]
    SPLASH_SCREEN_FILE2: str = "splash2.png" # [cite: 31, 85]
    GAME_OVER_SPLASH_FILE: str = "game_over.png" # [cite: 31, 85]
    SOUND_EFFECTS_PATH: str = "sounds/" # [cite: 31, 85]

    # Splash Screen
    SPLASH_DURATION: float = 2.0 # [cite: 31, 85]
    FADE_DURATION: float = 1.0 # [cite: 31, 85]

    # Game Modes & Timing
    TIMED_MODE_DURATION: float = 60.0 # From game_state analysis, original was 90.0 [cite: 31, 85]
    TIMED_MODE_WIN_SCORE: int = 500 # [cite: 31, 85]
    LOW_TIME_WARNING: float = 10.0 # Seconds remaining to trigger low time warning

    # Ball State / Scoring Logic
    POSITION_HISTORY_LENGTH: int = 10 # From game_state analysis, original was 5 [cite: 31, 85]
    ZONE_HISTORY_LENGTH: int = 5 # From game_state analysis
    REST_THRESHOLD_PIXELS: int = 3 # Max pixel movement for rest (from game_state analysis, related to REST_THRESHOLD_DISTANCE [cite: 31, 86])
    ZONE_STABILITY_THRESHOLD: int = 4 # Frames for stability (from game_state analysis, related to ZONE_STABILITY_FRAMES [cite: 32, 86])

    # Ball Tracking / Trail
    BALL_TRAIL_LENGTH: int = 15 # [cite: 32, 86]

    # Audio
    DEFAULT_SOUND_VOLUME: float = 0.7 # [cite: 32, 86]
    DEFAULT_MUSIC_VOLUME: float = 0.4 # From game_state analysis, original was 0.5 [cite: 32, 86]


# --- Scoring Constants ---
# Values based on the provided constants.txt and game_state.py analysis
class ScoringConstants:
    """Constants for scoring logic."""
    SCORE_COOLDOWN_DURATION: int = 1000 # Cooldown in ms (from game_state analysis, original was float 9000.0 [cite: 32, 86])
    SPECIAL_HOLE_POINTS: int = 100 # Fixed points for hitting the special hole
    SPECIAL_HOLE_BONUS_MULTIPLIER: int = 2 # Score multiplier if special hole hit

    # Ball Type Multipliers (Example - ensure these match intended logic)
    MULTIPLIER_RED_BALL: float = 2.0
    MULTIPLIER_HALF_BALL: float = 1.5
    MULTIPLIER_DEFAULT: float = 1.0

    # Zone Definition Limits (from original scoring.py constants)
    DEFAULT_POINTS: int = 100 # [cite: 37, 91]
    MAX_POINTS: int = 999 # [cite: 37, 91]
    MIN_ZONE_SIZE: int = 10 # [cite: 37, 91]

# Note: Other classes like MenuConstants, PlayerConstants, DetectionConstants,
# TrackingConstants, LeaderboardConstants from the original constants.py
# can be added here if they are needed by the modules involved in the refactoring.
# For now, only UIConstants, GameConstants, and ScoringConstants have been merged
# based on apparent usage in game.py, game_state.py, scoring.py, and game_scoring.py.