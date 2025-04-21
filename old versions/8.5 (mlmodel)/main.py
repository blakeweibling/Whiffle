import cv2
import numpy as np
from ball_tracker import BallTracker
from scoring_zones import ScoringZones
from game_settings import GameSettings
import pandas as pd
import os

def log_training_data(balls, scoring_zones, current_width, current_height, filename="training_data.csv", debug=False):
    data = []
    scale = min(current_width / 1920, current_height / 1080)
    for ball in balls:
        x, y, _, _, ball_type, _, ball_id = ball
        scaled_x = x * scale
        scaled_y = y * scale

        # Use manual scoring to determine the score for this ball
        score = 0
        in_zone = False
        for zone_idx, zone in enumerate(scoring_zones.zones):
            points = zone[-1]
            if len(zone) == 4:  # Circle
                zx, zy, radius, _ = zone
                scaled_radius = radius * scale
                distance = np.sqrt((scaled_x - (zx * scale))**2 + (scaled_y - (zy * scale))**2)
                if distance <= scaled_radius:
                    in_zone = True
            else:  # Rectangle
                zx, zy, zw, zh, _ = zone
                scaled_zx = zx * scale
                scaled_zy = zy * scale
                scaled_zw = zw * scale
                scaled_zh = zh * scale
                if scaled_zx <= scaled_x <= scaled_zx + scaled_zw and scaled_zy <= scaled_y <= scaled_zy + scaled_zh:
                    in_zone = True

            if in_zone:
                multiplier = 1.0
                if ball_type == "red":
                    multiplier = 2.0
                elif ball_type == "half":
                    multiplier = 1.5
                score = points * multiplier
                break

        data.append({
            "x": scaled_x,
            "y": scaled_y,
            "ball_type": ball_type,
            "score": score
        })

    df = pd.DataFrame(data)
    if os.path.exists(filename):
        df.to_csv(filename, mode='a', header=False, index=False)
    else:
        df.to_csv(filename, mode='w', header=True, index=False)
    if debug:
        print(f"Logged data to {filename}: {data}")

def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    print(f"Set base resolution to {cap.get(cv2.CAP_PROP_FRAME_WIDTH)}x{cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}")

    settings = GameSettings()
    tracker = BallTracker()
    global scoring_zones
    scoring_zones = ScoringZones()

    total_score = 0
    print(f"Game started with initial score: {total_score}")

    flip_horizontal = False
    debug = False
    cv2.namedWindow("Game", cv2.WINDOW_NORMAL)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            break

        if flip_horizontal:
            frame = cv2.flip(frame, 1)

        current_width = cv2.getWindowImageRect("Game")[2]
        current_height = cv2.getWindowImageRect("Game")[3]
        if current_width == 0 or current_height == 0:
            current_width, current_height = 1920, 1080

        frame = cv2.resize(frame, (current_width, current_height))

        # Tune HSV if enabled
        frame = tracker.tune_hsv(frame)

        balls = tracker.detect_balls(frame, current_width, current_height)
        tracker.update_physics(current_width, current_height)
        frame = tracker.draw_balls(frame, current_width, current_height)

        frame = scoring_zones.draw_zones(frame, current_width, current_height)
        score = scoring_zones.check_scores(balls, current_width, current_height)
        log_training_data(balls, scoring_zones, current_width, current_height, debug=debug)
        total_score += score
        if score > 0:
            print(f"Adding {score} to total score. New total: {total_score}")

        frame_height = frame.shape[0]
        score_text = f"Score: {total_score}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        thickness = 2
        text_size = cv2.getTextSize(score_text, font, font_scale, thickness)[0]
        text_x = 10
        text_y = frame_height - 10
        box_coords = ((text_x, text_y + 5), (text_x + text_size[0], text_y - text_size[1] - 5))
        cv2.rectangle(frame, box_coords[0], box_coords[1], (128, 128, 128), -1)
        cv2.putText(frame, score_text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)

        cv2.imshow("Game", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('c'):
            scoring_zones.calibrating = True
            cv2.namedWindow("Calibration", cv2.WINDOW_NORMAL)
            while scoring_zones.calibrating:
                ret, calib_frame = cap.read()
                if not ret:
                    print("Error: Could not read frame during calibration.")
                    break
                if flip_horizontal:
                    calib_frame = cv2.flip(calib_frame, 1)
                calib_frame = cv2.resize(calib_frame, (current_width, current_height))
                cv2.imshow("Calibration", calib_frame)
                current_calib_width = cv2.getWindowImageRect("Calibration")[2] if cv2.getWindowProperty("Calibration", 0) >= 0 else current_width
                current_calib_height = cv2.getWindowImageRect("Calibration")[3] if cv2.getWindowProperty("Calibration", 0) >= 0 else current_height
                try:
                    scoring_zones.calibrate_zones(calib_frame, current_calib_width, current_calib_height)
                except cv2.error as e:
                    print(f"Calibration error: {e}. Continuing without calibration.")
                    scoring_zones.calibrating = False
        elif key == ord('r'):
            total_score = 0
            scoring_zones.scored_balls.clear()
            print("Score reset to 0")
        elif key == ord('f'):
            flip_horizontal = not flip_horizontal
            print(f"Flip horizontal toggled to: {flip_horizontal}")
        elif key == ord('d'):
            debug = not debug
            tracker.debug = debug
            scoring_zones.debug = debug
            print(f"Debug mode toggled to: {debug}")
        elif key == ord('t'):
            tracker.tuning = not tracker.tuning
            if tracker.tuning:
                tracker.start_tuning(frame)
                print("HSV tuning enabled. Adjust trackbars in 'HSV Tuning' window. Press 't' to disable.")
            else:
                cv2.destroyWindow("HSV Tuning")
                print("HSV tuning disabled. Current HSV ranges:")
                print(f"White Lower: {tracker.white_lower}")
                print(f"White Upper: {tracker.white_upper}")
                print(f"Red Lower 1: {tracker.red_lower1}")
                print(f"Red Upper 1: {tracker.red_upper1}")
                print(f"Red Lower 2: {tracker.red_lower2}")
                print(f"Red Upper 2: {tracker.red_upper2}")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()