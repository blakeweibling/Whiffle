import cv2
import numpy as np
from zone_utils import ZoneManager, ZoneAnimator, UndoRedoHandler

class HelpWindow:
    """A draggable, semi-transparent window to display help text in the calibration window."""
    def __init__(self, help_text, initial_x, initial_y, width, height):
        self.help_text = help_text
        self.pos_x = initial_x
        self.pos_y = initial_y
        self.width = width
        self.height = height
        self.is_dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.header_rect = None
        self.close_button_rect = None
        self.is_visible = True

    def mouse_callback(self, event, x, y, flags):
        """Handle mouse events for dragging and closing the help window."""
        if not self.is_visible:
            return

        # Define the header area for dragging
        header_x, header_y, header_w, header_h = self.header_rect
        if event == cv2.EVENT_LBUTTONDOWN and header_x <= x <= header_x + header_w and header_y <= y <= header_y + header_h:
            self.is_dragging = True
            self.drag_offset_x = x - self.pos_x
            self.drag_offset_y = y - self.pos_y
        elif event == cv2.EVENT_MOUSEMOVE and self.is_dragging:
            self.pos_x = x - self.drag_offset_x
            self.pos_y = y - self.drag_offset_y
        elif event == cv2.EVENT_LBUTTONUP and self.is_dragging:
            self.is_dragging = False

        # Handle the close button
        if self.close_button_rect:
            cx, cy, cw, ch = self.close_button_rect
            if event == cv2.EVENT_LBUTTONDOWN and cx <= x <= cx + cw and cy <= y <= cy + ch:
                self.is_visible = False
                print("Help window closed")

    def draw(self, frame):
        """Draw the help window on the frame with semi-transparency."""
        if not self.is_visible:
            return frame

        overlay = frame.copy()
        h, w = frame.shape[:2]

        # Ensure the window stays within bounds
        self.pos_x = max(0, min(self.pos_x, w - self.width))
        self.pos_y = max(0, min(self.pos_y, h - self.height))
        x1, y1 = self.pos_x, self.pos_y
        x2, y2 = x1 + self.width, y1 + self.height

        # Draw the window background with semi-transparency
        alpha = 0.8  # Semi-transparency factor
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (100, 100, 100), -1)
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (150, 150, 150), 2)

        # Draw a draggable header
        header_height = 30
        cv2.rectangle(overlay, (x1, y1), (x2, y1 + header_height), (80, 80, 80), -1)
        cv2.rectangle(overlay, (x1, y1), (x2, y1 + header_height), (150, 150, 150), 1)
        self.header_rect = (x1, y1, x2 - x1, header_height)

        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.7
        thickness = 2
        title = "Help"
        text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
        text_x = x1 + ((x2 - x1) - text_size[0]) // 2
        text_y = y1 + header_height // 2 + text_size[1] // 2
        cv2.putText(overlay, title, (text_x, text_y), font, font_scale, (220, 220, 220), thickness)

        # Draw the close button
        close_x = x2 - 40
        close_y = y1 + 5
        close_w, close_h = 30, 20
        self.close_button_rect = (close_x, close_y, close_w, close_h)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 255), -1)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("X", font, 0.5, 1)[0]
        text_x = close_x + (close_w - text_size[0]) // 2
        text_y = close_y + (close_h + text_size[1]) // 2
        cv2.putText(overlay, "X", (text_x, text_y), font, 0.5, (255, 255, 255), 1)

        # Draw the help text
        font_scale = 0.5
        thickness = 1
        lines = self.help_text.split('\n')
        for i, line in enumerate(lines):
            y_pos = y1 + header_height + 20 + i * 20
            cv2.putText(overlay, line, (x1 + 10, y_pos), font, font_scale, (220, 220, 220), thickness)

        # Apply semi-transparency
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

class ZoneCalibrator:
    """Handles the calibration of scoring zones with a graphical interface."""
    def __init__(self, scoring_zones):
        self.manager = ZoneManager(scoring_zones)
        self.animator = ZoneAnimator()
        self.undo_redo = UndoRedoHandler()
        self.zones = self.manager.zones
        self.scoring_zones = scoring_zones
        self.calibrating = False
        self.start_point = None
        self.end_point = None
        self.pending_zone = None
        self.current_points = 0
        self.is_rectangle_mode = False
        self.exit_method = None
        self.selected_zone_idx = None
        self.is_editing = False
        self.hovered_zone_idx = None
        self.resize_handle = None
        self.help_window = None

    def get_zone_at_position(self, x, y, scale_x, scale_y):
        """Check if the given position (x, y) is inside any existing zone."""
        for idx, zone in enumerate(self.zones):
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

    def toggle_zone_shape(self, zone_idx):
        """Toggle the shape of the zone at the given index between circle and rectangle."""
        if zone_idx is None or zone_idx >= len(self.zones):
            return
        self.undo_redo.save_state("toggle_shape", self.zones)
        zone = self.zones[zone_idx]
        if len(zone) == 4:  # Circle to Rectangle
            x, y, radius, points = zone
            side = int(np.sqrt(np.pi * radius**2))
            self.zones[zone_idx] = [x - side//2, y - side//2, side, side, points]
        else:  # Rectangle to Circle
            x, y, w, h, points = zone
            radius = int(np.sqrt(w * h / np.pi))
            self.zones[zone_idx] = [x + w//2, y + h//2, radius, points]
        self.scoring_zones.save_zones()
        self.manager.save_current_zone_set()
        print(f"Toggled shape for zone {zone_idx}")

    def mouse_callback(self, event, x, y, flags, frame, scale_x, scale_y):
        """Handle mouse events for zone calibration."""
        if not self.calibrating:
            return

        # Handle mouse events for the help window
        if self.help_window:
            self.help_window.mouse_callback(event, x, y, flags)

        scaled_x = x / scale_x
        scaled_y = y / scale_y
        self.hovered_zone_idx = self.get_zone_at_position(scaled_x, scaled_y, scale_x, scale_y)

        if self.is_editing and self.selected_zone_idx is not None:
            self.resize_handle = self.get_resize_handle(scaled_x, scaled_y, self.zones[self.selected_zone_idx], scale_x, scale_y)
        else:
            self.resize_handle = None

        zone_idx = self.hovered_zone_idx

        if event == cv2.EVENT_LBUTTONDOWN:
            if self.resize_handle:
                self.start_point = (scaled_x, scaled_y)
            elif zone_idx is not None and not self.is_editing:
                self.undo_redo.save_state("start_edit", self.zones)
                self.selected_zone_idx = zone_idx
                self.is_editing = True
                self.start_point = None
                self.end_point = None
                self.pending_zone = None
                self.current_points = self.zones[zone_idx][-1]
                print(f"Editing zone {zone_idx}")
            elif not self.is_editing:
                self.start_point = (scaled_x, scaled_y)
                self.pending_zone = None
                self.selected_zone_idx = None
                self.current_points = 0
        elif event == cv2.EVENT_RBUTTONDOWN and zone_idx is not None:
            self.undo_redo.save_state("delete", self.zones)
            deleted_zone = self.zones.pop(zone_idx)
            self.animator.start_fade_out(deleted_zone, zone_idx)
            self.scoring_zones.save_zones()
            self.manager.save_current_zone_set()
            print(f"Deleted zone {zone_idx}: {deleted_zone}")
            if self.selected_zone_idx == zone_idx:
                self.selected_zone_idx = None
                self.is_editing = False
            elif self.selected_zone_idx is not None and zone_idx < self.selected_zone_idx:
                self.selected_zone_idx -= 1
            if self.hovered_zone_idx == zone_idx:
                self.hovered_zone_idx = None
            elif self.hovered_zone_idx is not None and zone_idx < self.hovered_zone_idx:
                self.hovered_zone_idx -= 1
        elif event == cv2.EVENT_LBUTTONUP and not self.is_editing:
            if self.start_point:
                self.end_point = (scaled_x, scaled_y)
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
        elif event == cv2.EVENT_MOUSEMOVE and self.start_point and not self.end_point and not self.is_editing:
            self.end_point = (scaled_x, scaled_y)
        elif event == cv2.EVENT_LBUTTONDOWN and self.is_editing and not self.resize_handle:
            if self.selected_zone_idx is not None:
                self.undo_redo.save_state("reposition", self.zones)
                zone = self.zones[self.selected_zone_idx]
                if len(zone) == 4:
                    zone[0] = scaled_x
                    zone[1] = scaled_y
                else:
                    zone[0] = scaled_x
                    zone[1] = scaled_y
                self.scoring_zones.save_zones()
                self.manager.save_current_zone_set()
                print(f"Updated position of zone {self.selected_zone_idx} to ({scaled_x}, {scaled_y})")
        elif event == cv2.EVENT_MOUSEMOVE and flags & cv2.EVENT_FLAG_LBUTTON and self.is_editing:
            if self.resize_handle and self.start_point:
                self.undo_redo.save_state("resize_handle", self.zones)
                zone = self.zones[self.selected_zone_idx]
                x0, y0 = zone[0], zone[1]
                if self.resize_handle == "top-left":
                    w = zone[2] + (x0 - scaled_x)
                    h = zone[3] + (y0 - scaled_y)
                    zone[0] = scaled_x
                    zone[1] = scaled_y
                elif self.resize_handle == "top-right":
                    w = scaled_x - x0
                    h = zone[3] + (y0 - scaled_y)
                    zone[1] = scaled_y
                elif self.resize_handle == "bottom-left":
                    w = zone[2] + (x0 - scaled_x)
                    h = scaled_y - y0
                    zone[0] = scaled_x
                elif self.resize_handle == "bottom-right":
                    w = scaled_x - x0
                    h = scaled_y - y0
                zone[2] = max(10, w)
                zone[3] = max(10, h)
                self.scoring_zones.save_zones()
                self.manager.save_current_zone_set()
                print(f"Resized zone {self.selected_zone_idx} using {self.resize_handle}")
            elif self.is_editing and not self.resize_handle:
                self.undo_redo.save_state("resize", self.zones)
                zone = self.zones[self.selected_zone_idx]
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
                self.scoring_zones.save_zones()
                self.manager.save_current_zone_set()
                print(f"Resized zone {self.selected_zone_idx}")

    def calibrate_zones(self, frame, current_width, current_height):
        """Run the zone calibration process with a graphical interface."""
        self.calibrating = True
        cv2.namedWindow("Calibration", cv2.WINDOW_NORMAL)
        scale_x = current_width / frame.shape[1]
        scale_y = current_height / frame.shape[0]
        cv2.setMouseCallback("Calibration", lambda event, x, y, flags, param: self.mouse_callback(event, x, y, flags, frame, scale_x, scale_y))

        # Initialize the help window in the top right
        help_text = (
            "Calibration Controls:\n"
            "Drag to draw zone\n"
            "m: Toggle circle/rectangle\n"
            "Left-click: Edit zone\n"
            "Right-click: Delete zone\n"
            "s: Save zones\n"
            "e: Save & exit\n"
            "q: Discard & exit\n"
            "u: Undo\n"
            "r: Redo\n"
            "c: Clear all zones\n"
            "Editing Zone:\n"
            "Left-click: Reposition\n"
            "Drag: Resize\n"
            "Up/Down: Adjust points\n"
            "s: Toggle shape\n"
            "x: Exit edit mode"
        )
        help_window_width = 300
        help_window_height = 400
        self.help_window = HelpWindow(
            help_text,
            initial_x=current_width - help_window_width - 10,  # Top right
            initial_y=10,
            width=help_window_width,
            height=help_window_height
        )

        while self.calibrating:
            if cv2.getWindowProperty("Calibration", cv2.WND_PROP_VISIBLE) < 1:
                self.calibrating = False
                self.is_editing = False
                self.selected_zone_idx = None
                self.hovered_zone_idx = None
                self.resize_handle = None
                self.animator.animations = []
                self.exit_method = "x"
                cv2.destroyWindow("Calibration")
                break

            calib_frame = cv2.resize(frame, (current_width, current_height))
            self.animator.update_animations(calib_frame, scale_x, scale_y)

            for idx, zone in enumerate(self.zones):
                if any(anim["zone_idx"] == idx for anim in self.animator.animations):
                    continue
                if idx == self.selected_zone_idx:
                    color = (255, 0, 0)
                elif idx == self.hovered_zone_idx:
                    color = (0, 255, 255)
                else:
                    color = (0, 0, 255)

                if len(zone) == 4:
                    x, y, radius, points = zone
                    scaled_x = int(x * scale_x)
                    scaled_y = int(y * scale_y)
                    scaled_radius = int(radius * min(scale_x, scale_y))
                    cv2.circle(calib_frame, (scaled_x, scaled_y), scaled_radius, color, 2)
                    if idx == self.hovered_zone_idx or idx == self.selected_zone_idx:
                        tooltip = f"Circle: Pos=({x:.1f}, {y:.1f}), Radius={radius:.1f}, Points={points}"
                        cv2.putText(calib_frame, tooltip, (scaled_x - scaled_radius, scaled_y - scaled_radius - 30),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                    cv2.putText(calib_frame, f"Points: {points}", (scaled_x - scaled_radius, scaled_y - scaled_radius - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                else:
                    x, y, w, h, points = zone
                    scaled_x = int(x * scale_x)
                    scaled_y = int(y * scale_y)
                    scaled_w = int(w * scale_x)
                    scaled_h = int(h * scale_y)
                    cv2.rectangle(calib_frame, (scaled_x, scaled_y), (scaled_x + scaled_w, scaled_y + scaled_h), color, 2)
                    if idx == self.selected_zone_idx:
                        handle_size = 10
                        handles = [
                            (scaled_x, scaled_y),
                            (scaled_x + scaled_w, scaled_y),
                            (scaled_x, scaled_y + scaled_h),
                            (scaled_x + scaled_w, scaled_y + scaled_h)
                        ]
                        for hx, hy in handles:
                            cv2.rectangle(calib_frame, (hx - handle_size//2, hy - handle_size//2),
                                         (hx + handle_size//2, hy + handle_size//2), (255, 255, 255), -1)
                            cv2.rectangle(calib_frame, (hx - handle_size//2, hy - handle_size//2),
                                         (hx + handle_size//2, hy + handle_size//2), (0, 0, 0), 1)
                    if idx == self.hovered_zone_idx or idx == self.selected_zone_idx:
                        tooltip = f"Rect: Pos=({x:.1f}, {y:.1f}), Size=({w:.1f}, {h:.1f}), Points={points}"
                        cv2.putText(calib_frame, tooltip, (scaled_x + 5, scaled_y - 30),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                    cv2.putText(calib_frame, f"Points: {points}", (scaled_x + 5, scaled_y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            if self.start_point and self.end_point and not self.is_editing:
                x1, y1 = [int(x * scale_x) for x in self.start_point]
                x2, y2 = [ WND_PROP_VISIBLE) < 1:
                self.calibrating = False
                self.is_editing = False
                self.selected_zone_idx = None
                self.hovered_zone_idx = None
                self.resize_handle = None
                self.animator.animations = []
                self.exit_method = "x"
                cv2.destroyWindow("Calibration")
                break

            calib_frame = cv2.resize(frame, (current_width, current_height))
            self.animator.update_animations(calib_frame, scale_x, scale_y)

            for idx, zone in enumerate(self.zones):
                if any(anim["zone_idx"] == idx for anim in self.animator.animations):
                    continue
                if idx == self.selected_zone_idx:
                    color = (255, 0, 0)
                elif idx == self.hovered_zone_idx:
                    color = (0, 255, 255)
                else:
                    color = (0, 0, 255)

                if len(zone) == 4:
                    x, y, radius, points = zone
                    scaled_x = int(x * scale_x)
                    scaled_y = int(y * scale_y)
                    scaled_radius = int(radius * min(scale_x, scale_y))
                    cv2.circle(calib_frame, (scaled_x, scaled_y), scaled_radius, color, 2)
                    if idx == self.hovered_zone_idx or idx == self.selected_zone_idx:
                        tooltip = f"Circle: Pos=({x:.1f}, {y:.1f}), Radius={radius:.1f}, Points={points}"
                        cv2.putText(calib_frame, tooltip, (scaled_x - scaled_radius, scaled_y - scaled_radius - 30),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                    cv2.putText(calib_frame, f"Points: {points}", (scaled_x - scaled_radius, scaled_y - scaled_radius - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                else:
                    x, y, w, h, points = zone
                    scaled_x = int(x * scale_x)
                    scaled_y = int(y * scale_y)
                    scaled_w = int(w * scale_x)
                    scaled_h = int(h * scale_y)
                    cv2.rectangle(calib_frame, (scaled_x, scaled_y), (scaled_x + scaled_w, scaled_y + scaled_h), color, 2)
                    if idx == self.selected_zone_idx:
                        handle_size = 10
                        handles = [
                            (scaled_x, scaled_y),
                            (scaled_x + scaled_w, scaled_y),
                            (scaled_x, scaled_y + scaled_h),
                            (scaled_x + scaled_w, scaled_y + scaled_h)
                        ]
                        for hx, hy in handles:
                            cv2.rectangle(calib_frame, (hx - handle_size//2, hy - handle_size//2),
                                         (hx + handle_size//2, hy + handle_size//2), (255, 255, 255), -1)
                            cv2.rectangle(calib_frame, (hx - handle_size//2, hy - handle_size//2),
                                         (hx + handle_size//2, hy + handle_size//2), (0, 0, 0), 1)
                    if idx == self.hovered_zone_idx or idx == self.selected_zone_idx:
                        tooltip = f"Rect: Pos=({x:.1f}, {y:.1f}), Size=({w:.1f}, {h:.1f}), Points={points}"
                        cv2.putText(calib_frame, tooltip, (scaled_x + 5, scaled_y - 30),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                    cv2.putText(calib_frame, f"Points: {points}", (scaled_x + 5, scaled_y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            if self.start_point and self.end_point and not self.is_editing:
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
                if len(self.pending_zone) == 4:
                    x, y, radius, _ = self.pending_zone
                    scaled_x = int(x * scale_x)
                    scaled_y = int(y * scale_y)
                    scaled_radius = int(radius * min(scale_x, scale_y))
                    cv2.circle(calib_frame, (scaled_x, scaled_y), scaled_radius, (0, 255, 0), 2)
                    cv2.putText(calib_frame, f"Enter Points: {self.current_points} (Enter to confirm)",
                               (scaled_x - scaled_radius, scaled_y - scaled_radius - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                else:
                    x, y, w, h, _ = self.pending_zone
                    scaled_x = int(x * scale_x)
                    scaled_y = int(y * scale_y)
                    scaled_w = int(w * scale_x)
                    scaled_h = int(h * scale_y)
                    cv2.rectangle(calib_frame, (scaled_x, scaled_y), (scaled_x + scaled_w, scaled_y + scaled_h), (0, 255, 0), 2)
                    cv2.putText(calib_frame, f"Enter Points: {self.current_points} (Enter to confirm)",
                               (scaled_x + 5, scaled_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            # Draw the help window
            if self.help_window:
                calib_frame = self.help_window.draw(calib_frame)

            # Draw the undo/redo stack and zone set info at the top
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            stack_text = f"Undo: {len(self.undo_redo.undo_stack)} actions, Redo: {len(self.undo_redo.redo_stack)} actions"
            stack_size = cv2.getTextSize(stack_text, font, font_scale, thickness)[0]
            stack_x = 10
            stack_y = 30
            box_coords = ((stack_x, stack_y + 5), (stack_x + stack_size[0], stack_y - stack_size[1] - 5))
            cv2.rectangle(calib_frame, box_coords[0], box_coords[1], (128, 128, 128), -1)
            cv2.putText(calib_frame, stack_text, (stack_x, stack_y), font, font_scale, (255, 255, 255), thickness)

            set_text = f"Zone Set: {self.manager.current_zone_set}"
            set_size = cv2.getTextSize(set_text, font, font_scale, thickness)[0]
            set_x = current_width - set_size[0] - 10
            set_y = 30
            box_coords = ((set_x, set_y + 5), (set_x + set_size[0], set_y - set_size[1] - 5))
            cv2.rectangle(calib_frame, box_coords[0], box_coords[1], (128, 128, 128), -1)
            cv2.putText(calib_frame, set_text, (set_x, set_y), font, font_scale, (255, 255, 255), thickness)

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
                # Discard changes since last save (reload zones from file)
                self.zones.clear()
                self.scoring_zones.load_zones()
                self.zones.extend(self.scoring_zones.zones)
                self.calibrating = False
                self.is_editing = False
                self.selected_zone_idx = None
                self.hovered_zone_idx = None
                self.resize_handle = None
                self.animator.animations = []
                self.exit_method = "q"
                cv2.destroyWindow("Calibration")
                print("Discarded changes and exited calibration")
                break
            elif key == ord('s'):
                # Save zones without exiting
                self.scoring_zones.save_zones()
                self.manager.save_current_zone_set()
                print("Saved zones without exiting calibration")
            elif key == ord('e'):
                # Save and exit
                self.scoring_zones.save_zones()
                self.manager.save_current_zone_set()
                self.calibrating = False
                self.is_editing = False
                self.selected_zone_idx = None
                self.hovered_zone_idx = None
                self.resize_handle = None
                self.animator.animations = []
                self.exit_method = "e"
                cv2.destroyWindow("Calibration")
                print("Saved zones and exited calibration")
                break
            elif key == ord('m') and not self.is_editing:
                self.is_rectangle_mode = not self.is_rectangle_mode
                self.start_point = None
                self.end_point = None
                self.pending_zone = None
                print(f"Switched to {'rectangle' if self.is_rectangle_mode else 'circle'} mode")
            elif key == ord('x') and self.is_editing:
                self.is_editing = False
                self.selected_zone_idx = None
                self.start_point = None
                self.end_point = None
                self.pending_zone = None
                self.hovered_zone_idx = None
                self.resize_handle = None
                print("Exited edit mode")
            elif key == ord('u'):
                self.undo_redo.undo(self.zones, self.scoring_zones)
                if self.is_editing and (self.selected_zone_idx is None or self.selected_zone_idx >= len(self.zones)):
                    self.is_editing = False
                    self.selected_zone_idx = None
                    self.resize_handle = None
            elif key == ord('r'):
                self.undo_redo.redo(self.zones, self.scoring_zones)
            elif key == ord('c'):
                self.undo_redo.save_state("clear_all", self.zones)
                self.zones.clear()
                self.scoring_zones.save_zones()
                self.manager.save_current_zone_set()
                self.is_editing = False
                self.selected_zone_idx = None
                self.hovered_zone_idx = None
                self.resize_handle = None
                print("Cleared all zones")
            elif key == ord('s') and self.is_editing:
                self.toggle_zone_shape(self.selected_zone_idx)
            elif key == 13:  # Enter
                if self.pending_zone:
                    self.undo_redo.save_state("add_zone", self.zones)
                    self.pending_zone[-1] = max(0, self.current_points)
                    self.zones.append(self.pending_zone)
                    self.animator.start_scale_up(self.pending_zone[:], len(self.zones) - 1)
                    self.pending_zone = None
                    self.current_points = 0
                    self.start_point = None  # Reset start_point to prevent artifact
                    self.end_point = None    # Reset end_point to prevent artifact
                    self.scoring_zones.save_zones()
                    self.manager.save_current_zone_set()
                elif self.is_editing and self.selected_zone_idx is not None:
                    self.undo_redo.save_state("update_points", self.zones)
                    self.zones[self.selected_zone_idx][-1] = max(0, self.current_points)
                    self.scoring_zones.save_zones()
                    self.manager.save_current_zone_set()
                    print(f"Updated points for zone {self.selected_zone_idx} to {self.current_points}")
            elif key in [ord(str(i)) for i in range(10)]:
                self.current_points = self.current_points * 10 + int(chr(key))
            elif key == 82:  # Up arrow
                if self.is_editing:
                    self.undo_redo.save_state("increment_points", self.zones)
                    self.current_points = min(9999, self.current_points + 1)
                    print(f"Incremented points to {self.current_points}")
            elif key == 84:  # Down arrow
                if self.is_editing:
                    self.undo_redo.save_state("decrement_points", self.zones)
                    self.current_points = max(0, self.current_points - 1)
                    print(f"Decremented points to {self.current_points}")