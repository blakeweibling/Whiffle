# confirmation_dialog.py
import cv2

class ConfirmationDialog:
    """A simple dialog to confirm an action."""
    def __init__(self, frame, message="Are you sure? (Y/N)"):
        self.frame = frame.copy()
        self.message = message
        self.confirmed = None  # None: undecided, True: yes, False: no
        self.active = True

    def draw(self, frame):
        """Draw the confirmation dialog on the frame."""
        if not self.active:
            return frame

        overlay = frame.copy()
        h, w = frame.shape[:2]

        # Draw a semi-transparent overlay
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

        # Draw the message
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.0
        thickness = 2
        text_size = cv2.getTextSize(self.message, font, font_scale, thickness)[0]
        text_x = (w - text_size[0]) // 2
        text_y = h // 2
        cv2.putText(frame, self.message, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)

        return frame

    def handle_key(self, key):
        """Handle keyboard input for confirmation."""
        if key == ord('y') or key == ord('Y'):
            self.confirmed = True
            self.active = False
        elif key == ord('n') or key == ord('N') or key == 27:  # Escape to cancel
            self.confirmed = False
            self.active = False

    def is_active(self):
        """Check if the dialog is still active."""
        return self.active

    def get_result(self):
        """Get the confirmation result."""
        return self.confirmed