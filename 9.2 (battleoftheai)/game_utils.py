import cv2
import numpy as np
import os
import sys
import csv
import pickle

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def log_training_data(balls, scoring_zones, current_width, current_height, filename="train_ball_detector.csv", debug=False):
    filename = resource_path(filename)
    data = []
    scale = min(current_width / 1920, current_height / 1080)
    for ball in balls:
        x, y, _, _, ball_type, _, ball_id = ball
        scaled_x = x * scale
        scaled_y = y * scale
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
                if scaled_zx <= scaled_x <= scaled_x + scaled_zw and scaled_zy <= scaled_y <= scaled_zy + scaled_zh:
                    in_zone = True
            if in_zone:
                multiplier = 1.0
                if ball_type == "red":
                    multiplier = 2.0
                elif ball_type == "half":
                    multiplier = 1.5
                score = points * multiplier
                break
        data.append({"x": scaled_x, "y": scaled_y, "ball_type": ball_type, "score": score})

    mode = 'a' if os.path.exists(filename) else 'w'
    with open(filename, mode, newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["x", "y", "ball_type", "score"])
        if mode == 'w':
            writer.writeheader()
        writer.writerows(data)
    if debug:
        print(f"Logged data to {filename}: {data}")

class LabelingSession:
    def __init__(self, frame):
        self.frame = frame.copy()
        self.labels = []
        self.current_label = None
        self.window_name = "Label Balls (r: red, w: white, h: half, b: background, s: skip)"
        print(f"Creating labeling window: {self.window_name}")
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.moveWindow(self.window_name, 0, 0)
        cv2.setWindowProperty(self.window_name, cv2.WND_PROP_VISIBLE, 1)
        cv2.setWindowProperty(self.window_name, cv2.WND_PROP_TOPMOST, 1)
        cv2.setMouseCallback(self.window_name, self.mouse_callback)

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and self.current_label is not None:
            self.labels.append((x, y, self.current_label))
            print(f"Labeled point at ({x}, {y}) as {self.current_label}")
            color = {
                "red": (0, 0, 255),
                "white": (255, 255, 255),
                "half": (0, 255, 255),
                "background": (0, 255, 0)
            }.get(self.current_label, (0, 255, 0))
            cv2.circle(self.frame, (x, y), 5, color, -1)
            cv2.imshow(self.window_name, self.frame)

    def run(self):
        while True:
            cv2.imshow(self.window_name, self.frame)
            key = cv2.waitKey(30) & 0xFF
            if key == ord('r'):
                self.current_label = "red"
                print("Labeling as red")
            elif key == ord('w'):
                self.current_label = "white"
                print("Labeling as white")
            elif key == ord('h'):
                self.current_label = "half"
                print("Labeling as half_red_white")
            elif key == ord('b'):
                self.current_label = "background"
                print("Labeling as background")
            elif key == ord('s'):
                self.current_label = None
                print("Skipping label")
            elif key == ord('q'):
                break
        cv2.destroyWindow(self.window_name)
        return self.labels

def save_labeled_data(frame, labels, filename="labeled_data.pkl"):
    filename = resource_path(filename)
    patch_size = 20
    data = []
    for x, y, label in labels:
        x_start = max(0, x - patch_size // 2)
        x_end = min(frame.shape[1], x + patch_size // 2)
        y_start = max(0, y - patch_size // 2)
        y_end = min(frame.shape[0], y + patch_size // 2)
        patch = frame[y_start:y_end, x_start:x_end]
        if patch.shape[0] > 0 and patch.shape[1] > 0:
            patch = cv2.resize(patch, (20, 20))
            data.append((patch, label))

    if os.path.exists(filename):
        with open(filename, "rb") as f:
            existing_data = pickle.load(f)
        data.extend(existing_data)

    try:
        with open(filename, "wb") as f:
            pickle.dump(data, f)
        print(f"Saved {len(data)} labeled patches to {filename}")
    except Exception as e:
        print(f"Error saving labeled data to {filename}: {e}")