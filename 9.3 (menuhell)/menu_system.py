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
        self.image_rect = None
        self.menu_area = None
        self.menu_item_rects = []
        self.settings_sliders = []
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
                 lambda: self.toggle_setting("background_music"))
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

        if self.state in ["main_menu", "mode_selection"]:
            return self.renderer.draw_text_page(frame, menu["items"], menu["title"])
        elif self.state == "settings":
            return self.renderer.draw_settings_page(frame, menu["items"], menu["title"])
        elif self.state == "leaderboard":
            return self.renderer.draw_leaderboard_page(frame, menu["items"], menu["title"])
        elif self.state == "help":
            return self.renderer.draw_help_page(frame, menu["items"], menu["title"])
        elif self.state == "about":
            return self.renderer.draw_about_page(frame, menu["items"], menu["title"])
        elif self.state == "game_over":
            return self.renderer.draw_game_over_page(frame, menu["items"], menu["title"])
        return frame

    def handle_input(self, key):
        if self.confirmation_dialog and self.confirmation_dialog.is_active():
            self.confirmation_dialog.handle_key(key)
            if not self.confirmation_dialog.is_active():
                self.restart_game()
            return True
        return self.input_handler.handle_input(key)

    def mouse_callback(self, event, x, y, flags, param):
        self.input_handler.mouse_callback(event, x, y, flags, param)