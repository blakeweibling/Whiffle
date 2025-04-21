# menu_renderer.py
class MenuRenderer:
    def __init__(self, menu_system):
        self.menu_system = menu_system
        self.leaderboard_scores = None
        self.leaderboard_is_online = False
        self.leaderboard_loading = False
        self.leaderboard_error = None
        self.last_update = 0  # For frame rate limiting

    def draw_menu_bar(self, frame):
        """Draw the menu bar at the top of the frame with a button to toggle the menu."""
        overlay = frame.copy()
        h, w = frame.shape[:2]

        cv2.rectangle(overlay, (0, 0), (w, 40), (128, 128, 128), -1)

        x, y, bw, bh = self.menu_system.button_rect
        cv2.rectangle(overlay, (x, y), (x + bw, y + bh), (200, 200, 200), -1)
        cv2.rectangle(overlay, (x, y), (x + bw, y + bh), (0, 0, 0), 1)

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1
        text_size = cv2.getTextSize(self.menu_system.button_text, font, font_scale, thickness)[0]
        text_x = x + (bw - text_size[0]) // 2
        text_y = y + (bh + text_size[1]) // 2
        cv2.putText(overlay, self.menu_system.button_text, (text_x, text_y), font, font_scale, (0, 0, 0), thickness)

        if self.menu_system.timer_text:
            timer_size = cv2.getTextSize(self.menu_system.timer_text, font, font_scale, thickness)[0]
            timer_x = w - timer_size[0] - 10
            timer_y = 10 + timer_size[1]
            cv2.putText(overlay, self.menu_system.timer_text, (timer_x, timer_y), font, font_scale, (255, 255, 255), thickness)

        alpha = 0.95
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

    def draw_menu(self, frame):
        """Draw the current menu based on the menu system's state."""
        # Limit frame rate to 10 FPS
        current_time = time.time()
        if current_time - self.last_update < 0.1:  # 0.1 seconds = 10 FPS
            return frame
        self.last_update = current_time

        if self.menu_system.state == "help":
            help_text = (
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
            return draw_text_page(self, frame, help_text, "Help")
        elif self.menu_system.state == "about":
            about_text = "Ball Tracking Game v1.0\nDeveloped by Bob Weibling\nPowered by OpenCV and xAI's Grok"
            return draw_text_page(self, frame, about_text, "About")
        elif self.menu_system.state == "leaderboard":
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
            return draw_leaderboard(self, frame)
        elif self.menu_system.state == "settings":
            return draw_settings_menu(self, frame)
        elif self.menu_system.state == "game_over":
            return draw_game_over_menu(self, frame)
        elif self.menu_system.state == "main_menu":
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

    # Other methods (draw_menu_items, draw_toggle, etc.) remain unchanged