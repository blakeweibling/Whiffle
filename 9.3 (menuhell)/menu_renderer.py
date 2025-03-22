import cv2
import numpy as np
from game_utils import resource_path
import contextlib
import io

class MenuRenderer:
    def __init__(self, menu_system):
        self.menu_system = menu_system
        self.leaderboard_scores = []
        self.leaderboard_is_online = False
        # Load the logo once during initialization to minimize cv2.imread calls
        self.logo = None
        logo_path = resource_path("logo.png")
        with contextlib.redirect_stderr(io.StringIO()):
            self.logo = cv2.imread(logo_path)
        if self.logo is None:
            print("Warning: Could not load logo.png for About page.")

    def draw_text_page(self, frame, items, title):
        h, w = frame.shape[:2]
        self.menu_system.menu_item_rects = []
        overlay = frame.copy()
        alpha = 0.8

        menu_x1 = w // 4  # 320
        menu_y1 = 100
        menu_x2 = w - (w // 4)  # 960
        menu_y2 = h - 100  # 620
        self.menu_system.menu_area = (menu_x1, menu_y1, menu_x2, menu_y2)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

        header_height = 30
        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.7
        thickness = 2
        text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
        text_x = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        text_y = menu_y1 + header_height // 2 + text_size[1] // 2
        cv2.putText(overlay, title, (text_x, text_y), font, font_scale, (220, 220, 220), thickness)

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

        back_x = menu_x1 + 10
        back_y = menu_y2 - 30
        back_w, back_h = 60, 20
        self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (200, 200, 200), -1)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
        text_x = back_x + (back_w - text_size[0]) // 2
        text_y = back_y + (back_h + text_size[1]) // 2
        cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

        font_scale = 0.6
        thickness = 1
        line_height = 30
        items_per_column = (len(items) + 1) // 2
        left_column_x = menu_x1 + 10
        right_column_x = (menu_x1 + menu_x2) // 2 + 10

        for idx, (item_text, _) in enumerate(items):
            x_pos = left_column_x if idx < items_per_column else right_column_x
            col_idx = idx if idx < items_per_column else idx - items_per_column
            y_pos = menu_y1 + header_height + 10 + col_idx * line_height
            color = (250, 206, 135) if idx == self.menu_system.selection else (220, 220, 220)
            text_size = cv2.getTextSize(item_text, font, font_scale, thickness)[0]
            rect_x = x_pos
            rect_y = y_pos - text_size[1]
            rect_w = text_size[0] + 40
            rect_h = text_size[1] + 20
            self.menu_system.menu_item_rects.append((rect_x, rect_y, rect_w, rect_h, idx))
            cv2.putText(overlay, item_text, (x_pos, y_pos), font, font_scale, color, thickness)

        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

    def draw_settings_page(self, frame, items, title):
        h, w = frame.shape[:2]
        self.menu_system.menu_item_rects = []
        self.menu_system.settings_sliders = []
        overlay = frame.copy()
        alpha = 0.8

        menu_x1 = w // 4
        menu_y1 = 100
        menu_x2 = w - (w // 4)
        menu_y2 = h - 100
        self.menu_system.menu_area = (menu_x1, menu_y1, menu_x2, menu_y2)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

        header_height = 30
        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.7
        thickness = 2
        text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
        text_x = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        text_y = menu_y1 + header_height // 2 + text_size[1] // 2
        cv2.putText(overlay, title, (text_x, text_y), font, font_scale, (220, 220, 220), thickness)

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

        back_x = menu_x1 + 10
        back_y = menu_y2 - 30
        back_w, back_h = 60, 20
        self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (200, 200, 200), -1)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
        text_x = back_x + (back_w - text_size[0]) // 2
        text_y = back_y + (back_h + text_size[1]) // 2
        cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

        font_scale = 0.6
        thickness = 1
        line_height = 30
        left_column_x = menu_x1 + 20
        right_column_x = (menu_x1 + menu_x2) // 2 + 20

        for idx, (item_text, _) in enumerate(items):
            x_pos = left_column_x
            y_pos = menu_y1 + header_height + 30 + idx * line_height
            color = (250, 206, 135) if idx == self.menu_system.selection else (220, 220, 220)
            text_size = cv2.getTextSize(item_text, font, font_scale, thickness)[0]
            rect_x = x_pos
            rect_y = y_pos - text_size[1]
            rect_w = text_size[0] + 20
            rect_h = text_size[1] + 10
            self.menu_system.menu_item_rects.append((rect_x, rect_y, rect_w, rect_h, idx))
            cv2.putText(overlay, item_text, (x_pos, y_pos), font, font_scale, color, thickness)

        settings = [
            ("detection_confidence_threshold", "Confidence Threshold"),
            ("detection_radius_tolerance", "Radius Tolerance"),
            ("detection_area_min", "Min Area"),
            ("detection_area_max", "Max Area"),
            ("detection_circularity_min", "Min Circularity"),
            ("detection_circularity_max", "Max Circularity")
        ]
        slider_width = 200
        slider_height = 10
        for idx, (setting_name, display_name) in enumerate(settings):
            y_pos = menu_y1 + header_height + 30 + (len(items) + idx) * line_height
            x_pos = left_column_x
            value = getattr(self.menu_system.settings.config, setting_name)
            min_val = 0.0 if "threshold" in setting_name or "min" in setting_name else 1.0
            max_val = 1.0 if "threshold" in setting_name or "circularity" in setting_name else 2000.0 if "area_max" in setting_name else 100.0
            if setting_name == "detection_circularity_max":
                min_val = 0.0
            if max_val - min_val == 0:
                slider_pos = 0
            else:
                slider_pos = (value - min_val) / (max_val - min_val) * slider_width
            cv2.rectangle(overlay, (x_pos, y_pos - 5), (x_pos + slider_width, y_pos + 5), (200, 200, 200), -1)
            cv2.rectangle(overlay, (x_pos, y_pos - 5), (x_pos + int(slider_pos), y_pos + 5), (0, 255, 0), -1)
            cv2.rectangle(overlay, (x_pos, y_pos - 5), (x_pos + slider_width, y_pos + 5), (0, 0, 0), 1)
            text = f"{display_name}: {value:.2f}"
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            cv2.putText(overlay, text, (x_pos + slider_width + 20, y_pos + text_size[1] // 2), font, font_scale, (220, 220, 220), thickness)
            self.menu_system.settings_sliders.append(((x_pos, y_pos - 5, slider_width, 10), (setting_name, value)))

        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

    def draw_leaderboard_page(self, frame, items, title):
        h, w = frame.shape[:2]
        self.menu_system.menu_item_rects = []
        overlay = frame.copy()
        alpha = 0.8

        menu_x1 = w // 4
        menu_y1 = 100
        menu_x2 = w - (w // 4)
        menu_y2 = h - 100
        self.menu_system.menu_area = (menu_x1, menu_y1, menu_x2, menu_y2)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

        header_height = 30
        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.7
        thickness = 2
        text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
        text_x = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        text_y = menu_y1 + header_height // 2 + text_size[1] // 2
        cv2.putText(overlay, title, (text_x, text_y), font, font_scale, (220, 220, 220), thickness)

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

        back_x = menu_x1 + 10
        back_y = menu_y2 - 30
        back_w, back_h = 60, 20
        self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (200, 200, 200), -1)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
        text_x = back_x + (back_w - text_size[0]) // 2
        text_y = back_y + (back_h + text_size[1]) // 2
        cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

        font_scale = 0.6
        thickness = 1
        line_height = 30
        left_column_x = menu_x1 + 20

        status_text = "Online Leaderboard" if self.leaderboard_is_online else "Local Leaderboard"
        text_size = cv2.getTextSize(status_text, font, font_scale, thickness)[0]
        text_x = menu_x1 + 20
        text_y = menu_y1 + header_height + 20
        cv2.putText(overlay, status_text, (text_x, text_y), font, font_scale, (220, 220, 220), thickness)

        for idx, (item_text, _) in enumerate(items):
            x_pos = left_column_x
            y_pos = menu_y1 + header_height + 50 + idx * line_height
            color = (250, 206, 135) if idx == self.menu_system.selection else (220, 220, 220)
            text_size = cv2.getTextSize(item_text, font, font_scale, thickness)[0]
            rect_x = x_pos
            rect_y = y_pos - text_size[1]
            rect_w = text_size[0] + 20
            rect_h = text_size[1] + 10
            self.menu_system.menu_item_rects.append((rect_x, rect_y, rect_w, rect_h, idx))
            cv2.putText(overlay, item_text, (x_pos, y_pos), font, font_scale, color, thickness)

        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

    def draw_help_page(self, frame, items, title):
        h, w = frame.shape[:2]
        self.menu_system.menu_item_rects = []
        overlay = frame.copy()
        alpha = 0.8

        menu_x1 = w // 4
        menu_y1 = 100
        menu_x2 = w - (w // 4)
        menu_y2 = h - 100
        self.menu_system.menu_area = (menu_x1, menu_y1, menu_x2, menu_y2)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

        header_height = 30
        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.7
        thickness = 2
        text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
        text_x = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        text_y = menu_y1 + header_height // 2 + text_size[1] // 2
        cv2.putText(overlay, title, (text_x, text_y), font, font_scale, (220, 220, 220), thickness)

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

        back_x = menu_x1 + 10
        back_y = menu_y2 - 30
        back_w, back_h = 60, 20
        self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (200, 200, 200), -1)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
        text_x = back_x + (back_w - text_size[0]) // 2
        text_y = back_y + (back_h + text_size[1]) // 2
        cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

        font_scale = 0.6
        thickness = 1
        line_height = 30
        left_column_x = menu_x1 + 20

        for idx, (item_text, _) in enumerate(items):
            x_pos = left_column_x
            y_pos = menu_y1 + header_height + 30 + idx * line_height
            color = (220, 220, 220)
            text_size = cv2.getTextSize(item_text, font, font_scale, thickness)[0]
            rect_x = x_pos
            rect_y = y_pos - text_size[1]
            rect_w = text_size[0] + 20
            rect_h = text_size[1] + 10
            self.menu_system.menu_item_rects.append((rect_x, rect_y, rect_w, rect_h, idx))
            cv2.putText(overlay, item_text, (x_pos, y_pos), font, font_scale, color, thickness)

        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

    def draw_about_page(self, frame, items, title):
        h, w = frame.shape[:2]
        self.menu_system.menu_item_rects = []
        overlay = frame.copy()
        alpha = 0.8

        menu_x1 = w // 4
        menu_y1 = 100
        menu_x2 = w - (w // 4)
        menu_y2 = h - 100
        self.menu_system.menu_area = (menu_x1, menu_y1, menu_x2, menu_y2)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

        header_height = 30
        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.7
        thickness = 2
        text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
        text_x = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        text_y = menu_y1 + header_height // 2 + text_size[1] // 2
        cv2.putText(overlay, title, (text_x, text_y), font, font_scale, (220, 220, 220), thickness)

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

        back_x = menu_x1 + 10
        back_y = menu_y2 - 30
        back_w, back_h = 60, 20
        self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (200, 200, 200), -1)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
        text_x = back_x + (back_w - text_size[0]) // 2
        text_y = back_y + (back_h + text_size[1]) // 2
        cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

        font_scale = 0.6
        thickness = 1
        left_column_x = menu_x1 + 20

        # Draw the text first
        for idx, (item_text, _) in enumerate(items):
            x_pos = left_column_x
            y_pos = menu_y1 + header_height + 30 + idx * 30  # Position text right after the header
            color = (220, 220, 220)
            text_size = cv2.getTextSize(item_text, font, font_scale, thickness)[0]
            x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
            rect_x = x_pos
            rect_y = y_pos - text_size[1]
            rect_w = text_size[0] + 20
            rect_h = text_size[1] + 10
            self.menu_system.menu_item_rects.append((rect_x, rect_y, rect_w, rect_h, idx))
            cv2.putText(overlay, item_text, (x_pos, y_pos), font, font_scale, color, thickness)

        # Draw the image below the text using the pre-loaded logo
        if self.logo is not None:
            logo_h, logo_w = self.logo.shape[:2]
            # Scale the logo to 50% of the menu window's dimensions while maintaining aspect ratio
            target_width = (menu_x2 - menu_x1) * 0.5  # 50% of menu width
            target_height = (menu_y2 - menu_y1) * 0.5  # 50% of menu height
            scale = min(target_width / logo_w, target_height / logo_h)
            new_w, new_h = int(logo_w * scale), int(logo_h * scale)
            logo_resized = cv2.resize(self.logo, (new_w, new_h))
            # Position the image below the text (text ends at y_pos + text_size[1])
            logo_y = y_pos + text_size[1] + 20  # Add some padding (20 pixels) below the text
            logo_x = menu_x1 + ((menu_x2 - menu_x1) - new_w) // 2
            # Ensure the logo fits within the menu area
            if logo_y + new_h <= menu_y2 - 10:  # Check if the logo fits vertically
                overlay[logo_y:logo_y + new_h, logo_x:logo_x + new_w] = logo_resized
                self.menu_system.image_rect = (logo_x, logo_y, new_w, new_h)
            else:
                # If the logo doesn't fit, adjust its size further
                scale = (menu_y2 - 10 - logo_y) / logo_h
                new_w, new_h = int(logo_w * scale), int(logo_h * scale)
                logo_resized = cv2.resize(self.logo, (new_w, new_h))
                overlay[logo_y:logo_y + new_h, logo_x:logo_x + new_w] = logo_resized
                self.menu_system.image_rect = (logo_x, logo_y, new_w, new_h)

        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

    def draw_game_over_page(self, frame, items, title):
        h, w = frame.shape[:2]
        self.menu_system.menu_item_rects = []
        overlay = frame.copy()
        alpha = 0.8

        menu_x1 = w // 4
        menu_y1 = 100
        menu_x2 = w - (w // 4)
        menu_y2 = h - 100
        self.menu_system.menu_area = (menu_x1, menu_y1, menu_x2, menu_y2)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

        header_height = 30
        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.7
        thickness = 2
        text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
        text_x = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        text_y = menu_y1 + header_height // 2 + text_size[1] // 2
        cv2.putText(overlay, title, (text_x, text_y), font, font_scale, (220, 220, 220), thickness)

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

        back_x = menu_x1 + 10
        back_y = menu_y2 - 30
        back_w, back_h = 60, 20
        self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (200, 200, 200), -1)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
        text_x = back_x + (back_w - text_size[0]) // 2
        text_y = back_y + (back_h + text_size[1]) // 2
        cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

        font_scale = 0.6
        thickness = 1
        left_column_x = menu_x1 + 20

        for idx, (item_text, _) in enumerate(items):
            x_pos = left_column_x
            y_pos = menu_y1 + header_height + 30 + idx * 30
            color = (220, 220, 220)
            text_size = cv2.getTextSize(item_text, font, font_scale, thickness)[0]
            x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
            rect_x = x_pos
            rect_y = y_pos - text_size[1]
            rect_w = text_size[0] + 20
            rect_h = text_size[1] + 10
            self.menu_system.menu_item_rects.append((rect_x, rect_y, rect_w, rect_h, idx))
            cv2.putText(overlay, item_text, (x_pos, y_pos), font, font_scale, color, thickness)

        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame