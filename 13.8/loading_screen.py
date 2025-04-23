"""
Loading screen wrapper for Whiffle Tracker.
Displays a loading screen with progress bar until the main OpenCV window is loaded.
"""

import threading
import time
import logging
import cv2
import numpy as np
from typing import Callable, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global loading screen instance for access from other modules
_global_loading_screen = None

class LoadingScreen:
    """Loading screen manager that displays a progress bar until the main application is ready."""
    
    def __init__(self, window_name: str = "Whiffle Tracker - Loading...", width: int = 600, height: int = 400):
        """Initialize the loading screen with given dimensions."""
        self.window_name = window_name
        self.width = width
        self.height = height
        self.progress = 0.0  # Progress from 0.0 to 1.0
        self.running = False
        self.thread = None
        self.loading_stage = "Initializing..."
        self.window_created = False
        
    def _create_loading_frame(self) -> np.ndarray:
        """Create a loading screen frame with current progress."""
        # Create a dark background
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Add gradient background
        for y in range(self.height):
            blend = min(1.0, y / (self.height * 0.7))
            color = [int(30 * blend), int(30 * blend), int(40 * blend)]
            frame[y, :] = color
            
        # Add title
        cv2.putText(
            frame,
            "Whiffle Tracker",
            (self.width // 2 - 130, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (220, 220, 255),
            2,
            cv2.LINE_AA,
        )
        
        # Add subtitle
        cv2.putText(
            frame,
            self.loading_stage,
            (self.width // 2 - 100, 130),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (200, 200, 220),
            1,
            cv2.LINE_AA,
        )
        
        # Draw progress bar background
        bar_width = int(self.width * 0.8)
        bar_height = 20
        bar_x = (self.width - bar_width) // 2
        bar_y = self.height // 2
        cv2.rectangle(
            frame,
            (bar_x, bar_y),
            (bar_x + bar_width, bar_y + bar_height),
            (50, 50, 60),
            -1,  # Filled rectangle
        )
        
        # Draw progress bar fill
        filled_width = int(bar_width * self.progress)
        if filled_width > 0:
            cv2.rectangle(
                frame,
                (bar_x, bar_y),
                (bar_x + filled_width, bar_y + bar_height),
                (100, 180, 255),
                -1,  # Filled rectangle
            )
            
        # Add progress percentage text
        percentage = int(self.progress * 100)
        cv2.putText(
            frame,
            f"{percentage}%",
            (bar_x + bar_width // 2 - 20, bar_y + bar_height + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (180, 180, 200),
            1,
            cv2.LINE_AA,
        )
        
        # Add hint text
        cv2.putText(
            frame,
            "Please wait while the game initializes...",
            (bar_x, bar_y + bar_height + 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (170, 170, 190),
            1,
            cv2.LINE_AA,
        )
        
        return frame
    
    def _update_loop(self):
        """Main update loop for the loading screen."""
        self.window_created = True
        
        # Create window with specific flags for better UI
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, self.width, self.height)
        
        # Center the window on the screen
        try:
            # Try to get screen resolution - this is platform-dependent
            # For Windows, we can use GetSystemMetrics
            import ctypes
            user32 = ctypes.windll.user32
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)
            
            # Calculate center position
            x_pos = max(0, (screen_width - self.width) // 2)
            y_pos = max(0, (screen_height - self.height) // 2)
            
            # Move window to center
            cv2.moveWindow(self.window_name, x_pos, y_pos)
            logger.info(f"Centered loading window at ({x_pos}, {y_pos})")
        except Exception as e:
            logger.error(f"Failed to center window: {e}")
        
        fake_progress_speed = 0.002  # Speed of the fake progress increment
        
        while self.running and self.progress < 0.95:
            frame = self._create_loading_frame()
            
            # Show the frame
            try:
                cv2.imshow(self.window_name, frame)
                cv2.waitKey(1)  # Required to update window
                
                # Increment progress for visual feedback
                # This automatic increment will stop at 95% and wait for completion signal
                if self.progress < 0.95:
                    time.sleep(0.03)  # Small delay between updates
                    self.progress += fake_progress_speed
                    # Slow down progress as it approaches 95%
                    if self.progress > 0.7:
                        fake_progress_speed = 0.001
            except cv2.error as e:
                logger.error(f"Error in loading screen update loop: {e}")
                self.running = False
                break
    
    def start(self):
        """Start displaying the loading screen in a separate thread."""
        if self.thread is not None and self.thread.is_alive():
            logger.warning("Loading screen is already running")
            return
            
        self.running = True
        self.progress = 0.0
        self.thread = threading.Thread(target=self._update_loop)
        self.thread.daemon = True  # Thread will exit when main program exits
        self.thread.start()
        logger.info("Loading screen started")
        print("Loading screen started - waiting for initialization...")
        
        # Set this instance as the global loading screen
        global _global_loading_screen
        _global_loading_screen = self
    
    def update_stage(self, stage_text: str, progress_increment: float = 0.05):
        """Update the current loading stage text and increment progress."""
        self.loading_stage = stage_text
        self.progress = min(0.95, self.progress + progress_increment)
        logger.info(f"Loading stage: {stage_text}, Progress: {self.progress:.0%}")
        print(f"Loading: {stage_text} - {int(self.progress * 100)}%")
    
    def finish(self):
        """Complete the loading process and close the loading screen."""
        if not self.running:
            return
            
        # Set progress to 100% for visual feedback
        self.progress = 1.0
        self.loading_stage = "Ready!"
        print("Loading completed! (100%)")
        
        # Show the final 100% frame briefly
        final_frame = self._create_loading_frame()
        try:
            if self.window_created:
                cv2.imshow(self.window_name, final_frame)
                cv2.waitKey(300)  # Show completion for a moment
                
                # Close the loading window
                cv2.destroyWindow(self.window_name)
                print("Loading screen closed")
        except cv2.error as e:
            logger.error(f"Error in loading screen finish: {e}")
            print(f"Error closing loading screen: {e}")
        
        # Stop the update thread
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1.0)  # Wait for thread to finish
        
        logger.info("Loading screen finished")
        
        # Clear the global reference
        global _global_loading_screen
        _global_loading_screen = None


def update_loading_progress(stage_text: str, progress_increment: float = 0.05):
    """
    Update the global loading screen progress from any module.
    
    Args:
        stage_text: Text describing the current loading stage
        progress_increment: How much to increment the progress bar (0.0-1.0)
    """
    global _global_loading_screen
    if _global_loading_screen is not None and _global_loading_screen.running:
        _global_loading_screen.update_stage(stage_text, progress_increment)


def wrap_initialization(initialization_func: Callable, *args, **kwargs) -> Optional[object]:
    """
    Wrap the main initialization function with a loading screen.
    
    Args:
        initialization_func: The function to call for initialization
        *args, **kwargs: Arguments to pass to the initialization function
        
    Returns:
        The result of the initialization function
    """
    # Create and start loading screen
    loading_screen = LoadingScreen()
    loading_screen.start()
    
    # Update loading screen with initialization steps
    loading_screen.update_stage("Loading configuration...", 0.1)
    time.sleep(0.5)  # Small delay for visual feedback
    
    loading_screen.update_stage("Initializing game state...", 0.15)
    time.sleep(0.5)  # Small delay for visual feedback
    
    loading_screen.update_stage("Connecting to camera...", 0.2)
    
    # Run the initialization function
    try:
        result = initialization_func(*args, **kwargs)
        
        # If initialization was successful
        if result is not None:
            loading_screen.update_stage("Loading resources...", 0.3)
            time.sleep(0.5)  # Small delay for visual feedback
            
            loading_screen.update_stage("Setting up user interface...", 0.1)
            time.sleep(0.5)  # Small delay for visual feedback
        
        # Finish loading and close the screen
        loading_screen.finish()
        return result
        
    except Exception as e:
        logger.error(f"Error during initialization: {e}")
        loading_screen.loading_stage = f"Error: {str(e)}"
        time.sleep(2.0)  # Show error for a bit
        loading_screen.finish()
        raise  # Re-raise the exception for proper handling 