# heatmap_utils.py
"""
Utility functions for generating heatmap visualizations from session data.
"""

import logging
import cv2
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict # [ADD] Import defaultdict if used

# Import SessionData for type hinting
try:
    from data_logger import SessionData #
except ImportError:
    SessionData = Any  # Fallback type

# [REMOVE] Remove direct import/reliance on UIConstants for dimensions here
# try: from constants import UIConstants
# except ImportError: ...

logger = logging.getLogger(__name__)

# Heatmap Generation Parameters (Unchanged)
HEATMAP_BLUR_KERNEL_SIZE = (21, 21)
HEATMAP_POINT_INTENSITY = 5
HEATMAP_COLORMAP = cv2.COLORMAP_JET

# --- [MODIFY] Remove UIConstants defaults, add simple fallbacks ---
def generate_heatmap(
    session_data: Optional[SessionData],
    width: int = 1280, # Fallback default width
    height: int = 720, # Fallback default height
) -> Optional[np.ndarray]:
    """
    Generates a heatmap image based on logged ball positions from session data.
    Args:
        session_data: The SessionData object containing ball position history. Can be None.
        width: The desired width of the output heatmap image.
        height: The desired height of the output heatmap image.
    Returns:
        A BGR numpy array representing the heatmap image, or None.
    """
    # --- Function Body (Unchanged) ---
    if not session_data or not hasattr(session_data, "ball_position_history"): #
        logger.warning("Heatmap generation skipped: No session data or position history.") #
        return None #

    all_positions = [] #
    # Ensure ball_position_history is a dict (it should be defaultdict now)
    if isinstance(session_data.ball_position_history, dict):
        for ball_id, history in session_data.ball_position_history.items(): #
            all_positions.extend([(pos[0], pos[1]) for pos in history]) #
    else:
        logger.error("ball_position_history is not a dictionary.")
        return None


    if not all_positions: #
        logger.info("Heatmap generation skipped: No ball positions logged.") #
        return None #

    logger.info(f"Generating heatmap from {len(all_positions)} logged positions...") #

    heatmap_raw = np.zeros((height, width), dtype=np.float32) #

    valid_points_added = 0 #
    for x, y in all_positions: #
        if 0 <= x < width and 0 <= y < height: #
            # Using circle for slightly larger point, adjust radius or use direct pixel access if needed
            cv2.circle(heatmap_raw, (int(x), int(y)), radius=1, color=(HEATMAP_POINT_INTENSITY,), thickness=-1,) # Use int(x), int(y)
            valid_points_added += 1 #
    if valid_points_added == 0: logger.warning("No valid points found within heatmap bounds."); return None #

    try: heatmap_blurred = cv2.GaussianBlur(heatmap_raw, HEATMAP_BLUR_KERNEL_SIZE, 0) #
    except cv2.error as e: logger.error(f"OpenCV error during GaussianBlur for heatmap: {e}"); heatmap_blurred = heatmap_raw #
    except Exception as e: logger.exception(f"Unexpected error during GaussianBlur: {e}"); heatmap_blurred = heatmap_raw #

    max_val = np.max(heatmap_blurred) #
    if max_val > 0: heatmap_norm = (heatmap_blurred / max_val * 255).astype(np.uint8) #
    else: heatmap_norm = np.zeros((height, width), dtype=np.uint8) #

    try: heatmap_colored = cv2.applyColorMap(heatmap_norm, HEATMAP_COLORMAP) #
    except cv2.error as e: logger.error(f"OpenCV error applying colormap: {e}"); heatmap_colored = cv2.cvtColor(heatmap_norm, cv2.COLOR_GRAY2BGR) #
    except Exception as e: logger.exception(f"Unexpected error applying colormap: {e}"); heatmap_colored = cv2.cvtColor(heatmap_norm, cv2.COLOR_GRAY2BGR) #

    logger.info("Heatmap generation complete.") #
    return heatmap_colored #