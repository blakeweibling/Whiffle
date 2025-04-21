import pickle
import os
import numpy as np
import cv2
import time
from quadtree import Quadtree, Boundary

class ScoringZones:
    """Optimized scoring system using Quadtrees for efficient spatial lookups."""
    def __init__(self, reference_width=1280, reference_height=720, sound_manager=None):
        self.reference_width = reference_width
        self.reference_height = reference_height
        self.zones = []
        self.scored_balls = {}  # Tracks which balls have been scored
        self.zone_occupancy = {}  # Tracks which ball occupies each zone (zone_idx -> ball_id)
        self.frame_counter = 0  # For periodic logging
        self.quadtree = None
        self.sound_manager = sound_manager
        self.debug = True  # Debug mode for detailed logging
        self.load_zones()
        print(f"ScoringZones initialized with reference resolution {self.reference_width}x{self.reference_height}")

    def load_zones(self):
        """Load zones from a pickle file and rebuild the quadtree."""
        if os.path.exists("zones.pkl"):
            with open("zones.pkl", "rb") as f:
                self.zones = pickle.load(f)
            print(f"Loaded {len(self.zones)} zones.")
            if self.debug:
                for idx, zone in enumerate(self.zones):
                    if len(zone) == 4:
                        print(f"Zone {idx}: Circle at ({zone[0]}, {zone[1]}), radius={zone[2]}, points={zone[3]}")
                    else:
                        print(f"Zone {idx}: Rectangle at ({zone[0]}, {zone[1]}), size=({zone[2]}x{zone[3]}), points={zone[4]}")
        else:
            print("No zones.pkl file found, starting with empty zones.")
        self.build_quadtree()

    def save_zones(self):
        """Save zones to a pickle file and rebuild the quadtree."""
        try:
            with open("zones.pkl", "wb") as f:
                pickle.dump(self.zones, f)
            print(f"Saved {len(self.zones)} zones to zones.pkl")
            self.build_quadtree()
        except Exception as e:
            print(f"Error saving zones: {e}")

    def build_quadtree(self):
        """Rebuild the quadtree for efficient lookups."""
        boundary = Boundary(0, 0, self.reference_width, self.reference_height)
        self.quadtree = Quadtree(boundary, capacity=8)
        for zone in self.zones:
            if len(zone) == 4:  # Circle zone
                x, y, radius, _ = zone
                x_min = x - radius
                y_min = y - radius
                x_max = x + radius
                y_max = y + radius
            else:  # Rectangle zone
                x, y, w, h, _ = zone
                x_min = x
                y_min = y
                x_max = x + w
                y_max = y + h
            self.quadtree.insert((x_min, y_min, x_max, y_max, zone))
        if self.debug:
            print(f"Quadtree rebuilt with {len(self.zones)} zones.")

    def check_scores(self, balls, current_width, current_height):
        """Optimized scoring using Quadtrees, limiting one ball per zone."""
        scale_x = current_width / self.reference_width
        scale_y = current_height / self.reference_height

        frame_score = 0
        scored_balls = []
        occupied_zones = set()

        # First, check which zones are still occupied
        current_occupancy = {}
        for ball in balls:
            x, y, _, _, ball_type, _, ball_id, _ = ball
            scaled_x = x * scale_x
            scaled_y = y * scale_y

            possible_zones = self.quadtree.query(scaled_x, scaled_y)

            best_score = 0
            best_zone_idx = None
            for zone in possible_zones:
                if len(zone) == 4:  # Circle zone
                    zx, zy, radius, points = zone
                    scaled_zx = zx * scale_x
                    scaled_zy = zy * scale_y
                    scaled_radius = radius * scale_x
                    distance = np.sqrt((scaled_x - scaled_zx)**2 + (scaled_y - scaled_zy)**2)
                    if distance <= scaled_radius:
                        adjusted_points = points * (2.0 if ball_type == "red" else 1.5 if ball_type == "half" else 1.0)
                        if adjusted_points > best_score:
                            best_score = adjusted_points
                            best_zone_idx = self.zones.index(zone)
                else:  # Rectangle zone
                    zx, zy, zw, zh, points = zone
                    scaled_zx = zx * scale_x
                    scaled_zy = zy * scale_y
                    scaled_zw = zw * scale_x
                    scaled_zh = zh * scale_y
                    if scaled_zx <= scaled_x <= scaled_zx + scaled_zw and scaled_zy <= scaled_y <= scaled_zy + scaled_zh:
                        adjusted_points = points * (2.0 if ball_type == "red" else 1.5 if ball_type == "half" else 1.0)
                        if adjusted_points > best_score:
                            best_score = adjusted_points
                            best_zone_idx = self.zones.index(zone)

            if best_zone_idx is not None:
                current_occupancy[best_zone_idx] = ball_id

        # Clear zones that are no longer occupied
        zones_to_clear = [zone_idx for zone_idx, occupant in self.zone_occupancy.items() if zone_idx not in current_occupancy]
        for zone_idx in zones_to_clear:
            del self.zone_occupancy[zone_idx]
            if self.debug:
                print(f"Cleared zone {zone_idx} as it is no longer occupied")

        # Now score the balls
        for ball in balls:
            x, y, _, _, ball_type, _, ball_id, _ = ball
            scaled_x = x * scale_x
            scaled_y = y * scale_y

            possible_zones = self.quadtree.query(scaled_x, scaled_y)

            best_score = 0
            best_zone_idx = None
            for zone in possible_zones:
                if len(zone) == 4:  # Circle zone
                    zx, zy, radius, points = zone
                    scaled_zx = zx * scale_x
                    scaled_zy = zy * scale_y
                    scaled_radius = radius * scale_x
                    distance = np.sqrt((scaled_x - scaled_zx)**2 + (scaled_y - scaled_zy)**2)
                    if distance <= scaled_radius:
                        adjusted_points = points * (2.0 if ball_type == "red" else 1.5 if ball_type == "half" else 1.0)
                        if adjusted_points > best_score:
                            best_score = adjusted_points
                            best_zone_idx = self.zones.index(zone)
                else:  # Rectangle zone
                    zx, zy, zw, zh, points = zone
                    scaled_zx = zx * scale_x
                    scaled_zy = zy * scale_y
                    scaled_zw = zw * scale_x
                    scaled_zh = zh * scale_y
                    if scaled_zx <= scaled_x <= scaled_zx + scaled_zw and scaled_zy <= scaled_y <= scaled_zy + scaled_zh:
                        adjusted_points = points * (2.0 if ball_type == "red" else 1.5 if ball_type == "half" else 1.0)
                        if adjusted_points > best_score:
                            best_score = adjusted_points
                            best_zone_idx = self.zones.index(zone)

            if best_zone_idx is not None:
                if ball_id not in self.scored_balls:
                    current_occupant = self.zone_occupancy.get(best_zone_idx)
                    if current_occupant is None or current_occupant != ball_id:
                        final_score = best_score
                        frame_score += final_score
                        self.scored_balls[ball_id] = best_zone_idx
                        self.zone_occupancy[best_zone_idx] = ball_id
                        occupied_zones.add(best_zone_idx)
                        scored_balls.append((ball_id, ball_type, best_zone_idx, final_score))
                        print(f"Ball {ball_id} (type={ball_type}) scored {final_score} in zone {best_zone_idx}")
                        if self.debug:
                            print(f"Ball {ball_id} (type={ball_type}) at ({scaled_x:.1f}, {scaled_y:.1f}) scored {final_score} in zone {best_zone_idx}")
                        if self.sound_manager:
                            self.sound_manager.play_sound_effect("score")
                elif self.scored_balls[ball_id] == best_zone_idx:
                    continue
                else:
                    if self.debug:
                        print(f"Ball {ball_id} moved to zone {best_zone_idx} but already scored in zone {self.scored_balls[ball_id]}")

        # Periodic logging (every 10 frames, only in debug mode)
        self.frame_counter += 1
        if self.frame_counter % 10 == 0 and self.debug:
            print("Current ball states:")
            for ball in balls:
                x, y, _, _, ball_type, _, ball_id, _ = ball
                scaled_x = x * scale_x
                scaled_y = y * scale_y
                in_zone = None
                for zone_idx, zone in enumerate(self.zones):
                    if zone_idx in occupied_zones:
                        continue
                    if len(zone) == 4:
                        zx, zy, radius, _ = zone
                        scaled_zx = zx * scale_x
                        scaled_zy = zy * scale_y
                        scaled_radius = radius * scale_x
                        if np.sqrt((scaled_x - scaled_zx)**2 + (scaled_y - scaled_zy)**2) <= scaled_radius:
                            in_zone = zone_idx
                            break
                    else:
                        zx, zy, zw, zh, _ = zone
                        scaled_zx = zx * scale_x
                        scaled_zy = zy * scale_y
                        scaled_zw = zw * scale_x
                        scaled_zh = zh * scale_y
                        if scaled_zx <= scaled_x <= scaled_zx + scaled_zw and scaled_zy <= scaled_y <= scaled_zy + scaled_zh:
                            in_zone = zone_idx
                            break
                status = "scored" if ball_id in self.scored_balls else "not scored"
                zone_info = f"in zone {in_zone}" if in_zone is not None else "not in any zone"
                print(f"Ball {ball_id} (type={ball_type}) at ({scaled_x:.1f}, {scaled_y:.1f}): {zone_info}, {status}")

        return frame_score

    def draw_zones(self, frame, current_width, current_height):
        """Draw scoring zones on the frame, scaled to the current resolution."""
        scale_x = current_width / self.reference_width
        scale_y = current_height / self.reference_height

        for idx, zone in enumerate(self.zones):
            color = (0, 255, 0) if idx not in self.zone_occupancy else (255, 0, 0)  # Green if free, red if occupied

            if len(zone) == 4:  # Circle zone
                zx, zy, radius, points = zone
                scaled_x = int(zx * scale_x)
                scaled_y = int(zy * scale_y)
                scaled_radius = int(radius * scale_x)
                cv2.circle(frame, (scaled_x, scaled_y), scaled_radius, color, 2)
                if self.debug:
                    cv2.putText(frame, f"{points} pts", (scaled_x + 10, scaled_y - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            else:  # Rectangle zone
                zx, zy, zw, zh, points = zone
                scaled_x = int(zx * scale_x)
                scaled_y = int(zy * scale_y)
                scaled_w = int(zw * scale_x)
                scaled_h = int(zh * scale_y)
                cv2.rectangle(frame, (scaled_x, scaled_y), 
                             (scaled_x + scaled_w, scaled_y + scaled_h), color, 2)
                if self.debug:
                    cv2.putText(frame, f"{points} pts", (scaled_x + 10, scaled_y - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        return frame

    def reset_scored_balls(self):
        """Reset the scored balls dictionary and zone occupancy."""
        self.scored_balls.clear()
        self.zone_occupancy.clear()
        self.frame_counter = 0
        if self.debug:
            print("Reset scored balls and zone occupancy.")