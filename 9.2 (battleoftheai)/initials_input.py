# initials_input.py
import cv2
import numpy as np

class InitialsInput:
    """Handles graphical input for entering 3-letter initials."""
    def __init__(self, frame, max_length=3):
        self.frame = frame.copy()
        self.max_length = max_length
        self.initials = ""
        self.active = False
        self.submitted = False
        self.text_box_rect = None  # Will be set based on frame size
        self.cursor_visible = True
        self.cursor_timer = 0
        self.cursor_blink_rate = 0.5  # Blink every 0.5 seconds

    def draw(self, frame):
        """Draw the initials input UI on the frame."""
        overlay = frame.copy()
        h, w = frame.shape[:2]

        # Draw a semi-transparent overlay
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

        # Draw the prompt
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.0
        thickness = 2
        prompt_text = "Enter your initials (3 letters, Enter to submit):"
        text_size = cv2.getTextSize(prompt_text, font, font_scale, thickness)[0]
        text_x = (w - text_size[0]) // 2
        text_y = h // 2 - 50
        cv2.putText(frame, prompt_text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)

        # Draw the text box
        box_width = 100
        box_height = 40
        box_x = (w - box_width) // 2
        box_y = h // 2
        self.text_box_rect = (box_x, box_y, box_width, box_height)
        color = (255, 255, 255) if self.active else (200, 200, 200)
        cv2.rectangle(frame, (box_x, box_y), (box_x + box_width, box_y + box_height), color, 2)

        # Draw the current initials or placeholder
        display_text = self.initials if self.initials else "___"
        if self.active and self.cursor_visible and len(self.initials) < self.max_length:
            display_text += "|"
        font_scale = 0.8
        text_size = cv2.getTextSize(display_text, font, font_scale, thickness)[0]
        text_x = box_x + (box_width - text_size[0]) // 2
        text_y = box_y + (box_height + text_size[1]) // 2
        cv2.putText(frame, display_text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)

        # Update cursor blink
        self.cursor_timer += 1 / 60  # Assuming 60 FPS
        if self.cursor_timer >= self.cursor_blink_rate:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0

        return frame

    def handle_mouse(self, event, x, y):
        """Handle mouse events for the text box."""
        if self.text_box_rect:
            bx, by, bw, bh = self.text_box_rect
            if event == cv2.EVENT_LBUTTONDOWN:
                if bx <= x <= bx + bw and by <= y <= by + bh:
                    self.active = True
                else:
                    self.active = False

    def handle_key(self, key):
        """Handle keyboard input for entering initials."""
        if key == 27:  # Escape to cancel
            self.initials = ""
            self.submitted = True
            self.active = False
        elif key == 13 and len(self.initials) == self.max_length:  # Enter to submit
            self.submitted = True
            self.active = False
        elif key == 8 and self.initials:  # Backspace to delete
            self.initials = self.initials[:-1]
        elif key in range(65, 91) or key in range(97, 123):  # A-Z or a-z
            if len(self.initials) < self.max_length and self.active:
                self.initials += chr(key).upper()

    def is_submitted(self):
        """Check if the initials have been submitted."""
        return self.submitted

    def get_initials(self):
        """Get the entered initials."""
        return self.initials