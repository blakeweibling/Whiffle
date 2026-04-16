# detection.py
"""
Ball detection and tracking using YOLOv8 for the Whiffle Tracker project.
"""

import logging
import os
from typing import Any, List, Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO

from constants import DetectionConstants, GameSpecificConstants, GameConstants  #

# Set up logging
logger = logging.getLogger(__name__)

# Enable OpenCL for OpenCV (Unchanged)
cv2.ocl.setUseOpenCL(True)
if not cv2.ocl.haveOpenCL():
    logger.warning("OpenCL is not available on this device. Falling back to CPU.")  #

# Use GameSpecificConstants for excluded positions (Unchanged)
EXCLUDED_POSITIONS: List[Tuple[int, int]] = GameSpecificConstants.EXCLUDED_POSITIONS  #


class BallDetector:

    def __init__(self, model_path: Optional[str] = None):
        # Load the trained YOLOv8 model
        self.model_path = model_path or GameConstants.WHIFFLE_MODEL_PATH
        self.model = YOLO(self.model_path)
        
        # Extract class names directly from the model file
        self.class_names = self._extract_class_names_from_model()
        
        logger.debug(f"BallDetector initialized with model: {self.model_path}")
        logger.debug(f"Extracted class names from model: {self.class_names}")
        self.state_names = ["on_playfield", "in_hole"]
    
    def _extract_class_names_from_model(self) -> List[str]:
        """
        Extract class names from the YOLO model file.
        Returns a list of class names in order (index 0, 1, 2, etc.)
        """
        try:
            # YOLO models store class names in the model.names attribute
            # It can be a dict {0: 'class0', 1: 'class1', ...} or a list
            if hasattr(self.model, 'names') and self.model.names:
                if isinstance(self.model.names, dict):
                    # Convert dict to ordered list
                    max_index = max(self.model.names.keys()) if self.model.names else -1
                    class_names = [self.model.names.get(i, f"class_{i}") for i in range(max_index + 1)]
                    logger.debug(f"Extracted class names from model dict: {class_names}")
                    return class_names
                elif isinstance(self.model.names, list):
                    logger.debug(f"Extracted class names from model list: {self.model.names}")
                    return self.model.names
                else:
                    logger.warning(f"Model names format not recognized: {type(self.model.names)}")
            
            # Try alternative: check model metadata or model.yaml
            if hasattr(self.model, 'model') and hasattr(self.model.model, 'names'):
                names = self.model.model.names
                if isinstance(names, dict):
                    max_index = max(names.keys()) if names else -1
                    class_names = [names.get(i, f"class_{i}") for i in range(max_index + 1)]
                    logger.debug(f"Extracted class names from model.model.names: {class_names}")
                    return class_names
                elif isinstance(names, list):
                    logger.debug(f"Extracted class names from model.model.names list: {names}")
                    return names
            
            # If we can't extract from model, log warning and return empty list
            # The detection code should handle this gracefully
            logger.warning(f"Could not extract class names from model at {self.model_path}")
            logger.warning("Model may not have class names embedded. Detection may fail.")
            return []
            
        except Exception as e:
            logger.error(f"Error extracting class names from model: {e}")
            return []

        # Attempt to use OpenCL for YOLOv8 inference (Unchanged)
        try:
            # Note: YOLO might handle device preference automatically in newer versions.
            # self.model.to('ocl') or similar might be alternatives if direct predictor access changes.
            pass  # Assuming model handles device preference, or previous attempts were sufficient.
            logger.info(
                "YOLOv8 device preference potentially set (check Ultralytics docs)."
            )  #
        except Exception as e:
            logger.warning(
                f"Could not configure YOLOv8 device preference explicitly: {e}"
            )  #

    def _is_position_excluded(
        self, x: int, y: int, excluded_positions: List[Tuple[int, int]]
    ) -> bool:
        """Check if a position is within the exclusion distance of any excluded position."""
        # (Unchanged)
        for ex, ey in excluded_positions:  #
            dist = np.sqrt((x - ex) ** 2 + (y - ey) ** 2)  #
            if dist < DetectionConstants.EXCLUSION_DISTANCE:  #
                logger.debug(
                    f"Position ({x}, {y}) excluded: distance {dist} to excluded position ({ex}, {ey})"
                )  #
                return True
        return False

    # --- [MODIFY] Correct the logic here for consistency ---
    def _is_in_scoring_zone(
        self,
        x: float,  # Ball center X
        y: float,  # Ball center Y
        radius: float,  # Ball radius (unused in corrected logic)
        scoring_zones: List[Tuple[int, int, int, int, int]],
    ) -> bool:
        """
        Check if a ball's center is within a scoring zone (hole).
        Uses Top-Left Corner, Width, Height definition for zones.
        """
        for zone in scoring_zones:  #
            zone_x, zone_y, zone_width, zone_height, _ = (
                zone  # Assumes Top-Left X, Y, Width, Height
            )

            # Corrected Logic: Check if ball center (x,y) is within the zone boundaries
            if zone_x <= x < zone_x + zone_width and zone_y <= y < zone_y + zone_height:
                return True
        return False

    # --- [END MODIFY] ---

    def detect_all_balls(
        self,
        frame: np.ndarray,  #
        frame_count: int,  #
        game_state: Any,  #
        scoring_zones: List[Tuple[int, int, int, int, int]],  #
        hsv_frame: Optional[np.ndarray] = None,  #
        debug_mode: bool = False,  #
    ) -> Tuple[
        List[Tuple[int, int, float]],  # silver_balls (or red/white balls in whiffle mode)
        List[Tuple[int, int, float]],  # gold_balls (or half-red balls in whiffle mode)
    ]:
        """
        Detect balls in the frame using YOLOv8 and infer their state.
        Class names are extracted from the model file (.pt) automatically.
        Uses internal scaling for inference and scales results back.
        """
        # Class names are already extracted from model in __init__, no need to update here
        if not self.class_names:
            logger.error("No class names available from model. Detection may fail.")
            return [], []
        # Downscale the frame for YOLO inference (Unchanged)
        inference_scale = 0.5
        inference_frame = cv2.resize(
            frame,
            None,
            fx=inference_scale,
            fy=inference_scale,
            interpolation=cv2.INTER_AREA,
        )  #

        # Detect balls using YOLOv8 (Unchanged)
        results = self.model(inference_frame, conf=0.5, iou=0.5, verbose=False)

        # Separate balls by type
        silver_balls = []
        gold_balls = []

        # Scale coordinates back to original resolution (Unchanged logic)
        scale_factor = 1 / inference_scale
        for result in results:  #
            boxes = result.boxes.xyxy.cpu().numpy()  #
            scores = result.boxes.conf.cpu().numpy()  #
            classes = result.boxes.cls.cpu().numpy()  #

            for box, score, cls in zip(boxes, scores, classes):  #
                x_min, y_min, x_max, y_max = box
                # Scale coordinates back to original resolution
                x_min_orig, x_max_orig = int(x_min * scale_factor), int(
                    x_max * scale_factor
                )  #
                y_min_orig, y_max_orig = int(y_min * scale_factor), int(
                    y_max * scale_factor
                )  #
                x_center = (x_min_orig + x_max_orig) / 2
                y_center = (y_min_orig + y_max_orig) / 2
                width = x_max_orig - x_min_orig  #
                height = y_max_orig - y_min_orig  #
                radius = max(width, height) / 2  # Estimate radius

                # Filter out excluded positions (Unchanged)
                if self._is_position_excluded(
                    x_center, y_center, EXCLUDED_POSITIONS
                ):  #
                    if debug_mode:
                        logger.debug(
                            f"Ball at ({x_center:.0f}, {y_center:.0f}) excluded due to position"
                        )  #
                    continue

                # Assign ball type with bounds checking
                cls_int = int(cls)
                if cls_int < 0 or cls_int >= len(self.class_names):
                    logger.warning(
                        f"Invalid class index {cls_int} detected (expected 0-{len(self.class_names)-1}). "
                        f"Model has {len(self.class_names)} classes: {self.class_names}. Skipping detection."
                    )
                    continue
                
                ball_type = self.class_names[cls_int]
                if debug_mode:
                    logger.debug(
                        f"Detected {ball_type} ball at ({x_center:.0f}, {y_center:.0f}) with radius={radius:.1f}, confidence={score:.2f}"
                    )  #

                # Append to respective lists with ball type information
                # Store as (x, y, radius, ball_type) to preserve the actual type name
                # Map ball types to return lists dynamically based on model's class names
                if len(self.class_names) == 2:
                    # Two classes: first -> silver_balls, second -> gold_balls
                    if cls_int == 0:
                        silver_balls.append((int(x_center), int(y_center), radius, ball_type))
                    elif cls_int == 1:
                        gold_balls.append((int(x_center), int(y_center), radius, ball_type))
                    else:
                        logger.warning(f"Unexpected class index {cls_int} for 2-class model")
                        silver_balls.append((int(x_center), int(y_center), radius, ball_type))
                elif len(self.class_names) == 3:
                    # Three classes: first two -> silver_balls, third -> gold_balls
                    # (e.g., whiffle: red, white -> silver_balls; half-red -> gold_balls)
                    if cls_int in [0, 1]:
                        silver_balls.append((int(x_center), int(y_center), radius, ball_type))
                    elif cls_int == 2:
                        gold_balls.append((int(x_center), int(y_center), radius, ball_type))
                    else:
                        logger.warning(f"Unexpected class index {cls_int} for 3-class model")
                        silver_balls.append((int(x_center), int(y_center), radius, ball_type))
                else:
                    # Generic mapping: split classes roughly in half
                    # First half -> silver_balls, second half -> gold_balls
                    mid_point = len(self.class_names) // 2
                    if cls_int < mid_point:
                        silver_balls.append((int(x_center), int(y_center), radius, ball_type))
                    else:
                        gold_balls.append((int(x_center), int(y_center), radius, ball_type))

        # Debug frame drawing.
        #
        # Historically this block called ``cv2.imshow("Ball Detection", ...)``
        # unconditionally whenever ``debug_mode`` was True. That opened a SECOND
        # OpenCV window separate from the main game window, which never received
        # ``cv2.waitKey`` drain calls in the main loop and showed up as a blank
        # "Ball Detection" window that could not be closed cleanly. The
        # ``debug_mode`` argument is never passed as True by any caller, so the
        # simplest correct fix is to gate the debug overlay behind an explicit
        # environment variable AND keep the window out of the picture unless the
        # developer has opted in.
        if debug_mode and os.environ.get("WHIFFLE_BALL_DETECTION_DEBUG") == "1":
            debug_frame = frame.copy()
            for ball in silver_balls:
                x, y, radius = ball[:3]
                cv2.circle(debug_frame, (x, y), int(radius), (0, 0, 255), 2)
            for ball in gold_balls:
                x, y, radius = ball[:3]
                cv2.circle(debug_frame, (x, y), int(radius), (0, 215, 255), 2)
            cv2.imshow("Ball Detection", debug_frame)

        return silver_balls, gold_balls
