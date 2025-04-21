import pickle
import os
import numpy as np
import cv2
from quadtree import Quadtree, Boundary  # Using a spatial partitioning system

class ScoringZones:
    """Optimized scoring system using Quadtrees for efficient spatial lookups."""
    def __init__(self, reference_width=1920, reference_height=1080, sound_manager=None):
        self.reference_width = reference_width
        self.reference_height = reference_height
        self.zones = []
        self.scored_balls = {}
        self.zone_scores = {}
        self.quadtree = None
        self.sound_manager = sound_manager
        self.debug = True
        self.load_zones()
        self.build_quadtree()

    def load_zones(self):
        """Load zones from a pickle file."""
        if os.path.exists("zones.pkl"):
            with open("zones.pkl", "rb") as f:
                self.zones = pickle.load(f)
            print(f"Loaded {len(self.zones)} zones.")
        else:
            print("No zones.pkl file found, starting with empty zones.")

    def save_zones(self):
        """Save zones to a pickle file."""
        try:
            with open("zones.pkl", "wb") as f:
                pickle.dump(self.zones, f)
            print(f"Saved {len(self.zones)} zones to zones.pkl")
        except Exception as e:
            print(f"Error saving zones: {e}")

    def build_quadtree(self):
        """Rebuild the quadtree for efficient lookups."""
        boundary = Boundary(0, 0, self.reference_width, self.reference_height)
        self.quadtree = Quadtree(boundary, capacity=4)
        for zone in self.zones:
            x, y = zone[:2]
            self.quadtree.insert((x, y, zone))

    def check_scores(self, balls, current_width, current_height):
        """Optimized scoring using Quadtrees for spatial queries, including both circular and rectangular zones."""
        total_score = 0
        scale_x = current_width / self.reference_width
        scale_y = current_height / self.reference_height
        
        for ball in balls:
            x, y, _, _, ball_type, _, ball_id, _ = ball
            scaled_x = x * scale_x
            scaled_y = y * scale_y
            
            # Query the quadtree for nearby zones
            possible_zones = self.quadtree.query((scaled_x, scaled_y))
            
            best_score = 0
            best_zone_idx = None
            for zone in possible_zones:
                if len(zone) == 4:  # Circle zone
                    zx, zy, radius, points = zone
                    if np.sqrt((scaled_x - zx)**2 + (scaled_y - zy)**2) <= radius:
                        adjusted_points = points * (2.0 if ball_type == "red" else 1.5 if ball_type == "half" else 1.0)
                        if adjusted_points > best_score:
                            best_score = adjusted_points
                            best_zone_idx = self.zones.index(zone)
                else:  # Rectangle zone
                    zx, zy, zw, zh, points = zone
                    if zx <= scaled_x <= zx + zw and zy <= scaled_y <= zy + zh:
                        adjusted_points = points * (2.0 if ball_type == "red" else 1.5 if ball_type == "half" else 1.0)
                        if adjusted_points > best_score:
                            best_score = adjusted_points
                            best_zone_idx = self.zones.index(zone)
            
            if best_zone_idx is not None and ball_id not in self.scored_balls:
                total_score += best_score
                self.scored_balls[ball_id] = best_zone_idx
                if self.debug:
                    print(f"Ball {ball_id} scored {best_score} points in zone {best_zone_idx} at position ({scaled_x:.1f}, {scaled_y:.1f}).")
                if self.sound_manager:
                    self.sound_manager.play_sound_effect("score")
            elif self.debug and best_zone_idx is None:
                print(f"Ball {ball_id} (type={ball_type}) at ({scaled_x:.1f}, {scaled_y:.1f}) not in any zone.")
        
        return total_score

    def draw_zones(self, frame, current_width, current_height):
        """Draw scoring zones on the frame, scaled to the current resolution."""
        scale_x = current_width / self.reference_width
        scale_y = current_height / self.reference_height

        for zone in self.zones:
            if len(zone) == 4:  # Circle zone
                zx, zy, radius, points = zone
                scaled_x = int(zx * scale_x)
                scaled_y = int(zy * scale_y)
                scaled_radius = int(radius * scale_x)  # Use scale_x for radius to maintain aspect
                cv2.circle(frame, (scaled_x, scaled_y), scaled_radius, (0, 255, 0), 2)
                if self.debug:
                    label = f"{points} pts"
                    cv2.putText(frame, label, (scaled_x + 10, scaled_y - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            else:  # Rectangle zone
                zx, zy, zw, zh, points = zone
                scaled_x = int(zx * scale_x)
                scaled_y = int(zy * scale_y)
                scaled_w = int(zw * scale_x)
                scaled_h = int(zh * scale_y)
                cv2.rectangle(frame, (scaled_x, scaled_y), 
                             (scaled_x + scaled_w, scaled_y + scaled_h), (0, 255, 0), 2)
                if self.debug:
                    label = f"{points} pts"
                    cv2.putText(frame, label, (scaled_x + 10, scaled_y - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        return frame

    def reset_scored_balls(self):
        """Reset the scored balls dictionary."""
        self.scored_balls.clear()
        if self.debug:
            print("Reset scored balls dictionary.")