import cv2
import numpy as np
from ball_tracker import BallTracker
from scoring_zones import ScoringZones
from game_settings import GameSettings

def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    # Set base resolution to 1080p
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    print(f"Set base resolution to {cap.get(cv2.CAP_PROP_FRAME_WIDTH)}x{cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}")

    settings = GameSettings()
    tracker = BallTracker()
    scoring_zones = ScoringZones()

    total_score = 0
    print(f"Game started with initial score: {total_score}")

    flip_horizontal = False
    cv2.namedWindow("Game", cv2.WINDOW_NORMAL)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            break

        if flip_horizontal:
            frame = cv2.flip(frame, 1)

        # Get current window size
        current_width = cv2.getWindowImageRect("Game")[2]
        current_height = cv2.getWindowImageRect("Game")[3]
        if current_width == 0 or current_height == 0:  # Default to base resolution if not resized
            current_width, current_height = 1920, 1080

        # Resize frame to fit window
        frame = cv2.resize(frame, (current_width, current_height))

        balls = tracker.detect_balls(frame, current_width, current_height)
        tracker.update_physics(current_width, current_height)
        frame = tracker.draw_balls(frame, current_width, current_height)

        frame = scoring_zones.draw_zones(frame, current_width, current_height)
        score = scoring_zones.check_scores(balls, current_width, current_height)
        total_score += score
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
            cv2.namedWindow("Calibration", cv2.WINDOW_NORMAL)  # Ensure window is created
            while scoring_zones.calibrating:
                ret, calib_frame = cap.read()
                if not ret:
                    print("Error: Could not read frame during calibration.")
                    break
                if flip_horizontal:
                    calib_frame = cv2.flip(calib_frame, 1)
                calib_frame = cv2.resize(calib_frame, (current_width, current_height))
                cv2.imshow("Calibration", calib_frame)  # Display window first
                # Get window dimensions after displaying
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

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()