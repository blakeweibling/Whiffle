# ui_utils.py
import cv2
import numpy as np
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Helper Function: Draw text with background (Moved from ui.py)
def _draw_text_with_background(
    frame: np.ndarray,
    text: str,
    pos: Tuple[int, int],
    font_scale: float,
    text_color: Tuple[int, int, int],
    bg_color: Tuple[int, int, int],
    thickness: int = 1,
    padding: int = 3,
    font: int = cv2.FONT_HERSHEY_SIMPLEX,
    alpha: float = 0.6, # Opacity for background
) -> None:
    """Draws text with a semi-transparent background rectangle."""
    try:
        (text_width, text_height), baseline = cv2.getTextSize(
            text, font, font_scale, thickness
        )
    except cv2.error as e:
         logger.error(f"cv2.getTextSize error for text '{text}': {e}")
         # Optionally draw text without background as fallback or just return
         cv2.putText(frame, text, pos, font, font_scale, text_color, thickness, cv2.LINE_AA)
         return

    x, y = pos
    # Rectangle coordinates (top-left and bottom-right)
    rect_x1 = x - padding
    rect_y1 = y - text_height - padding - baseline // 2 # Adjust y based on baseline
    rect_x2 = x + text_width + padding
    rect_y2 = y + padding - baseline // 2

    # Ensure coordinates are within frame bounds
    rect_x1 = max(0, rect_x1)
    rect_y1 = max(0, rect_y1)
    rect_x2 = min(frame.shape[1], rect_x2)
    rect_y2 = min(frame.shape[0], rect_y2)

    # Calculate text position adjusted for baseline
    # Ensure pos[1] (y) is used for vertical positioning relative to the original point
    text_y_pos = y - baseline // 2

    # Extract ROI and create overlay only if rectangle is valid
    if rect_x1 < rect_x2 and rect_y1 < rect_y2:
        try:
            sub_img = frame[rect_y1:rect_y2, rect_x1:rect_x2]
            if sub_img.size == 0:
                # If ROI is invalid after clipping, just draw text
                logger.warning(f"Empty sub_img after clipping for text background at {pos}. Text: '{text}'")
                cv2.putText(frame, text, (x, text_y_pos), font, font_scale, text_color, thickness, cv2.LINE_AA)
                return

            bg_rect = np.zeros(sub_img.shape, dtype=np.uint8)
            bg_rect[:] = bg_color

            # Blend background
            res = cv2.addWeighted(sub_img, 1.0 - alpha, bg_rect, alpha, 0)
            frame[rect_y1:rect_y2, rect_x1:rect_x2] = res

        except cv2.error as e:
            logger.error(
                f"CV2 error processing background for text '{text}': {e}. ROI rect: ({rect_x1},{rect_y1})-({rect_x2},{rect_y2})"
            )
            # Fallback: Just draw text without background if blending fails
            cv2.putText(frame, text, (x, text_y_pos), font, font_scale, text_color, thickness, cv2.LINE_AA)
            return
        except Exception as e:
            logger.error(f"Unexpected error drawing text background for '{text}': {e}")
            # Fallback: Just draw text
            cv2.putText(frame, text, (x, text_y_pos), font, font_scale, text_color, thickness, cv2.LINE_AA)
            return

    # Draw text on top (either over the blended background or directly if background failed/skipped)
    # Use the calculated text_y_pos
    cv2.putText(
        frame,
        text,
        (x, text_y_pos), # Use original x, adjusted y
        font,
        font_scale,
        text_color,
        thickness,
        cv2.LINE_AA,
    )