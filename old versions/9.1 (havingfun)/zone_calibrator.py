# zone_calibrator.py
import cv2
import numpy as np
import time
from zone_utils import ZoneManager, ZoneAnimator, UndoRedoHandler
from zone_mouse_handler import ZoneMouseHandler
from zone_help_window import HelpWindow
from zone_shape_utils import toggle_zone_shape

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
        self.mouse_handler = ZoneMouseHandler(self)
        self.help_window = None
        self.help_button_rect = None

    def calibrate_zones(self, frame, current_width, current_height):
        """Run the zone calibration process with a graphical interface."""
        self.calibrating = True
        window_closed = False
        cv2.namedWindow("Calibration", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Calibration", current_width, current_height)
        scale_x = current_width / frame.shape[1]
        scale_y = current_height / frame.shape[0]
        cv2.setMouseCallback("Calibration", lambda event, x, y, flags, param: self.mouse_handler.mouse_callback(event, x, y, flags, frame, scale_x, scale_y))

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
            "h: Toggle help window\n"
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
            initial_x=current_width - help_window_width - 10,
            initial_y=10,
            width=help_window_width,
            height=help_window_height
        )

        # Track the previous frame time to calculate delta_time
        prev_frame_time = time.time()

        while self.calibrating:
            # Calculate delta_time
            current_time = time.time()
            delta_time = current_time - prev_frame_time
            prev_frame_time = current_time

            # Check if the window was closed via 'X'
            try:
                if cv2.getWindowProperty("Calibration", cv2.WND_PROP_VISIBLE) < 1:
                    self.calibrating = False
                    self.is_editing = False
                    self.selected_zone_idx = None
                    self.hovered_zone_idx = None
                    self.resize_handle = None
                    self.animator.animations = []
                    self.exit_method = "x"
                    window_closed = True
                    break
            except cv2.error:
                self.calibrating = False
                self.is_editing = False
                self.selected_zone_idx = None
                self.hovered_zone_idx = None
                self.resize_handle = None
                self.animator.animations = []
                self.exit_method = "x"
                window_closed = True
                break

            calib_frame = cv2.resize(frame, (current_width, current_height))
            self.animator.update_animations(calib_frame, scale_x, scale_y, delta_time)

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

            # Draw the "Help" button if the help window is closed
            if self.help_window and not self.help_window.is_visible:
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.5
                thickness = 1
                button_text = "Help"
                button_size = cv2.getTextSize(button_text, font, font_scale, thickness)[0]
                button_width = button_size[0] + 20
                button_height = button_size[1] + 10
                button_x = current_width - button_width - 10
                button_y = 10
                self.help_button_rect = (button_x, button_y, button_width, button_height)
                cv2.rectangle(calib_frame, (button_x, button_y), (button_x + button_width, button_y + button_height), (200, 200, 200), -1)
                cv2.rectangle(calib_frame, (button_x, button_y), (button_x + button_width, button_y + button_height), (0, 0, 0), 1)
                text_x = button_x + (button_width - button_size[0]) // 2
                text_y = button_y + (button_height + button_size[1]) // 2
                cv2.putText(calib_frame, button_text, (text_x, text_y), font, font_scale, (0, 0, 0), thickness)
            else:
                self.help_button_rect = None

            # Draw the undo/redo stack at the top left
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

            # Draw "Zone Set" at the bottom left
            set_text = f"Zone Set: {self.manager.current_zone_set}"
            set_size = cv2.getTextSize(set_text, font, font_scale, thickness)[0]
            set_x = 10
            set_y = current_height - 10
            box_coords = ((set_x, set_y + 5), (set_x + set_size[0], set_y - set_size[1] - 5))
            cv2.rectangle(calib_frame, box_coords[0], box_coords[1], (128, 128, 128), -1)
            cv2.putText(calib_frame, set_text, (set_x, set_y), font, font_scale, (255, 255, 255), thickness)

            # Draw the mode text at the bottom right
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
                self.animator.animations = []
                self.exit_method = "q"
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
                break
            elif key == ord('h'):
                # Toggle help window visibility
                if self.help_window:
                    self.help_window.toggle_visibility()
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
                toggle_zone_shape(self, zone_idx=self.selected_zone_idx)
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

        # Destroy the window only if it wasn't already closed via 'X'
        if not window_closed:
            try:
                if cv2.getWindowProperty("Calibration", cv2.WND_PROP_VISIBLE) >= 0:
                    cv2.destroyWindow("Calibration")
            except cv2.error as e:
                print(f"Window 'Calibration' already destroyed: {e}")