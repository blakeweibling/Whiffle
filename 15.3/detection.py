# detection.py
"""
Ball detection and tracking using YOLOv8 for the Whiffle Tracker project.
"""

import logging
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
        resolved_model_path = model_path or GameConstants.WHIFFLE_MODEL_PATH
        self.model = YOLO(resolved_model_path)
        
        # Try to get class names from the model, fall back to default if not available
        if hasattr(self.model, 'names') and self.model.names:
            # Convert model names dict to list (YOLO models typically have names as dict {0: 'class0', 1: 'class1', ...})
            if isinstance(self.model.names, dict):
                max_index = max(self.model.names.keys()) if self.model.names else -1
                self.class_names = [self.model.names.get(i, f"class_{i}") for i in range(max_index + 1)]
            elif isinstance(self.model.names, list):
                self.class_names = self.model.names
            else:
                self.class_names = ["silver", "gold"]
                logger.warning(f"Model names format not recognized, using default: {self.class_names}")
        else:
            self.class_names = ["silver", "gold"]
            logger.info(f"Using default class names: {self.class_names}")
        
        logger.info(f"BallDetector initialized with class names: {self.class_names}")
        self.state_names = ["on_playfield", "in_hole"]

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
        For whiffle mode: detects red, white, and half-red balls.
        For fivestar mode: detects silver and gold balls.
        Uses internal scaling for inference and scales results back.
        """
        # Determine playfield type to use appropriate class names
        is_whiffle = True  # Default to whiffle
        if hasattr(game_state, 'is_fivestar_playfield'):
            is_whiffle = not game_state.is_fivestar_playfield()
        elif hasattr(game_state, 'playfield_type'):
            is_whiffle = getattr(game_state, 'playfield_type', 'whiffle') != 'fivestar'
        
        # Update class names based on playfield type
        if is_whiffle:
            # For whiffle mode, expect red, white, and half-red balls
            # Try to get from model, otherwise use expected names
            if hasattr(self.model, 'names') and self.model.names:
                if isinstance(self.model.names, dict):
                    max_index = max(self.model.names.keys()) if self.model.names else -1
                    model_class_names = [self.model.names.get(i, f"class_{i}") for i in range(max_index + 1)]
                elif isinstance(self.model.names, list):
                    model_class_names = self.model.names
                else:
                    model_class_names = []
                
                # Use model's class names if available, otherwise use defaults
                if model_class_names:
                    self.class_names = model_class_names
                    logger.debug(f"Using model class names for whiffle mode: {self.class_names}")
                else:
                    # Expected class names for whiffle: red, white, half-red (or variations)
                    self.class_names = ["red", "white", "half-red"]
            else:
                # Expected class names for whiffle: red, white, half-red (or variations)
                self.class_names = ["red", "white", "half-red"]
        else:
            # For fivestar mode, use silver and gold
            if hasattr(self.model, 'names') and self.model.names:
                if isinstance(self.model.names, dict):
                    max_index = max(self.model.names.keys()) if self.model.names else -1
                    model_class_names = [self.model.names.get(i, f"class_{i}") for i in range(max_index + 1)]
                elif isinstance(self.model.names, list):
                    model_class_names = self.model.names
                else:
                    model_class_names = ["silver", "gold"]
                self.class_names = model_class_names if model_class_names else ["silver", "gold"]
            else:
                self.class_names = ["silver", "gold"]
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
        results = self.model(inference_frame, conf=0.5, iou=0.5)

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

                # Append to respective lists based on ball type
                # For whiffle mode: red and white -> silver_balls, half-red -> gold_balls
                # For fivestar mode: silver -> silver_balls, gold -> gold_balls
                ball_type_lower = ball_type.lower()
                if is_whiffle:
                    # Whiffle mode: map red, white, half-red to return lists
                    if ball_type_lower in ["red", "white"]:
                        silver_balls.append((int(x_center), int(y_center), radius))
                    elif ball_type_lower in ["half-red", "half_red", "half", "halfred"]:
                        gold_balls.append((int(x_center), int(y_center), radius))
                    else:
                        # Default: put unknown types in silver_balls
                        logger.debug(f"Unknown whiffle ball type '{ball_type}', adding to silver_balls")
                        silver_balls.append((int(x_center), int(y_center), radius))
                else:
                    # Fivestar mode: map silver and gold
                    if ball_type_lower == "silver":
                        silver_balls.append((int(x_center), int(y_center), radius))
                    elif ball_type_lower == "gold":
                        gold_balls.append((int(x_center), int(y_center), radius))
                    else:
                        # Default: put unknown types in silver_balls
                        logger.debug(f"Unknown fivestar ball type '{ball_type}', adding to silver_balls")
                        silver_balls.append((int(x_center), int(y_center), radius))

        # Debug frame drawing
        if debug_mode:
            debug_frame = frame.copy()
            if is_whiffle:
                # Whiffle mode: red/white balls in silver_balls (use red/white colors)
                for x, y, radius in silver_balls:
                    cv2.circle(debug_frame, (x, y), int(radius), (0, 0, 255), 2)  # Red color for red/white balls
                # Half-red balls in gold_balls (use orange/red-orange color)
                for x, y, radius in gold_balls:
                    cv2.circle(debug_frame, (x, y), int(radius), (0, 100, 255), 2)  # Orange-red color for half-red
            else:
                # Fivestar mode: silver and gold
                for x, y, radius in silver_balls:
                    cv2.circle(debug_frame, (x, y), int(radius), (192, 192, 192), 2)  # Silver color
                for x, y, radius in gold_balls:
                    cv2.circle(debug_frame, (x, y), int(radius), (0, 215, 255), 2)  # Gold color
            cv2.imshow("Ball Detection", debug_frame)

        return silver_balls, gold_balls
