import cv2
import numpy as np
from datetime import datetime
from game_utils import resource_path
import contextlib
import io

class MenuRenderer:
    def __init__(self, menu_system):
        self.menu_system = menu_system
        self.leaderboard_scores = []
        self.leaderboard_is_online = False
        self.leaderboard_loading = False
        self.leaderboard_error = False
        # Load the logo once during initialization
        self.logo = None
        logo_path = resource_path("logo.png")
        with contextlib.redirect_stderr(io.StringIO()):
            self.logo = cv2.imread(logo_path)
        if self.logo is None:
            print("Warning: Could not load logo.png for About page.")

    def wrap_text(self, text, font, font_scale, thickness, max_width):
        """Wrap text to fit within a maximum width."""
        if isinstance(text, list):
            return [item[0] for item in text]  # Extract text from (text, action) pairs
        words = text.split()
        lines = []
        current_line = []
        current_width = 0
        for word in words:
            word_size = cv2.getTextSize(word + " ", font, font_scale, thickness)[0][0]
            if current_width + word_size <= max_width:
                current_line.append(word)
                current_width += word_size
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_width = word_size
        if current_line:
            lines.append(" ".join(current_line))
        return lines

    def draw_toggle(self, overlay, x, y, width, height, value):
        """Draw a toggle switch."""
        color = (0, 255, 0) if value else (0, 0, 255)
        cv2.rectangle(overlay, (x, y), (x + width, y + height), (150, 150, 150), -1)
        cv2.rectangle(overlay, (x, y), (x + width, y + height), (0, 0, 0), 1)
        knob_x = x + width - height if value else x
        cv2.circle(overlay, (knob_x + height // 2, y + height // 2), height // 2, color, -1)
        cv2.circle(overlay, (knob_x + height // 2, y + height // 2), height // 2, (0, 0, 0), 1)

    def draw_menu(self, frame, menu):
        """Draw the current menu based on the state."""
        if not menu:
            return frame

        title = menu["title"]
        items = menu["items"]

        if title in ["Main Menu", "Select Game Mode"]:
            return self.draw_text_page(frame, items, title)
        elif title == "Settings":
            return self.draw_settings_menu(frame)
        elif title == "Leaderboard":
            return self.draw_leaderboard(frame)
        elif title == "Help":
            return self.draw_help_page(frame, items, title)
        elif title == "About":
            return self.draw_about_page(frame, items, title)
        elif title == "Game Over":
            return self.draw_game_over_menu(frame)
        return frame

    def draw_text_page(self, frame, items, title):
        """Draw a text page (e.g., Main Menu, Mode Selection) with the given items and title."""
        overlay = frame.copy()
        h, w = frame.shape[:2]

        # Use stored position or default to center
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
        header_color = (80, 80, 80) if not self.menu_system.is_dragging else (120, 120, 120)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), header_color, -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
        self.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

        font = cv2.FONT_HERSHEY_SIMPLEX
        title_font_scale = 0.7
        item_font_scale = 0.6
        thickness = 1

        # Draw title
        text_size = cv2.getTextSize(title, font, title_font_scale, thickness)[0]
        x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        y_pos = menu_y1 + header_height // 2 + text_size[1] // 2
        cv2.putText(overlay, title, (x_pos, y_pos), font, title_font_scale, (220, 220, 220), thickness)

        # Draw close button
        close_x = menu_x2 - 40
        close_y = menu_y1 + 5
        close_w, close_h = 30, 20
        self.menu_system.close_button_rect = (close_x, close_y, close_w, close_h)
        close_color = (0, 0, 255) if not self.menu_system.is_close_hovered else (255, 0, 0)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), close_color, -1)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("X", font, 0.5, 1)[0]
        text_x = close_x + (close_w - text_size[0]) // 2
        text_y = close_y + (close_h + text_size[1]) // 2
        cv2.putText(overlay, "X", (text_x, text_y), font, 0.5, (255, 255, 255), 1)

        # Draw back button
        back_x = menu_x1 + 20
        back_y = menu_y2 - 60
        back_w, back_h = 100, 30
        self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
        back_color = (200, 200, 200) if not self.menu_system.is_back_hovered else (150, 150, 150)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), back_color, -1)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
        text_x = back_x + (back_w - text_size[0]) // 2
        text_y = back_y + (back_h + text_size[1]) // 2
        cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

        # Draw menu items with scrolling support
        num_items = len(items)
        max_visible_items = 6  # Adjust based on menu height
        start_idx = self.menu_system.scroll_offset
        end_idx = min(start_idx + max_visible_items, num_items)
        items_per_column = (max_visible_items + 1) // 2
        column_width = ((menu_x2 - menu_x1) - 60) // 2
        left_column_x = menu_x1 + 20
        right_column_x = left_column_x + column_width + 20
        line_height = 40
        self.menu_system.menu_item_rects = []

        for idx in range(start_idx, end_idx):
            item_text, _ = items[idx]
            col_idx = (idx - start_idx) % items_per_column
            if (idx - start_idx) < items_per_column:
                x_pos = left_column_x
            else:
                x_pos = right_column_x

            y_pos = menu_y1 + header_height + 30 + col_idx * line_height
            is_hovered = any(rect[0] <= self.menu_system.mouse_x <= rect[0] + rect[2] and
                             rect[1] <= self.menu_system.mouse_y <= rect[1] + rect[3] and
                             rect[4] == idx for rect in self.menu_system.menu_item_rects)
            color = (250, 206, 135) if idx == self.menu_system.selection or is_hovered else (220, 220, 220)
            text_size = cv2.getTextSize(item_text, font, item_font_scale, thickness)[0]
            rect_x = x_pos
            rect_y = y_pos - text_size[1]
            rect_w = text_size[0] + 20
            rect_h = text_size[1] + 10
            self.menu_system.menu_item_rects.append((rect_x, rect_y, rect_w, rect_h, idx))
            cv2.putText(overlay, item_text, (x_pos, y_pos), font, item_font_scale, color, thickness)

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
        header_color = (80, 80, 80) if not self.menu_system.is_dragging else (120, 120, 120)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), header_color, -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
        self.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

        font = cv2.FONT_HERSHEY_SIMPLEX
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

        max_visible_items = 6  # Adjust based on menu height
        start_idx = self.menu_system.scroll_offset
        end_idx = min(start_idx + max_visible_items, len(settings_items))
        visible_items = settings_items[start_idx:end_idx]

        toggles = [item for item in visible_items if item[2] == "toggle"]
        sliders = [item for item in visible_items if item[2] == "slider"]

        column_width = (menu_x2 - menu_x1 - 60) // 2
        left_column_x = menu_x1 + 20
        right_column_x = left_column_x + column_width + 20

        line_height = 40

        for idx, (label, key, item_type, *slider_args) in enumerate(toggles, start=start_idx):
            x_pos = left_column_x
            y_pos = menu_y1 + header_height + 30 + (idx - start_idx) * line_height
            is_hovered = any(rect[0] <= self.menu_system.mouse_x <= rect[0] + rect[2] and
                             rect[1] <= self.menu_system.mouse_y <= rect[1] + rect[3] and
                             rect[4] == idx for rect in self.menu_system.menu_item_rects)
            color = (250, 206, 135) if idx == self.menu_system.selection or is_hovered else (220, 220, 220)

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

        for idx, (label, key, item_type, *slider_args) in enumerate(sliders, start=len(toggles) + start_idx):
            x_pos = right_column_x
            y_pos = menu_y1 + header_height + 30 + (idx - len(toggles) - start_idx) * line_height
            is_hovered = any(isinstance(rect, dict) and rect["index"] == idx and
                             rect["rect"][0] <= self.menu_system.mouse_x <= rect["rect"][0] + rect["rect"][2] and
                             rect["rect"][1] <= self.menu_system.mouse_y <= rect["rect"][1] + rect["rect"][3]
                             for rect in self.menu_system.menu_item_rects)
            color = (250, 206, 135) if idx == self.menu_system.selection or is_hovered else (220, 220, 220)

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
        close_color = (0, 0, 255) if not self.menu_system.is_close_hovered else (255, 0, 0)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), close_color, -1)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("X", font, 0.5, 1)[0]
        text_x = close_x + (close_w - text_size[0]) // 2
        text_y = close_y + (close_h + text_size[1]) // 2
        cv2.putText(overlay, "X", (text_x, text_y), font, 0.5, (255, 255, 255), 1)

        back_x = menu_x1 + 20
        back_y = menu_y2 - 60
        back_w, back_h = 100, 30
        self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
        back_color = (200, 200, 200) if not self.menu_system.is_back_hovered else (150, 150, 150)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), back_color, -1)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
        text_x = back_x + (back_w - text_size[0]) // 2
        text_y = back_y + (back_h + text_size[1]) // 2
        cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

        reset_x = back_x + back_w + 20
        reset_y = menu_y2 - 60
        reset_w, reset_h = 150, 30
        self.menu_system.reset_button_rect = (reset_x, reset_y, reset_w, reset_h)
        reset_color = (200, 200, 200) if not self.menu_system.is_reset_hovered else (150, 150, 150)
        cv2.rectangle(overlay, (reset_x, reset_y), (reset_x + reset_w, reset_y + reset_h), reset_color, -1)
        cv2.rectangle(overlay, (reset_x, reset_y), (reset_x + reset_w, reset_y + reset_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("Reset to Defaults", font, 0.5, 1)[0]
        text_x = reset_x + (reset_w - text_size[0]) // 2
        text_y = reset_y + (reset_h + text_size[1]) // 2
        cv2.putText(overlay, "Reset to Defaults", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

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
        header_color = (80, 80, 80) if not self.menu_system.is_dragging else (120, 120, 120)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), header_color, -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
        self.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

        font = cv2.FONT_HERSHEY_SIMPLEX
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

        back_button_height = 30
        back_button_margin = 60
        line_height = 30
        text_area_height = (menu_y2 - menu_y1) - header_height - back_button_margin - back_button_height - 10
        max_lines = int(text_area_height // line_height)

        if self.leaderboard_loading:
            text = "Loading..."
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
            y_pos = menu_y1 + (menu_y2 - menu_y1) // 2
            cv2.putText(overlay, text, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)
        elif self.leaderboard_error:
            text = f"Failed to load online leaderboard. Showing local scores."
            wrapped_lines = self.wrap_text(text, font, font_scale, thickness, menu_x2 - menu_x1 - 40)
            start_idx = self.menu_system.scroll_offset
            end_idx = min(start_idx + max_lines, len(wrapped_lines))
            for i, line in enumerate(wrapped_lines[start_idx:end_idx]):
                text_size = cv2.getTextSize(line, font, font_scale, thickness)[0]
                x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
                y_pos = menu_y1 + header_height + 50 + i * line_height
                cv2.putText(overlay, line, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)
            if self.leaderboard_scores:
                offset = len(wrapped_lines)
                start_idx = max(0, self.menu_system.scroll_offset - offset)
                end_idx = min(start_idx + (max_lines - offset), len(self.leaderboard_scores))
                for i in range(start_idx, end_idx):
                    score_entry = self.leaderboard_scores[i]
                    initials = score_entry["initials"]
                    score = score_entry["score"]
                    created_at = datetime.fromisoformat(score_entry["created_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d")
                    text = f"{i+1}. {initials}: {score} ({created_at})"
                    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                    x_pos = menu_x1 + 20
                    y_pos = menu_y1 + header_height + 50 + (i - start_idx + offset) * line_height
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
            start_idx = self.menu_system.scroll_offset
            end_idx = min(start_idx + (max_lines - 1), len(self.leaderboard_scores))
            for i in range(start_idx, end_idx):
                score_entry = self.leaderboard_scores[i]
                initials = score_entry["initials"]
                score = score_entry["score"]
                created_at = datetime.fromisoformat(score_entry["created_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d")
                text = f"{i+1}. {initials}: {score} ({created_at})"
                text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                x_pos = menu_x1 + 20
                y_pos = menu_y1 + header_height + 50 + (i - start_idx + 1) * line_height
                cv2.putText(overlay, text, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)

        close_x = menu_x2 - 40
        close_y = menu_y1 + 5
        close_w, close_h = 30, 20
        self.menu_system.close_button_rect = (close_x, close_y, close_w, close_h)
        close_color = (0, 0, 255) if not self.menu_system.is_close_hovered else (255, 0, 0)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), close_color, -1)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("X", font, 0.5, 1)[0]
        text_x = close_x + (close_w - text_size[0]) // 2
        text_y = close_y + (close_h + text_size[1]) // 2
        cv2.putText(overlay, "X", (text_x, text_y), font, 0.5, (255, 255, 255), 1)

        back_x = menu_x1 + 20
        back_y = menu_y2 - 60
        back_w, back_h = 100, 30
        self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
        back_color = (200, 200, 200) if not self.menu_system.is_back_hovered else (150, 150, 150)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), back_color, -1)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
        text_x = back_x + (back_w - text_size[0]) // 2
        text_y = back_y + (back_h + text_size[1]) // 2
        cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

        alpha = 0.95
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

    def draw_help_page(self, frame, items, title):
        """Draw the help page with the given items and title."""
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
        header_color = (80, 80, 80) if not self.menu_system.is_dragging else (120, 120, 120)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), header_color, -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
        self.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2

        text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
        x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        y_pos = menu_y1 + header_height // 2 + text_size[1] // 2
        cv2.putText(overlay, title, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)

        close_x = menu_x2 - 40
        close_y = menu_y1 + 5
        close_w, close_h = 30, 20
        self.menu_system.close_button_rect = (close_x, close_y, close_w, close_h)
        close_color = (0, 0, 255) if not self.menu_system.is_close_hovered else (255, 0, 0)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), close_color, -1)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("X", font, 0.5, 1)[0]
        text_x = close_x + (close_w - text_size[0]) // 2
        text_y = close_y + (close_h + text_size[1]) // 2
        cv2.putText(overlay, "X", (text_x, text_y), font, 0.5, (255, 255, 255), 1)

        back_x = menu_x1 + 20
        back_y = menu_y2 - 60
        back_w, back_h = 100, 30
        self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
        back_color = (200, 200, 200) if not self.menu_system.is_back_hovered else (150, 150, 150)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), back_color, -1)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
        text_x = back_x + (back_w - text_size[0]) // 2
        text_y = back_y + (back_h + text_size[1]) // 2
        cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

        font_scale = 0.6
        thickness = 1
        line_height = 30
        back_button_height = 30
        back_button_margin = 60
        text_area_height = (menu_y2 - menu_y1) - header_height - back_button_margin - back_button_height - 10
        max_lines = int(text_area_height // line_height)
        max_width = (menu_x2 - menu_x1) - 40
        wrapped_lines = self.wrap_text(items, font, font_scale, thickness, max_width)

        start_idx = self.menu_system.scroll_offset
        end_idx = min(start_idx + max_lines, len(wrapped_lines))
        for i, line in enumerate(wrapped_lines[start_idx:end_idx]):
            y_pos = menu_y1 + header_height + 30 + i * line_height
            cv2.putText(overlay, line, (menu_x1 + 20, y_pos), font, font_scale, (220, 220, 220), thickness)

        # Draw scrollbar
        total_lines = len(wrapped_lines)
        if total_lines > max_lines:
            scrollbar_width = 10
            scrollbar_x = menu_x2 - scrollbar_width - 5
            scrollbar_y_start = menu_y1 + header_height + 5
            scrollbar_height = (menu_y2 - menu_y1) - header_height - back_button_margin - back_button_height - 10
            cv2.rectangle(overlay, (scrollbar_x, scrollbar_y_start), 
                          (scrollbar_x + scrollbar_width, scrollbar_y_start + scrollbar_height), 
                          (150, 150, 150), -1)
            cv2.rectangle(overlay, (scrollbar_x, scrollbar_y_start), 
                          (scrollbar_x + scrollbar_width, scrollbar_y_start + scrollbar_height), 
                          (0, 0, 0), 1)

            # Calculate the height of the scrollbar thumb
            thumb_height = max(20, (max_lines / total_lines) * scrollbar_height)
            thumb_y_start = scrollbar_y_start + (self.menu_system.scroll_offset / total_lines) * (scrollbar_height - thumb_height)
            thumb_y_end = thumb_y_start + thumb_height
            cv2.rectangle(overlay, (scrollbar_x, int(thumb_y_start)), 
                          (scrollbar_x + scrollbar_width, int(thumb_y_end)), 
                          (200, 200, 200), -1)
            cv2.rectangle(overlay, (scrollbar_x, int(thumb_y_start)), 
                          (scrollbar_x + scrollbar_width, int(thumb_y_end)), 
                          (0, 0, 0), 1)

        alpha = 0.95
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

    def draw_about_page(self, frame, items, title):
        """Draw the about page with the given items and title."""
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
        header_color = (80, 80, 80) if not self.menu_system.is_dragging else (120, 120, 120)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), header_color, -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
        self.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2

        text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
        x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        y_pos = menu_y1 + header_height // 2 + text_size[1] // 2
        cv2.putText(overlay, title, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)

        close_x = menu_x2 - 40
        close_y = menu_y1 + 5
        close_w, close_h = 30, 20
        self.menu_system.close_button_rect = (close_x, close_y, close_w, close_h)
        close_color = (0, 0, 255) if not self.menu_system.is_close_hovered else (255, 0, 0)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), close_color, -1)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("X", font, 0.5, 1)[0]
        text_x = close_x + (close_w - text_size[0]) // 2
        text_y = close_y + (close_h + text_size[1]) // 2
        cv2.putText(overlay, "X", (text_x, text_y), font, 0.5, (255, 255, 255), 1)

        back_x = menu_x1 + 20
        back_y = menu_y2 - 60
        back_w, back_h = 100, 30
        self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
        back_color = (200, 200, 200) if not self.menu_system.is_back_hovered else (150, 150, 150)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), back_color, -1)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
        text_x = back_x + (back_w - text_size[0]) // 2
        text_y = back_y + (back_h + text_size[1]) // 2
        cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

        font_scale = 0.6
        thickness = 1
        back_button_height = 30
        back_button_margin = 60

        # Draw the text
        about_text = "Whiffle Game v 9.2, Ideas by Blake Weibling coding by Grok"
        text_size = cv2.getTextSize(about_text, font, font_scale, thickness)[0]
        text_x = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        text_y = menu_y1 + header_height + 30
        cv2.putText(overlay, about_text, (text_x, text_y), font, font_scale, (220, 220, 220), thickness)

        # Draw the image below the text
        if self.logo is not None:
            logo_h, logo_w = self.logo.shape[:2]
            target_width = (menu_x2 - menu_x1) * 0.5
            target_height = (menu_y2 - menu_y1) * 0.5
            scale = min(target_width / logo_w, target_height / logo_h)
            new_w, new_h = int(logo_w * scale), int(logo_h * scale)
            logo_resized = cv2.resize(self.logo, (new_w, new_h))
            logo_y = text_y + text_size[1] + 20
            logo_x = menu_x1 + ((menu_x2 - menu_x1) - new_w) // 2
            if logo_y + new_h <= menu_y2 - back_button_margin - back_button_height:
                overlay[logo_y:logo_y + new_h, logo_x:logo_x + new_w] = logo_resized
                self.menu_system.image_rect = (logo_x, logo_y, new_w, new_h)
            else:
                scale = (menu_y2 - back_button_margin - back_button_height - logo_y) / logo_h
                new_w, new_h = int(logo_w * scale), int(logo_h * scale)
                logo_resized = cv2.resize(self.logo, (new_w, new_h))
                overlay[logo_y:logo_y + new_h, logo_x:logo_x + new_w] = logo_resized
                self.menu_system.image_rect = (logo_x, logo_y, new_w, new_h)
        else:
            self.menu_system.image_rect = None

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
        header_color = (80, 80, 80) if not self.menu_system.is_dragging else (120, 120, 120)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), header_color, -1)
        cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
        self.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

        font = cv2.FONT_HERSHEY_SIMPLEX
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
        close_color = (0, 0, 255) if not self.menu_system.is_close_hovered else (255, 0, 0)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), close_color, -1)
        cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("X", font, 0.5, 1)[0]
        text_x = close_x + (close_w - text_size[0]) // 2
        text_y = close_y + (close_h + text_size[1]) // 2
        cv2.putText(overlay, "X", (text_x, text_y), font, 0.5, (255, 255, 255), 1)

        back_x = menu_x1 + 20
        back_y = menu_y2 - 60
        back_w, back_h = 100, 30
        self.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
        back_color = (200, 200, 200) if not self.menu_system.is_back_hovered else (150, 150, 150)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), back_color, -1)
        cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
        text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
        text_x = back_x + (back_w - text_size[0]) // 2
        text_y = back_y + (back_h + text_size[1]) // 2
        cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

        alpha = 0.95
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame