import cv2
import time
from menu_renderer import MenuRenderer
from menu_input_handler import MenuInputHandler
from confirmation_dialog import ConfirmationDialog

class MenuSystem:
    def __init__(self, scoring_zones, leaderboard, game_duration=120, sound_manager=None):
        self.state = "closed"
        self.selection = 0
        self.menu_stack = []
        self.scroll_offset = 0
        self.button_rect = None
        self.close_button_rect = None
        self.back_button_rect = None
        self.reset_button_rect = None
        self.image_rect = None
        self.menu_area = None
        self.header_rect = None
        self.menu_item_rects = []
        self.settings_sliders = []
        self.is_dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.mouse_x = 0
        self.mouse_y = 0
        self.is_close_hovered = False
        self.is_back_hovered = False
        self.is_reset_hovered = False
        self.is_slider_dragging = False
        self.dragged_slider = None
        # Initialize menu position
        self.menu_pos_x = None
        self.menu_pos_y = None
        self.renderer = MenuRenderer(self)
        self.input_handler = MenuInputHandler(self)
        self.scoring_zones = scoring_zones
        self.leaderboard = leaderboard
        self.game_duration = game_duration
        self.timer_start = None
        self.timer_active = False
        self.timer_text = ""
        self.is_game_in_progress = False
        self.total_score = 0
        self.mode = "classic"
        self.sound_manager = sound_manager
        self.confirmation_dialog = None

        self.main_menu = {
            "File": {
                "New Game": lambda: self.set_state("mode_selection"),
                "Resume Game": lambda: self.resume_game(),
                "Pause Game": lambda: self.pause_game(),
                "Restart Game": lambda: self.prompt_restart_game(),
                "Settings": lambda: self.set_state("settings"),
                "Leaderboard": lambda: self.set_state("leaderboard"),
                "Help": lambda: self.set_state("help"),
                "About": lambda: self.set_state("about")
            },
            "Exit": lambda: self.set_state("closed")
        }
        self.current_menu = self.main_menu

    def reset_menu(self):
        self.current_menu = self.main_menu
        self.menu_stack = []
        self.selection = 0
        self.scroll_offset = 0
        self.menu_pos_x = None
        self.menu_pos_y = None

    def set_state(self, state):
        print(f"Setting state to: {state}")
        self.state = state
        self.selection = 0
        self.scroll_offset = 0
        self.menu_item_rects = []
        self.settings_sliders = []

    def enter_submenu(self, submenu_key):
        if submenu_key in self.current_menu and isinstance(self.current_menu[submenu_key], dict):
            self.menu_stack.append(self.current_menu)
            self.current_menu = self.current_menu[submenu_key]
            self.selection = 0
            self.set_state("main_menu")

    def is_menu_active(self):
        return self.state != "closed"

    def get_current_menu(self):
        if not self.is_menu_active():
            return None

        state_titles = {
            "main_menu": "Main Menu",
            "settings": "Settings",
            "leaderboard": "Leaderboard",
            "help": "Help",
            "about": "About",
            "mode_selection": "Select Game Mode",
            "game_over": "Game Over"
        }
        title = state_titles.get(self.state, "Menu")

        items = []
        if self.state == "main_menu":
            for key, value in self.current_menu.items():
                if key == "Resume Game":
                    if self.is_game_in_progress and not self.timer_active:
                        items.append((key, value))
                elif key == "Pause Game":
                    if self.is_game_in_progress and self.timer_active:
                        items.append((key, value))
                elif key == "Restart Game":
                    if self.is_game_in_progress:
                        items.append((key, value))
                else:
                    items.append((key, value if callable(value) else lambda k=key: self.enter_submenu(k)))
        elif self.state == "mode_selection":
            items = [
                ("Classic", lambda: self.start_new_game("classic")),
                ("Timed", lambda: self.start_new_game("timed"))
            ]
        elif self.state == "settings":
            items = [
                (f"White Ball Detection: {'On' if self.settings.config.white_ball_detection else 'Off'}", 
                 lambda: self.toggle_setting("white_ball_detection")),
                (f"Red Ball Detection: {'On' if self.settings.config.red_ball_detection else 'Off'}", 
                 lambda: self.toggle_setting("red_ball_detection")),
                (f"Game Sounds: {'On' if self.settings.config.game_sounds else 'Off'}", 
                 lambda: self.toggle_setting("game_sounds")),
                (f"Background Music: {'On' if self.settings.config.background_music else 'Off'}", 
                 lambda: self.toggle_setting("background_music")),
                (f"Confidence Threshold: {self.settings.config.detection_confidence_threshold:.2f}", lambda: None),
                (f"Radius Tolerance: {self.settings.config.detection_radius_tolerance:.2f}", lambda: None),
                (f"Area Min: {self.settings.config.detection_area_min:.2f}", lambda: None),
                (f"Area Max: {self.settings.config.detection_area_max:.2f}", lambda: None),
                (f"Circularity Min: {self.settings.config.detection_circularity_min:.2f}", lambda: None),
                (f"Circularity Max: {self.settings.config.detection_circularity_max:.2f}", lambda: None),
            ]
        elif self.state == "leaderboard":
            scores, is_online = self.leaderboard.get_top_scores(self.mode)
            self.renderer.leaderboard_scores = scores
            self.renderer.leaderboard_is_online = is_online
            items = [(f"{entry['initials']}: {entry['score']}", lambda: None) 
                     for entry in scores] if scores else [("No scores yet", lambda: None)]
        elif self.state == "help":
            all_items = [
                ("Click 'New Game' to start playing", lambda: None),
                ("W/S or Arrows: Navigate menu", lambda: None),
                ("Enter: Select menu item", lambda: None),
                ("Esc: Close menu", lambda: None),
                ("Red balls: 2x points, White: 1x", lambda: None),
                ("Half balls: 1.5x points", lambda: None),
                ("'c': Calibrate zones", lambda: None),
                ("'r': Reset score", lambda: None),
                ("'q': Submit score when game ends", lambda: None),
                ("'f': Flip camera horizontally", lambda: None),
                ("'d': Toggle debug mode", lambda: None)
            ]
            max_visible_items = 9
            start_idx = self.scroll_offset
            end_idx = min(start_idx + max_visible_items, len(all_items))
            items = all_items[start_idx:end_idx]
        elif self.state == "about":
            items = [("Whiffle Game v 9.2, Ideas by Blake Weibling coding by Grok", lambda: None)]
        elif self.state == "game_over":
            items = [(f"Game Over! Final Score: {self.total_score}", lambda: None)]
        return {"title": title, "items": items}

    def toggle_setting(self, setting_name):
        current_value = getattr(self.settings.config, setting_name)
        setattr(self.settings.config, setting_name, not current_value)
        self.settings.save_config()
        if self.sound_manager:
            self.sound_manager.update_settings()

    def start_new_game(self, mode):
        self.mode = mode
        self.timer_active = True
        self.timer_start = time.time()
        self.is_game_in_progress = True
        self.total_score = 0
        self.scoring_zones.reset_scored_balls()
        self.set_state("closed")

    def resume_game(self):
        if self.is_game_in_progress and not self.timer_active:
            self.timer_active = True
            self.timer_start = time.time() - (self.game_duration - int(self.timer_text.split(":")[1]))
            self.set_state("closed")

    def pause_game(self):
        if self.is_game_in_progress and self.timer_active:
            self.timer_active = False
            self.set_state("main_menu")

    def prompt_restart_game(self):
        self.confirmation_dialog = ConfirmationDialog("Restart game? (y/n)", self.restart_game)

    def restart_game(self):
        self.timer_active = False
        self.is_game_in_progress = False
        self.total_score = 0
        self.scoring_zones.reset_scored_balls()
        self.set_state("main_menu")
        self.confirmation_dialog = None

    def update_timer(self):
        if not self.timer_active:
            return
        elapsed = time.time() - self.timer_start
        remaining = max(0, self.game_duration - int(elapsed))
        minutes = remaining // 60
        seconds = remaining % 60
        self.timer_text = f"Time: {minutes:02d}:{seconds:02d}"
        if remaining <= 0:
            self.timer_active = False
            self.is_game_in_progress = False
            self.set_state("game_over")

    def draw_menu_bar(self, frame):
        h, w = frame.shape[:2]
        scale_x = w / 1280
        scale_y = h / 720
        self.button_rect = (int(10 * scale_x), int(5 * scale_y), int(150 * scale_x), int(30 * scale_y))
        overlay = frame.copy()
        cv2.rectangle(overlay, (self.button_rect[0], self.button_rect[1]), 
                     (self.button_rect[0] + self.button_rect[2], self.button_rect[1] + self.button_rect[3]), 
                     (200, 200, 200), -1)
        cv2.rectangle(overlay, (self.button_rect[0], self.button_rect[1]), 
                     (self.button_rect[0] + self.button_rect[2], self.button_rect[1] + self.button_rect[3]), 
                     (0, 0, 0), 1)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1
        text = "Click for Menu"
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = self.button_rect[0] + (self.button_rect[2] - text_size[0]) // 2
        text_y = self.button_rect[1] + (self.button_rect[3] + text_size[1]) // 2
        cv2.putText(overlay, text, (text_x, text_y), font, font_scale, (0, 0, 0), thickness)
        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)
        return frame

    def draw_menu(self, frame):
        if self.confirmation_dialog and self.confirmation_dialog.is_active():
            return self.confirmation_dialog.draw(frame)

        if not self.is_menu_active():
            return frame

        menu = self.get_current_menu()
        if not menu:
            return frame

        return self.renderer.draw_menu(frame, menu)

    def handle_input(self, key):
        if self.confirmation_dialog and self.confirmation_dialog.is_active():
            self.confirmation_dialog.handle_key(key)
            if not self.confirmation_dialog.is_active():
                self.restart_game()
            return True
        return self.input_handler.handle_input(key)

    def mouse_callback(self, event, x, y, flags, param):
        self.mouse_x = x
        self.mouse_y = y

        # Check hover states
        self.is_close_hovered = False
        self.is_back_hovered = False
        self.is_reset_hovered = False

        if self.close_button_rect:
            cx, cy, cw, ch = self.close_button_rect
            if cx <= x <= cx + cw and cy <= y <= cy + ch:
                self.is_close_hovered = True

        if self.back_button_rect:
            bx, by, bw, bh = self.back_button_rect
            if bx <= x <= bx + bw and by <= y <= by + bh:
                self.is_back_hovered = True

        if self.reset_button_rect:
            rx, ry, rw, rh = self.reset_button_rect
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                self.is_reset_hovered = True

        # Handle dragging
        if event == cv2.EVENT_LBUTTONDOWN and self.header_rect:
            hx, hy, hw, hh = self.header_rect
            if hx <= x <= hx + hw and hy <= y <= hy + hh:
                self.is_dragging = True
                self.drag_offset_x = x - self.menu_pos_x
                self.drag_offset_y = y - self.menu_pos_y

        elif event == cv2.EVENT_MOUSEMOVE and self.is_dragging:
            self.menu_pos_x = x - self.drag_offset_x
            self.menu_pos_y = y - self.drag_offset_y

        elif event == cv2.EVENT_LBUTTONUP and self.is_dragging:
            self.is_dragging = False

        # Handle slider dragging
        if event == cv2.EVENT_LBUTTONDOWN and self.state == "settings":
            for idx, rect in enumerate(self.menu_item_rects):
                if isinstance(rect, dict) and rect["type"] == "slider":
                    rx, ry, rw, rh = rect["rect"]
                    if rx <= x <= rx + rw and ry <= y <= ry + rh:
                        self.is_slider_dragging = True
                        self.dragged_slider = rect
                        self.selection = rect["index"]
                        setting_name = rect["key"]
                        min_val = rect["min_val"]
                        max_val = rect["max_val"]
                        slider_pos = (x - rx) / rw
                        new_value = min_val + (max_val - min_val) * slider_pos
                        new_value = max(min_val, min(max_val, new_value))
                        setattr(self.settings.config, setting_name, new_value)
                        self.settings.save_config()
                        print(f"Updated {setting_name} to {new_value}")
                        break

        elif event == cv2.EVENT_MOUSEMOVE and self.is_slider_dragging and self.dragged_slider:
            rx, ry, rw, rh = self.dragged_slider["rect"]
            setting_name = self.dragged_slider["key"]
            min_val = self.dragged_slider["min_val"]
            max_val = self.dragged_slider["max_val"]
            slider_pos = min(1.0, max(0.0, (x - rx) / rw))
            new_value = min_val + (max_val - min_val) * slider_pos
            new_value = max(min_val, min(max_val, new_value))
            setattr(self.settings.config, setting_name, new_value)
            self.settings.save_config()
            print(f"Updated {setting_name} to {new_value}")

        elif event == cv2.EVENT_LBUTTONUP and self.is_slider_dragging:
            self.is_slider_dragging = False
            self.dragged_slider = None

        # Handle menu bar button click
        if event == cv2.EVENT_LBUTTONDOWN and self.button_rect:
            bx, by, bw, bh = self.button_rect
            if bx <= x <= bx + bw and by <= y <= by + bh:
                if self.state == "closed":
                    self.reset_menu()
                    self.set_state("main_menu")
                else:
                    self.set_state("closed")
                    if self.sound_manager:
                        self.sound_manager.update_settings()
                return

        # Handle close button click
        if event == cv2.EVENT_LBUTTONDOWN and self.is_close_hovered:
            self.set_state("closed")
            if self.sound_manager:
                self.sound_manager.update_settings()
            return

        # Handle back button click
        if event == cv2.EVENT_LBUTTONDOWN and self.is_back_hovered:
            if self.menu_stack:
                self.current_menu = self.menu_stack.pop()
                self.selection = 0
                if not self.menu_stack:
                    self.set_state("main_menu")
            else:
                self.set_state("main_menu")
            return

        # Handle reset button click in settings
        if event == cv2.EVENT_LBUTTONDOWN and self.is_reset_hovered and self.state == "settings":
            self.settings.config.white_ball_detection = True
            self.settings.config.red_ball_detection = True
            self.settings.config.game_sounds = True
            self.settings.config.background_music = True
            self.settings.config.detection_confidence_threshold = 0.7
            self.settings.config.detection_radius_tolerance = 20.0
            self.settings.config.detection_area_min = 5.0
            self.settings.config.detection_area_max = 4000.0
            self.settings.config.detection_circularity_min = 0.01
            self.settings.config.detection_circularity_max = 2.0
            self.settings.save_config()
            if self.sound_manager:
                self.sound_manager.update_settings()
            return

        # Handle logo click on About page
        if event == cv2.EVENT_LBUTTONDOWN and self.state == "about" and self.image_rect:
            ix, iy, iw, ih = self.image_rect
            if ix <= x <= ix + iw and iy <= y <= iy + ih:
                if param and hasattr(param, 'is_splash_active'):
                    param.is_splash_active = True
                return

        # Handle menu item clicks
        if event == cv2.EVENT_LBUTTONDOWN and self.state in ["main_menu", "mode_selection"]:
            menu = self.get_current_menu()
            for idx, rect in enumerate(self.menu_item_rects):
                rx, ry, rw, rh, item_idx = rect
                if rx <= x <= rx + rw and ry <= y <= ry + rh:
                    self.selection = item_idx
                    _, action = menu["items"][item_idx]
                    action()
                    return

        # Handle settings menu interactions
        if event == cv2.EVENT_LBUTTONDOWN and self.state == "settings":
            for idx, rect in enumerate(self.menu_item_rects):
                if isinstance(rect, tuple):  # Toggle
                    rx, ry, rw, rh, item_idx = rect
                    if rx <= x <= rx + rw and ry <= y <= ry + rh:
                        self.selection = item_idx
                        menu = self.get_current_menu()
                        _, action = menu["items"][item_idx]
                        action()
                        return

        # Handle mouse wheel for scrolling
        if event == cv2.EVENT_MOUSEWHEEL:
            if flags > 0:  # Scroll up
                self.scroll_offset = max(0, self.scroll_offset - 1)
                if self.state in ["main_menu", "mode_selection", "settings", "leaderboard", "help"]:
                    if self.selection > self.scroll_offset + 5:  # Adjust based on max visible items
                        self.selection -= 1
            else:  # Scroll down
                if self.state == "main_menu" or self.state == "mode_selection":
                    max_items = len(self.get_current_menu()["items"])
                    if self.scroll_offset < max_items - 6:  # Adjust based on max visible items
                        self.scroll_offset += 1
                    if self.selection < self.scroll_offset:
                        self.selection += 1
                elif self.state == "settings":
                    max_items = len(self.get_current_menu()["items"])
                    if self.scroll_offset < max_items - 6:
                        self.scroll_offset += 1
                    if self.selection < self.scroll_offset:
                        self.selection += 1
                elif self.state == "leaderboard":
                    max_items = len(self.leaderboard_scores) + (2 if self.renderer.leaderboard_error else 1)
                    if self.scroll_offset < max_items - 7:  # Adjust based on max visible lines
                        self.scroll_offset += 1
                elif self.state == "help":
                    max_items = 11  # Total help items
                    if self.scroll_offset < max_items - 9:
                        self.scroll_offset += 1