# detection.py
"""
Ball detection and tracking using YOLOv8 for the Whiffle Tracker project.
"""

import logging
from typing import Any, List, Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO

from constants import DetectionConstants, GameSpecificConstants #

# Set up logging
logger = logging.getLogger(__name__)

# Enable OpenCL for OpenCV (Unchanged)
cv2.ocl.setUseOpenCL(True)
if not cv2.ocl.haveOpenCL():
    logger.warning("OpenCL is not available on this device. Falling back to CPU.") #

# Use GameSpecificConstants for excluded positions (Unchanged)
EXCLUDED_POSITIONS: List[Tuple[int, int]] = GameSpecificConstants.EXCLUDED_POSITIONS #


class BallDetector:

    def __init__(self):
        # Load the trained YOLOv8 model (Unchanged)
        self.model = YOLO("whiffle_new_best.pt")
        self.class_names = ["white", "red", "half"]
        self.state_names = ["on_playfield", "in_hole"]

        # Attempt to use OpenCL for YOLOv8 inference (Unchanged)
        try:
            # Note: YOLO might handle device preference automatically in newer versions.
            # self.model.to('ocl') or similar might be alternatives if direct predictor access changes.
            pass # Assuming model handles device preference, or previous attempts were sufficient.
            logger.info("YOLOv8 device preference potentially set (check Ultralytics docs).") #
        except Exception as e:
            logger.warning(f"Could not configure YOLOv8 device preference explicitly: {e}") #


    def _is_position_excluded(
            self, x: int, y: int,
            excluded_positions: List[Tuple[int, int]]) -> bool:
        """Check if a position is within the exclusion distance of any excluded position."""
        # (Unchanged)
        for ex, ey in excluded_positions: #
            dist = np.sqrt((x - ex)**2 + (y - ey)**2) #
            if dist < DetectionConstants.EXCLUSION_DISTANCE: #
                logger.debug(f"Position ({x}, {y}) excluded: distance {dist} to excluded position ({ex}, {ey})") #
                return True
        return False

    # --- [MODIFY] Correct the logic here for consistency ---
    def _is_in_scoring_zone(
        self,
        x: float, # Ball center X
        y: float, # Ball center Y
        radius: float, # Ball radius (unused in corrected logic)
        scoring_zones: List[Tuple[int, int, int, int, int]],
    ) -> bool:
        """
        Check if a ball's center is within a scoring zone (hole).
        Uses Top-Left Corner, Width, Height definition for zones.
        """
        for zone in scoring_zones: #
            zone_x, zone_y, zone_width, zone_height, _ = zone # Assumes Top-Left X, Y, Width, Height

            # Corrected Logic: Check if ball center (x,y) is within the zone boundaries
            if zone_x <= x < zone_x + zone_width and zone_y <= y < zone_y + zone_height:
                 return True
        return False
    # --- [END MODIFY] ---

    def detect_all_balls(
        self,
        frame: np.ndarray, #
        frame_count: int, #
        game_state: Any, #
        scoring_zones: List[Tuple[int, int, int, int, int]], #
        hsv_frame: Optional[np.ndarray] = None, #
        debug_mode: bool = False, #
    ) -> Tuple[
            List[Tuple[int, int, float]], # white_balls
            List[Tuple[int, int, float]], # red_balls
            List[Tuple[int, int, float]], # half_balls
    ]:
        """
        Detect white, red, and half red/half white balls in the frame using YOLOv8 and infer their state.
        Uses internal scaling for inference and scales results back.
        """
        # Downscale the frame for YOLO inference (Unchanged)
        inference_scale = 0.5
        inference_frame = cv2.resize(frame, None, fx=inference_scale, fy=inference_scale, interpolation=cv2.INTER_AREA,) #

        # Detect balls using YOLOv8 (Unchanged)
        results = self.model(inference_frame, conf=0.5, iou=0.5)

        # Separate balls by type
        white_balls = [] #
        red_balls = [] #
        half_balls = [] #

        # Scale coordinates back to original resolution (Unchanged logic)
        scale_factor = 1 / inference_scale
        for result in results: #
            boxes = result.boxes.xyxy.cpu().numpy() #
            scores = result.boxes.conf.cpu().numpy() #
            classes = result.boxes.cls.cpu().numpy() #

            for box, score, cls in zip(boxes, scores, classes): #
                x_min, y_min, x_max, y_max = box
                # Scale coordinates back to original resolution
                x_min_orig, x_max_orig = int(x_min * scale_factor), int(x_max * scale_factor) #
                y_min_orig, y_max_orig = int(y_min * scale_factor), int(y_max * scale_factor) #
                x_center = (x_min_orig + x_max_orig) / 2
                y_center = (y_min_orig + y_max_orig) / 2
                width = x_max_orig - x_min_orig #
                height = y_max_orig - y_min_orig #
                radius = max(width, height) / 2 # Estimate radius

                # Filter out excluded positions (Unchanged)
                if self._is_position_excluded(x_center, y_center, EXCLUDED_POSITIONS): #
                    if debug_mode: logger.debug(f"Ball at ({x_center:.0f}, {y_center:.0f}) excluded due to position") #
                    continue

                # Assign ball type (Unchanged)
                ball_type = self.class_names[int(cls)]
                if debug_mode: logger.debug(f"Detected {ball_type} ball at ({x_center:.0f}, {y_center:.0f}) with radius={radius:.1f}, confidence={score:.2f}") #

                # Append to respective lists (Unchanged)
                if ball_type == "white":
                    white_balls.append((int(x_center), int(y_center), radius))
                elif ball_type == "red":
                    red_balls.append((int(x_center), int(y_center), radius))
                elif ball_type == "half":
                    half_balls.append((int(x_center), int(y_center), radius))

        # Debug frame drawing (Unchanged)
        if debug_mode:
            debug_frame = frame.copy() #
            for x, y, radius in white_balls: cv2.circle(debug_frame, (x, y), int(radius), (255, 255, 255), 2) #
            for x, y, radius in red_balls: cv2.circle(debug_frame, (x, y), int(radius), (0, 0, 255), 2) #
            for x, y, radius in half_balls: cv2.circle(debug_frame, (x, y), int(radius), (255, 0, 255), 2) #
            cv2.imshow("Ball Detection", debug_frame) #

        return white_balls, red_balls, half_balls #