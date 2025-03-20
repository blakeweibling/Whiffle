# ball_tracker.py
import cv2
import numpy as np
from game_settings import GameSettings
import torch
from models import BallClassifier

class BallTracker:
    """Tracks and detects balls in the game using a CNN model."""
    def __init__(self):
        self.settings = GameSettings()
        self.balls = []  # [x, y, vx, vy, type, missed_frames, ball_id]
        self.tracked_balls = set()
        self.ball_id_counter = 0
        self.debug = True  # Enable debug output by default
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

    def detect_balls(self, frame, current_width, current_height):
        """Detect balls in the frame using the CNN model."""
        if self.model is None:
            if not hasattr(self, "model_warning_printed"):
                print("No CNN model loaded. Detection disabled.")
                self.model_warning_printed = True
            return self.balls

        if self.debug:
            print(f"Frame resolution: {current_width}x{current_height}")

        scale = min(current_width / self.settings.base_frame_width, current_height / self.settings.base_frame_height)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        edges = cv2.Canny(blurred, 50, 150)  # Tightened thresholds
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if self.debug:
            print(f"Found {len(contours)} contours")

        detected_balls = []
        patch_size = 20
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if self.debug:
                print(f"Contour area: {area}")
            if 100 < area < 2000:  # Tightened area range
                perimeter = cv2.arcLength(cnt, True)
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    if self.debug:
                        print(f"Circularity: {circularity}")
                    if 0.7 < circularity < 1.2:  # Tightened circularity range
                        (x, y), radius = cv2.minEnclosingCircle(cnt)
                        scaled_radius = self.settings.scale_value(self.settings.ball_radius, current_width, current_height)
                        if self.debug:
                            print(f"Radius: {radius}, Scaled radius: {scaled_radius}")
                        if scaled_radius - 15 <= radius <= scaled_radius + 15:  # Tightened tolerance
                            x_int, y_int = int(x), int(y)
                            x_start = max(0, x_int - patch_size // 2)
                            x_end = min(frame.shape[1], x_int + patch_size // 2)
                            y_start = max(0, y_int - patch_size // 2)
                            y_end = min(frame.shape[0], y_int + patch_size // 2)
                            patch = frame[y_start:y_end, x_start:x_end]
                            if patch.shape[0] > 0 and patch.shape[1] > 0:
                                patch = cv2.resize(patch, (20, 20))
                                patch_tensor = torch.tensor(patch.transpose(2, 0, 1), dtype=torch.float32) / 255.0
                                patch_tensor = patch_tensor.unsqueeze(0).to(self.device)
                                with torch.no_grad():
                                    output = self.model(patch_tensor)
                                    probabilities = torch.softmax(output, dim=1)
                                    confidence, predicted = torch.max(probabilities, 1)
                                    label_idx = predicted.item()
                                    ball_type = self.label_map[label_idx]
                                    if self.debug:
                                        print(f"Predicted label: {label_idx} ({ball_type}) at position ({x_int}, {y_int}) with confidence {confidence.item():.2f}")
                                    if ball_type != "background" and confidence.item() > 0.9:  # Added confidence threshold
                                        ball_id = (x_int, y_int)
                                        if len(self.tracked_balls) > 100:
                                            self.tracked_balls.clear()
                                            if self.debug:
                                                print("Cleared tracked_balls due to size limit")
                                        if ball_id not in self.tracked_balls:
                                            self.tracked_balls.add(ball_id)
                                            self.ball_id_counter += 1
                                            detected_balls.append([int(x / scale), int(y / scale), 0, 0, ball_type, 0, self.ball_id_counter])
                                            if self.debug:
                                                print(f"Detected ball at ({int(x / scale)}, {int(y / scale)}) with ball_id {self.ball_id_counter} and type {ball_type}")

        if self.debug:
            print(f"Detected {len(detected_balls)} balls in this frame")

        # Update existing balls
        new_balls = []
        for new_ball in detected_balls:
            x_new, y_new, _, _, ball_type, _, new_ball_id = new_ball
            matched = False
            for old_ball in self.balls:
                x_old, y_old, vx, vy, old_type, missed_frames, ball_id = old_ball
                distance = np.sqrt((x_new - x_old)**2 + (y_new - y_old)**2)
                if distance < 30 / scale and ball_type == old_type:
                    old_ball[0], old_ball[1] = x_new, y_new
                    old_ball[2] = (x_new - x_old) / 0.033
                    old_ball[3] = (y_new - y_old) / 0.033
                    old_ball[5] = 0
                    matched = True
                    break
            if not matched:
                new_balls.append(new_ball)

        self.balls.extend(new_balls)
        if new_balls and self.debug:
            print(f"Added new balls: {new_balls}")

        current_positions = {(b[0], b[1]) for b in detected_balls}
        for ball in self.balls[:]:
            if (ball[0], ball[1]) not in current_positions:
                ball[5] += 1
            if ball[5] >= 1:  # Reduced threshold to remove balls immediately if not detected
                self.balls.remove(ball)
                if self.debug:
                    print(f"Removed ball {ball[6]} due to missed frames")
            # Remove balls that are outside the frame
            scaled_x = ball[0] * scale
            scaled_y = ball[1] * scale
            if scaled_x < 0 or scaled_x > current_width or scaled_y < 0 or scaled_y > current_height:
                self.balls.remove(ball)
                if self.debug:
                    print(f"Removed ball {ball[6]} at ({scaled_x}, {scaled_y}) - outside frame")

        if self.debug:
            print(f"After update: self.balls = {self.balls}")
        return self.balls

    def draw_balls(self, frame, current_width, current_height):
        """Draw detected balls on the frame, with special handling for 'half' balls."""
        scale = min(current_width / self.settings.base_frame_width, current_height / self.settings.base_frame_height)
        scaled_radius = self.settings.scale_value(self.settings.ball_radius, current_width, current_height)
        for ball in self.balls:
            x, y, _, _, ball_type, _, _ = ball
            scaled_x = int(x * scale)
            scaled_y = int(y * scale)
            center = (scaled_x, scaled_y)
            # Only draw if the ball is within the frame
            if 0 <= scaled_x <= current_width and 0 <= scaled_y <= current_height:
                if ball_type == "half":
                    # Draw left half (red)
                    cv2.ellipse(frame, center, (int(scaled_radius), int(scaled_radius)), 0, 90, 270, (0, 0, 255), -1)
                    # Draw right half (white)
                    cv2.ellipse(frame, center, (int(scaled_radius), int(scaled_radius)), 0, -90, 90, (255, 255, 255), -1)
                    cv2.circle(frame, center, int(scaled_radius), (0, 0, 0), 1)  # Outline
                else:
                    color = self.settings.balls.get(ball_type, {"color": (0, 255, 0)})["color"]
                    if color:
                        cv2.circle(frame, center, int(scaled_radius), color, -1)
                        if self.debug:
                            print(f"Drawing ball {ball[6]} (type: {ball_type}) at ({scaled_x}, {scaled_y})")
            else:
                if self.debug:
                    print(f"Skipping drawing ball {ball[6]} at ({scaled_x}, {scaled_y}) - outside frame")
        return frame

    def update_physics(self, current_width, current_height):
        """Update the physics of tracked balls (position, velocity, gravity, friction)."""
        scale = min(current_width / self.settings.base_frame_width, current_height / self.settings.base_frame_height)
        velocity_threshold = 0.1  # Threshold to consider a ball stationary (pixels per frame)
        for ball in self.balls:
            x, y, vx, vy, ball_type, missed_frames, ball_id = ball

            # Skip physics update for stationary balls (optional optimization)
            if self.debug and abs(vx) < velocity_threshold and abs(vy) < velocity_threshold:
                if self.debug:
                    print(f"Skipping physics update for ball {ball_id} - stationary (vx={vx:.2f}, vy={vy:.2f})")
                continue

            scaled_gravity = self.settings.gravity * self.settings.scale_value(1, current_width, current_height)
            vy += scaled_gravity * self.settings.time_step * 10
            x += vx * self.settings.time_step
            y += vy * self.settings.time_step
            vx *= self.settings.friction
            vy *= self.settings.friction

            scaled_radius = self.settings.scale_value(self.settings.ball_radius, current_width, current_height)
            scaled_width = current_width / scale
            scaled_height = current_height / scale

            if x < scaled_radius:
                x = scaled_radius
                vx = -vx * 0.7
            elif x > scaled_width - scaled_radius:
                x = scaled_width - scaled_radius
                vx = -vx * 0.7
            if y < scaled_radius:
                y = scaled_radius
                vy = -vy * 0.7
            elif y > scaled_height - scaled_radius:
                y = scaled_height - scaled_radius
                vy = -vy * 0.7

            ball[:] = [x, y, vx, vy, ball_type, missed_frames, ball_id]