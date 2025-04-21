import cv2
import numpy as np
from game_settings import GameSettings

class BallTracker:
    def __init__(self):
        self.settings = GameSettings()
        self.balls = []  # List of [x, y, vx, vy, type, missed_frames, ball_id]
        self.tracked_balls = set()
        self.ball_id_counter = 0
        self.debug = False
        # HSV tuning parameters
        self.tuning = False
        self.white_lower = np.array([0, 0, 180])
        self.white_upper = np.array([180, 40, 255])
        self.red_lower1 = np.array([0, 120, 70])
        self.red_upper1 = np.array([10, 255, 255])
        self.red_lower2 = np.array([170, 120, 70])
        self.red_upper2 = np.array([180, 255, 255])

    def start_tuning(self, frame):
        self.tuning = True
        cv2.namedWindow("HSV Tuning", cv2.WINDOW_NORMAL)
        cv2.createTrackbar("White H Min", "HSV Tuning", self.white_lower[0], 180, self.update_white_h_min)
        cv2.createTrackbar("White S Min", "HSV Tuning", self.white_lower[1], 255, self.update_white_s_min)
        cv2.createTrackbar("White V Min", "HSV Tuning", self.white_lower[2], 255, self.update_white_v_min)
        cv2.createTrackbar("White H Max", "HSV Tuning", self.white_upper[0], 180, self.update_white_h_max)
        cv2.createTrackbar("White S Max", "HSV Tuning", self.white_upper[1], 255, self.update_white_s_max)
        cv2.createTrackbar("White V Max", "HSV Tuning", self.white_upper[2], 255, self.update_white_v_max)
        cv2.createTrackbar("Red1 H Min", "HSV Tuning", self.red_lower1[0], 180, self.update_red1_h_min)
        cv2.createTrackbar("Red1 S Min", "HSV Tuning", self.red_lower1[1], 255, self.update_red1_s_min)
        cv2.createTrackbar("Red1 V Min", "HSV Tuning", self.red_lower1[2], 255, self.update_red1_v_min)
        cv2.createTrackbar("Red1 H Max", "HSV Tuning", self.red_upper1[0], 180, self.update_red1_h_max)
        cv2.createTrackbar("Red1 S Max", "HSV Tuning", self.red_upper1[1], 255, self.update_red1_s_max)
        cv2.createTrackbar("Red1 V Max", "HSV Tuning", self.red_upper1[2], 255, self.update_red1_v_max)
        cv2.createTrackbar("Red2 H Min", "HSV Tuning", self.red_lower2[0], 180, self.update_red2_h_min)
        cv2.createTrackbar("Red2 S Min", "HSV Tuning", self.red_lower2[1], 255, self.update_red2_s_min)
        cv2.createTrackbar("Red2 V Min", "HSV Tuning", self.red_lower2[2], 255, self.update_red2_v_min)
        cv2.createTrackbar("Red2 H Max", "HSV Tuning", self.red_upper2[0], 180, self.update_red2_h_max)
        cv2.createTrackbar("Red2 S Max", "HSV Tuning", self.red_upper2[1], 255, self.update_red2_s_max)
        cv2.createTrackbar("Red2 V Max", "HSV Tuning", self.red_upper2[2], 255, self.update_red2_v_max)

    def update_white_h_min(self, val):
        self.white_lower[0] = val

    def update_white_s_min(self, val):
        self.white_lower[1] = val

    def update_white_v_min(self, val):
        self.white_lower[2] = val

    def update_white_h_max(self, val):
        self.white_upper[0] = val

    def update_white_s_max(self, val):
        self.white_upper[1] = val

    def update_white_v_max(self, val):
        self.white_upper[2] = val

    def update_red1_h_min(self, val):
        self.red_lower1[0] = val

    def update_red1_s_min(self, val):
        self.red_lower1[1] = val

    def update_red1_v_min(self, val):
        self.red_lower1[2] = val

    def update_red1_h_max(self, val):
        self.red_upper1[0] = val

    def update_red1_s_max(self, val):
        self.red_upper1[1] = val

    def update_red1_v_max(self, val):
        self.red_upper1[2] = val

    def update_red2_h_min(self, val):
        self.red_lower2[0] = val

    def update_red2_s_min(self, val):
        self.red_lower2[1] = val

    def update_red2_v_min(self, val):
        self.red_lower2[2] = val

    def update_red2_h_max(self, val):
        self.red_upper2[0] = val

    def update_red2_s_max(self, val):
        self.red_upper2[1] = val

    def update_red2_v_max(self, val):
        self.red_upper2[2] = val

    def tune_hsv(self, frame):
        if not self.tuning:
            return frame

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        white_mask = cv2.inRange(hsv, self.white_lower, self.white_upper)
        red_mask1 = cv2.inRange(hsv, self.red_lower1, self.red_upper1)
        red_mask2 = cv2.inRange(hsv, self.red_lower2, self.red_upper2)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)
        half_mask = cv2.bitwise_and(white_mask, red_mask)

        # Display masks for tuning
        combined_mask = cv2.bitwise_or(white_mask, red_mask)
        combined_mask = cv2.bitwise_or(combined_mask, half_mask)
        result = cv2.bitwise_and(frame, frame, mask=combined_mask)
        cv2.imshow("HSV Tuning", result)
        return frame

    def detect_balls(self, frame, current_width, current_height):
        scale = min(current_width / self.settings.base_frame_width, current_height / self.settings.base_frame_height)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        white_mask = cv2.inRange(hsv, self.white_lower, self.white_upper)
        red_mask1 = cv2.inRange(hsv, self.red_lower1, self.red_upper1)
        red_mask2 = cv2.inRange(hsv, self.red_lower2, self.red_upper2)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)
        half_mask = cv2.bitwise_and(white_mask, red_mask)

        # Enhanced mask processing
        half_mask = cv2.GaussianBlur(half_mask, (13, 13), 0)
        half_mask = cv2.dilate(half_mask, None, iterations=5)
        half_mask = cv2.erode(half_mask, None, iterations=2)

        for mask in [white_mask, red_mask, half_mask]:
            mask = cv2.GaussianBlur(mask, (7, 7), 0)
            mask = cv2.erode(mask, None, iterations=1)
            mask = cv2.dilate(mask, None, iterations=2)

        detected_balls = []
        for mask, ball_type in [(white_mask, "white"), (red_mask, "red"), (half_mask, "half")]:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for i, cnt in enumerate(contours):
                area = cv2.contourArea(cnt)
                if self.debug:
                    print(f"Contour {i} area: {area} (type: {ball_type})")
                # Relaxed area threshold for both white and red
                area_min = 200 if ball_type == "white" else 300
                area_max = 6000  # Increased max area to capture larger contours
                if area_min < area < area_max:
                    perimeter = cv2.arcLength(cnt, True)
                    if perimeter > 0:
                        circularity = 4 * np.pi * area / (perimeter * perimeter)
                        if self.debug:
                            print(f"Contour {i} circularity: {circularity}")
                        # Relaxed circularity for both white and red
                        circularity_min = 0.5 if ball_type == "white" else 0.6
                        if circularity_min < circularity < 1.3:
                            (x, y), radius = cv2.minEnclosingCircle(cnt)
                            scaled_radius = self.settings.scale_value(self.settings.ball_radius, current_width, current_height)
                            if self.debug:
                                print(f"Contour {i} at ({int(x)}, {int(y)}), Radius: {radius}, Scaled Ball radius: {scaled_radius}")
                            # Relaxed radius tolerance
                            if scaled_radius - 15 <= radius <= scaled_radius + 15:
                                ball_id = (int(x), int(y))
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
                            elif self.debug:
                                print(f"Contour {i} failed radius check: {radius} not in [{scaled_radius - 15}, {scaled_radius + 15}]")
                        elif self.debug:
                            print(f"Contour {i} failed circularity check: {circularity} not in [{circularity_min}, 1.3]")
                elif self.debug:
                    print(f"Contour {i} failed area check: {area} not in [{area_min}, {area_max}]")

        if self.debug:
            print(f"Before update: self.balls = {self.balls}")
        new_balls = []
        for new_ball in detected_balls:
            x_new, y_new, _, _, _, _, new_ball_id = new_ball
            matched = False
            for old_ball in self.balls:
                x_old, y_old, vx, vy, ball_type, missed_frames, ball_id = old_ball
                distance = np.sqrt((x_new - x_old)**2 + (y_new - y_old)**2)
                if distance < 50 / scale:
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
        if new_balls and self.debug:
            print(f"Added new balls: {new_balls}")

        current_positions = {(b[0], b[1]) for b in detected_balls}
        for ball in self.balls:
            if (ball[0], ball[1]) not in current_positions:
                ball[5] += 1

        self.balls = [b for b in self.balls if b[5] < 15]
        if self.debug:
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