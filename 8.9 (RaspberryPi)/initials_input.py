# initials_input.py
class InitialsInput:
    def __init__(self, frame, max_length=3):
        self.frame = frame.copy()
        self.max_length = max_length
        self.initials = ""
        self.active = False
        self.submitted = False
        self.text_box_rect = None
        self.cursor_visible = True
        self.cursor_timer = 0
        self.cursor_blink_rate = 0.5
        self.last_update = 0  # For frame rate limiting

    def draw(self, frame):
        # Limit frame rate to 10 FPS
        current_time = time.time()
        if current_time - self.last_update < 0.1:  # 0.1 seconds = 10 FPS
            return frame
        self.last_update = current_time

        overlay = frame.copy()
        h, w = frame.shape[:2]

        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.0
        thickness = 2
        prompt_text = "Enter your initials (3 letters, Enter to submit):"
        text_size = cv2.getTextSize(prompt_text, font, font_scale, thickness)[0]
        text_x = (w - text_size[0]) // 2
        text_y = h // 2 - 50
        cv2.putText(frame, prompt_text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)

        box_width = 100
        box_height = 40
        box_x = (w - box_width) // 2
        box_y = h // 2
        self.text_box_rect = (box_x, box_y, box_width, box_height)
        color = (255, 255, 255) if self.active else (200, 200, 200)
        cv2.rectangle(frame, (box_x, box_y), (box_x + box_width, box_y + box_height), color, 2)

        display_text = self.initials if self.initials else "___"
        if self.active and self.cursor_visible and len(self.initials) < self.max_length:
            display_text += "|"
        font_scale = 0.8
        text_size = cv2.getTextSize(display_text, font, font_scale, thickness)[0]
        text_x = box_x + (box_width - text_size[0]) // 2
        text_y = box_y + (box_height + text_size[1]) // 2
        cv2.putText(frame, display_text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)

        self.cursor_timer += 1 / 60
        if self.cursor_timer >= self.cursor_blink_rate:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0

        return frame

    # Other methods (handle_mouse, handle_key, etc.) remain unchanged