import cv2
import numpy as np
import torch
from models import BallClassifier
from game_settings import GameSettings

class BallTracker:
    """Tracks and detects balls in the game using a CNN model with persistent tracking."""
    
    def __init__(self):
        self.settings = GameSettings()
        self.balls = []  # List of tracked balls: [x, y, radius, confidence, ball_type, None, ball_id, frames_unseen]
        self.tracked_balls = set()  # Set of all ball_ids ever assigned
        self.debug = True
        self.debug_contours = False
        self.debug_cnn = False
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.label_map = {0: "red", 1: "white", 2: "half", 3: "background"}
        self.ball_id_counter = 0
        self.load_model()
        if self.debug:
            print(f"BallTracker config: area range=[{self.settings.detection_area_min}, {self.settings.detection_area_max}], "
                  f"circularity range=[{self.settings.detection_circularity_min}, {self.settings.detection_circularity_max}], "
                  f"confidence threshold={self.settings.detection_confidence_threshold}")

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
        """Detect and track balls in the frame using the CNN model with persistence."""
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
        filtered_count = 0
        filtered_by_area = 0
        filtered_by_circularity = 0
        filtered_by_patch = 0

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if self.settings.detection_area_min < area < self.settings.detection_area_max:
                perimeter = cv2.arcLength(cnt, True)
                if perimeter > 0:
                    (x, y), radius = cv2.minEnclosingCircle(cnt)
                    x_int, y_int = int(x), int(y)
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    if self.settings.detection_circularity_min < circularity < self.settings.detection_circularity_max:
                        x_start = max(0, x_int - patch_size // 2)
                        x_end = min(frame.shape[1], x_int + patch_size // 2)
                        y_start = max(0, y_int - patch_size // 2)
                        y_end = min(frame.shape[0], y_int + patch_size // 2)
                        patch = frame[y_start:y_end, x_start:x_end]
                        
                        if patch.shape[0] > 0 and patch.shape[1] > 0:
                            patch = cv2.resize(patch, (20, 20))
                            patches.append(patch)
                            locations.append((x_int, y_int, radius))
                        else:
                            filtered_by_patch += 1
                            if self.debug:
                                print(f"Filtered contour at ({x_int}, {y_int}) due to invalid patch size: {patch.shape}")
                    else:
                        filtered_by_circularity += 1
                        if self.debug:
                            print(f"Filtered contour at ({x_int}, {y_int}) due to circularity {circularity:.2f} outside range [{self.settings.detection_circularity_min}, {self.settings.detection_circularity_max}]")
                else:
                    filtered_by_area += 1
                    if self.debug:
                        print(f"Filtered contour at ({x_int}, {y_int}) due to area {area:.1f} outside range [{self.settings.detection_area_min}, {self.settings.detection_area_max}]")
            else:
                filtered_by_area += 1
                if self.debug:
                    (x, y), radius = cv2.minEnclosingCircle(cnt)
                    x_int, y_int = int(x), int(y)
                    print(f"Filtered contour at ({x_int}, {y_int}) due to area {area:.1f} outside range [{self.settings.detection_area_min}, {self.settings.detection_area_max}]")

        filtered_count = filtered_by_area + filtered_by_circularity + filtered_by_patch
        if self.debug:
            print(f"Filtered {filtered_count} contours (area: {filtered_by_area}, circularity: {filtered_by_circularity}, patch: {filtered_by_patch}), {len(patches)} passed for CNN classification")

        if patches:
            patches_array = np.array(patches).transpose(0, 3, 1, 2)
            patches_tensor = torch.tensor(patches_array, dtype=torch.float32) / 255.0
            patches_tensor = patches_tensor.to(self.device).contiguous()

            with torch.no_grad():
                outputs = self.model(patches_tensor)
                probabilities = torch.softmax(outputs, dim=1)
                confidences, predicted = torch.max(probabilities, 1)

                filtered_by_cnn = 0
                position_groups = {}
                for i in range(len(locations)):
                    if i >= len(predicted) or i >= len(confidences):
                        print(f"Skipping out-of-range index: i={i}, predicted_len={len(predicted)}, confidences_len={len(confidences)}")
                        continue

                    label_idx = predicted[i].item()
                    confidence = confidences[i].item()
                    ball_type = self.label_map.get(label_idx, "unknown")
                    x, y, radius = locations[i]

                    pos_key = (round(x / 5) * 5, round(y / 5) * 5)
                    if pos_key not in position_groups:
                        position_groups[pos_key] = []
                    position_groups[pos_key].append((x, y, radius, confidence, ball_type))

                for pos_key, group in position_groups.items():
                    best_detection = max(group, key=lambda d: d[3])
                    x, y, radius, confidence, ball_type = best_detection
                    if ball_type != "background" and confidence > self.settings.detection_confidence_threshold:
                        # Check if this position is already tracked
                        matched = False
                        for ball in self.balls:
                            tx, ty, _, _, _, _, _, frames_unseen = ball
                            distance = np.sqrt((x - tx)**2 + (y - ty)**2)
                            if distance <= 10.0:  # Increased threshold to catch duplicates
                                matched = True
                                break
                        if not matched:
                            detected_balls.append([x, y, radius, confidence, ball_type, None, None, 0])
                            if self.debug:
                                print(f"Detected {ball_type} at ({x}, {y}) with confidence {confidence:.2f} (chosen from {len(group)} overlapping detections)")
                    else:
                        filtered_by_cnn += len(group)
                        if self.debug:
                            print(f"Filtered contour at ({x}, {y}) by CNN: type={ball_type}, confidence={confidence:.2f} (threshold={self.settings.detection_confidence_threshold})")

                if self.debug:
                    print(f"Filtered {filtered_by_cnn} contours by CNN, {len(detected_balls)} balls detected")

        new_balls = []
        matched_ids = set()
        match_threshold = 50
        exact_match_threshold = 10.0  # Increased to catch duplicates

        for detected in detected_balls:
            x, y, radius, confidence, ball_type, _, _, _ = detected
            matched = False
            exact_match = False

            for i, tracked in enumerate(self.balls):
                tx, ty, tradius, tconfidence, ttype, _, tid, frames_unseen = tracked
                distance = np.sqrt((x - tx)**2 + (y - ty)**2)
                if distance <= exact_match_threshold:
                    self.balls[i] = [x, y, radius, confidence, ball_type, None, tid, 0]
                    matched_ids.add(tid)
                    exact_match = True
                    if self.debug and ttype != ball_type:
                        print(f"Exact match for {ball_type} ball ID {tid} at ({x}, {y}) with distance {distance:.1f}, updated type from {ttype} to {ball_type}")
                    break

            if exact_match:
                continue

            for i, tracked in enumerate(self.balls):
                tx, ty, tradius, tconfidence, ttype, _, tid, frames_unseen = tracked
                distance = np.sqrt((x - tx)**2 + (y - ty)**2)
                if distance < match_threshold and ball_type == ttype and tid not in matched_ids:
                    self.balls[i] = [x, y, radius, confidence, ball_type, None, tid, 0]
                    matched_ids.add(tid)
                    matched = True
                    if self.debug:
                        print(f"Updated {ball_type} ball ID {tid} at ({x}, {y}) with distance {distance:.1f}")
                    break

            if not matched:
                ball_id = f"ball_{self.ball_id_counter}"
                self.ball_id_counter += 1
                new_balls.append([x, y, radius, confidence, ball_type, None, ball_id, 0])
                self.tracked_balls.add(ball_id)
                if self.debug:
                    print(f"Detected new {ball_type} ball at ({x}, {y}) with ID {ball_id}")

        max_frames_unseen = 1000  # Increased to prevent removal of static balls
        updated_balls = []
        for ball in self.balls:
            if ball[6] not in matched_ids:
                ball[7] += 1
            if ball[7] <= max_frames_unseen:
                updated_balls.append(ball)
            elif self.debug:
                print(f"Removed stale ball ID {ball[6]} after {ball[7]} frames unseen")

        self.balls = updated_balls + new_balls
        return self.balls

    def update_physics(self, width, height, delta_time):
        """Update ball physics (placeholder for future implementation)."""
        pass

    def draw_balls(self, frame, width, height):
        """Draw detected balls on the frame."""
        for ball in self.balls:
            x, y, radius, confidence, ball_type, _, ball_id, _ = ball
            color = {
                "red": (0, 0, 255),
                "white": (255, 255, 255),
                "half": (0, 255, 255)
            }.get(ball_type, (0, 255, 0))
            cv2.circle(frame, (x, y), int(radius), color, 2)
            if self.debug:
                label = f"{ball_type} ({confidence:.2f}) ID: {ball_id}"
                cv2.putText(frame, label, (x + 10, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        return frame