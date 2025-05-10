# constants.py
"""
Constants for the Whiffle Tracker project.

This file defines constants used throughout the project, including color values
in BGR format (for OpenCV) and game configuration settings. Constants are grouped
into classes for organization and can be partially configured via environment variables.
"""

import logging
import os
import string  # Import string for player name characters
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

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


# --- [ADD] Resolution Constants ---
class ResolutionConstants:
    RESOLUTIONS = {
        "1080p": (1920, 1080),
        "720p": (1280, 720),
    }
    # Set the initial default resolution key
    DEFAULT_RESOLUTION = "1080p"


# --- [END ADD] ---


class UIConstants:
    """Constants for user interface and display settings."""

    # Colors in BGR format for OpenCV (Blue, Green, Red)
    GREEN: Tuple[int, int, int] = (0, 255, 0)
    RED: Tuple[int, int, int] = (0, 0, 255)
    YELLOW: Tuple[int, int, int] = (0, 255, 255)
    WHITE: Tuple[int, int, int] = (255, 255, 255)
    CV2_BLUE: Tuple[int, int, int] = (255, 0, 0)
    LIGHT_BLUE: Tuple[int, int, int] = (255, 191, 0)  # Light blue in BGR format
    CV2_ORANGE: Tuple[int, int, int] = (
        0,
        165,
        255,
    )  # BGR format (Blue=0, Green=165, Red=255)
    BLACK: Tuple[int, int, int] = (0, 0, 0)
    GREY_BG: Tuple[int, int, int] = (100, 100, 100)
    SLIDER_BG: Tuple[int, int, int] = (50, 50, 50)  # Color for slider background
    SLIDER_HANDLE: Tuple[int, int, int] = (200, 200, 200)  # Color for slider handle

    # Colorblind-friendly colors (BGR format)
    # These are selected to work well for most types of color blindness
    CB_BLUE: Tuple[int, int, int] = (
        214,
        122,
        0,
    )  # Dark orange in BGR (appears as distinctive blue to colorblind users)
    CB_LIGHT_BLUE: Tuple[int, int, int] = (239, 179, 0)  # Lighter orange in BGR
    CB_HIGHLIGHT: Tuple[int, int, int] = (
        0,
        193,
        222,
    )  # Yellow-orange in BGR (appears distinct from blues)
    CB_SELECT: Tuple[int, int, int] = (
        69,
        182,
        255,
    )  # Bright blue-ish color that works well for selections

    # Default colorblind mode state
    DEFAULT_COLORBLIND_MODE: bool = False

    # Window and Display
    WINDOW_NAME: str = "Whiffle Tracker"
    # --- [MODIFY] Window dimensions are now dynamic, managed by game_state ---
    # These values might represent the *initial* size at startup based on DEFAULT_RESOLUTION
    # but should not be treated as constant throughout the application runtime.
    # INITIAL_WINDOW_WIDTH: int = ResolutionConstants.RESOLUTIONS[ResolutionConstants.DEFAULT_RESOLUTION][0]
    # INITIAL_WINDOW_HEIGHT: int = ResolutionConstants.RESOLUTIONS[ResolutionConstants.DEFAULT_RESOLUTION][1]
    # --- [END MODIFY] ---

    # Font Sizes (Absolute pixel sizes are generally okay)
    FONT_SCALE_SMALL: float = _assert_positive(0.5, "FONT_SCALE_SMALL")
    FONT_SCALE_MEDIUM: float = _assert_positive(0.7, "FONT_SCALE_MEDIUM")
    FONT_SCALE_LARGE: float = _assert_positive(1.0, "FONT_SCALE_LARGE")
    FONT_SCALE_XLARGE: float = _assert_positive(2.0, "FONT_SCALE_XLARGE")
    FONT_THICKNESS: int = _assert_positive(1, "FONT_THICKNESS")

    # Text Positioning (Consider making these relative for better adaptation)
    TEXT_OFFSET_X: int = _assert_non_negative(5, "TEXT_OFFSET_X")
    TEXT_OFFSET_Y: int = _assert_non_negative(15, "TEXT_OFFSET_Y")
    TEXT_SAFE_DISTANCE: int = _assert_non_negative(10, "TEXT_SAFE_DISTANCE")

    # Menu Button (Absolute Positioning - consider relative alternative)
    MENU_BUTTON_WIDTH: int = _assert_positive(100, "MENU_BUTTON_WIDTH")
    MENU_BUTTON_HEIGHT: int = _assert_positive(40, "MENU_BUTTON_HEIGHT")
    MENU_BUTTON_X: int = 10
    MENU_BUTTON_Y: int = 80

    # --- [ADD] Resolution Button ---
    # Positioned below the Menu button using absolute coordinates for now.
    # Consider calculating relatively: e.g., res_y = menu_y + menu_h + int(0.01 * current_height)
    RESOLUTION_BUTTON_X: int = MENU_BUTTON_X
    RESOLUTION_BUTTON_Y: int = (
        MENU_BUTTON_Y + MENU_BUTTON_HEIGHT + 10
    )  # 10px spacing below
    RESOLUTION_BUTTON_WIDTH: int = MENU_BUTTON_WIDTH
    RESOLUTION_BUTTON_HEIGHT: int = MENU_BUTTON_HEIGHT
    # --- [END ADD] ---

    # Menu Close Button
    MENU_CLOSE_BUTTON_SIZE: int = _assert_positive(40, "MENU_CLOSE_BUTTON_SIZE")
    MENU_CLOSE_BUTTON_PADDING: int = _assert_non_negative(
        10, "MENU_CLOSE_BUTTON_PADDING"
    )
    MENU_CLOSE_BUTTON_COLOR: Tuple[int, int, int] = RED
    MENU_CLOSE_BUTTON_THICKNESS: int = _assert_positive(
        2, "MENU_CLOSE_BUTTON_THICKNESS"
    )

    # Zone Editing Visuals (Handle size absolute, colors okay)
    ZONE_EDIT_HANDLE_SIZE: int = 8
    ZONE_EDIT_HANDLE_COLOR: Tuple[int, int, int] = (255, 165, 0)  # Orange
    ZONE_EDIT_LINE_COLOR: Tuple[int, int, int] = (255, 165, 0)  # Orange
    ZONE_EDIT_SELECTED_COLOR: Tuple[int, int, int] = (0, 255, 255)  # Yellow highlight
    ZONE_EDIT_MOVE_COLOR: Tuple[int, int, int] = (0, 165, 255)  # Orange-Red for move
    ZONE_EDIT_RESIZE_COLOR: Tuple[int, int, int] = (255, 0, 255)  # Magenta for resize

    # Settings Slider Dimensions (Absolute pixel sizes okay for sliders)
    SLIDER_WIDTH: int = 200
    SLIDER_HEIGHT: int = 20
    SLIDER_HANDLE_WIDTH: int = 10
    SLIDER_PADDING: int = 5

    # Click Feedback
    CLICK_FEEDBACK_DURATION: float = 0.2


class CameraConfig:
    """Configuration for camera index and backend selection."""

    # --- (Content of CameraConfig remains unchanged) ---
    CAMERA_INDICES: List[int] = [0, 1, -1]
    CAMERA_BACKENDS: Dict[str, int] = {
        "default": cv2.CAP_ANY,
        "dshow": cv2.CAP_DSHOW,
        "msmf": cv2.CAP_MSMF,
    }
    DEFAULT_BACKEND: str = "dshow"

    @staticmethod
    def get_camera_config() -> Tuple[Optional[int], Optional[int], bool]:
        # (Implementation unchanged)
        env_index = os.getenv("WHIFFLE_CAMERA_INDEX")
        env_backend = os.getenv("WHIFFLE_CAMERA_BACKEND", CameraConfig.DEFAULT_BACKEND)
        preferred_index = None
        if env_index is not None:
            try:
                preferred_index = int(env_index)
                if preferred_index < -1:
                    preferred_index = None
            except ValueError:
                preferred_index = None
        if env_backend not in CameraConfig.CAMERA_BACKENDS:
            env_backend = CameraConfig.DEFAULT_BACKEND
        indices_to_try = (
            [preferred_index]
            if preferred_index is not None
            else CameraConfig.CAMERA_INDICES
        )
        backend = CameraConfig.CAMERA_BACKENDS[env_backend]
        backend_name = env_backend
        for index in indices_to_try:
            # logger.info(f"Trying camera index {index} with backend {backend_name} ({backend})...")
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    cap.release()
                    return index, backend, True
            cap.release()
        if env_backend == CameraConfig.DEFAULT_BACKEND:
            other_backends = [
                name
                for name in CameraConfig.CAMERA_BACKENDS.keys()
                if name != CameraConfig.DEFAULT_BACKEND
            ]
            for backend_name in other_backends:
                backend = CameraConfig.CAMERA_BACKENDS[backend_name]
                for index in indices_to_try:
                    # logger.info(f"Trying camera index {index} with fallback backend {backend_name} ({backend})...")
                    cap = cv2.VideoCapture(index, backend)
                    if cap.isOpened():
                        ret, _ = cap.read()
                        if ret:
                            cap.release()
                            return index, backend, True
                    cap.release()
        logger.warning("No working camera found. Falling back to static frame.")
        return None, None, False


class GameConstants:
    """Constants for general game configuration and timing."""

    # Application Configuration
    USE_CAMERA = True
    CAMERA_INDEX = 0  # Default camera (built-in webcam)
    CAMERA_BACKEND = cv2.CAP_DSHOW  # Default backend (DirectShow for Windows)
    STATIC_FRAME_FILE = "assets/last_frame.png"  # Default static image if no camera
    FRAME_RATE = 30  # Target frame rate
    DEBUG_MODE = False  # Debug mode flag
    DETECTION_FRAME_INTERVAL = 2  # Process every Nth frame for detection

    # Retro mode constants
    RETRO_PIXEL_FACTOR = 2  # Pixelation factor for retro mode (higher = more pixelated)
    # Pre-computed sepia kernel for faster processing
    RETRO_SEPIA_KERNEL = np.array(
        [[0.272, 0.534, 0.131], [0.349, 0.686, 0.168], [0.393, 0.769, 0.189]]
    )

    # Game Modes & Timers
    TIMED_MODE_DURATION = 90.0  # Seconds for timed mode
    TIMED_MODE_WIN_SCORE = 2000  # Score to win in timed mode
    SURVIVAL_MODE_START_TIME = 45.0  # Initial time for survival mode
    SURVIVAL_MODE_TIME_GAIN_PER_SCORE = 10.0  # Time added per score in survival
    SURVIVAL_MODE_WIN_SCORE = 2000  # Score to win in survival mode
    CLASSIC_MODE_WIN_SCORE = 2000  # Score to win in classic mode

    # ... rest of the constants
    FRAME_RATE: int = _assert_positive(30, "FRAME_RATE")
    WAIT_KEY_DELAY: int = max(1, int(1000 / FRAME_RATE) // 3)
    DETECTION_FRAME_INTERVAL: int = _assert_positive(2, "DETECTION_FRAME_INTERVAL")

    ZONES_FILE: str = "data/game/scoring_zones.json"
    ACHIEVEMENTS_FILE: str = "data/achievements/achievements_status.json"
    HSV_RANGES_FILE: str = "configs/hsv_ranges.json"
    HIGH_SCORE_FILE: str = "data/scores/high_scores.json"
    SETTINGS_FILE: str = "configs/settings.json"
    SPLASH_SCREEN_FILE: str = "assets/splash.png"
    GAME_OVER_SPLASH_FILE: str = "assets/game_over.png"
    SOUND_EFFECTS_PATH: str = "data/sounds/"
    # Replay files location
    REPLAY_DIR: str = "data/replays"

    SPLASH_DURATION: float = _assert_non_negative(2.0, "SPLASH_DURATION")
    FADE_DURATION: float = _assert_non_negative(1.0, "FADE_DURATION")

    POSITION_HISTORY_LENGTH: int = _assert_positive(5, "POSITION_HISTORY_LENGTH")
    REST_THRESHOLD_DISTANCE: float = _assert_non_negative(
        10.0, "REST_THRESHOLD_DISTANCE"
    )
    ZONE_STABILITY_FRAMES: int = _assert_positive(30, "ZONE_STABILITY_FRAMES")
    SCORE_COOLDOWN_DURATION: float = _assert_non_negative(
        9000.0, "SCORE_COOLDOWN_DURATION"
    )

    # Audio defaults
    INITIAL_SOUND_VOLUME: float = _assert_fractional(0.7, "INITIAL_SOUND_VOLUME")
    INITIAL_MUSIC_VOLUME: float = _assert_fractional(0.5, "INITIAL_MUSIC_VOLUME")

    # Background Music Tracks
    BACKGROUND_MUSIC_TRACKS: List[str] = [
        "background_music.mp3",
        "background_music2.mp3",
        "background_music3.mp3",
        "background_music4.mp3",  # --- >>> MODIFICATION: Added this line <<< ---
    ]

    # Camera Configuration uses the dynamic method now
    CAMERA_INDEX, CAMERA_BACKEND, USE_CAMERA = CameraConfig.get_camera_config()


class MenuConstants:
    """Constants defining menu structures."""

    # --- (Content remains unchanged) ---
    MAIN_MENU_ITEMS: List[Tuple[str, str]] = [
        ("Resume", "resume"),
        ("Settings", "settings"),
        ("Game Mode", "game_mode"),
        ("Manage Zones", "manage_zones"),
        ("Players", "players"),
        ("Replays", "replays"),
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

    REPLAY_SUBMENU_ITEMS: List[Tuple[str, str]] = [
        ("Start Recording", "start_recording"),
        ("Stop Recording", "stop_recording"),
        ("My Replays", "view_replays"),
        ("Back", "back_to_main"),
    ]


class GameSpecificConstants:
    """Constants specific to the Whiffle ball game physics or rules."""

    EXCLUDED_POSITIONS: List[Tuple[int, int, int]] = []


class PlayerConstants:
    """Constants related to player configuration."""

    MAX_PLAYER_NAME_LENGTH: int = _assert_positive(15, "MAX_PLAYER_NAME_LENGTH")
    ALLOWED_PLAYER_NAME_CHARS: str = string.ascii_letters + string.digits + " _-"


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
    EXCLUSION_DISTANCE: float = _assert_non_negative(
        50.0, "EXCLUSION_DISTANCE"
    )  # Added based on detection.txt usage


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

    LEADERBOARD_FILE: str = "data/scores/whiffle_leaderboard.json"
    TABLE_NAME: str = "whifflescores"
    BATCH_SIZE: int = _assert_positive(10, "BATCH_SIZE")
    FLUSH_INTERVAL: float = _assert_positive(60.0, "FLUSH_INTERVAL")


class ReplayConstants:
    """Constants for replay system management."""

    MAX_REPLAY_HISTORY = 50  # Maximum number of replays to keep in history
    KEYFRAME_INTERVAL = 60  # Save a frame every 60 frames (2 seconds at 30fps)
    REPLAY_VIDEO_FPS = (
        24  # FPS for generated replay videos (higher for smoother playback)
    )
    HIGHLIGHT_VIDEO_FPS = 30  # FPS for highlight videos (higher for better quality)
    DEFAULT_HIGHLIGHT_SECONDS_BEFORE = (
        3.0  # Seconds before score event to include in highlight
    )
    DEFAULT_HIGHLIGHT_SECONDS_AFTER = (
        2.0  # Seconds after score event to include in highlight
    )
    REPLAY_THUMBNAIL_SIZE = (320, 180)  # Default thumbnail size (16:9 aspect ratio)

    # Video quality settings
    VIDEO_JPEG_QUALITY = 95  # JPEG quality for keyframes (0-100)
    VIDEO_MP4_QUALITY = 95  # MP4 quality for exported videos (0-100)

    # The number of replays to show per page in the replay browser
    REPLAYS_PER_PAGE = 6

    # Playback control constants
    PLAYBACK_SPEED_INCREMENT = 0.25  # Speed increment when changing playback speed
    MIN_PLAYBACK_SPEED = 0.25  # Minimum playback speed
    MAX_PLAYBACK_SPEED = 4.0  # Maximum playback speed
    DEFAULT_PLAYBACK_SPEED = 1.0  # Default playback speed

    # Timeline scrubber constants
    TIMELINE_HEIGHT = 20  # Height of the timeline scrubber
    TIMELINE_HANDLE_WIDTH = 10  # Width of the timeline scrubber handle

    # Sharing options constants
    EXPORT_FORMATS = ["MP4", "GIF"]  # Supported export formats
    SHARING_PLATFORMS = [
        "Local",
        "Discord",
        "Share Link",
        "YouTube",
    ]  # Supported sharing platforms
    DEFAULT_EXPORT_FORMAT = "MP4"  # Default export format


# Discord integration constants
class DiscordConstants:
    """Constants for Discord integration."""

    # Discord webhook URL - must be configured to enable sharing
    # To set up a webhook:
    # 1. Go to your Discord server: https://discord.gg/B7S8BYpgmT
    # 2. Go to the channel settings (click the gear icon next to a channel)
    # 3. Select 'Integrations'
    # 4. Click on 'Webhooks' and create a new webhook
    # 5. Copy the webhook URL and paste it below, replacing the placeholder
    WEBHOOK_URL = "https://discord.com/api/webhooks/1364797662938792048/n4OQsfGzatpAaXDuQWarK_loIMqVXfK7fd8R3TSZOwv4Hx5aFH3lau1GdpokwsbG5GSV"

    # Bot details (these will be displayed in Discord)
    BOT_USERNAME = "Whiffle Bot"
    BOT_AVATAR_URL = "https://www.whiffle.co/images/logo.png"

    # Template for the replay share message
    REPLAY_SHARE_TEMPLATE = "🎮 **{player_name}** just scored **{score}** in Whiffle ({game_mode} mode)! Check out this replay! 🎯"

    # Request timeout in seconds
    REQUEST_TIMEOUT = 30


class YouTubeConstants:
    """Constants for YouTube API integration."""

    # YouTube upload defaults
    DEFAULT_CATEGORY_ID = "20"  # Category ID for Gaming
    DEFAULT_TAGS = ["whiffle", "game", "replay", "sports"]
    DEFAULT_PRIVACY_STATUS = "unlisted"  # 'private', 'public', or 'unlisted'

    # Template for video information
    TITLE_TEMPLATE = "Whiffle Replay - {player} - {score} points ({game_mode})"
    DESCRIPTION_TEMPLATE = (
        "Gameplay replay of {player} scoring {score} points in {game_mode} mode."
    )

    # Upload settings
    MAX_VIDEO_SIZE_MB = 2048  # Reasonable limit for upload size warning (2GB)
    REQUEST_TIMEOUT = 300  # 5 minutes timeout for uploads
    MAX_RETRIES = 3  # Maximum number of retries for failed uploads

    # Additional settings
    INCLUDE_PLAYER_NAME = True  # Whether to include player name in video title
