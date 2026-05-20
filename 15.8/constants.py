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
import sys
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


def _is_linux() -> bool:
    """Returns True when running on Linux (including Raspberry Pi)."""
    return sys.platform in ("linux", "linux2")


def _detect_raspberry_pi() -> bool:
    """Best-effort detection of a Raspberry Pi host.

    Order of precedence:

    1. ``WHIFFLE_LOW_POWER`` env var (``1/true/yes`` forces on, ``0/false/no``
       forces off). Useful for forcing the low-power profile on any machine
       (e.g. benchmarking) or disabling it on a Pi for an experiment.
    2. ``/proc/device-tree/model`` -- canonical on Pi OS, contains a string
       like ``Raspberry Pi 4 Model B Rev 1.4``.
    3. ``/proc/cpuinfo`` ``Hardware``/``Model`` fields -- fallback for older
       images.

    Returns False on anything that isn't clearly a Pi (Windows, macOS, generic
    x86 Linux, other ARM SBCs).
    """
    override = os.environ.get("WHIFFLE_LOW_POWER", "").strip().lower()
    if override in ("1", "true", "yes", "on"):
        return True
    if override in ("0", "false", "no", "off"):
        return False

    if not _is_linux():
        return False

    try:
        with open("/proc/device-tree/model", "rb") as fh:
            model = fh.read().decode("utf-8", errors="ignore").strip("\x00").strip()
        if "raspberry pi" in model.lower():
            return True
    except (OSError, IOError):
        pass

    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as fh:
            cpuinfo = fh.read().lower()
        if "raspberry pi" in cpuinfo:
            return True
        # Pi 3/4 expose BCM27xx / BCM28xx; Pi 5 uses BCM2712.
        if any(tag in cpuinfo for tag in ("bcm2708", "bcm2709", "bcm2711", "bcm2712", "bcm2835", "bcm2836", "bcm2837")):
            return True
    except (OSError, IOError):
        pass

    return False


_IS_RASPBERRY_PI: bool = _detect_raspberry_pi()


# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

if _IS_RASPBERRY_PI:
    logger.info(
        "Raspberry Pi detected -- enabling low-power detection profile "
        "(YOLO imgsz=640, inference scale=0.5, detection every 4th frame). "
        "Set WHIFFLE_LOW_POWER=0 to override."
    )


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
    ACCENT: Tuple[int, int, int] = (0, 165, 255)  # Orange accent color (BGR)
    GREEN = ACCENT  # Legacy alias
    RED: Tuple[int, int, int] = (0, 0, 255)
    YELLOW: Tuple[int, int, int] = (0, 255, 255)
    WHITE: Tuple[int, int, int] = (255, 255, 255)
    PRIMARY: Tuple[int, int, int] = (28, 45, 82)  # Dark brown / mahogany (BGR)
    CV2_BLUE = PRIMARY  # Legacy alias
    PRIMARY_LIGHT: Tuple[int, int, int] = (43, 68, 124)  # Medium brown (BGR)
    LIGHT_BLUE = PRIMARY_LIGHT  # Legacy alias
    CV2_ORANGE: Tuple[int, int, int] = (
        0,
        165,
        255,
    )  # Orange, same as ACCENT (BGR)
    BLACK: Tuple[int, int, int] = (0, 0, 0)
    GREY_BG: Tuple[int, int, int] = (100, 100, 100)
    SLIDER_BG: Tuple[int, int, int] = (50, 50, 50)
    SLIDER_HANDLE: Tuple[int, int, int] = (200, 200, 200)

    # Colorblind-friendly palette (BGR format)
    CB_PRIMARY: Tuple[int, int, int] = (28, 45, 82)  # Dark brown (BGR)
    CB_BLUE = CB_PRIMARY  # Legacy alias
    CB_PRIMARY_LIGHT: Tuple[int, int, int] = (43, 68, 124)  # Medium brown (BGR)
    CB_LIGHT_BLUE = CB_PRIMARY_LIGHT  # Legacy alias
    CB_HIGHLIGHT: Tuple[int, int, int] = (
        0,
        193,
        222,
    )  # Yellow-orange accent (BGR)
    CB_SELECT: Tuple[int, int, int] = (
        69,
        182,
        255,
    )  # Warm amber for selections (BGR)

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
    """Configuration for camera index and backend selection.
    Platform-aware: uses CAP_ANY on Linux/Raspberry Pi, DirectShow on Windows.
    On Linux with no camera, fails fast to avoid OpenCV error spam and segfaults.
    """

    # Windows: try multiple indices with DirectShow. Linux: try only 0 with CAP_ANY.
    CAMERA_INDICES_WINDOWS: List[int] = [0, 1, -1]
    CAMERA_INDICES_LINUX: List[int] = [0]  # Fail fast - avoid retry storm and segfault

    CAMERA_BACKENDS: Dict[str, int] = {
        "default": cv2.CAP_ANY,
        "v4l2": getattr(cv2, "CAP_V4L2", cv2.CAP_ANY),
        "dshow": cv2.CAP_DSHOW,
        "msmf": cv2.CAP_MSMF,
    }
    # Linux-safe backends only (dshow, msmf are Windows-only and can cause issues)
    LINUX_BACKENDS: List[str] = ["default", "v4l2"]
    DEFAULT_BACKEND_WINDOWS: str = "dshow"
    DEFAULT_BACKEND_LINUX: str = "default"

    @staticmethod
    def _default_backend() -> str:
        return (
            CameraConfig.DEFAULT_BACKEND_LINUX
            if _is_linux()
            else CameraConfig.DEFAULT_BACKEND_WINDOWS
        )

    @staticmethod
    def _indices_to_try(preferred_index: Optional[int]) -> List[int]:
        base = [preferred_index] if preferred_index is not None else (
            CameraConfig.CAMERA_INDICES_LINUX
            if _is_linux()
            else CameraConfig.CAMERA_INDICES_WINDOWS
        )
        return base

    @staticmethod
    def _fallback_backends() -> List[str]:
        """On Linux, only try Linux-safe backends. Skip Windows-only dshow/msmf."""
        if _is_linux():
            return [
                b for b in CameraConfig.LINUX_BACKENDS
                if b != CameraConfig._default_backend()
            ]
        return [
            name for name in CameraConfig.CAMERA_BACKENDS.keys()
            if name != CameraConfig._default_backend()
        ]

    @staticmethod
    def _try_open_camera(index: int, backend: int) -> Optional[Tuple[int, int, bool]]:
        """Try to open camera; return (index, backend, True) if OK, else None.
        Safely releases capture on failure to reduce segfault risk.
        """
        cap = None
        try:
            cap = cv2.VideoCapture(index, backend)
            if cap and cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    return (index, backend, True)
        except Exception:
            pass
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
        return None

    @staticmethod
    def get_camera_config() -> Tuple[Optional[int], Optional[int], bool]:
        env_index = os.getenv("WHIFFLE_CAMERA_INDEX")
        default_backend = CameraConfig._default_backend()
        env_backend = os.getenv("WHIFFLE_CAMERA_BACKEND", default_backend)
        preferred_index = None
        if env_index is not None:
            try:
                preferred_index = int(env_index)
                if preferred_index < -1:
                    preferred_index = None
            except ValueError:
                preferred_index = None
        if env_backend not in CameraConfig.CAMERA_BACKENDS:
            env_backend = default_backend
        indices_to_try = CameraConfig._indices_to_try(preferred_index)
        backend = CameraConfig.CAMERA_BACKENDS[env_backend]

        def _probe():
            for index in indices_to_try:
                result = CameraConfig._try_open_camera(index, backend)
                if result is not None:
                    return result
            for backend_name_fb in CameraConfig._fallback_backends():
                backend_fb = CameraConfig.CAMERA_BACKENDS[backend_name_fb]
                for index in indices_to_try:
                    result = CameraConfig._try_open_camera(index, backend_fb)
                    if result is not None:
                        return result
            return None

        # Suppress OpenCV VIDEOIO/obsensor stderr spam during camera probe (all platforms).
        # OpenCV writes to fd 2 directly, so we must redirect at fd level.
        with open(os.devnull, "w") as dn:
            devnull_fd = dn.fileno()
            old_stderr_fd = os.dup(2)
            try:
                os.dup2(devnull_fd, 2)
                result = _probe()
            finally:
                os.dup2(old_stderr_fd, 2)
                os.close(old_stderr_fd)

        if result is not None:
            return result

        logger.warning("No working camera found. Falling back to static frame.")
        return None, None, False


class GameConstants:
    """Constants for general game configuration and timing."""

    # Application Configuration
    USE_CAMERA = True
    CAMERA_INDEX = 0  # Default camera (built-in webcam)
    CAMERA_BACKEND = cv2.CAP_DSHOW  # Default backend (DirectShow for Windows)
    STATIC_FRAME_FILE = "assets/last_frame.png"  # Default static image if no camera
    STATIC_FIVESTAR_FRAME_FILE = "assets/static_fivestar.png"  # Static image for fivestar mode if no camera
    FRAME_RATE = 30  # Target frame rate
    DEBUG_MODE = False  # Debug mode flag
    # Process every Nth frame for detection. The Pi CPU cannot keep up with
    # YOLO inference at every-other-frame, so we space detections out further
    # when running on low-power hardware (see _detect_raspberry_pi()).
    DETECTION_FRAME_INTERVAL = 4 if _IS_RASPBERRY_PI else 2

    # Retro mode constants
    RETRO_PIXEL_FACTOR = 2  # Pixelation factor for retro mode (higher = more pixelated)
    # Pre-computed sepia kernel for faster processing
    RETRO_SEPIA_KERNEL = np.array(
        [[0.272, 0.534, 0.131], [0.349, 0.686, 0.168], [0.393, 0.769, 0.189]]
    )

    # Game Modes & Timers — Whiffle layout (standard table)
    TIMED_MODE_DURATION = 90.0  # Seconds for timed mode
    TIMED_MODE_WIN_SCORE = 2000  # Score to win in timed mode (Whiffle)
    SURVIVAL_MODE_START_TIME = 45.0  # Initial time for survival mode
    SURVIVAL_MODE_TIME_GAIN_PER_SCORE = 10.0  # Time added per score in survival
    SURVIVAL_MODE_WIN_SCORE = 2000  # Score to win in survival mode (Whiffle)
    CLASSIC_MODE_WIN_SCORE = 2000  # Not used as win threshold (classic has no score cap); kept for achievements/display (Whiffle)

    # Five Star layout — higher win thresholds (easier to score on Five Star table)
    FIVESTAR_TIMED_MODE_WIN_SCORE = 4000  # Score to win in timed mode (Five Star)
    FIVESTAR_SURVIVAL_MODE_WIN_SCORE = 4000  # Score to win in survival mode (Five Star)
    FIVESTAR_CLASSIC_MODE_WIN_SCORE = 4000  # For achievements/display only; classic has no score cap (Five Star)

    # ... rest of the constants
    FRAME_RATE: int = _assert_positive(30, "FRAME_RATE")
    WAIT_KEY_DELAY: int = max(1, int(1000 / FRAME_RATE) // 3)
    DETECTION_FRAME_INTERVAL: int = _assert_positive(
        4 if _IS_RASPBERRY_PI else 2, "DETECTION_FRAME_INTERVAL"
    )

    ZONES_FILE: str = "data/game/scoring_zones.json"
    FIVESTAR_ZONES_FILE: str = "data/game/fivestar_scoring_zones.json"
    ACHIEVEMENTS_FILE: str = "data/achievements/achievements_status.json"
    HSV_RANGES_FILE: str = "configs/hsv_ranges.json"
    HIGH_SCORE_FILE: str = "data/scores/high_scores.json"
    SETTINGS_FILE: str = "configs/settings.json"
    SPLASH_SCREEN_FILE: str = "assets/splash.png"
    GAME_OVER_SPLASH_FILE: str = "assets/game_over.png"
    SOUND_EFFECTS_PATH: str = "data/sounds/"
    # Replay files location
    REPLAY_DIR: str = "data/replays"
    WHIFFLE_MODEL_PATH: str = "data/whiffle_new_best.pt"
    FIVESTAR_MODEL_PATH: str = "data/whiffle_new_best_fivestar.pt"

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
        ("New Game", "new_game"),
        ("Resume", "resume"),
        ("Restart Round", "restart_round"),
        ("Settings", "settings"),
        ("Game Mode", "game_mode"),
        ("Layout", "layout"),
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
    # Raw boxes before per-class filtering. Kept very low so dim reds in
    # shadowed holes -- and especially white balls at the far perspective
    # extreme of the table where YOLO's confidence is suppressed by
    # foreshortening and reduced contrast -- are surfaced to the CV gates
    # in detection.py. The downstream confidence floors
    # (YOLO_CONFIDENCE_THRESHOLD for white / silver out in the open, and
    # RED_BALL_MIN_YOLO_CONFIDENCE for unique balls out of zone) protect
    # against the extra FPs this would otherwise admit.
    YOLO_RAW_INFERENCE_CONFIDENCE: float = _assert_fractional(
        0.15, "YOLO_RAW_INFERENCE_CONFIDENCE"
    )
    SMALL_BALL_CONFIRM_THRESHOLD: int = _assert_positive(
        3, "SMALL_BALL_CONFIRM_THRESHOLD"
    )
    # YOLO boxes at or below this max side length (px) need consecutive-frame confirmation.
    SMALL_BALL_MAX_BOX_PX: int = _assert_positive(28, "SMALL_BALL_MAX_BOX_PX")

    # Higher inference scale = larger image fed to YOLO = small/dim balls
    # near the playfield edges remain detectable. 1.0 (full source resolution)
    # combined with a 1920 imgsz override is the maximum information density
    # we can give YOLO; required to recover balls in the leftmost holes that
    # perspective makes physically small and dim. On a Raspberry Pi the CPU
    # cannot sustain that workload, so we drop to half resolution there;
    # combined with imgsz=640 below this is ~10x faster per frame and keeps
    # the game playable. Override with WHIFFLE_LOW_POWER=0/1.
    YOLO_INFERENCE_SCALE: float = _assert_fractional(
        0.5 if _IS_RASPBERRY_PI else 1.0, "YOLO_INFERENCE_SCALE"
    )
    YOLO_IOU_THRESHOLD: float = _assert_fractional(0.45, "YOLO_IOU_THRESHOLD")
    # 0 = let Ultralytics choose imgsz from the model (usually 640). Override
    # to 1920 on capable hardware so far-edge balls aren't decimated by YOLO's
    # internal letterbox. On a Raspberry Pi we drop back to the model's native
    # 640 -- inference cost scales roughly as imgsz^2, so this is the single
    # biggest speedup available without changing the model itself.
    YOLO_INFERENCE_IMG_SIZE: int = _assert_non_negative(
        640 if _IS_RASPBERRY_PI else 1920, "YOLO_INFERENCE_IMG_SIZE"
    )

    DETECTION_NMS_MIN_DISTANCE_PX: float = _assert_positive(
        20.0, "DETECTION_NMS_MIN_DISTANCE_PX"
    )

    KERNEL_SIZE: Tuple[int, int] = (5, 5)
    ERODE_ITERATIONS: int = _assert_positive(1, "ERODE_ITERATIONS")
    DILATE_ITERATIONS: int = _assert_positive(2, "DILATE_ITERATIONS")
    EXCLUSION_DISTANCE: float = _assert_non_negative(
        50.0, "EXCLUSION_DISTANCE"
    )  # Added based on detection.txt usage

    # Red ball only: YOLO fires often on reddish wood, pin art, and frame edges.
    RED_BALL_MIN_YOLO_CONFIDENCE: float = _assert_fractional(
        0.62, "RED_BALL_MIN_YOLO_CONFIDENCE"
    )
    # Red in a hole is often lower-confidence for YOLO (shadow, wood tint).
    RED_BALL_IN_HOLE_CONFIDENCE_RELAX: float = _assert_non_negative(
        0.14, "RED_BALL_IN_HOLE_CONFIDENCE_RELAX"
    )
    RED_BALL_FRAME_EDGE_MARGIN_PX: int = _assert_positive(
        22, "RED_BALL_FRAME_EDGE_MARGIN_PX"
    )
    RED_BALL_BGR_DOMINANCE_SUM: float = _assert_non_negative(
        32.0, "RED_BALL_BGR_DOMINANCE_SUM"
    )
    RED_BALL_BGR_MIN_LEAD: float = _assert_non_negative(
        10.0, "RED_BALL_BGR_MIN_LEAD"
    )
    RED_BALL_HUE_FRACTION_THRESHOLD: float = _assert_fractional(
        0.18, "RED_BALL_HUE_FRACTION_THRESHOLD"
    )
    RED_BALL_HUE_MIN_SATURATION: int = _assert_positive(38, "RED_BALL_HUE_MIN_SATURATION")
    RED_BALL_HUE_MIN_VALUE: int = _assert_positive(28, "RED_BALL_HUE_MIN_VALUE")

    # In-hole red is often dark / wood-colored in RGB; relax hue/BGR vs playfield.
    RED_BALL_IN_HOLE_HUE_FRAC: float = _assert_fractional(
        0.06, "RED_BALL_IN_HOLE_HUE_FRAC"
    )
    RED_BALL_IN_HOLE_BGR_SUM: float = _assert_non_negative(
        14.0, "RED_BALL_IN_HOLE_BGR_SUM"
    )
    RED_BALL_IN_HOLE_BGR_LEAD: float = _assert_non_negative(
        5.0, "RED_BALL_IN_HOLE_BGR_LEAD"
    )
    RED_BALL_IN_HOLE_HUE_SAT: int = _assert_positive(22, "RED_BALL_IN_HOLE_HUE_SAT")
    RED_BALL_IN_HOLE_HUE_VAL: int = _assert_positive(18, "RED_BALL_IN_HOLE_HUE_VAL")

    # Radial rim: real balls give a stable circular rim; flat ring art varies by angle.
    RED_BALL_RIM_RAY_MIN_HITS: int = _assert_positive(14, "RED_BALL_RIM_RAY_MIN_HITS")
    RED_BALL_RIM_RAY_CV_MAX: float = _assert_non_negative(
        0.34, "RED_BALL_RIM_RAY_CV_MAX"
    )
    RED_BALL_RIM_RAY_MIN_RADIUS_PX: float = _assert_non_negative(
        3.5, "RED_BALL_RIM_RAY_MIN_RADIUS_PX"
    )
    RED_BALL_PLAYFIELD_NEED_RIM: bool = True
    # Flat printed reds have very weak interior shading vs a sphere.
    RED_BALL_MIN_INTERIOR_SOBEL_MEAN: float = _assert_non_negative(
        2.2, "RED_BALL_MIN_INTERIOR_SOBEL_MEAN"
    )

    # Printed bullseye / logo: inner vs outer hue differs strongly (e.g. yellow + red).
    RED_RING_ART_HUE_SEP_MIN: float = _assert_non_negative(
        22.0, "RED_RING_ART_HUE_SEP_MIN"
    )

    # When YOLO misses a red in a hole, HSV + shape fallback inside scoring zones.
    RED_ZONE_FALLBACK_ENABLED: bool = True
    RED_ZONE_FALLBACK_MIN_AREA_RATIO: float = _assert_fractional(
        0.012, "RED_ZONE_FALLBACK_MIN_AREA_RATIO"
    )
    RED_ZONE_FALLBACK_MAX_AREA_RATIO: float = _assert_fractional(
        0.45, "RED_ZONE_FALLBACK_MAX_AREA_RATIO"
    )
    RED_ZONE_FALLBACK_CIRCULARITY: float = _assert_fractional(
        0.52, "RED_ZONE_FALLBACK_CIRCULARITY"
    )
    RED_ZONE_FALLBACK_RED_PIXEL_FRAC: float = _assert_fractional(
        0.045, "RED_ZONE_FALLBACK_RED_PIXEL_FRAC"
    )
    # Restrict hue mask to central portion of the zone (reduces wood rim in crop).
    RED_ZONE_FALLBACK_CENTER_FRACTION: float = _assert_fractional(
        0.55, "RED_ZONE_FALLBACK_CENTER_FRACTION"
    )
    RED_ZONE_FALLBACK_REQUIRE_RIM: bool = True
    # At most one zone fallback red per frame; must clear this quality bar.
    RED_ZONE_FALLBACK_MIN_QUALITY_SCORE: float = _assert_non_negative(
        4.5, "RED_ZONE_FALLBACK_MIN_QUALITY_SCORE"
    )

    # Whiffle has a single player red on the field; extra reds are almost always FPs.
    RED_MAX_PLAYER_RED_BALLS: int = _assert_positive(1, "RED_MAX_PLAYER_RED_BALLS")

    # Finer steps along rim rays (fractional pixel advance).
    RED_BALL_RIM_RAY_STEP_PX: float = _assert_positive(0.5, "RED_BALL_RIM_RAY_STEP_PX")


class TrackingConstants:
    """Constants for ball tracking parameters."""

    TRACKING_DISTANCE_THRESHOLD: float = _assert_positive(
        100.0, "TRACKING_DISTANCE_THRESHOLD"
    )
    SCORED_DISTANCE_THRESHOLD: float = _assert_positive(
        100.0, "SCORED_DISTANCE_THRESHOLD"
    )
    MAX_AGE_FRAMES: int = _assert_positive(30000, "MAX_AGE_FRAMES")
    # After a solid red ball scores, block new track IDs near this pixel radius (flicker).
    RED_BALL_SCORED_POSITION_SUPPRESS_RADIUS_PX: float = _assert_positive(
        90.0, "RED_BALL_SCORED_POSITION_SUPPRESS_RADIUS_PX"
    )


class ScoringConstants:
    """Constants for scoring logic."""

    DEFAULT_POINTS: int = _assert_positive(100, "DEFAULT_POINTS")
    MAX_POINTS: int = _assert_positive(2000, "MAX_POINTS")
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
