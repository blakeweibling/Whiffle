# zone_utils.py
import json
import os
import time
import cv2
import numpy as np
from collections import deque

class ZoneManager:
    """Manages zone data, including loading and saving zones and zone sets."""
    def __init__(self, scoring_zones):
        self.scoring_zones = scoring_zones
        self.zones = scoring_zones.zones
        self.zone_sets = {"default": []}
        self.current_zone_set = "default"
        self.load_zone_sets()

    def load_zone_sets(self):
        """Load zone sets from a JSON file."""
        if os.path.exists("zone_sets.json"):
            try:
                with open("zone_sets.json", "r") as f:
                    self.zone_sets = json.load(f)
                print(f"Loaded zone sets: {list(self.zone_sets.keys())}")
            except Exception as e:
                print(f"Error loading zone sets: {e}")
                self.zone_sets = {"default": []}
        else:
            self.zone_sets = {"default": []}
            self.save_zone_sets()

    def save_zone_sets(self):
        """Save zone sets to a JSON file."""
        try:
            with open("zone_sets.json", "w") as f:
                json.dump(self.zone_sets, f, indent=4)
            print(f"Saved zone sets: {list(self.zone_sets.keys())}")
        except Exception as e:
            print(f"Error saving zone sets: {e}")

    def save_current_zone_set(self):
        """Save the current zones to the current zone set."""
        self.zone_sets[self.current_zone_set] = [zone[:] for zone in self.zones]
        self.save_zone_sets()

    def load_zone_set(self, set_name, undo_redo):
        """Load a specific zone set."""
        if set_name in self.zone_sets:
            undo_redo.save_state("load_zone_set")
            self.current_zone_set = set_name
            self.zones.clear()
            self.zones.extend([zone[:] for zone in self.zone_sets[set_name]])
            self.scoring_zones.save_zones()
            print(f"Loaded zone set: {set_name}")
        else:
            print(f"Zone set {set_name} not found")

    def save_zone_set(self, set_name, undo_redo):
        """Save the current zones as a new zone set."""
        undo_redo.save_state("save_zone_set")
        self.current_zone_set = set_name
        self.zone_sets[set_name] = [zone[:] for zone in self.zones]
        self.save_zone_sets()
        print(f"Saved current zones as zone set: {set_name}")

    def delete_zone_set(self, set_name, undo_redo):
        """Delete a zone set."""
        if set_name in self.zone_sets and set_name != "default":
            undo_redo.save_state("delete_zone_set")
            del self.zone_sets[set_name]
            if self.current_zone_set == set_name:
                self.current_zone_set = "default"
                self.load_zone_set("default", undo_redo)
            self.save_zone_sets()
            print(f"Deleted zone set: {set_name}")
        else:
            print(f"Cannot delete zone set {set_name}")

class ZoneAnimator:
    """Manages animations for zones, such as fade-out and scale-up effects."""
    def __init__(self):
        self.animations = []
        self.animation_duration = 0.5

    def ease_in_out(self, t):
        """Apply an ease-in-out function for smoother animations."""
        return t * t * (3 - 2 * t) if t < 0.5 else 1 - (1 - t) * (1 - t) * (3 - 2 * (1 - t))

    def start_fade_out(self, zone, zone_idx):
        """Start a fade-out animation for a deleted zone."""
        self.animations.append({
            "type": "fade_out",
            "zone": zone,
            "start_time": time.time(),
            "duration": self.animation_duration,
            "zone_idx": zone_idx
        })

    def start_scale_up(self, zone, zone_idx):
        """Start a scale-up animation for a newly added zone."""
        self.animations.append({
            "type": "scale_up",
            "zone": zone,
            "start_time": time.time(),
            "duration": self.animation_duration,
            "zone_idx": zone_idx
        })

    def update_animations(self, frame, scale_x, scale_y):
        """Update and draw active animations on the frame."""
        current_time = time.time()
        self.animations = [anim for anim in self.animations if current_time < anim["start_time"] + anim["duration"]]
        for anim in self.animations:
            t = (current_time - anim["start_time"]) / anim["duration"]
            t = self.ease_in_out(t)
            zone = anim["zone"]
            if anim["type"] == "fade_out":
                alpha = 1.0 - t
                color = (0, 0, 255, int(255 * alpha))
                if len(zone) == 4:  # Circle
                    x, y, radius, points = zone
                    scaled_x = int(x * scale_x)
                    scaled_y = int(y * scale_y)
                    scaled_radius = int(radius * min(scale_x, scale_y))
                    cv2.circle(frame, (scaled_x, scaled_y), scaled_radius, color[:3], 2)
                    cv2.putText(frame, f"Points: {points}", (scaled_x - scaled_radius, scaled_y - scaled_radius - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color[:3], 1)
                else:  # Rectangle
                    x, y, w, h, points = zone
                    scaled_x = int(x * scale_x)
                    scaled_y = int(y * scale_y)
                    scaled_w = int(w * scale_x)
                    scaled_h = int(h * scale_y)
                    cv2.rectangle(frame, (scaled_x, scaled_y), (scaled_x + scaled_w, scaled_y + scaled_h), color[:3], 2)
                    cv2.putText(frame, f"Points: {points}", (scaled_x + 5, scaled_y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color[:3], 1)
            elif anim["type"] == "scale_up":
                scale = 0.5 + 0.5 * t
                if len(zone) == 4:  # Circle
                    x, y, radius, points = zone
                    scaled_x = int(x * scale_x)
                    scaled_y = int(y * scale_y)
                    scaled_radius = int(radius * min(scale_x, scale_y) * scale)
                    cv2.circle(frame, (scaled_x, scaled_y), scaled_radius, (0, 255, 0), 2)
                    cv2.putText(frame, f"Points: {points}", (scaled_x - scaled_radius, scaled_y - scaled_radius - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                else:  # Rectangle
                    x, y, w, h, points = zone
                    scaled_x = int(x * scale_x)
                    scaled_y = int(y * scale_y)
                    scaled_w = int(w * scale_x * scale)
                    scaled_h = int(h * scale_y * scale)
                    dx = (w * scale_x * (1 - scale)) / 2
                    dy = (h * scale_y * (1 - scale)) / 2
                    cv2.rectangle(frame, (int(scaled_x + dx), int(scaled_y + dy)),
                                 (int(scaled_x + scaled_w + dx), int(scaled_y + scaled_h + dy)), (0, 255, 0), 2)
                    cv2.putText(frame, f"Points: {points}", (int(scaled_x + dx + 5), int(scaled_y + dy - 10)),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

class UndoRedoHandler:
    """Manages undo and redo functionality for zone changes."""
    def __init__(self):
        self.undo_stack = deque(maxlen=50)
        self.redo_stack = deque(maxlen=50)

    def save_state(self, action, zones):
        """Save the current state to the undo stack and clear the redo stack."""
        state = {
            "zones": [zone[:] for zone in zones],
            "action": action
        }
        self.undo_stack.append(state)
        self.redo_stack.clear()
        print(f"Saved state for action: {action}")

    def undo(self, zones, scoring_zones):
        """Undo the last action."""
        if not self.undo_stack:
            print("Nothing to undo")
            return
        current_state = {
            "zones": [zone[:] for zone in zones],
            "action": "undo"
        }
        self.redo_stack.append(current_state)
        state = self.undo_stack.pop()
        zones.clear()
        zones.extend([zone[:] for zone in state["zones"]])
        scoring_zones.save_zones()
        print(f"Undid action: {state['action']}")

    def redo(self, zones, scoring_zones):
        """Redo the last undone action."""
        if not self.redo_stack:
            print("Nothing to redo")
            return
        current_state = {
            "zones": [zone[:] for zone in zones],
            "action": "redo"
        }
        self.undo_stack.append(current_state)
        state = self.redo_stack.pop()
        zones.clear()
        zones.extend([zone[:] for zone in state["zones"]])
        scoring_zones.save_zones()
        print(f"Redid action: {state['action']}")