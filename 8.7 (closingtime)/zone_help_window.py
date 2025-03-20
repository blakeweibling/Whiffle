import cv2

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

    def toggle_visibility(self):
        """Toggle the visibility of the help window."""
        self.is_visible = not self.is_visible
        if self.is_visible:
            print("Help window opened")
        else:
            print("Help window closed")

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
        alpha = 0.95  # Increased opacity for better readability
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