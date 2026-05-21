# game.py
"""
Main entry point for the Whiffle Tracker project.
Initializes the game and runs the main loop.
"""

import os
import sys
import logging
import gc
import threading
import time
import warnings
import contextlib
import faulthandler

# Print a native-stack trace if the interpreter is killed by SIGSEGV / SIGABRT /
# SIGFPE / SIGBUS / SIGILL. Without this a crash inside cv2 / torch / pygame /
# numpy just prints "Segmentation fault" with no clue which library died.
# The trace is written to stderr (and also to crash.log when the env var is set)
# *before* the process actually exits, so we always see where it crashed.
try:
    _fh_log_path = os.environ.get("WHIFFLE_FAULT_LOG", "")
    if _fh_log_path:
        _fh_log = open(_fh_log_path, "a", buffering=1)
        faulthandler.enable(file=_fh_log, all_threads=True)
    else:
        faulthandler.enable(all_threads=True)
except Exception:
    pass

# Configure logging to filter out libpng warnings
class LibPNGFilter(logging.Filter):
    def filter(self, record):
        return not record.getMessage().startswith('libpng warning: iCCP:')

# Filter for repetitive debug messages
class RepetitiveDebugFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.last_messages = {}
        self.message_count = {}
        self.threshold = 3  # Number of times a message can repeat before being filtered

    def filter(self, record):
        msg = record.getMessage()
        if record.levelno != logging.DEBUG:
            return True
            
        # Check if this is a repetitive message
        if msg in self.last_messages:
            self.message_count[msg] = self.message_count.get(msg, 0) + 1
            if self.message_count[msg] > self.threshold:
                return False
        else:
            self.last_messages[msg] = time.time()
            self.message_count[msg] = 1
            
        return True

# Set up logging with filters
logging.basicConfig(
    level=logging.INFO,  # Default to INFO level
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add filters to root logger
root_logger = logging.getLogger()
libpng_filter = LibPNGFilter()
repetitive_filter = RepetitiveDebugFilter()
root_logger.addFilter(libpng_filter)
root_logger.addFilter(repetitive_filter)

# Set specific modules to DEBUG level only when WHIFFLE_DEBUG=1 (reduces log noise)
_debug_enabled = os.getenv("WHIFFLE_DEBUG", "").lower() in ("1", "true", "yes")
if _debug_enabled:
    logging.getLogger("game_loop").setLevel(logging.DEBUG)
    logging.getLogger("ball_tracker").setLevel(logging.DEBUG)

# Also suppress warnings at the Python level
warnings.filterwarnings("ignore", message=".*iCCP.*")

# Create a context manager to suppress stderr
@contextlib.contextmanager
def suppress_stderr():
    stderr = sys.stderr
    try:
        sys.stderr = open(os.devnull, 'w')
        yield
    finally:
        sys.stderr = stderr

import cv2

# Suppress OpenCV log messages (VIDEOIO/obsensor may still use stderr; camera probe redirects it)
try:
    _cv2_log = getattr(cv2, "utils", None) and getattr(cv2.utils, "logging", None)
    if _cv2_log and hasattr(_cv2_log, "setLogLevel"):
        _cv2_log.setLogLevel(getattr(_cv2_log, "LOG_LEVEL_SILENT", 0))
except Exception:
    pass

import numpy as np
import pygame  # Import pygame
from dotenv import load_dotenv

# Initialize pygame with stderr suppression
with suppress_stderr():
    pygame.init()
    pygame.display.init()  # Explicitly initialize the video subsystem
    pygame.display.set_mode((1, 1), pygame.HIDDEN)  # Create a small hidden display

# Updated imports: clean_exit from utils, mouse_callback from utils
from cleanup_utils import clean_exit

# Import constants
from constants import UIConstants
from game_loop import run_game_loop

# Import necessary classes and functions
# Import the specific utility function needed
from game_state_utils import save_score  # For exception handling
from ui_screens import show_splash_screen  # Assuming this is correct
from utils import mouse_callback  # Assuming mouse_callback remains in utils
from loading_screen import wrap_initialization  # Import the loading screen wrapper
from path_utils import bootstrap_frozen_paths, get_app_dir, get_bundle_dir, is_frozen


def validate_config(supabase_url: str, supabase_key: str) -> None:
    """Validate Supabase configuration at startup."""
    if not supabase_url or "default-supabase-url" in supabase_url:
        logger.error("Invalid Supabase URL. Please set SUPABASE_URL in .env file.")
        raise ValueError("Invalid Supabase URL")
    if not supabase_key or "default-supabase-api-key" in supabase_key:
        logger.error("Invalid Supabase key. Please set SUPABASE_KEY in .env file.")
        raise ValueError("Invalid Supabase key")


def _resolve_env_path() -> str:
    """Return the path to the .env file to load.

    When frozen (PyInstaller), bundled data files land under ``sys._MEIPASS``
    (the ``_internal/`` folder), not next to the executable. We check there
    first, then fall back to ``.env`` beside the binary so a deployed Pi can
    override secrets without rebuilding.
    """
    candidates: list[str] = []
    bundle = get_bundle_dir()
    if bundle:
        candidates.append(os.path.join(bundle, ".env"))
    candidates.append(os.path.join(get_app_dir(), ".env"))
    if not is_frozen():
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0] if candidates else os.path.join(get_app_dir(), ".env")


def initialize_game_state():
    """
    Initialize the game state with proper configuration.
    This function encapsulates the initialization process to be wrapped by the loading screen.
    """
    env_path = _resolve_env_path()
    if os.path.isfile(env_path):
        load_dotenv(env_path)
        logger.debug("Loaded environment from %s", env_path)
    else:
        logger.warning(
            "No .env file found (looked for bundled and local copies). "
            "Set SUPABASE_URL and SUPABASE_KEY in the environment or add .env next to the app."
        )
    supabase_url = os.getenv("SUPABASE_URL")  # Get URL from env
    supabase_key = os.getenv("SUPABASE_KEY")  # Get Key from env

    # Validate configuration
    validate_config(supabase_url, supabase_key)

    # Initialize game state via splash screen
    game_state = show_splash_screen(supabase_url, supabase_key)
    if game_state is None:
        logger.info(
            "Exiting due to None game_state from show_splash_screen (likely window closed or init failed)."
        )
        return None

    return game_state


def main() -> None:
    """Run the main game loop for Whiffle Tracker."""
    bootstrap_frozen_paths()
    # Use the loading screen wrapper for initialization
    game_state = wrap_initialization(initialize_game_state)

    # Exit if initialization failed
    if game_state is None:
        return

    try:
        # Check for window close immediately after splash screen
        try:
            # Ensure window name is correct and window exists
            if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                logger.info("Window closed after splash screen.")
                # clean_exit should be called even if window closed prematurely
                clean_exit(
                    game_state.cap,
                    game_state.background_music,
                    game_state.background_music_on,
                    game_state,
                )
                return
        except cv2.error:
            # Error likely means window doesn't exist or was closed.
            logger.info(
                "Window property check failed after splash screen (cv2.error), assuming window closed."
            )
            # Still attempt cleanup if game_state exists
            clean_exit(
                game_state.cap,
                game_state.background_music,
                game_state.background_music_on,
                game_state,
            )
            return

        # --- Set Mouse Callback ---
        try:
            # Ensure window exists before setting callback
            if (
                cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE)
                >= 1
            ):
                cv2.setMouseCallback(
                    UIConstants.WINDOW_NAME, mouse_callback, game_state
                )
                logger.debug("Mouse callback set.")
            else:
                logger.warning("Cannot set mouse callback, window not visible.")
                # Proceed without callback, or exit if essential
                # clean_exit(...) # Decide if exit is needed here
                # return
        except cv2.error as e:
            logger.error(f"Error setting mouse callback: {e}")
            # Decide how to handle this - proceed without callback or exit?
            # clean_exit(...)
            # return
        except Exception as e:
            logger.exception(f"Unexpected error setting mouse callback: {e}")
            # clean_exit(...)
            # return

        if _debug_enabled:
            logger.debug("--- Whiffle Tracker ---")
            logger.debug("Press 'q' to quit at any time.")
            logger.debug("Press 'm' during gameplay to open the menu.")

        # --- Initial Frame Display ---
        # Ensure game_state has camera/frame attributes before accessing
        initial_frame = None
        ret = False
        if hasattr(game_state, "camera_available") and game_state.camera_available:
            if (
                hasattr(game_state, "cap")
                and game_state.cap
                and game_state.cap.isOpened()
            ):
                ret, initial_frame = game_state.cap.read()
            else:
                logger.error(
                    "Camera was expected but not available/opened for initial frame."
                )
                ret = False  # Mark as failed
        elif (
            hasattr(game_state, "static_frame") and game_state.static_frame is not None
        ):
            initial_frame = game_state.static_frame.copy()
            ret = True  # Static frame counts as success
        else:
            logger.error(
                "Neither camera nor static frame available for initial display."
            )
            ret = False

        if ret and initial_frame is not None:
            try:
                # Ensure window exists before showing frame
                if (
                    cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE)
                    >= 1
                ):
                    cv2.imshow(UIConstants.WINDOW_NAME, initial_frame)
                    cv2.waitKey(100)  # Short delay to ensure frame displays
                else:
                    logger.warning("Cannot display initial frame, window not visible.")
                    # clean_exit(...) # Decide if exit needed
                    # return
            except cv2.error as e:
                logger.error(f"Error showing initial frame: {e}")
                # clean_exit(...) # Decide if exit needed
                # return
        else:
            logger.error("Failed to capture or load initial frame for display.")
            clean_exit(
                getattr(game_state, "cap", None),  # Safely get attributes
                getattr(game_state, "background_music", None),
                getattr(game_state, "background_music_on", False),
                game_state,  # Pass game_state itself
            )
            return

        # --- Run Main Game Loop ---
        run_game_loop(game_state)

    except Exception as e:
        logger.exception(f"Unexpected error in main: {e}")
        # Make sure to display the error
        if (
            hasattr(game_state, "window_name")
            and game_state.window_name
            and cv2.getWindowProperty(game_state.window_name, cv2.WND_PROP_VISIBLE) >= 1
        ):
            error_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            error_text = f"Error: {e}"
            cv2.putText(
                error_frame,
                error_text,
                (50, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                error_frame,
                "Press any key to exit",
                (50, 200),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.imshow(game_state.window_name, error_frame)
            cv2.waitKey(5000)  # Wait for 5 seconds or key press

        # Try to handle any score saving if possible
        try:
            if hasattr(game_state, "score") and game_state.score > 0:
                # Attempt to save final score if reasonable
                save_score(game_state, reason="error", error_message=str(e))
                logger.info(f"Saved final score of {game_state.score} despite error.")
        except Exception as save_error:
            logger.error(f"Failed to save score after error: {save_error}")

    finally:
        try:
            # Clean exit from all resources
            # Proper clean exit handles any attributes being None
            clean_exit(
                getattr(game_state, "cap", None),
                getattr(game_state, "background_music", None),
                getattr(game_state, "background_music_on", False),
                game_state,
            )
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}")
            # Last resort cleanup attempt focused on OpenCV only
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass  # Best-effort cleanup during shutdown
            if hasattr(game_state, "cap") and game_state.cap:
                try:
                    game_state.cap.release()
                except Exception:
                    pass  # Best-effort cleanup during shutdown

        # Force garbage collection
        gc.collect()
        logger.info("Clean exit complete")


if __name__ == "__main__":
    main()
