import cv2
import numpy as np
import pickle
import os
import pandas as pd

class ScoringZones:
    def __init__(self):
        self.zones = []  # List of [x, y, radius, points] for circles or [x, y, width, height, points] for rectangles
        self.calibrating = False
        self.start_point = None
        self.end_point = None
        self.pending_zone = None
        self.current_points = 0
        self.scored_balls = {}
        self.zone_scores = {}
        self.is_rectangle_mode = False
        self.debug = False
        self.load_zones()
        # Disable ML model for now
        self.model = None
        self.ball_type_encoder = None
        print("ML model disabled, using manual scoring")

    def load_zones(self):
        if os.path.exists("zones.pkl"):
            try:
                with open("zones.pkl", "rb") as f:
                    self.zones = pickle.load(f)
                print(f"Loaded zones: {self.zones}")
            except Exception as e:
                print(f"Error loading zones: {e}")
                self.zones = []
        else:
            print("No zones.pkl file found, starting with empty zones")

    def save_zones(self):
        try:
            with open("zones.pkl", "wb") as f:
                pickle.dump(self.zones, f)
            print(f"Saved zones: {self.zones}")
        except Exception as e:
            print(f"Error saving zones: {e}")

    def mouse_callback(self, event, x, y, flags, frame, scale_x, scale_y):
        if not self.calibrating:
            return

        if event == cv2.EVENT_LBUTTONDOWN:
            self.start_point = (x / scale_x, y / scale_y)
            self.pending_zone = None
        elif event == cv2.EVENT_LBUTTONUP:
            if self.start_point:
                self.end_point = (x / scale_x, y / scale_y)
                x1, y1 = self.start_point
                x2, y2 = self.end_point
                if self.is_rectangle_mode:
                    width = abs(x2 - x1)
                    height = abs(y2 - y1)
                    x = min(x1, x2)
                    y = min(y1, y2)
                    self.pending_zone = [x, y, width, height, 0]
                else:
                    radius = int(np.sqrt((x2 - x1)**2 + (y2 - y1)**2))
                    self.pending_zone = [x1, y1, radius, 0]
        elif event == cv2.EVENT_MOUSEMOVE and self.start_point and not self.end_point:
            self.end_point = (x / scale_x, y / scale_y)

    def calibrate_zones(self, frame, current_width, current_height):
        self.calibrating = True
        cv2.namedWindow("Calibration", cv2.WINDOW_NORMAL)
        scale_x = current_width / frame.shape[1]
        scale_y = current_height / frame.shape[0]
        cv2.setMouseCallback("Calibration", lambda event, x, y, flags, param: self.mouse_callback(event, x, y, flags, frame, scale_x, scale_y))

        while self.calibrating:
            calib_frame = cv2.resize(frame, (current_width, current_height))
            for zone in self.zones:
                if len(zone) == 4:  # Circle
                    x, y, radius, points = zone
                    scaled_x = int(x * scale_x)
                    scaled_y = int(y * scale_y)
                    scaled_radius = int(radius * min(scale_x, scale_y))
                    cv2.circle(calib_frame, (scaled_x, scaled_y), scaled_radius, (0, 0, 255), 2)
                    cv2.putText(calib_frame, f"Points: {points}", (scaled_x - scaled_radius, scaled_y - scaled_radius - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                else:  # Rectangle
                    x, y, w, h, points = zone
                    scaled_x = int(x * scale_x)
                    scaled_y = int(y * scale_y)
                    scaled_w = int(w * scale_x)
                    scaled_h = int(h * scale_y)
                    cv2.rectangle(calib_frame, (scaled_x, scaled_y), (scaled_x + scaled_w, scaled_y + scaled_h), (0, 0, 255), 2)
                    cv2.putText(calib_frame, f"Points: {points}", (scaled_x + 5, scaled_y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

            if self.start_point and self.end_point:
                x1, y1 = [int(x * scale_x) for x in self.start_point]
                x2, y2 = [int(x * scale_x) for x in self.end_point]
                if self.is_rectangle_mode:
                    cv2.rectangle(calib_frame, (min(x1, x2), min(y1, y2)), (max(x1, x2), max(y1, y2)), (0, 255, 0), 2)
                    cv2.putText(calib_frame, f"Points: {self.current_points}",
                               (min(x1, x2) + 5, min(y1, y2) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                else:
                    radius = int(np.sqrt((x2/scale_x - x1/scale_x)**2 + (y2/scale_y - y1/scale_y)**2) * min(scale_x, scale_y))
                    cv2.circle(calib_frame, (x1, y1), radius, (0, 255, 0), 2)
                    cv2.putText(calib_frame, f"Points: {self.current_points}",
                               (x1 - radius, y1 - radius - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            if self.pending_zone:
                if len(self.pending_zone) == 4:  # Circle
                    x, y, radius, _ = self.pending_zone
                    scaled_x = int(x * scale_x)
                    scaled_y = int(y * scale_y)
                    scaled_radius = int(radius * min(scale_x, scale_y))
                    cv2.circle(calib_frame, (scaled_x, scaled_y), scaled_radius, (0, 255, 0), 2)
                    cv2.putText(calib_frame, f"Enter Points: {self.current_points} (Enter to confirm)",
                               (scaled_x - scaled_radius, scaled_y - scaled_radius - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                else:  # Rectangle
                    x, y, w, h, _ = self.pending_zone
                    scaled_x = int(x * scale_x)
                    scaled_y = int(y * scale_y)
                    scaled_w = int(w * scale_x)
                    scaled_h = int(h * scale_y)
                    cv2.rectangle(calib_frame, (scaled_x, scaled_y), (scaled_x + scaled_w, scaled_y + scaled_h), (0, 255, 0), 2)
                    cv2.putText(calib_frame, f"Enter Points: {self.current_points} (Enter to confirm)",
                               (scaled_x + 5, scaled_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            text = "Drag to draw zone (m to toggle mode). Enter to confirm points, 'q' to quit"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            text_x = 10
            text_y = current_height - 10
            box_coords = ((text_x, text_y + 5), (text_x + text_size[0], text_y - text_size[1] - 5))
            cv2.rectangle(calib_frame, box_coords[0], box_coords[1], (128, 128, 128), -1)
            cv2.putText(calib_frame, text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)

            mode_text = f"Mode: {'Rectangle' if self.is_rectangle_mode else 'Circle'}"
            mode_size = cv2.getTextSize(mode_text, font, font_scale, thickness)[0]
            mode_x = current_width - mode_size[0] - 10
            mode_y = current_height - 10
            box_coords = ((mode_x, mode_y + 5), (mode_x + mode_size[0], mode_y - mode_size[1] - 5))
            cv2.rectangle(calib_frame, box_coords[0], box_coords[1], (128, 128, 128), -1)
            cv2.putText(calib_frame, mode_text, (mode_x, mode_y), font, font_scale, (255, 255, 255), thickness)

            cv2.imshow("Calibration", calib_frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                self.calibrating = False
            elif key == ord('m'):
                self.is_rectangle_mode = not self.is_rectangle_mode
                self.start_point = None
                self.end_point = None
                self.pending_zone = None
                print(f"Switched to {'rectangle' if self.is_rectangle_mode else 'circle'} mode")
            elif key == 13:
                if self.pending_zone:
                    self.pending_zone[-1] = self.current_points
                    self.zones.append(self.pending_zone)
                    self.pending_zone = None
                    self.current_points = 0
                    self.save_zones()
            elif key in [ord(str(i)) for i in range(10)]:
                self.current_points = self.current_points * 10 + int(chr(key))

        cv2.destroyWindow("Calibration")

    def check_scores(self, balls, current_width, current_height):
        total_score = 0
        scale = min(current_width / 1920, current_height / 1080)

        # Force manual scoring
        if self.debug:
            print("Using manual scoring")
        return self._manual_check_scores(balls, current_width, current_height)

    def _manual_check_scores(self, balls, current_width, current_height):
        total_score = 0
        current_balls_in_zones = {}
        scale = min(current_width / 1920, current_height / 1080)

        if not self.zones:
            if self.debug:
                print("No zones defined, skipping scoring")
            return 0

        if self.debug:
            print(f"Checking {len(balls)} balls with scale {scale}")
        for ball in balls:
            x, y, _, _, ball_type, missed_frames, ball_id = ball
            scaled_x = x * scale
            scaled_y = y * scale
            in_zone = False

            for zone_idx, zone in enumerate(self.zones):
                points = zone[-1]
                if len(zone) == 4:  # Circle
                    zx, zy, radius, _ = zone
                    scaled_radius = radius * scale
                    distance = np.sqrt((scaled_x - (zx * scale))**2 + (scaled_y - (zy * scale))**2)
                    if distance <= scaled_radius:
                        in_zone = True
                        if self.debug:
                            print(f"Ball at ({scaled_x:.1f}, {scaled_y:.1f}) is in circle zone at ({zx*scale:.1f}, {zy*scale:.1f}) with radius {scaled_radius:.1f}, points {points}")
                else:  # Rectangle
                    zx, zy, zw, zh, _ = zone
                    scaled_zx = zx * scale
                    scaled_zy = zy * scale
                    scaled_zw = zw * scale
                    scaled_zh = zh * scale
                    if scaled_zx <= scaled_x <= scaled_zx + scaled_zw and scaled_zy <= scaled_y <= scaled_zy + scaled_zh:
                        in_zone = True
                        if self.debug:
                            print(f"Ball at ({scaled_x:.1f}, {scaled_y:.1f}) is in rectangle zone at ({scaled_zx:.1f}, {scaled_zy:.1f}) with size ({scaled_zw:.1f}, {scaled_zh:.1f}), points {points}")

                if in_zone:
                    multiplier = 1.0
                    if ball_type == "red":
                        multiplier = 2.0
                        if self.debug:
                            print(f"Red ball detected, doubling points from {points} to {points * multiplier}")
                    elif ball_type == "half":
                        multiplier = 1.5
                        if self.debug:
                            print(f"Half red/half white ball detected, multiplying points by 1.5 from {points} to {points * multiplier}")

                    if ball_id not in current_balls_in_zones:
                        current_balls_in_zones[ball_id] = set()
                    current_balls_in_zones[ball_id].add(zone_idx)

                    if ball_id not in self.scored_balls or zone_idx not in self.scored_balls[ball_id]:
                        adjusted_points = points * multiplier
                        total_score += adjusted_points
                        if ball_id not in self.scored_balls:
                            self.scored_balls[ball_id] = set()
                        self.scored_balls[ball_id].add(zone_idx)
                        print(f"Scored {adjusted_points} points for ball_id {ball_id} (type: {ball_type}) in zone {zone_idx}")
                    break

        active_ball_ids = {ball[6] for ball in balls}
        self.scored_balls = {b_id: zones for b_id, zones in self.scored_balls.items() if b_id in active_ball_ids}
        if self.debug:
            print(f"Total score this frame: {total_score}, Scored balls: {self.scored_balls}")
        return total_score

    def draw_zones(self, frame, current_width, current_height):
        scale_x = current_width / frame.shape[1]
        scale_y = current_height / frame.shape[0]
        for zone in self.zones:
            if len(zone) == 4:  # Circle
                x, y, radius, points = zone
                scaled_x = int(x * scale_x)
                scaled_y = int(y * scale_y)
                scaled_radius = int(radius * min(scale_x, scale_y))
                cv2.circle(frame, (scaled_x, scaled_y), scaled_radius, (0, 255, 0), 2)
                cv2.putText(frame, str(points), (scaled_x - scaled_radius, scaled_y - scaled_radius - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            else:  # Rectangle
                x, y, w, h, points = zone
                scaled_x = int(x * scale_x)
                scaled_y = int(y * scale_y)
                scaled_w = int(w * scale_x)
                scaled_h = int(h * scale_y)
                cv2.rectangle(frame, (scaled_x, scaled_y), (scaled_x + scaled_w, scaled_y + scaled_h), (0, 255, 0), 2)
                cv2.putText(frame, str(points), (scaled_x + 10, scaled_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        return frame