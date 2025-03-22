import cv2
import time
from menu_renderer_base import MenuRenderer
from menu_renderer_text import draw_text_page
from menu_renderer_leaderboard import draw_leaderboard
from menu_renderer_settings import draw_settings_menu
from menu_renderer_gameover import draw_game_over_menu
from menu_input_handler import MenuInputHandler
from menu_settings import MenuSettings
from leaderboard import Leaderboard
from config import GameConfig

class MenuSystem:
    """Manages the game's menu system, including state, navigation, settings, and dragging."""
    def __init__(self, scoring_zones, game_duration=120, sound_manager=None):
        self.state = "closed"
        self.is_game_in_progress = False
        self.options = {
            "File": {
                "New Game": self.prompt_new_game,
                "Restart Game": self.restart_game,
                "Resume Game": self.resume_game,
                "Pause Game": self.pause_game,
                "Mode": {
                    "Classic": lambda: self.set_mode("classic"),
                    "Timed": lambda: self.set_mode("timed")
                },
                "Settings": lambda: self.set_state("settings"),
                "Leaderboard": lambda: self.set_state("leaderboard"),
                "Help": lambda: self.set_state("help"),
                "About": lambda: self.set_state("about")
            },
            "Exit": lambda: self.set_state("closed")
        }
        self.current_menu = self.options
        self.menu_stack = []
        self.selection = 0
        self.scroll_offset = 0
        self.mode = "classic"  # Default to Classic mode
        self.total_score = 0
        self.scoring_zones = scoring_zones
        self.game_duration = game_duration
        self.game_start_time = None
        self.timer_active = False
        self.timer_text = ""
        self.button_rect = (10, 5, 150, 30)
        self.button_text = "Click for Menu"
        self.menu_item_rects = []
        self.menu_area = None
        self.back_button_rect = None
        self.close_button_rect = None
        self.image_rect = None
        self.is_dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.menu_pos_x = 200
        self.menu_pos_y = 100
        self.settings = MenuSettings()
        self.sound_manager = sound_manager
        self.renderer = MenuRenderer(self)
        self.input_handler = MenuInputHandler(self)
        self.leaderboard = Leaderboard()
        self.confirmation_dialog = None
        self.load_settings()
        # Force default mode to "classic" on startup
        self.mode = "classic"
        self.timer_active = False  # Ensure timer is off unless explicitly set to "timed"
        if self.sound_manager:
            self.sound_manager.update_settings()

    def reset_menu(self):
        self.current_menu = self.options
        self.menu_stack = []
        self.selection = 0
        self.scroll_offset = 0

    def set_state(self, state):
        self.state = state
        self.selection = 0
        self.scroll_offset = 0
        if state == "closed":
            self.menu_item_rects = []
            self.menu_area = None
            self.back_button_rect = None
            self.close_button_rect = None
            self.image_rect = None
        if state != "closed" and self.sound_manager:
            self.sound_manager.play_sound_effect("menu_click")

    def is_menu_active(self):
        return self.state in ["main_menu", "settings", "help", "about", "leaderboard", "mode_selection"]

    def get_current_menu(self):
        if not self.is_menu_active():
            return None

        state_titles = {
            "main_menu": "Main Menu",
            "settings": "Settings",
            "leaderboard": "Leaderboard",
            "help": "Help",
            "about": "About",
            "mode_selection": "Select Game Mode"
        }
        title = state_titles.get(self.state, "Menu")

        items = []
        if self.state == "settings":
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
            print(f"Leaderboard scores for mode '{self.mode}': {scores} (Online: {is_online})")
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
            max_visible_items = 11
            start_idx = self.scroll_offset
            end_idx = min(start_idx + max_visible_items, len(all_items))
            items = all_items[start_idx:end_idx]
        elif self.state == "about":
            items = [("Whiffle Game v 9.2, Ideas by Blake Weibling coding by Grok", lambda: None)]
        elif self.state == "mode_selection":
            items = [
                ("Classic", lambda: self.start_new_game("classic")),
                ("Timed", lambda: self.start_new_game("timed"))
            ]
        else:
            menu_items = {}
            for key, value in self.current_menu.items():
                if key == "File":
                    submenu = {}
                    for subkey, subvalue in value.items():
                        if subkey == "Resume Game":
                            if self.is_game_in_progress and not self.timer_active:
                                submenu[subkey] = subvalue
                        elif subkey == "Pause Game":
                            if self.is_game_in_progress and self.timer_active:
                                submenu[subkey] = subvalue
                        elif subkey == "Restart Game":
                            if self.is_game_in_progress:
                                submenu[subkey] = subvalue
                        else:
                            submenu[subkey] = subvalue
                    menu_items[key] = submenu
                else:
                    menu_items[key] = value
            items = [(key, value if callable(value) else lambda: self.enter_submenu(key)) 
                     for key, value in menu_items.items()]
        
        print(f"Current menu state: {self.state}, items: {[item[0] for item in items]}")
        return {"title": title, "items": items}

    def has_parent_menu(self):
        return len(self.menu_stack) > 0

    def enter_submenu(self, submenu_key):
        print(f"Entering submenu: {submenu_key}")
        if submenu_key in self.current_menu and isinstance(self.current_menu[submenu_key], dict):
            self.menu_stack.append(self.current_menu)
            self.current_menu = self.current_menu[submenu_key]
            self.selection = 0
            self.scroll_offset = 0
            self.set_state("main_menu")
            print(f"Submenu entered. New current_menu keys: {list(self.current_menu.keys())}")
        else:
            print(f"Failed to enter submenu: {submenu_key} not in current_menu or not a dict")

    def toggle_setting(self, setting_name):
        current_value = getattr(self.settings.config, setting_name)
        setattr(self.settings.config, setting_name, not current_value)
        self.save_settings()

    def prompt_new_game(self):
        """Prompt the user to select a game mode before starting a new game."""
        self.set_state("mode_selection")

    def start_new_game(self, mode):
        """Start a new game with the selected mode."""
        self.mode = mode
        self.total_score = 0
        self.scoring_zones.reset_scored_balls()
        self.game_start_time = time.time() if self.mode == "timed" else None
        self.timer_active = (self.mode == "timed")
        self.is_game_in_progress = True
        self.set_state("closed")
        print(f"New game started. Mode: {self.mode}, Timer active: {self.timer_active}")
        if self.sound_manager:
            self.sound_manager.update_settings()

    def pause_game(self):
        if self.is_game_in_progress and self.timer_active:
            self.timer_active = False
            self.set_state("closed")
            print("Game paused. Select 'Resume Game' or press 'p' to resume.")
            if self.sound_manager:
                self.sound_manager.stop_background_music()

    def resume_game(self):
        if self.is_game_in_progress and not self.timer_active:
            self.timer_active = True
            if self.mode == "timed":
                elapsed = time.time() - self.game_start_time
                self.game_start_time = time.time() - elapsed
            self.set_state("closed")
            print("Game resumed.")
            if self.sound_manager:
                self.sound_manager.play_background_music()

    def restart_game(self):
        if self.is_game_in_progress and not self.confirmation_dialog:
            self.confirmation_dialog = ConfirmationDialog(self.frame, "Restart game? (Y/N)")
            return
        elif self.confirmation_dialog and not self.confirmation_dialog.is_active():
            if self.confirmation_dialog.get_result():
                self.total_score = 0
                self.scoring_zones.reset_scored_balls()
                self.game_start_time = time.time() if self.mode == "timed" else None
                self.timer_active = (self.mode == "timed")
                self.set_state("closed")
                print(f"Game restarted. Mode: {self.mode}, Timer active: {self.timer_active}")
                if self.sound_manager:
                    self.sound_manager.update_settings()
            self.confirmation_dialog = None

    def set_mode(self, mode):
        self.mode = mode
        self.timer_active = (mode == "timed")
        self.save_settings()
        self.game_start_time = time.time() if self.mode == "timed" else None
        self.set_state("closed")
        print(f"Mode set to: {self.mode}, Timer active: {self.timer_active}")
        if self.sound_manager:
            self.sound_manager.update_settings()

    def load_settings(self):
        self.settings.load_settings()
        # Load mode from settings, but we'll override it in __init__ to ensure "classic" default
        self.mode = self.settings.config.mode if hasattr(self.settings.config, 'mode') else "classic"

    def save_settings(self):
        self.settings.save_settings(self.mode)
        if self.sound_manager:
            self.sound_manager.update_settings()

    def update_timer(self):
        if self.timer_active and self.game_start_time:
            elapsed = time.time() - self.game_start_time
            remaining = max(0, self.game_duration - elapsed)
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            self.timer_text = f"Time: {minutes:02d}:{seconds:02d}"
            if remaining <= 0:
                self.timer_active = False
                self.set_state("game_over")
                if self.sound_manager:
                    self.sound_manager.play_sound_effect("game_over")

    def draw_menu_bar(self, frame):
        h, w = frame.shape[:2]
        scale_x = w / 1280
        scale_y = h / 720
        self.button_rect = (int(10 * scale_x), int(5 * scale_y), int(150 * scale_x), int(30 * scale_y))
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1
        text_size = cv2.getTextSize(self.button_text, font, font_scale, thickness)[0]
        bx, by, bw, bh = self.button_rect
        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (200, 200, 200), -1)
        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (0, 0, 0), 1)
        text_x = bx + (bw - text_size[0]) // 2
        text_y = by + (bh + text_size[1]) // 2
        cv2.putText(frame, self.button_text, (text_x, text_y), font, font_scale, (0, 0, 0), thickness)
        return frame

    def draw_menu(self, frame):
        if self.is_menu_active():
            menu = self.get_current_menu()
            if self.state == "main_menu":
                frame = draw_text_page(self.renderer, frame, menu["items"], menu["title"])
            elif self.state == "settings":
                frame = draw_settings_menu(self.renderer, frame)
            elif self.state == "leaderboard":
                frame = draw_leaderboard(self.renderer, frame)
            elif self.state == "help":
                frame = draw_text_page(self.renderer, frame, "\n".join([item[0] for item in menu["items"]]), menu["title"])
            elif self.state == "about":
                frame = draw_text_page(self.renderer, frame, "", menu["title"])
            elif self.state == "mode_selection":
                frame = draw_text_page(self.renderer, frame, menu["items"], menu["title"])
            elif self.state == "game_over":
                frame = draw_game_over_menu(self.renderer, frame)
        self.frame = frame  # Store frame for confirmation dialog
        return frame

    def handle_input(self, key):
        return self.input_handler.handle_input(key)

    def mouse_callback(self, event, x, y, flags, param):
        self.input_handler.mouse_callback(event, x, y, flags, param)