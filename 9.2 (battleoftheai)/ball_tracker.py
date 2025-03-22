import cv2
import numpy as np
import torch
from models import BallClassifier
from game_settings import GameSettings

class BallTracker:
    """Tracks and detects balls in the game using a CNN model."""
    
    def __init__(self):
        self.settings = GameSettings()
        self.balls = []
        self.tracked_balls = set()
        self.debug = True
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.label_map = {0: "red", 1: "white", 2: "half", 3: "background"}
        self.load_model()

    def load_model(self):
        """Load the CNN model for ball detection."""
        try:
            self.model = BallClassifier().to(self.device)
            self.model.load_state_dict(torch.load("ball_detector_cnn.pth", map_location=self.device))
            self.model.eval()
            print("Loaded CNN ball detector model")
        except FileNotFoundError:
            self.model = None
            print("No CNN model found at 'ball_detector_cnn.pth'. Run train_ball_detector.py with labeled data to create the model.")
        except Exception as e:
            self.model = None
            print(f"Error loading CNN model: {e}. Detection will be disabled.")

    def detect_balls(self, frame):
        """Detect balls in the frame using the CNN model."""
        if self.model is None:
            if not hasattr(self, "model_warning_printed"):
                print("No CNN model loaded. Detection disabled.")
                self.model_warning_printed = True
            return self.balls

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if self.debug:
            print(f"Found {len(contours)} contours")

        detected_balls = []
        patches = []
        locations = []
        patch_size = 20
        ball_id_counter = len(self.tracked_balls)  # Simple counter for unique IDs

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if self.settings.detection_area_min < area < self.settings.detection_area_max:
                perimeter = cv2.arcLength(cnt, True)
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    if self.settings.detection_circularity_min < circularity < self.settings.detection_circularity_max:
                        (x, y), radius = cv2.minEnclosingCircle(cnt)
                        x_int, y_int = int(x), int(y)
                        x_start = max(0, x_int - patch_size // 2)
                        x_end = min(frame.shape[1], x_int + patch_size // 2)
                        y_start = max(0, y_int - patch_size // 2)
                        y_end = min(frame.shape[0], y_int + patch_size // 2)
                        patch = frame[y_start:y_end, x_start:x_end]
                        
                        if patch.shape[0] > 0 and patch.shape[1] > 0:
                            patch = cv2.resize(patch, (20, 20))
                            patches.append(patch)
                            locations.append((x_int, y_int, radius))

        if patches:
            patches_array = np.array(patches).transpose(0, 3, 1, 2)  # Ensure correct shape (batch, channels, height, width)
            patches_tensor = torch.tensor(patches_array, dtype=torch.float32) / 255.0
            patches_tensor = patches_tensor.to(self.device)

            # Ensure tensor is contiguous before reshaping
            patches_tensor = patches_tensor.contiguous()

            with torch.no_grad():
                outputs = self.model(patches_tensor)
                probabilities = torch.softmax(outputs, dim=1)
                confidences, predicted = torch.max(probabilities, 1)

                for i in range(len(locations)):
                    if i >= len(predicted) or i >= len(confidences):
                        print(f"Skipping out-of-range index: i={i}, predicted_len={len(predicted)}, confidences_len={len(confidences)}")
                        continue

                    label_idx = predicted[i].item()
                    confidence = confidences[i].item()
                    ball_type = self.label_map.get(label_idx, "unknown")

                    if ball_type != "background" and confidence > self.settings.detection_confidence_threshold:
                        x_int, y_int, radius = locations[i]
                        ball_id = f"ball_{ball_id_counter}"  # Generate a unique ID
                        ball_id_counter += 1
                        # Return 7-element tuple: [x, y, radius, confidence, ball_type, None, ball_id]
                        detected_balls.append([x_int, y_int, radius, confidence, ball_type, None, ball_id])
                        self.tracked_balls.add(ball_id)  # Track the ball ID
                        if self.debug:
                            print(f"Detected {ball_type} ball at ({x_int}, {y_int}) with confidence {confidence:.2f}, ID: {ball_id}")

        self.balls = detected_balls  # Update the tracked balls
        return self.balls

    def update_physics(self, width, height, delta_time):
        """Update ball physics (placeholder for future implementation)."""
        # Currently a placeholder; implement physics if needed
        pass

    def draw_balls(self, frame, width, height):
        """Draw detected balls on the frame."""
        for ball in self.balls:
            x, y, radius, confidence, ball_type, _, ball_id = ball
            color = {
                "red": (0, 0, 255),
                "white": (255, 255, 255),
                "half": (0, 255, 255)
            }.get(ball_type, (0, 255, 0))  # Default to green if unknown
            cv2.circle(frame, (x, y), int(radius), color, 2)
            if self.debug:
                label = f"{ball_type} ({confidence:.2f}) ID: {ball_id}"
                cv2.putText(frame, label, (x + 10, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        return frame