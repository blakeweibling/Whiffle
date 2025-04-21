import cv2

class MenuRenderer:
    """Base class for rendering menu elements, providing shared utilities."""
    def __init__(self, menu_system):
        self.menu_system = menu_system
        self.leaderboard_loading = False  # Placeholder attributes for leaderboard
        self.leaderboard_error = False
        self.leaderboard_scores = []
        self.leaderboard_is_online = False

    def wrap_text(self, text, font, font_scale, thickness, max_width):
        """Wrap text to fit within a maximum width."""
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            text_size = cv2.getTextSize(test_line, font, font_scale, thickness)[0]
            if text_size[0] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        return lines

    def draw_toggle(self, overlay, x, y, width, height, value):
        """Draw a toggle switch."""
        color_on = (0, 255, 0) if value else (0, 0, 255)
        cv2.rectangle(overlay, (x, y), (x + width, y + height), (150, 150, 150), -1)
        cv2.rectangle(overlay, (x, y), (x + width // 2 if not value else x + width, y + height), color_on, -1)
        cv2.rectangle(overlay, (x, y), (x + width, y + height), (0, 0, 0), 1)