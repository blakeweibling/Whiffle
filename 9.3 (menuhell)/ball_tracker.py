import cv2
import numpy as np
from collections import defaultdict, deque
import time
import os
from game_utils import resource_path

# Try to import PyTorch
try:
    import torch
    import torch.nn as nn
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    print("PyTorch not installed. Please install PyTorch to enable CNN ball detection (e.g., pip install torch).")

class BallClassifier(nn.Module):
    """CNN architecture for classifying ball patches (red, white, half, background)."""
    def __init__(self):
        super(BallClassifier, self).__init__()
        self.conv1 = nn.Conv2d(3, 16, kernel_size=3, padding=1)  # Input: 40x40x3, Output: 40x40x16
        self.pool = nn.MaxPool2d(2, 2)  # Reduces size by half
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)  # Output: 40x40x32
        # After three pooling layers: 40x40 -> 20x20 -> 10x10 -> 5x5
        # After conv2 and pooling: 5x5x32
        self.fc1 = nn.Linear(32 * 5 * 5, 64)  # Flatten to 32*5*5=800, output 64
        self.fc2 = nn.Linear(64, 4)  # Output: 4 classes (red, white, half, background)

    def forward(self, x):
        x = torch.relu(self.conv1(x))
        x = self.pool(x)  # 40x40 -> 20x20
        x = torch.relu(self.conv2(x))
        x = self.pool(x)  # 20x20 -> 10x10
        x = self.pool(x)  # 10x10 -> 5x5
        x = x.view(x.size(0), -1)
        x = torch.relu(self.fc1(x))
        x = self.fc2(x)
        return x

class BallTracker:
    """Tracks balls in a video feed using a CNN classifier and OpenCV detection."""
    def __init__(self, max_balls=10):
        self.model = None
        self.config = None
        self.balls = {}  # ball_id -> (x, y, radius, velocity_x, velocity_y, type, last_seen, confidence)
        self.next_id = 0
        self.max_balls = max_balls
        self.friction = 0.98  # Friction to slow down balls
        self.min_speed = 1.0  # Minimum speed threshold
        self.max_age = 30  # Frames before a ball is considered stale
        self.debug = False  # Debug mode for detailed logging
        self.ball_history = defaultdict(lambda: deque(maxlen=10))  # History for smoothing positions
        self.label_map = {0: "red", 1: "white", 2: "half", 3: "background"}

        if not PYTORCH_AVAILABLE:
            print("PyTorch is required for ball detection but is not installed. Ball detection will be disabled.")
            return

        # Use resource_path to locate the model file
        model_path = resource_path("ball_detector_cnn.pth")
        if not os.path.exists(model_path):
            print(f"Error: CNN model file not found at {model_path}. Please ensure the file exists and is accessible.")
            print("Ball detection will be disabled. Run train_ball_detector.py with labeled data to generate the model.")
        else:
            try:
                # Load the PyTorch model
                self.model = BallClassifier()
                self.model.load_state_dict(torch.load(model_path, map_location=torch.device('cpu')))
                self.model.eval()
                print("Loaded PyTorch CNN ball classifier model")
            except Exception as e:
                print(f"Error loading PyTorch model from {model_path}: {e}")
                print("Ball detection will be disabled. Run train_ball_detector.py with labeled data to generate a valid model.")
                self.model = None

    def set_config(self, config):
        """Set detection parameters from GameSettings."""
        self.config = config
        print(f"BallTracker config: area range=[{config.detection_area_min}, {config.detection_area_max}], "
              f"circularity range=[{config.detection_circularity_min}, {config.detection_circularity_max}], "
              f"confidence threshold={config.detection_confidence_threshold}")

    def detect_balls(self, frame):
        """Detect balls in the frame using OpenCV for detection and PyTorch CNN for classification."""
        if self.model is None or self.config is None:
            return []

        # Step 1: Preprocess the frame for contour detection
        if self.debug:
            print("Starting ball detection pipeline...")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.debug:
            print(f"Grayscale image min: {gray.min()}, max: {gray.max()}")
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        # Try multiple thresholding methods to improve detection
        _, thresh_binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        _, thresh_binary_inv = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        thresh_adaptive = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                              cv2.THRESH_BINARY_INV, 11, 2)

        # Combine thresholds to improve detection
        thresh = cv2.bitwise_or(thresh_binary, thresh_binary_inv)
        thresh = cv2.bitwise_or(thresh, thresh_adaptive)
        if self.debug:
            print(f"Threshold image min: {thresh.min()}, max: {thresh.max()}")

        # Step 2: Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if self.debug:
            print(f"Found {len(contours)} contours in the frame")

        detected_balls = []
        height, width = frame.shape[:2]

        for contour in contours:
            area = cv2.contourArea(contour)
            # Relaxed area constraints to allow smaller/larger balls
            relaxed_area_min = self.config.detection_area_min * 0.5
            relaxed_area_max = self.config.detection_area_max * 1.5
            if not (relaxed_area_min <= area <= relaxed_area_max):
                if self.debug:
                    print(f"Contour filtered out due to area {area} (relaxed min: {relaxed_area_min}, max: {relaxed_area_max})")
                continue

            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                if self.debug:
                    print("Contour filtered out due to zero perimeter")
                continue

            circularity = 4 * np.pi * area / (perimeter * perimeter)
            # Relaxed circularity constraints
            relaxed_circularity_min = self.config.detection_circularity_min * 0.5
            relaxed_circularity_max = self.config.detection_circularity_max * 1.5
            if not (relaxed_circularity_min <= circularity <= relaxed_circularity_max):
                if self.debug:
                    print(f"Contour filtered out due to circularity {circularity:.2f} "
                          f"(relaxed min: {relaxed_circularity_min}, max: {relaxed_circularity_max})")
                continue

            # Get bounding box of the contour
            (x, y), radius = cv2.minEnclosingCircle(contour)
            center_x = int(x)
            center_y = int(y)
            radius = int(radius)

            # Extract a 40x40 patch around the center
            patch_size = 40
            half_patch = patch_size // 2
            x_start = max(0, center_x - half_patch)
            y_start = max(0, center_y - half_patch)
            x_end = min(width, center_x + half_patch)
            y_end = min(height, center_y + half_patch)

            # Ensure the patch is 40x40 by padding if necessary
            patch = frame[y_start:y_end, x_start:x_end]
            if patch.shape[0] != patch_size or patch.shape[1] != patch_size:
                # Pad the patch to 40x40
                pad_top = max(0, half_patch - (center_y - y_start))
                pad_bottom = max(0, half_patch - (y_end - center_y))
                pad_left = max(0, half_patch - (center_x - x_start))
                pad_right = max(0, half_patch - (x_end - center_x))
                patch = cv2.copyMakeBorder(patch, pad_top, pad_bottom, pad_left, pad_right, 
                                         cv2.BORDER_CONSTANT, value=(0, 0, 0))

            # Preprocess the patch for PyTorch
            patch_rgb = cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)
            patch_tensor = torch.from_numpy(patch_rgb).permute(2, 0, 1).float() / 255.0
            patch_tensor = patch_tensor.unsqueeze(0)  # Add batch dimension

            # Perform inference with PyTorch
            with torch.no_grad():
                outputs = self.model(patch_tensor)
                probabilities = torch.softmax(outputs, dim=1)
                confidence, predicted = torch.max(probabilities, 1)
                label_idx = predicted.item()
                confidence = confidence.item()

            label = self.label_map[label_idx]
            if label == "background" or confidence < self.config.detection_confidence_threshold:
                if self.debug:
                    print(f"Patch at ({center_x}, {center_y}) classified as {label} with confidence {confidence:.2f}, skipping")
                continue

            detected_balls.append((center_x, center_y, radius, 0, 0, label, confidence))
            print(f"Detected {label} at ({center_x}, {center_y}) with confidence {confidence:.2f}")

        # Handle overlapping detections by choosing the highest confidence
        unique_balls = []
        detected_balls.sort(key=lambda x: x[6], reverse=True)  # Sort by confidence
        for ball in detected_balls:
            x, y, radius, _, _, label, confidence = ball
            overlap = False
            for ux, uy, uradius, _, _, ulabel, _ in unique_balls:
                distance = np.sqrt((x - ux)**2 + (y - uy)**2)
                if distance < (radius + uradius) * self.config.detection_radius_tolerance:
                    overlap = True
                    break
            if not overlap:
                unique_balls.append(ball)

        if len(unique_balls) > self.max_balls:
            unique_balls = unique_balls[:self.max_balls]
            if self.debug:
                print(f"Reached max balls limit ({self.max_balls}), keeping top {self.max_balls} detections")

        print(f"Detected {len(unique_balls)} balls (within limit of {self.max_balls})")
        return [(x, y, radius, 0, label, 0, f"ball_{self.next_id + i}", confidence) 
                for i, (x, y, radius, _, label, _, confidence) in enumerate(unique_balls)]

    def update_physics(self, width, height, delta_time):
        """Update ball positions based on physics (velocity, friction, boundaries)."""
        balls_to_remove = []
        for ball_id, (x, y, radius, vx, vy, ball_type, last_seen, confidence) in list(self.balls.items()):
            # Apply friction to slow down
            vx *= self.friction
            vy *= self.friction

            # Stop if speed is below threshold
            speed = np.sqrt(vx**2 + vy**2)
            if speed < self.min_speed:
                vx = vy = 0

            # Update position
            x += vx * delta_time
            y += vy * delta_time

            # Boundary collisions
            if x - radius < 0:
                x = radius
                vx = -vx
            if x + radius > width:
                x = width - radius
                vx = -vx
            if y - radius < 0:
                y = radius
                vy = -vy
            if y + radius > height:
                y = height - radius
                vy = -vy

            self.balls[ball_id] = (x, y, radius, vx, vy, ball_type, last_seen, confidence)

            # Remove stale balls
            if last_seen >= self.max_age:
                balls_to_remove.append(ball_id)
                if self.debug:
                    print(f"Removed stale ball ID {ball_id} after {self.max_age} frames unseen")

        for ball_id in balls_to_remove:
            del self.balls[ball_id]

    def update_balls(self, detected_balls):
        """Update existing balls with new detections and assign IDs."""
        new_balls = []
        for detection in detected_balls:
            x, y, radius, _, ball_type, _, suggested_id, confidence = detection
            matched = False

            # Try to match with existing balls
            min_distance = float('inf')
            closest_id = None
            for ball_id, (bx, by, bradius, vx, vy, btype, last_seen, bconfidence) in self.balls.items():
                distance = np.sqrt((x - bx)**2 + (y - by)**2)
                if distance < min_distance and distance < radius * self.config.detection_radius_tolerance:
                    min_distance = distance
                    closest_id = ball_id

            if closest_id is not None:
                # Update existing ball
                bx, by, bradius, vx, vy, btype, _, bconfidence = self.balls[closest_id]
                self.balls[closest_id] = (x, y, radius, vx, vy, btype, 0, confidence)
                if self.debug:
                    print(f"Updated {btype} ball ID {closest_id} at ({x}, {y}) with distance {min_distance:.1f}")
            else:
                # Add new ball
                ball_id = f"ball_{self.next_id}"
                self.next_id += 1
                new_balls.append((x, y, radius, 0, ball_type, 0, ball_id, confidence))
                print(f"Detected new {ball_type} ball at ({x}, {y}) with ID {ball_id}")

        # Add new balls
        for x, y, radius, vx, vy, ball_type, last_seen, confidence in new_balls:
            self.balls[ball_id] = (x, y, radius, vx, vy, ball_type, last_seen, confidence)

        # Update last seen for unmatched balls
        for ball_id in list(self.balls.keys()):
            if ball_id not in [f"ball_{i}" for i in range(self.next_id - len(new_balls), self.next_id)]:
                x, y, radius, vx, vy, ball_type, last_seen, confidence = self.balls[ball_id]
                self.balls[ball_id] = (x, y, radius, vx, vy, ball_type, last_seen + 1, confidence)

    def draw_balls(self, frame, width, height):
        """Draw tracked balls on the frame with their IDs and smoothed positions."""
        for ball_id, (x, y, radius, _, _, ball_type, _, _) in self.balls.items():
            # Smooth positions using history
            self.ball_history[ball_id].append((x, y))
            smoothed_positions = list(self.ball_history[ball_id])
            if len(smoothed_positions) > 1:
                x = int(sum(pos[0] for pos in smoothed_positions) / len(smoothed_positions))
                y = int(sum(pos[1] for pos in smoothed_positions) / len(smoothed_positions))

            # Ensure ball stays within frame
            x = max(radius, min(width - radius, x))
            y = max(radius, min(height - radius, y))

            color = (255, 255, 255) if ball_type == "white" else (0, 0, 255) if ball_type == "red" else (0, 255, 255)
            cv2.circle(frame, (x, y), radius, color, 2)
            cv2.putText(frame, ball_id, (x + radius + 5, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        return frame