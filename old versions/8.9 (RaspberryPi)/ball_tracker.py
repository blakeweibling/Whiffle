# ball_tracker.py
class BallTracker:
    def __init__(self):
        self.settings = GameSettings()
        self.balls = []  # [x, y, vx, vy, type, missed_frames, ball_id]
        self.tracked_balls = set()
        self.ball_id_counter = 0
        self.debug = True
        print("CNN model disabled on Raspberry Pi. Using color-based detection.")

    def detect_balls(self, frame, current_width, current_height):
        """Detect balls in the frame using color-based detection."""
        if self.debug:
            print(f"Frame resolution: {current_width}x{current_height}")

        # Downscale frame for processing (to 640x360)
        processing_width, processing_height = 640, 360
        scale_x = current_width / processing_width
        scale_y = current_height / processing_height
        small_frame = cv2.resize(frame, (processing_width, processing_height))

        # Convert to HSV for color-based detection
        hsv = cv2.cvtColor(small_frame, cv2.COLOR_BGR2HSV)

        # Adjusted color ranges for Raspberry Pi Camera
        red_lower1 = np.array([0, 100, 50])
        red_upper1 = np.array([10, 255, 255])
        red_lower2 = np.array([160, 100, 50])
        red_upper2 = np.array([180, 255, 255])
        white_lower = np.array([0, 0, 180])
        white_upper = np.array([180, 40, 255])

        red_mask1 = cv2.inRange(hsv, red_lower1, red_upper1)
        red_mask2 = cv2.inRange(hsv, red_lower2, red_upper2)
        red_mask = red_mask1 | red_mask2
        white_mask = cv2.inRange(hsv, white_lower, white_upper)

        half_mask = red_mask & white_mask

        detected_balls = []
        for mask, ball_type in [(red_mask, "red"), (white_mask, "white"), (half_mask, "half")]:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if self.settings.detection_area_min < area < self.settings.detection_area_max:
                    perimeter = cv2.arcLength(cnt, True)
                    if perimeter > 0:
                        circularity = 4 * np.pi * area / (perimeter * perimeter)
                        if self.settings.detection_circularity_min < circularity < self.settings.detection_circularity_max:
                            (x, y), radius = cv2.minEnclosingCircle(cnt)
                            scaled_radius = self.settings.scale_value(self.settings.ball_radius, processing_width, processing_height)
                            if scaled_radius - self.settings.detection_radius_tolerance <= radius <= scaled_radius + self.settings.detection_radius_tolerance:
                                x_orig = int(x * scale_x)
                                y_orig = int(y * scale_y)
                                ball_id = (x_orig, y_orig)
                                if len(self.tracked_balls) > 100:
                                    self.tracked_balls.clear()
                                    if self.debug:
                                        print("Cleared tracked_balls due to size limit")
                                if ball_id not in self.tracked_balls:
                                    self.tracked_balls.add(ball_id)
                                    self.ball_id_counter += 1
                                    detected_balls.append([x_orig, y_orig, 0, 0, ball_type, 0, self.ball_id_counter])
                                    if self.debug:
                                        print(f"Detected {ball_type} ball at ({x_orig}, {y_orig}) with ball_id {self.ball_id_counter}")

        new_balls = []
        for new_ball in detected_balls:
            x_new, y_new, _, _, ball_type, _, new_ball_id = new_ball
            matched = False
            for old_ball in self.balls:
                x_old, y_old, vx, vy, old_type, missed_frames, ball_id = old_ball
                distance = np.sqrt((x_new - x_old)**2 + (y_new - y_old)**2)
                if distance < 30 and ball_type == old_type:
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
            if ball[5] >= 1:
                self.balls.remove(ball)
                if self.debug:
                    print(f"Removed ball {ball[6]} due to missed frames")
            scaled_x = ball[0]
            scaled_y = ball[1]
            if scaled_x < 0 or scaled_x > current_width or scaled_y < 0 or scaled_y > current_height:
                self.balls.remove(ball)
                if self.debug:
                    print(f"Removed ball {ball[6]} at ({scaled_x}, {scaled_y}) - outside frame")

        if self.debug:
            print(f"After update: self.balls = {self.balls}")
        return self.balls

    # draw_balls and update_physics remain unchanged