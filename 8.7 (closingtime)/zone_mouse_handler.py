# zone_mouse_handler.py
import cv2
import numpy as np

class ZoneMouseHandler:
    """Handles mouse events for the ZoneCalibrator."""
    def __init__(self, calibrator):
        self.calibrator = calibrator

    def get_zone_at_position(self, x, y, scale_x, scale_y):
        """Check if the given position (x, y) is inside any existing zone."""
        for idx, zone in enumerate(self.calibrator.zones):
            if len(zone) == 4:  # Circle
                zx, zy, radius, _ = zone
                scaled_zx = zx * scale_x
                scaled_zy = zy * scale_y
                scaled_radius = radius * min(scale_x, scale_y)
                distance = np.sqrt((x - scaled_zx)**2 + (y - scaled_zy)**2)
                if distance <= scaled_radius:
                    return idx
            else:  # Rectangle
                zx, zy, zw, zh, _ = zone
                scaled_zx = zx * scale_x
                scaled_zy = zy * scale_y
                scaled_zw = zw * scale_x
                scaled_zh = zh * scale_y
                if scaled_zx <= x <= scaled_zx + scaled_zw and scaled_zy <= y <= scaled_zy + scaled_zh:
                    return idx
        return None

    def get_resize_handle(self, x, y, zone, scale_x, scale_y):
        """Check if the position (x, y) is over a resize handle of the given zone."""
        if len(zone) != 5:  # Only rectangles have resize handles
            return None
        zx, zy, zw, zh, _ = zone
        scaled_zx = zx * scale_x
        scaled_zy = zy * scale_y
        scaled_zw = zw * scale_x
        scaled_zh = zh * scale_y
        handle_size = 10
        handles = {
            "top-left": (scaled_zx, scaled_zy),
            "top-right": (scaled_zx + scaled_zw, scaled_zy),
            "bottom-left": (scaled_zx, scaled_zy + scaled_zh),
            "bottom-right": (scaled_zx + scaled_zw, scaled_zy + scaled_zh)
        }
        for handle_name, (hx, hy) in handles.items():
            if (hx - handle_size <= x <= hx + handle_size and
                hy - handle_size <= y <= hy + handle_size):
                return handle_name
        return None

    def mouse_callback(self, event, x, y, flags, frame, scale_x, scale_y):
        """Handle mouse events for zone calibration."""
        if not self.calibrator.calibrating:
            return

        # Handle mouse events for the help window first
        if self.calibrator.help_window:
            self.calibrator.help_window.mouse_callback(event, x, y, flags)

        # Check if the mouse event is within the HelpWindow's bounds when it's visible
        if (self.calibrator.help_window and self.calibrator.help_window.is_visible and
                self.calibrator.help_window.is_point_inside(x, y)):
            # If the event is within the HelpWindow, skip zone-related actions
            return

        # Handle clicks on the "Help" button to reopen the help window
        if self.calibrator.help_button_rect and event == cv2.EVENT_LBUTTONDOWN:
            bx, by, bw, bh = self.calibrator.help_button_rect
            if bx <= x <= bx + bw and by <= y <= by + bh:
                if self.calibrator.help_window:
                    self.calibrator.help_window.toggle_visibility()
                return

        scaled_x = x / scale_x
        scaled_y = y / scale_y
        self.calibrator.hovered_zone_idx = self.get_zone_at_position(scaled_x, scaled_y, scale_x, scale_y)

        if self.calibrator.is_editing and self.calibrator.selected_zone_idx is not None:
            self.calibrator.resize_handle = self.get_resize_handle(scaled_x, scaled_y, self.calibrator.zones[self.calibrator.selected_zone_idx], scale_x, scale_y)
        else:
            self.calibrator.resize_handle = None

        zone_idx = self.calibrator.hovered_zone_idx

        if event == cv2.EVENT_LBUTTONDOWN:
            if self.calibrator.resize_handle:
                self.calibrator.start_point = (scaled_x, scaled_y)
            elif zone_idx is not None and not self.calibrator.is_editing:
                self.calibrator.undo_redo.save_state("start_edit", self.calibrator.zones)
                self.calibrator.selected_zone_idx = zone_idx
                self.calibrator.is_editing = True
                self.calibrator.start_point = None
                self.calibrator.end_point = None
                self.calibrator.pending_zone = None
                self.calibrator.current_points = self.calibrator.zones[zone_idx][-1]
                print(f"Editing zone {zone_idx}")
            elif not self.calibrator.is_editing:
                self.calibrator.start_point = (scaled_x, scaled_y)
                self.calibrator.pending_zone = None
                self.calibrator.selected_zone_idx = None
                self.calibrator.current_points = 0
        elif event == cv2.EVENT_RBUTTONDOWN and zone_idx is not None:
            self.calibrator.undo_redo.save_state("delete", self.calibrator.zones)
            deleted_zone = self.calibrator.zones.pop(zone_idx)
            self.calibrator.animator.start_fade_out(deleted_zone, zone_idx)
            self.calibrator.scoring_zones.save_zones()
            self.calibrator.manager.save_current_zone_set()
            print(f"Deleted zone {zone_idx}: {deleted_zone}")
            if self.calibrator.selected_zone_idx == zone_idx:
                self.calibrator.selected_zone_idx = None
                self.calibrator.is_editing = False
            elif self.calibrator.selected_zone_idx is not None and zone_idx < self.calibrator.selected_zone_idx:
                self.calibrator.selected_zone_idx -= 1
            if self.calibrator.hovered_zone_idx == zone_idx:
                self.calibrator.hovered_zone_idx = None
            elif self.calibrator.hovered_zone_idx is not None and zone_idx < self.calibrator.hovered_zone_idx:
                self.calibrator.hovered_zone_idx -= 1
        elif event == cv2.EVENT_LBUTTONUP and not self.calibrator.is_editing:
            if self.calibrator.start_point:
                self.calibrator.end_point = (scaled_x, scaled_y)
                x1, y1 = self.calibrator.start_point
                x2, y2 = self.calibrator.end_point
                if self.calibrator.is_rectangle_mode:
                    width = abs(x2 - x1)
                    height = abs(y2 - y1)
                    x = min(x1, x2)
                    y = min(y1, y2)
                    self.calibrator.pending_zone = [x, y, width, height, 0]
                else:
                    radius = int(np.sqrt((x2 - x1)**2 + (y2 - y1)**2))
                    self.calibrator.pending_zone = [x1, y1, radius, 0]
        elif event == cv2.EVENT_MOUSEMOVE and self.calibrator.start_point and not self.calibrator.end_point and not self.calibrator.is_editing:
            self.calibrator.end_point = (scaled_x, scaled_y)
        elif event == cv2.EVENT_LBUTTONDOWN and self.calibrator.is_editing and not self.calibrator.resize_handle:
            if self.calibrator.selected_zone_idx is not None:
                self.calibrator.undo_redo.save_state("reposition", self.calibrator.zones)
                zone = self.calibrator.zones[self.calibrator.selected_zone_idx]
                if len(zone) == 4:
                    zone[0] = scaled_x
                    zone[1] = scaled_y
                else:
                    zone[0] = scaled_x
                    zone[1] = scaled_y
                self.calibrator.scoring_zones.save_zones()
                self.calibrator.manager.save_current_zone_set()
                print(f"Updated position of zone {self.calibrator.selected_zone_idx} to ({scaled_x}, {scaled_y})")
        elif event == cv2.EVENT_MOUSEMOVE and flags & cv2.EVENT_FLAG_LBUTTON and self.calibrator.is_editing:
            if self.calibrator.resize_handle and self.calibrator.start_point:
                self.calibrator.undo_redo.save_state("resize_handle", self.calibrator.zones)
                zone = self.calibrator.zones[self.calibrator.selected_zone_idx]
                x0, y0 = zone[0], zone[1]
                if self.calibrator.resize_handle == "top-left":
                    w = zone[2] + (x0 - scaled_x)
                    h = zone[3] + (y0 - scaled_y)
                    zone[0] = scaled_x
                    zone[1] = scaled_y
                elif self.calibrator.resize_handle == "top-right":
                    w = scaled_x - x0
                    h = zone[3] + (y0 - scaled_y)
                    zone[1] = scaled_y
                elif self.calibrator.resize_handle == "bottom-left":
                    w = zone[2] + (x0 - scaled_x)
                    h = scaled_y - y0
                    zone[0] = scaled_x
                elif self.calibrator.resize_handle == "bottom-right":
                    w = scaled_x - x0
                    h = scaled_y - y0
                zone[2] = max(10, w)
                zone[3] = max(10, h)
                self.calibrator.scoring_zones.save_zones()
                self.calibrator.manager.save_current_zone_set()
                print(f"Resized zone {self.calibrator.selected_zone_idx} using {self.calibrator.resize_handle}")
            elif self.calibrator.is_editing and not self.calibrator.resize_handle:
                self.calibrator.undo_redo.save_state("resize", self.calibrator.zones)
                zone = self.calibrator.zones[self.calibrator.selected_zone_idx]
                if len(zone) == 4:
                    x1, y1 = zone[0], zone[1]
                    radius = int(np.sqrt((scaled_x - x1)**2 + (scaled_y - y1)**2))
                    zone[2] = max(10, radius)
                else:
                    x1, y1 = zone[0], zone[1]
                    width = abs(scaled_x - x1)
                    height = abs(scaled_y - y1)
                    zone[2] = max(10, width)
                    zone[3] = max(10, height)
                self.calibrator.scoring_zones.save_zones()
                self.calibrator.manager.save_current_zone_set()
                print(f"Resized zone {self.calibrator.selected_zone_idx}")