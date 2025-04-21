import cv2
import numpy as np
from datetime import datetime

class MenuRenderer:
    """Renders the game's menu system based on the current state."""
    def __init__(self, menu_system):
        self.menu_system = menu_system
        self.help_text = (
            "Hotkeys:\n"
            "  c: Calibrate zones\n"
            "  r: Reset score\n"
            "  f: Flip horizontal\n"
            "  d: Toggle debug\n"
            "  s: Start labeling\n"
            "  p: Toggle processing\n"
            "Calibration: Drag to draw zones, 'm' to toggle circle/rectangle, Enter to confirm\n"
            "Labeling: 'r' for red, 'w' for white, 'h' to half, 'b' for background, 's' to skip\n"
            "Menu: Up/Down arrows to navigate, Enter to select, Esc to go back/close\n"
            "Drag the header to move the menu"
        )
        self.about_text = "Ball Tracking Game v1.0\nDeveloped by [Your Name]\nPowered by OpenCV and xAI's Grok"
        self.leaderboard_scores = None  # Cache the leaderboard scores
        self.leaderboard_is_online = False  # Indicates if scores are from online
        self.leaderboard_loading = False
        self.leaderboard_error = None

    def wrap_text(self, text, font, font_scale, thickness, max_width):
        """Wrap text to fit within a specified width."""
        lines = text.split('\n')
        wrapped_lines = []
        for line in lines:
            if not line:
                wrapped_lines.append("")
                continue
            words = line.split(' ')
            current_line = ""
            for word in words:
                test_line = current_line + word + " "
                text_size = cv2.getTextSize(test_line, font, font_scale, thickness)[0]
                if text_size[0] <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        wrapped_lines.append(current_line.strip())
                    current_line = word + " "
            if current_line:
                wrapped_lines.append(current_line.strip())
        return wrapped_lines

    def draw_menu_bar(self, frame):
        """Draw the menu bar at the top of the frame with a button to toggle the menu."""
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (w, 40), (128, 128, 128), -1)
        x, y, bw, bh = self.menu_system.button_rect
        cv2.rectangle(frame, (x, y), (x + bw, y + bh), (200, 200, 200), -1)
        cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 0, 0), 1)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1
        text_size = cv2.getTextSize(self.menu_system.button_text, font, font_scale, thickness)[0]
        text_x = x + (bw - text_size[0]) // 2
        text_y = y + (bh + text_size[1]) // 2
        cv2.putText(frame, self.menu_system.button_text, (text_x, text_y), font, font_scale, (0, 0, 0), thickness)
        if self.menu_system.timer_text:
            timer_size = cv2.getTextSize(self.menu_system.timer_text, font, font_scale, thickness)[0]
            timer_x = w - timer_size[0] - 10
            timer_y = 10 + timer_size[1]
            cv2.putText(frame, self.menu_system.timer_text, (timer_x, timer_y), font, font_scale, (255, 255, 255), thickness)
        return frame

    def draw_toggle(self, frame, x, y, width, height, is_on):
        """Draw a simple toggle switch at (x, y) with the given state."""
        bg_color = (0, 255, 0) if is_on else (0, 0, 255)  # Green for On, Red for Off
        cv2.rectangle(frame, (x, y), (x + width, y + height), bg_color, -1)
        cv2.rectangle(frame, (x, y), (x + width, y + height), (0, 0, 0), 1)
        knob_x = x + width - height if is_on else x
        cv2.circle(frame, (knob_x + height // 2, y + height // 2), height // 2 - 2, (255, 255, 255), -1)
        cv2.circle(frame, (knob_x + height // 2, y + height // 2), height // 2 - 2, (0, 0, 0), 1)

    def draw_menu_items(self, frame, items, title=None, show_back=True, show_close=True):
        """Draw a menu with a list of items, an optional title, and back/close buttons."""
        overlay = frame.copy()
        h, w = frame.shape[:2]

        # Use the menu position from MenuSystem, default to w//4, h//4 if not set
        if self.menu_system.menu_pos_x is None or self.menu_system.menu_pos_y is None:
            self.menu_system.menu_pos_x = w // 4
            self.menu_system.menu_pos_y = h // 4

        menu_x1 = self.menu_system.menu_pos_x
        menu_y1 = self.menu_system.menu_pos_y
        menu_x2 = menu_x1 + (w // 2)  # Fixed width: half the screen width
        menu_y2 = menu_y1 + (h // 2)  # Fixed height: half the screen height

        # Ensure the menu stays within the window bounds
        menu_x1 = max(0, min(menu_x1, w - (menu_x2 - menu_x1)))
        menu_y1 = max(0, min(menu_y1, h - (menu_y2 - menu_y1)))
        menu_x2 = menu_x1 + (w // 2)
        menu_y2 = menu_y1 + (h // 2)

        # Update the menu position in case it was adjusted
        self.menu_system.menu_pos_x = menu_x1
        self.menu_system.menu_pos_y = menu_y1

        self.menu_system.menu_area = (menu_x1, menu_y1, menu_x2 - menu_x1, menu_y2 - menu_y1)

        # Draw the menu background
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

        # Draw a draggable header
        header_height = 30
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (80, 80, 80), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
        self.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.7
        thickness = 2

        if title:
            text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
            x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
            y_pos = menu_y1 + header_height // 2 + text_size[1] // 2
            cv2.putText(overlay, title, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)

        self.menu_system.menu_item_rects = []
        for i, item in enumerate(items):
            text, _ = item
            color = (250, 206, 135) if i == self.menu_system.selection else (220, 220, 220)
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            x_pos = menu_x1 + 20
            y_pos = menu_y1 + header_height + 50 + i * 40
            rect_x = x_pos - 5
            rect_y = y_pos - text_size[1] - 5
            rect_w = text_size[0] + 10
            rect_h = text_size[1] + 10
            self.menu_system.menu_item_rects.append((rect_x, rect_y, rect_w, rect_h, i))
            cv2.putText(overlay, text, (x_pos, y_pos), font, font_scale, color, thickness)

        if show_close:
            close_x = menu_x2 - 40
            close_y = menu_y1 + 5
            close_w, close_h = 30, 20
            self.menu_system.close_button_rect = (close_x, close_y, close_w, close_h)
            cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 255), -1)
            cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 0), 1)
            text_size = cv2.getTextSize("X", font, 0.5, 1)[0]
            text_x = close_x + (close_w - text_size[0]) // 2
            text_y = close_y + (close_h + text_size[1]) // 2
            cv2.putText(overlay, "X", (text_x, text_y), font, 0.5, (255, 255, 255), 1)

        if show_back and self.menu_system.menu_stack:
            back_x = menu_x1 + 20
            back_y = menu_y2 - 60
            back_w, back_h = 100, 30
            self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
            cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (200, 200, 200), -1)
            cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
            text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
            text_x = back_x + (back_w - text_size[0]) // 2
            text_y = back_y + (back_h + text_size[1]) // 2
            cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

        # Apply semi-transparency (same as HelpWindow)
        alpha = 0.95  # Match the opacity of HelpWindow
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

    def draw_text_page(self, frame, text, title):
        """Draw a text page (e.g., Help or About) with the given text and title."""
        overlay = frame.copy()
        h, w = frame.shape[:2]

        # Use the menu position from MenuSystem, default to w//4, h//4 if not set
        if self.menu_system.menu_pos_x is None or self.menu_system.menu_pos_y is None:
            self.menu_system.menu_pos_x = w // 4
            self.menu_system.menu_pos_y = h // 4

        menu_x1 = self.menu_system.menu_pos_x
        menu_y1 = self.menu_system.menu_pos_y
        menu_x2 = menu_x1 + (w // 2)
        menu_y2 = menu_y1 + (h // 2)

        # Ensure the menu stays within the window bounds
        menu_x1 = max(0, min(menu_x1, w - (menu_x2 - menu_x1)))
        menu_y1 = max(0, min(menu_y1, h - (menu_y2 - menu_y1)))
        menu_x2 = menu_x1 + (w // 2)
        menu_y2 = menu_y1 + (h // 2)

        self.menu_system.menu_pos_x = menu_x1
        self.menu_system.menu_pos_y = menu_y1

        self.menu_system.menu_area = (menu_x1, menu_y1, menu_x2 - menu_x1, menu_y2 - menu_y1)

        # Draw the menu background
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

        # Draw a draggable header
        header_height = 30
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (80, 80, 80), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
        self.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.5
        thickness = 1

        text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
        x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        y_pos = menu_y1 + header_height // 2 + text_size[1] // 2
        cv2.putText(overlay, title, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)

        max_width = (menu_x2 - menu_x1) - 40
        wrapped_lines = self.wrap_text(text, font, font_scale, thickness, max_width)

        for i, line in enumerate(wrapped_lines):
            y_pos = menu_y1 + header_height + 30 + i * 20
            cv2.putText(overlay, line, (menu_x1 + 20, y_pos), font, font_scale, (220, 220, 220), thickness)

        close_x = menu_x2 - 40
        close_y = menu_y1 + 5
        close_w, close_h = 30, 20
        self.menu_system.close_button_rect = (close_x, close_y, close_w, close_h)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 255), -1)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("X", font, 0.5, 1)[0]
        text_x = close_x + (close_w - text_size[0]) // 2
        text_y = close_y + (close_h + text_size[1]) // 2
        cv2.putText(overlay, "X", (text_x, text_y), font, 0.5, (255, 255, 255), 1)

        back_x = menu_x1 + 20
        back_y = menu_y2 - 60
        back_w, back_h = 100, 30
        self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (200, 200, 200), -1)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
        text_x = back_x + (back_w - text_size[0]) // 2
        text_y = back_y + (back_h + text_size[1]) // 2
        cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

        # Apply semi-transparency (same as HelpWindow)
        alpha = 0.95  # Match the opacity of HelpWindow
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

    def draw_leaderboard(self, frame):
        """Draw the leaderboard with the top scores."""
        overlay = frame.copy()
        h, w = frame.shape[:2]

        # Use the menu position from MenuSystem, default to w//4, h//4 if not set
        if self.menu_system.menu_pos_x is None or self.menu_system.menu_pos_y is None:
            self.menu_system.menu_pos_x = w // 4
            self.menu_system.menu_pos_y = h // 4

        menu_x1 = self.menu_system.menu_pos_x
        menu_y1 = self.menu_system.menu_pos_y
        menu_x2 = menu_x1 + (w // 2)
        menu_y2 = menu_y1 + (h // 2)

        # Ensure the menu stays within the window bounds
        menu_x1 = max(0, min(menu_x1, w - (menu_x2 - menu_x1)))
        menu_y1 = max(0, min(menu_y1, h - (menu_y2 - menu_y1)))
        menu_x2 = menu_x1 + (w // 2)
        menu_y2 = menu_y1 + (h // 2)

        self.menu_system.menu_pos_x = menu_x1
        self.menu_system.menu_pos_y = menu_y1

        self.menu_system.menu_area = (menu_x1, menu_y1, menu_x2 - menu_x1, menu_y2 - menu_y1)

        # Draw the menu background
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

        # Draw a draggable header
        header_height = 30
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (80, 80, 80), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
        self.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.7
        thickness = 2

        title = f"Leaderboard ({self.menu_system.mode})"
        text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
        x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        y_pos = menu_y1 + header_height // 2 + text_size[1] // 2
        cv2.putText(overlay, title, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)

        font_scale = 0.5
        thickness = 1
        self.menu_system.menu_item_rects = []

        if self.leaderboard_loading:
            text = "Loading..."
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
            y_pos = menu_y1 + (menu_y2 - menu_y1) // 2
            cv2.putText(overlay, text, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)
        elif self.leaderboard_error:
            text = f"Failed to load online leaderboard. Showing local scores."
            wrapped_lines = self.wrap_text(text, font, font_scale, thickness, menu_x2 - menu_x1 - 40)
            for i, line in enumerate(wrapped_lines):
                text_size = cv2.getTextSize(line, font, font_scale, thickness)[0]
                x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
                y_pos = menu_y1 + (menu_y2 - menu_y1) // 2 + i * 20
                cv2.putText(overlay, line, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)
            if self.leaderboard_scores:
                for i, score_entry in enumerate(self.leaderboard_scores):
                    initials = score_entry["initials"]
                    score = score_entry["score"]
                    created_at = datetime.fromisoformat(score_entry["created_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d")
                    text = f"{i+1}. {initials}: {score} ({created_at})"
                    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                    x_pos = menu_x1 + 20
                    y_pos = menu_y1 + header_height + 50 + (i + len(wrapped_lines)) * 30
                    cv2.putText(overlay, text, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)
        elif not self.leaderboard_scores:
            text = "No scores available."
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
            y_pos = menu_y1 + (menu_y2 - menu_y1) // 2
            cv2.putText(overlay, text, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)
        else:
            source_text = "Online Leaderboard" if self.leaderboard_is_online else "Local Leaderboard"
            text_size = cv2.getTextSize(source_text, font, font_scale, thickness)[0]
            x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
            y_pos = menu_y1 + header_height + 30
            cv2.putText(overlay, source_text, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)
            for i, score_entry in enumerate(self.leaderboard_scores):
                initials = score_entry["initials"]
                score = score_entry["score"]
                created_at = datetime.fromisoformat(score_entry["created_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d")
                text = f"{i+1}. {initials}: {score} ({created_at})"
                text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                x_pos = menu_x1 + 20
                y_pos = menu_y1 + header_height + 50 + (i + 1) * 30
                cv2.putText(overlay, text, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)

        close_x = menu_x2 - 40
        close_y = menu_y1 + 5
        close_w, close_h = 30, 20
        self.menu_system.close_button_rect = (close_x, close_y, close_w, close_h)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 255), -1)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("X", font, 0.5, 1)[0]
        text_x = close_x + (close_w - text_size[0]) // 2
        text_y = close_y + (close_h + text_size[1]) // 2
        cv2.putText(overlay, "X", (text_x, text_y), font, 0.5, (255, 255, 255), 1)

        back_x = menu_x1 + 20
        back_y = menu_y2 - 60
        back_w, back_h = 100, 30
        self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (200, 200, 200), -1)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
        text_x = back_x + (back_w - text_size[0]) // 2
        text_y = back_y + (back_h + text_size[1]) // 2
        cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

        # Apply semi-transparency (same as HelpWindow)
        alpha = 0.95  # Match the opacity of HelpWindow
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

    def draw_menu(self, frame):
        """Draw the current menu based on the menu system's state."""
        if self.menu_system.state == "help":
            return self.draw_text_page(frame, self.help_text, "Help")
        elif self.menu_system.state == "about":
            return self.draw_text_page(frame, self.about_text, "About")
        elif self.menu_system.state == "leaderboard":
            # Fetch scores only if not already cached
            if self.leaderboard_scores is None and not self.leaderboard_loading:
                self.leaderboard_loading = True
                self.leaderboard_error = None
                try:
                    self.leaderboard_scores, self.leaderboard_is_online = self.menu_system.leaderboard.get_top_scores(self.menu_system.mode)
                except Exception as e:
                    self.leaderboard_error = str(e)
                    self.leaderboard_scores = []
                    self.leaderboard_is_online = False
                finally:
                    self.leaderboard_loading = False
            return self.draw_leaderboard(frame)
        elif self.menu_system.state == "settings":
            items = [
                (f"White Ball Detection: {'On' if self.menu_system.settings.config.white_ball_detection else 'Off'}",
                 lambda: self.menu_system.settings.toggle('white_ball_detection')),
                (f"Red Ball Detection: {'On' if self.menu_system.settings.config.red_ball_detection else 'Off'}",
                 lambda: self.menu_system.settings.toggle('red_ball_detection')),
                (f"Game Sounds: {'On' if self.menu_system.settings.config.game_sounds else 'Off'}",
                 lambda: self.menu_system.settings.toggle('game_sounds')),
                (f"Background Music: {'On' if self.menu_system.settings.config.background_music else 'Off'}",
                 lambda: self.menu_system.settings.toggle('background_music'))
            ]
            overlay = frame.copy()
            h, w = frame.shape[:2]

            # Use the menu position from MenuSystem, default to w//4, h//4 if not set
            if self.menu_system.menu_pos_x is None or self.menu_system.menu_pos_y is None:
                self.menu_system.menu_pos_x = w // 4
                self.menu_system.menu_pos_y = h // 4

            menu_x1 = self.menu_system.menu_pos_x
            menu_y1 = self.menu_system.menu_pos_y
            menu_x2 = menu_x1 + (w // 2)
            menu_y2 = menu_y1 + (h // 2)

            # Ensure the menu stays within the window bounds
            menu_x1 = max(0, min(menu_x1, w - (menu_x2 - menu_x1)))
            menu_y1 = max(0, min(menu_y1, h - (menu_y2 - menu_y1)))
            menu_x2 = menu_x1 + (w // 2)
            menu_y2 = menu_y1 + (h // 2)

            self.menu_system.menu_pos_x = menu_x1
            self.menu_system.menu_pos_y = menu_y1

            self.menu_system.menu_area = (menu_x1, menu_y1, menu_x2 - menu_x1, menu_y2 - menu_y1)

            # Draw the menu background
            cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
            cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

            # Draw a draggable header
            header_height = 30
            cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (80, 80, 80), -1)
            cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
            self.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

            font = cv2.FONT_HERSHEY_DUPLEX
            font_scale = 0.5
            thickness = 1

            title = "Settings"
            text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
            x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
            y_pos = menu_y1 + header_height // 2 + text_size[1] // 2
            cv2.putText(overlay, title, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)

            self.menu_system.menu_item_rects = []
            toggle_width, toggle_height = 50, 20
            for i, (label, action) in enumerate(items):
                x_pos = menu_x1 + 20
                y_pos = menu_y1 + header_height + 30 + i * 40
                color = (250, 206, 135) if i == self.menu_system.selection else (220, 220, 220)

                text_size = cv2.getTextSize(label, font, font_scale, thickness)[0]
                toggle_x = x_pos + text_size[0] + 10
                toggle_y = y_pos - toggle_height // 2
                state = "On" in label
                self.draw_toggle(overlay, toggle_x, toggle_y, toggle_width, toggle_height, state)
                rect_x = toggle_x
                rect_y = toggle_y
                rect_w = toggle_width
                rect_h = toggle_height
                self.menu_system.menu_item_rects.append((rect_x, rect_y, rect_w, rect_h, i))

                cv2.putText(overlay, label, (x_pos, y_pos), font, font_scale, color, thickness)

            close_x = menu_x2 - 40
            close_y = menu_y1 + 5
            close_w, close_h = 30, 20
            self.menu_system.close_button_rect = (close_x, close_y, close_w, close_h)
            cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 255), -1)
            cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 0), 1)
            text_size = cv2.getTextSize("X", font, 0.5, 1)[0]
            text_x = close_x + (close_w - text_size[0]) // 2
            text_y = close_y + (close_h + text_size[1]) // 2
            cv2.putText(overlay, "X", (text_x, text_y), font, 0.5, (255, 255, 255), 1)

            back_x = menu_x1 + 20
            back_y = menu_y2 - 60
            back_w, back_h = 100, 30
            self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
            cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (200, 200, 200), -1)
            cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
            text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
            text_x = back_x + (back_w - text_size[0]) // 2
            text_y = back_y + (back_h + text_size[1]) // 2
            cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

            # Apply semi-transparency (same as HelpWindow)
            alpha = 0.95  # Match the opacity of HelpWindow
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
            return frame
        elif self.menu_system.state == "game_over":
            overlay = frame.copy()
            h, w = frame.shape[:2]

            # Use the menu position from MenuSystem, default to w//4, h//4 if not set
            if self.menu_system.menu_pos_x is None or self.menu_system.menu_pos_y is None:
                self.menu_system.menu_pos_x = w // 4
                self.menu_system.menu_pos_y = h // 4

            menu_x1 = self.menu_system.menu_pos_x
            menu_y1 = self.menu_system.menu_pos_y
            menu_x2 = menu_x1 + (w // 2)
            menu_y2 = menu_y1 + (h // 2)

            # Ensure the menu stays within the window bounds
            menu_x1 = max(0, min(menu_x1, w - (menu_x2 - menu_x1)))
            menu_y1 = max(0, min(menu_y1, h - (menu_y2 - menu_y1)))
            menu_x2 = menu_x1 + (w // 2)
            menu_y2 = menu_y1 + (h // 2)

            self.menu_system.menu_pos_x = menu_x1
            self.menu_system.menu_pos_y = menu_y1

            self.menu_system.menu_area = (menu_x1, menu_y1, menu_x2 - menu_x1, menu_y2 - menu_y1)

            # Draw the menu background
            cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
            cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

            # Draw a draggable header
            header_height = 30
            cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (80, 80, 80), -1)
            cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
            self.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

            font = cv2.FONT_HERSHEY_DUPLEX
            font_scale = 0.7
            thickness = 2
            text = f"Game Over! Final Score: {self.menu_system.total_score}"
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
            y_pos = menu_y1 + (menu_y2 - menu_y1) // 2
            cv2.putText(overlay, text, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)

            close_x = menu_x2 - 40
            close_y = menu_y1 + 5
            close_w, close_h = 30, 20
            self.menu_system.close_button_rect = (close_x, close_y, close_w, close_h)
            cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 255), -1)
            cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 0), 1)
            text_size = cv2.getTextSize("X", font, 0.5, 1)[0]
            text_x = close_x + (close_w - text_size[0]) // 2
            text_y = close_y + (close_h + text_size[1]) // 2
            cv2.putText(overlay, "X", (text_x, text_y), font, 0.5, (255, 255, 255), 1)

            back_x = menu_x1 + 20
            back_y = menu_y2 - 60
            back_w, back_h = 100, 30
            self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
            cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (200, 200, 200), -1)
            cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
            text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
            text_x = back_x + (back_w - text_size[0]) // 2
            text_y = back_y + (back_h + text_size[1]) // 2
            cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

            # Apply semi-transparency (same as HelpWindow)
            alpha = 0.95  # Match the opacity of HelpWindow
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
            return frame
        elif self.menu_system.state == "main_menu":
            # Reset leaderboard state when returning to main menu
            self.leaderboard_scores = None
            self.leaderboard_is_online = False
            self.leaderboard_loading = False
            self.leaderboard_error = None
            items = []
            for key, action in self.menu_system.current_menu.items():
                text = f"{key} {'>' if isinstance(action, dict) else ''}"
                items.append((text, action))
            return self.draw_menu_items(frame, items, title="Menu")
        else:
            self.menu_system.menu_item_rects = []
            self.menu_system.menu_area = None
            self.menu_system.back_button_rect = None
            self.menu_system.close_button_rect = None
            self.menu_system.header_rect = None
            return frame