# heatmap_utils.py
"""
Utility functions for generating heatmap visualizations from session data.
"""

import logging
import cv2
import numpy as np
from typing import Dict, List, Tuple, Any, Optional

# Import SessionData for type hinting
try:
    from data_logger import SessionData
except ImportError:
    SessionData = Any  # Fallback type

# Import constants for dimensions (assuming they exist in constants.py)
try:
    from constants import UIConstants
except ImportError:
    # Define fallback dimensions if constants cannot be imported
    class MockUIConstants:
        WINDOW_WIDTH = 1280
        WINDOW_HEIGHT = 720

    UIConstants = MockUIConstants
    logger.warning(
        "Could not import UIConstants, using default dimensions for heatmap.")

logger = logging.getLogger(__name__)

# Heatmap Generation Parameters (can be moved to constants.py later)
HEATMAP_BLUR_KERNEL_SIZE = (21, 21)  # Size of the Gaussian blur kernel
HEATMAP_POINT_INTENSITY = 5  # How much each position contributes to the raw heatmap
HEATMAP_COLORMAP = cv2.COLORMAP_JET  # OpenCV colormap (JET, HOT, etc.)


def generate_heatmap(
    session_data: Optional[SessionData],
    width: int = UIConstants.WINDOW_WIDTH,
    height: int = UIConstants.WINDOW_HEIGHT,
) -> Optional[np.ndarray]:
    """
    Generates a heatmap image based on logged ball positions from session data.

    Args:
        session_data: The SessionData object containing ball position history.
                      Can be None if no session data is available.
        width: The desired width of the output heatmap image.
        height: The desired height of the output heatmap image.

    Returns:
        A BGR numpy array representing the heatmap image, or None if no
        position data is available or an error occurs.
    """
    if not session_data or not hasattr(session_data, "ball_position_history"):
        logger.warning(
            "Heatmap generation skipped: No session data or position history.")
        return None

    # Flatten all position data from the history
    all_positions = []
    for ball_id, history in session_data.ball_position_history.items():
        # history contains tuples of (x, y, timestamp)
        all_positions.extend([(pos[0], pos[1]) for pos in history])

    if not all_positions:
        logger.info(
            "Heatmap generation skipped: No ball positions logged in the session."
        )
        return None

    logger.info(
        f"Generating heatmap from {len(all_positions)} logged positions...")

    # Create a blank canvas (single channel, float32 for accumulation)
    heatmap_raw = np.zeros((height, width), dtype=np.float32)

    # Accumulate points on the heatmap
    valid_points_added = 0
    for x, y in all_positions:
        # Ensure coordinates are within bounds
        if 0 <= x < width and 0 <= y < height:
            # Add intensity at the point's location
            # Using cv2.circle allows for a small radius if desired,
            # otherwise just increment the single pixel: heatmap_raw[y, x] += HEATMAP_POINT_INTENSITY
            cv2.circle(
                heatmap_raw,
                (x, y),
                radius=1,
                color=(HEATMAP_POINT_INTENSITY, ),
                thickness=-1,
            )
            valid_points_added += 1
        # else: logger.debug(f"Skipping out-of-bounds point: ({x}, {y})") # Can be noisy

    if valid_points_added == 0:
        logger.warning("No valid points found within heatmap bounds.")
        return None

    # Apply Gaussian blur to spread the intensity
    try:
        heatmap_blurred = cv2.GaussianBlur(heatmap_raw,
                                           HEATMAP_BLUR_KERNEL_SIZE, 0)
    except cv2.error as e:
        logger.error(f"OpenCV error during GaussianBlur for heatmap: {e}")
        # Fallback: use the raw heatmap (might look blocky)
        heatmap_blurred = heatmap_raw
    except Exception as e:
        logger.exception(f"Unexpected error during GaussianBlur: {e}")
        heatmap_blurred = heatmap_raw

    # Normalize the blurred heatmap to 0-255 range
    # Avoid division by zero if heatmap is somehow flat zero after blur
    max_val = np.max(heatmap_blurred)
    if max_val > 0:
        heatmap_norm = (heatmap_blurred / max_val * 255).astype(np.uint8)
    else:
        heatmap_norm = np.zeros((height, width),
                                dtype=np.uint8)  # Return black if no intensity

    # Apply colormap
    try:
        heatmap_colored = cv2.applyColorMap(heatmap_norm, HEATMAP_COLORMAP)
    except cv2.error as e:
        logger.error(f"OpenCV error applying colormap: {e}")
        # Fallback: return the grayscale normalized heatmap
        heatmap_colored = cv2.cvtColor(heatmap_norm, cv2.COLOR_GRAY2BGR)
    except Exception as e:
        logger.exception(f"Unexpected error applying colormap: {e}")
        heatmap_colored = cv2.cvtColor(heatmap_norm, cv2.COLOR_GRAY2BGR)

    logger.info("Heatmap generation complete.")
    return heatmap_colored


# Example Usage (for testing purposes, remove later)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Testing Heatmap Generation...")

    # Create dummy session data with positions
    class MockSessionDataHeatmap:

        def __init__(self):
            self.ball_position_history = defaultdict(list)
            # Simulate ball 1 moving across top-left
            for i in range(100):
                self.ball_position_history[1].append(
                    (50 + i, 50 + i // 2, time.time()))
            # Simulate ball 2 lingering bottom-right
            for i in range(200):
                self.ball_position_history[2].append((
                    UIConstants.WINDOW_WIDTH - 100 +
                    np.random.randint(-20, 20),
                    UIConstants.WINDOW_HEIGHT - 100 +
                    np.random.randint(-20, 20),
                    time.time(),
                ))
            # Add some out-of-bounds points
            self.ball_position_history[3].append((-10, 50, time.time()))
            self.ball_position_history[3].append(
                (50, UIConstants.WINDOW_HEIGHT + 10, time.time()))

    mock_data = MockSessionDataHeatmap()
    heatmap_image = generate_heatmap(mock_data)

    if heatmap_image is not None:
        print("Heatmap generated successfully.")
        cv2.imshow("Generated Heatmap", heatmap_image)
        print("Press any key to close the heatmap window...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        print("Heatmap generation failed.")

    # Test with no data
    print("\nTesting with empty session data...")
    empty_data = SessionData("Test", "test")  # Has attribute, but it's empty
    heatmap_empty = generate_heatmap(empty_data)
    if heatmap_empty is None:
        print("Correctly returned None for empty data.")
    else:
        print("ERROR: Should have returned None for empty data.")

    print("\nTesting with None session data...")
    heatmap_none = generate_heatmap(None)
    if heatmap_none is None:
        print("Correctly returned None for None data.")
    else:
        print("ERROR: Should have returned None for None data.")

    logger.info("Heatmap test complete.")
