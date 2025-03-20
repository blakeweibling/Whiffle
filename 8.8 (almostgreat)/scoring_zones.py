# scoring_zones.py
import pickle
import os
import pandas as pd
import numpy as np
import cv2
import sys  # Added for resource_path()

# Add resource_path() function to handle file paths for PyInstaller
def resource_path(relative_path):
    """Get the absolute path to a resource, works for dev and for PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores files there
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class ScoringZones:
    def __init__(self, reference_width=1920, reference_height=1080, sound_manager=None):
        self.zones = []  # List of [x, y, radius, points] for circles or [x, y, width, height, points] for rectangles
        self.scored_balls = {}  # ball_id -> set of zone indices
        self.zone_scores = {}
        self.debug = True  # Enable debug output
        self.reference_width = reference_width  # Resolution at which zones were recorded
        self.reference_height = reference_height
        self.sound_manager = sound_manager  # Store the SoundManager instance
        self.load_zones()
        self.model = None
        self.ball_type_encoder = None
        print("ML model disabled, using manual scoring")

    def load_zones(self):
        # Update zones.pkl path with resource_path()
        zones_path = resource_path("zones.pkl")
        if os.path.exists(zones_path):
            try:
                with open(zones_path, "rb") as f:
                    self.zones = pickle.load(f)
                print(f"Loaded zones: {self.zones}")
            except Exception as e:
                print(f"Error loading zones: {e}")
                self.zones = []
        else:
            print("No zones.pkl file found, starting with empty zones")

    def save_zones(self):
        # Update zones.pkl path with resource_path()
        zones_path = resource_path("zones.pkl")
        try:
            with open(zones_path, "wb") as f:
                pickle.dump(self.zones, f)
            print(f"Saved zones: {self.zones}")
        except Exception as e:
            print(f"Error saving zones: {e}")

    def reset_scored_balls(self):
        """Reset the scored_balls dictionary to start fresh."""
        self.scored_balls = {}
        print("Reset scored_balls dictionary")

    def check_scores(self, balls, current_width, current_height):
        total_score = 0
        scale_x = current_width / self.reference_width
        scale_y = current_height / self.reference_height

        if not self.zones:
            if self.debug:
                print("No zones defined, skipping scoring")
            return 0

        if self.debug:
            print(f"Checking {len(balls)} balls with scale_x {scale_x}, scale_y {scale_y}")
            print(f"Balls: {balls}")

        for ball in balls:
            x, y, _, _, ball_type, missed_frames, ball_id = ball
            best_score = 0
            best_zone_idx = None
            for zone_idx, zone in enumerate(self.zones):
                points = zone[-1]
                in_zone = False
                if len(zone) == 4:  # Circle
                    zx, zy, radius, _ = zone
                    scaled_zx = zx * scale_x
                    scaled_zy = zy * scale_y
                    scaled_radius = radius * min(scale_x, scale_y)
                    distance = np.sqrt((x - scaled_zx)**2 + (y - scaled_zy)**2)
                    if distance <= scaled_radius:
                        in_zone = True
                        if self.debug:
                            print(f"Ball at ({x:.1f}, {y:.1f}) is in circle zone {zone_idx} at ({scaled_zx:.1f}, {scaled_zy:.1f}) with radius {scaled_radius:.1f}, points {points}")
                else:  # Rectangle
                    zx, zy, zw, zh, _ = zone
                    scaled_zx = zx * scale_x
                    scaled_zy = zy * scale_y
                    scaled_zw = zw * scale_x
                    scaled_zh = zh * scale_y
                    if scaled_zx <= x <= scaled_zx + scaled_zw and scaled_zy <= y <= scaled_zy + scaled_zh:
                        in_zone = True
                        if self.debug:
                            print(f"Ball at ({x:.1f}, {y:.1f}) is in rectangle zone {zone_idx} at ({scaled_zx:.1f}, {scaled_zy:.1f}) with size ({scaled_zw:.1f}, {scaled_zh:.1f}), points {points}")

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

                    adjusted_points = points * multiplier
                    if adjusted_points > best_score:
                        best_score = adjusted_points
                        best_zone_idx = zone_idx

            if best_zone_idx is not None:
                if ball_id not in self.scored_balls or best_zone_idx not in self.scored_balls[ball_id]:
                    total_score += best_score
                    if ball_id not in self.scored_balls:
                        self.scored_balls[ball_id] = set()
                    self.scored_balls[ball_id].add(best_zone_idx)
                    print(f"Scored {best_score} points for ball_id {ball_id} (type: {ball_type}) in zone {best_zone_idx}")
                    # Play the score sound effect
                    if self.sound_manager:
                        self.sound_manager.play_sound_effect("score")

        if self.debug:
            print(f"Total score this frame: {total_score}, Scored balls: {self.scored_balls}")
        return total_score

    def draw_zones(self, frame, current_width, current_height):
        scale_x = current_width / self.reference_width
        scale_y = current_height / self.reference_height

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