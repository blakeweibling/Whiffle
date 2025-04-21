import cv2
import numpy as np
from game_settings import GameSettings

class BallTracker:
    def __init__(self):
        self.settings = GameSettings()
        self.balls = []  # List of [x, y, vx, vy, type, missed_frames, ball_id]
        self.tracked_balls = set()
        self.ball_id_counter = 0

    def detect_balls(self, frame, current_width, current_height):
        scale = min(current_width / self.settings.base_frame_width, current_height / self.settings.base_frame_height)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        white_lower = np.array([0, 0, 200])  # Adjusted for better white detection
        white_upper = np.array([180, 30, 255])
        red_lower1 = np.array([0, 100, 50])   # Adjusted for better red detection
        red_upper1 = np.array([10, 255, 255])
        red_lower2 = np.array([160, 100, 50]) # Adjusted for better red detection
        red_upper2 = np.array([180, 255, 255])

        white_mask = cv2.inRange(hsv, white_lower, white_upper)
        red_mask1 = cv2.inRange(hsv, red_lower1, red_upper1)
        red_mask2 = cv2.inRange(hsv, red_lower2, red_upper2)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)
        half_mask = cv2.bitwise_and(white_mask, red_mask)  # Enhanced half detection

        # Enhanced half_mask processing
        half_mask = cv2.GaussianBlur(half_mask, (13, 13), 0)  # Larger blur
        half_mask = cv2.dilate(half_mask, None, iterations=5)  # Increased dilation
        half_mask = cv2.erode(half_mask, None, iterations=2)   # Refined erosion

        for mask in [white_mask, red_mask, half_mask]:
            mask = cv2.GaussianBlur(mask, (7, 7), 0)  # Increased blur for noise reduction
            mask = cv2.erode(mask, None, iterations=1)
            mask = cv2.dilate(mask, None, iterations=2)

        detected_balls = []
        for mask, ball_type in [(white_mask, "white"), (red_mask, "red"), (half_mask, "half")]:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for i, cnt in enumerate(contours):
                area = cv2.contourArea(cnt)
                print(f"Contour {i} area: {area} (type: {ball_type})")
                if 150 < area < 15000:  # Further widened range
                    perimeter = cv2.arcLength(cnt, True)
                    if perimeter > 0:
                        circularity = 4 * np.pi * area / (perimeter * perimeter)
                        print(f"Contour {i} circularity: {circularity}")
                        if 0.3 < circularity < 1.7:  # Even looser circularity check
                            (x, y), radius = cv2.minEnclosingCircle(cnt)
                            scaled_radius = self.settings.scale_value(self.settings.ball_radius, current_width, current_height)
                            print(f"Contour {i} at ({int(x)}, {int(y)}), Radius: {radius}, Scaled Ball radius: {scaled_radius}")
                            if scaled_radius - 30 <= radius <= scaled_radius + 30:  # Widened radius tolerance
                                ball_id = (int(x), int(y))
                                if len(self.tracked_balls) > 100:
                                    self.tracked_balls.clear()
                                    print("Cleared tracked_balls due to size limit")
                                if ball_id not in self.tracked_balls:
                                    self.tracked_balls.add(ball_id)
                                    self.ball_id_counter += 1
                                    detected_balls.append([int(x / scale), int(y / scale), 0, 0, ball_type, 0, self.ball_id_counter])
                                    print(f"Detected ball at ({int(x / scale)}, {int(y / scale)}) with ball_id {self.ball_id_counter} and type {ball_type}")

        print(f"Before update: self.balls = {self.balls}")
        new_balls = []
        for new_ball in detected_balls:
            x_new, y_new, _, _, _, _, new_ball_id = new_ball
            matched = False
            for old_ball in self.balls:
                x_old, y_old, vx, vy, ball_type, missed_frames, ball_id = old_ball
                distance = np.sqrt((x_new - x_old)**2 + (y_new - y_old)**2)
                if distance < 50 / scale:  # Reduced matching distance to prevent duplicates
                    old_ball[0] = x_new
                    old_ball[1] = y_new
                    old_ball[2] = (x_new - x_old) / 0.033
                    old_ball[3] = (y_new - y_old) / 0.033
                    old_ball[5] = 0
                    matched = True
                    break
            if not matched:
                new_balls.append(new_ball)

        self.balls.extend(new_balls)
        if new_balls:
            print(f"Added new balls: {new_balls}")

        current_positions = {(b[0], b[1]) for b in detected_balls}
        for ball in self.balls:
            if (ball[0], ball[1]) not in current_positions:
                ball[5] += 1

        self.balls = [b for b in self.balls if b[5] < 15]  # Increased missed frames threshold
        print(f"After update: self.balls = {self.balls}")

        return self.balls

    def draw_balls(self, frame, current_width, current_height):
        scale = min(current_width / frame.shape[1], current_height / frame.shape[0])
        scaled_radius = self.settings.scale_value(self.settings.ball_radius, current_width, current_height)
        for ball in self.balls:
            x, y, _, _, ball_type, _, _ = ball
            color = self.settings.balls[ball_type]["color"] if ball_type in self.settings.balls else (0, 255, 0)
            if color:
                cv2.circle(frame, (int(x * scale), int(y * scale)), int(scaled_radius), color, -1)
        return frame

    def update_physics(self, current_width, current_height):
        scale = min(current_width / self.settings.base_frame_width, current_height / self.settings.base_frame_height)
        for ball in self.balls:
            x, y, vx, vy, ball_type, missed_frames, ball_id = ball
            scaled_gravity = self.settings.gravity * self.settings.scale_value(1, current_width, current_height)
            vy += scaled_gravity * self.settings.time_step * 10
            x += vx * self.settings.time_step
            y += vy * self.settings.time_step
            vx *= self.settings.friction  # Apply friction to x velocity
            vy *= self.settings.friction  # Apply friction to y velocity

            scaled_radius = self.settings.scale_value(self.settings.ball_radius, current_width, current_height)
            scaled_width = current_width / scale
            scaled_height = current_height / scale

            if x < scaled_radius:
                x = scaled_radius
                vx = -vx * 0.7  # Reduced bounce energy
            elif x > scaled_width - scaled_radius:
                x = scaled_width - scaled_radius
                vx = -vx * 0.7  # Reduced bounce energy
            if y < scaled_radius:
                y = scaled_radius
                vy = -vy * 0.7  # Reduced bounce energy
            elif y > scaled_height - scaled_radius:
                y = scaled_height - scaled_radius
                vy = -vy * 0.7  # Reduced bounce energy

            ball[:] = [x, y, vx, vy, ball_type, missed_frames, ball_id]