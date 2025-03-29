"""
Ball detection and tracking using YOLOv8 for the Whiffle Tracker project.
"""

import cv2
import numpy as np
from typing import List, Tuple, Dict, Optional, Any
import logging
from ultralytics import YOLO

from constants import DetectionConstants, GameSpecificConstants

# Set up logging
logger = logging.getLogger(__name__)

# Use GameSpecificConstants for excluded positions
EXCLUDED_POSITIONS: List[Tuple[int, int]] = GameSpecificConstants.EXCLUDED_POSITIONS

class BallDetector:
    def __init__(self):
        # Load the trained YOLOv8 model
        self.model = YOLO('best.pt')  # Update with your model path
        self.class_names = ['white', 'red', 'half']
        self.state_names = ['on_playfield', 'in_hole']

    def _is_position_excluded(self, x: int, y: int, excluded_positions: List[Tuple[int, int]]) -> bool:
        """
        Check if a position is within the exclusion distance of any excluded position.
        """
        for ex, ey in excluded_positions:
            dist = np.sqrt((x - ex) ** 2 + (y - ey) ** 2)
            if dist < DetectionConstants.EXCLUSION_DISTANCE:
                logger.debug(f"Position ({x}, {y}) excluded: distance {dist} to excluded position ({ex}, {ey})")
                return True
        return False

    def _is_in_scoring_zone(self, x: float, y: float, radius: float, scoring_zones: List[Tuple[int, int, int, int, int]]) -> bool:
        """
        Check if a ball is within a scoring zone (hole).

        Args:
            x: X-coordinate of the ball's center.
            y: Y-coordinate of the ball's center.
            radius: Radius of the ball.
            scoring_zones: List of scoring zones, each as (x, y, width, height, points).

        Returns:
            True if the ball is in a scoring zone, False otherwise.
        """
        for zone in scoring_zones:
            zone_x, zone_y, zone_width, zone_height, _ = zone
            zone_x_min = zone_x - (zone_width / 2)
            zone_x_max = zone_x + (zone_width / 2)
            zone_y_min = zone_y - (zone_height / 2)
            zone_y_max = zone_y + (zone_height / 2)

            # Check if the ball's center is within the scoring zone
            if (zone_x_min <= x <= zone_x_max and
                zone_y_min <= y <= zone_y_max):
                return True
        return False

    def detect_all_balls(
        self,
        frame: np.ndarray,
        frame_count: int,
        game_state: Any,
        scoring_zones: List[Tuple[int, int, int, int, int]],
        hsv_frame: Optional[np.ndarray] = None,
        debug_mode: bool = False
    ) -> Tuple[List[Tuple[int, int, float]], List[Tuple[int, int, float]], List[Tuple[int, int, float]]]:
        """
        Detect white, red, and half red/half white balls in the frame using YOLOv8 and infer their state.

        Args:
            frame: Input frame in BGR format.
            frame_count: Current frame number.
            game_state: GameState object containing state information.
            scoring_zones: List of scoring zones, each as (x, y, width, height, points).
            hsv_frame: Precomputed HSV frame (not used in this implementation).
            debug_mode: Whether to enable debug logging and windows.

        Returns:
            Tuple of (white_balls, red_balls, half_balls), where each is a list of (x, y, radius).
        """
        # Detect balls using YOLOv8
        results = self.model(frame, conf=0.5, iou=0.5)  # Adjust confidence and IoU thresholds as needed

        # Separate balls by type
        white_balls = []
        red_balls = []
        half_balls = []

        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy()  # Bounding boxes
            scores = result.boxes.conf.cpu().numpy()  # Confidence scores
            classes = result.boxes.cls.cpu().numpy()  # Class IDs

            for box, score, cls in zip(boxes, scores, classes):
                x_min, y_min, x_max, y_max = box
                x_center = (x_min + x_max) / 2
                y_center = (y_min + y_max) / 2
                width = x_max - x_min
                height = y_max - y_min
                radius = max(width, height) / 2

                # Filter out excluded positions
                if self._is_position_excluded(x_center, y_center, EXCLUDED_POSITIONS):
                    if debug_mode:
                        logger.debug(f"Ball at ({x_center}, {y_center}) excluded due to position")
                    continue

                ball_type = self.class_names[int(cls)]
                if debug_mode:
                    logger.debug(f"Detected {ball_type} ball at ({x_center}, {y_center}) with radius={radius}, confidence={score}")

                if ball_type == 'white':
                    white_balls.append((int(x_center), int(y_center), radius))
                elif ball_type == 'red':
                    red_balls.append((int(x_center), int(y_center), radius))
                elif ball_type == 'half':
                    half_balls.append((int(x_center), int(y_center), radius))

        if debug_mode:
            debug_frame = frame.copy()
            for x, y, radius in white_balls:
                cv2.circle(debug_frame, (x, y), int(radius), (255, 255, 255), 2)
            for x, y, radius in red_balls:
                cv2.circle(debug_frame, (x, y), int(radius), (0, 0, 255), 2)
            for x, y, radius in half_balls:
                cv2.circle(debug_frame, (x, y), int(radius), (255, 0, 255), 2)
            cv2.imshow("Ball Detection", debug_frame)

        return white_balls, red_balls, half_balls