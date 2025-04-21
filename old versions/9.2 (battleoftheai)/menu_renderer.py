import cv2
from datetime import datetime

class MenuRenderer:
    """Class to handle rendering of menu elements."""
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

    def draw_text_page(self, frame, items, title):
        """Draw a text page (e.g., Help, About, or Main Menu) with the given items and title."""
        overlay = frame.copy()
        h, w = frame.shape[:2]

        if self.menu_system.menu_pos_x is None or self.menu_system.menu_pos_y is None:
            self.menu_system.menu_pos_x = w // 4
            self.menu_system.menu_pos_y = h // 4

        menu_x1 = self.menu_system.menu_pos_x
        menu_y1 = self.menu_system.menu_pos_y
        menu_x2 = menu_x1 + (w // 2)
        menu_y2 = menu_y1 + (h // 2)

        menu_x1 = max(0, min(menu_x1, w - (menu_x2 - menu_x1)))
        menu_y1 = max(0, min(menu_y1, h - (menu_y2 - menu_y1)))
        menu_x2 = menu_x1 + (w // 2)
        menu_y2 = menu_y1 + (h // 2)

        self.menu_system.menu_pos_x = menu_x1
        self.menu_system.menu_pos_y = menu_y1

        self.menu_system.menu_area = (menu_x1, menu_y1, menu_x2 - menu_x1, menu_y2 - menu_y1)

        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

        header_height = 30
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (80, 80, 80), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
        self.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

        font = cv2.FONT_HERSHEY_SIMPLEX  # Use a more user-friendly font
        title_font_scale = 0.7
        item_font_scale = 0.6  # Slightly larger for better readability
        thickness = 1

        # Draw title
        text_size = cv2.getTextSize(title, font, title_font_scale, thickness)[0]
        x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        y_pos = menu_y1 + header_height // 2 + text_size[1] // 2
        cv2.putText(overlay, title, (x_pos, y_pos), font, title_font_scale, (220, 220, 220), thickness)

        back_button_height = 30
        back_button_margin = 60
        line_height = 40
        self.menu_system.menu_item_rects = []

        # Handle main menu items (split into two columns)
        if title == "Main Menu":
            num_items = len(items)
            items_per_column = (num_items + 1) // 2  # Split items across two columns
            column_width = ((menu_x2 - menu_x1) - 60) // 2  # Two columns with some padding
            left_column_x = menu_x1 + 20
            right_column_x = left_column_x + column_width + 20

            for idx, (item_text, _) in enumerate(items):
                # Determine which column to place the item in
                if idx < items_per_column:
                    x_pos = left_column_x
                    col_idx = idx
                else:
                    x_pos = right_column_x
                    col_idx = idx - items_per_column

                y_pos = menu_y1 + header_height + 30 + col_idx * line_height
                color = (250, 206, 135) if idx == self.menu_system.selection else (220, 220, 220)
                text_size = cv2.getTextSize(item_text, font, item_font_scale, thickness)[0]
                rect_x = x_pos
                rect_y = y_pos - text_size[1]
                rect_w = text_size[0] + 20
                rect_h = text_size[1] + 10
                self.menu_system.menu_item_rects.append((rect_x, rect_y, rect_w, rect_h, idx))
                cv2.putText(overlay, item_text, (x_pos, y_pos), font, item_font_scale, color, thickness)
        # Handle help page (text is a string)
        elif title == "Help":
            text_area_height = (menu_y2 - menu_y1) - header_height - back_button_margin - back_button_height - 10
            max_lines = int(text_area_height // line_height)
            max_width = (menu_x2 - menu_x1) - 40
            wrapped_lines = self.wrap_text(items, font, item_font_scale, thickness, max_width)
            for i, line in enumerate(wrapped_lines[:max_lines]):
                y_pos = menu_y1 + header_height + 30 + i * 20
                cv2.putText(overlay, line, (menu_x1 + 20, y_pos), font, item_font_scale, (220, 220, 220), thickness)
        # Handle about page
        elif title == "About":
            about_text = "Whiffle Game v 9.2, Ideas by Blake Weibling coding by Grok"
            text_size = cv2.getTextSize(about_text, font, item_font_scale, thickness)[0]
            text_x = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
            text_y = menu_y1 + header_height + 30
            cv2.putText(overlay, about_text, (text_x, text_y), font, item_font_scale, (220, 220, 220), thickness)

            small_img = cv2.imread("logo.png")
            if small_img is not None:
                small_img = cv2.resize(small_img, (100, 100))
                img_h, img_w = small_img.shape[:2]
                img_x = menu_x1 + ((menu_x2 - menu_x1) - img_w) // 2
                img_y = text_y + text_size[1] + 20
                if img_y + img_h < menu_y2 - back_button_margin - back_button_height:
                    overlay[img_y:img_y + img_h, img_x:img_x + img_w] = small_img
                    self.menu_system.image_rect = (img_x, img_y, img_w, img_h)
            else:
                print("Warning: Could not load logo.png for About page")
                self.menu_system.image_rect = None

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

        alpha = 0.95
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

    def draw_leaderboard(self, frame):
        """Draw the leaderboard with the top scores."""
        overlay = frame.copy()
        h, w = frame.shape[:2]

        if self.menu_system.menu_pos_x is None or self.menu_system.menu_pos_y is None:
            self.menu_system.menu_pos_x = w // 4
            self.menu_system.menu_pos_y = h // 4

        menu_x1 = self.menu_system.menu_pos_x
        menu_y1 = self.menu_system.menu_pos_y
        menu_x2 = menu_x1 + (w // 2)
        menu_y2 = menu_y1 + (h // 2)

        menu_x1 = max(0, min(menu_x1, w - (menu_x2 - menu_x1)))
        menu_y1 = max(0, min(menu_y1, h - (menu_y2 - menu_y1)))
        menu_x2 = menu_x1 + (w // 2)
        menu_y2 = menu_y1 + (h // 2)

        self.menu_system.menu_pos_x = menu_x1
        self.menu_system.menu_pos_y = menu_y1

        self.menu_system.menu_area = (menu_x1, menu_y1, menu_x2 - menu_x1, menu_y2 - menu_y1)

        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

        header_height = 30
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (80, 80, 80), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
        self.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

        font = cv2.FONT_HERSHEY_SIMPLEX  # Update to more user-friendly font
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

        alpha = 0.95
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

    def draw_settings_menu(self, frame):
        """Draw the settings menu with configurable options."""
        overlay = frame.copy()
        h, w = frame.shape[:2]

        if self.menu_system.menu_pos_x is None or self.menu_system.menu_pos_y is None:
            self.menu_system.menu_pos_x = w // 4
            self.menu_system.menu_pos_y = h // 4

        menu_x1 = self.menu_system.menu_pos_x
        menu_y1 = self.menu_system.menu_pos_y
        menu_x2 = menu_x1 + (w * 3 // 4)
        menu_y2 = menu_y1 + (h // 2)

        menu_x1 = max(0, min(menu_x1, w - (menu_x2 - menu_x1)))
        menu_y1 = max(0, min(menu_y1, h - (menu_y2 - menu_y1)))
        menu_x2 = menu_x1 + (w * 3 // 4)
        menu_y2 = menu_y1 + (h // 2)

        self.menu_system.menu_pos_x = menu_x1
        self.menu_system.menu_pos_y = menu_y1

        self.menu_system.menu_area = (menu_x1, menu_y1, menu_x2 - menu_x1, menu_y2 - menu_y1)

        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

        header_height = 30
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (80, 80, 80), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
        self.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

        font = cv2.FONT_HERSHEY_SIMPLEX  # Update to more user-friendly font
        font_scale = 0.7
        thickness = 2

        title = "Settings"
        text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
        x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        y_pos = menu_y1 + header_height // 2 + text_size[1] // 2
        cv2.putText(overlay, title, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)

        font_scale = 0.5
        thickness = 1
        self.menu_system.menu_item_rects = []

        settings_items = [
            ("White Ball Detection", "white_ball_detection", "toggle"),
            ("Red Ball Detection", "red_ball_detection", "toggle"),
            ("Game Sounds", "game_sounds", "toggle"),
            ("Background Music", "background_music", "toggle"),
            ("Confidence Threshold", "detection_confidence_threshold", "slider", 0.0, 1.0, 0.01),
            ("Radius Tolerance", "detection_radius_tolerance", "slider", 0.0, 50.0, 1.0),
            ("Area Min", "detection_area_min", "slider", 0.0, 1000.0, 10.0),
            ("Area Max", "detection_area_max", "slider", 0.0, 5000.0, 100.0),
            ("Circularity Min", "detection_circularity_min", "slider", 0.0, 1.0, 0.01),
            ("Circularity Max", "detection_circularity_max", "slider", 0.0, 2.0, 0.01),
        ]

        toggles = [item for item in settings_items if item[2] == "toggle"]
        sliders = [item for item in settings_items if item[2] == "slider"]

        column_width = (menu_x2 - menu_x1 - 60) // 2
        left_column_x = menu_x1 + 20
        right_column_x = left_column_x + column_width + 20

        line_height = 40

        for idx, (label, key, item_type, *slider_args) in enumerate(toggles):
            x_pos = left_column_x
            y_pos = menu_y1 + header_height + 30 + idx * line_height
            color = (250, 206, 135) if idx == self.menu_system.selection else (220, 220, 220)

            value = getattr(self.menu_system.settings.config, key)
            display_text = f"{label}: {'On' if value else 'Off'}"
            text_size = cv2.getTextSize(display_text, font, font_scale, thickness)[0]
            toggle_x = x_pos + text_size[0] + 10
            toggle_y = y_pos - 10
            toggle_width, toggle_height = 50, 20
            self.draw_toggle(overlay, toggle_x, toggle_y, toggle_width, toggle_height, value)
            rect_x = toggle_x
            rect_y = toggle_y
            rect_w = toggle_width
            rect_h = toggle_height
            self.menu_system.menu_item_rects.append((rect_x, rect_y, rect_w, rect_h, idx))
            cv2.putText(overlay, display_text, (x_pos, y_pos), font, font_scale, color, thickness)

        for idx, (label, key, item_type, *slider_args) in enumerate(sliders, start=len(toggles)):
            x_pos = right_column_x
            y_pos = menu_y1 + header_height + 30 + (idx - len(toggles)) * line_height
            color = (250, 206, 135) if idx == self.menu_system.selection else (220, 220, 220)

            min_val, max_val, step = slider_args
            value = getattr(self.menu_system.settings.config, key)
            display_text = f"{label}: {value:.2f}"
            text_size = cv2.getTextSize(display_text, font, font_scale, thickness)[0]
            slider_x = x_pos + text_size[0] + 10
            slider_y = y_pos - 5
            slider_width = 100
            slider_height = 10
            slider_pos = slider_x + int((value - min_val) / (max_val - min_val) * slider_width)
            cv2.rectangle(overlay, (slider_x, slider_y), (slider_x + slider_width, slider_y + slider_height), (150, 150, 150), -1)
            cv2.rectangle(overlay, (slider_x, slider_y), (slider_pos, slider_y + slider_height), (255, 255, 0), -1)
            cv2.rectangle(overlay, (slider_x, slider_y), (slider_x + slider_width, slider_y + slider_height), (200, 200, 200), 1)
            self.menu_system.menu_item_rects.append({
                "type": "slider",
                "rect": (slider_x, slider_y, slider_width, slider_height),
                "key": key,
                "min_val": min_val,
                "max_val": max_val,
                "step": step,
                "index": idx
            })
            cv2.putText(overlay, display_text, (x_pos, y_pos), font, font_scale, color, thickness)

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

        reset_x = back_x + back_w + 20
        reset_y = menu_y2 - 60
        reset_w, reset_h = 150, 30
        self.menu_system.reset_button_rect = (reset_x, reset_y, reset_w, reset_h)
        cv2.rectangle(overlay, (reset_x, reset_y), (reset_x + reset_w, reset_y + reset_h), (200, 200, 200), -1)
        cv2.rectangle(overlay, (reset_x, reset_y), (reset_x + reset_w, reset_y + reset_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("Reset to Defaults", font, 0.5, 1)[0]
        text_x = reset_x + (reset_w - text_size[0]) // 2
        text_y = reset_y + (reset_h + text_size[1]) // 2
        cv2.putText(overlay, "Reset to Defaults", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

        alpha = 0.95
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

    def draw_game_over_menu(self, frame):
        """Draw the game over menu with the final score."""
        overlay = frame.copy()
        h, w = frame.shape[:2]

        if self.menu_system.menu_pos_x is None or self.menu_system.menu_pos_y is None:
            self.menu_system.menu_pos_x = w // 4
            self.menu_system.menu_pos_y = h // 4

        menu_x1 = self.menu_system.menu_pos_x
        menu_y1 = self.menu_system.menu_pos_y
        menu_x2 = menu_x1 + (w // 2)
        menu_y2 = menu_y1 + (h // 2)

        menu_x1 = max(0, min(menu_x1, w - (menu_x2 - menu_x1)))
        menu_y1 = max(0, min(menu_y1, h - (menu_y2 - menu_y1)))
        menu_x2 = menu_x1 + (w // 2)
        menu_y2 = menu_y1 + (h // 2)

        self.menu_system.menu_pos_x = menu_x1
        self.menu_system.menu_pos_y = menu_y1

        self.menu_system.menu_area = (menu_x1, menu_y1, menu_x2 - menu_x1, menu_y2 - menu_y1)

        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

        header_height = 30
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (80, 80, 80), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
        self.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

        font = cv2.FONT_HERSHEY_SIMPLEX  # Update to more user-friendly font
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

        alpha = 0.95
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

def resource_path(relative_path):
    """Get the absolute path to a resource, works for dev and for PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)