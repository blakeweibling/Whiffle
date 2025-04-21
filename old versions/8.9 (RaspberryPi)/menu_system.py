import time
from menu_renderer import MenuRenderer
from menu_input_handler import MenuInputHandler
from menu_settings import MenuSettings

class MenuSystem:
    """Manages the menu system, including navigation and state transitions."""
    def __init__(self, scoring_zones, game_duration=120, sound_manager=None):
        self.scoring_zones = scoring_zones
        self.game_duration = game_duration
        self.sound_manager = sound_manager
        self.settings = MenuSettings()
        self.renderer = MenuRenderer(self)
        self.input_handler = MenuInputHandler(self)
        self.leaderboard = None  # Will be set by Game class
        self.state = "closed"
        self.menu_stack = []
        self.selection = 0
        self.menu_pos_x = None
        self.menu_pos_y = None
        self.menu_area = None
        self.menu_item_rects = []
        self.button_rect = (10, 10, 100, 20)
        self.button_text = "Menu"
        self.header_rect = None
        self.back_button_rect = None
        self.close_button_rect = None
        self.reset_button_rect = None
        self.is_dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.total_score = 0
        self.mode = self.settings.config.mode
        self.timer_active = False
        self.timer_start = None
        self.timer_text = None
        self.last_timer_update = 0  # For frame rate limiting

        self.main_menu = {
            "Start Game": self.start_game,
            "Reset Score": self.reset_score,
            "Calibrate Zones": self.calibrate_zones,
            "Settings": {
                "Change Mode": self.change_mode,
                "Options": self.show_settings,
                "Back": None
            },
            "Leaderboard": self.show_leaderboard,
            "Help": self.show_help,
            "About": self.show_about,
            "Quit": self.quit_game
        }
        self.current_menu = self.main_menu

    def reset_menu(self):
        """Reset the menu state when opening."""
        self.state = "main_menu"
        self.menu_stack = []
        self.selection = 0
        self.current_menu = self.main_menu
        self.menu_pos_x = None
        self.menu_pos_y = None
        self.menu_area = None
        self.menu_item_rects = []
        self.header_rect = None
        self.back_button_rect = None
        self.close_button_rect = None
        self.reset_button_rect = None
        self.is_dragging = False

    def set_state(self, state):
        """Set the menu state and play a sound effect if applicable."""
        self.state = state
        if self.state != "closed":
            # Check if the sound effect exists before playing
            if self.sound_manager and hasattr(self.sound_manager.sound_effects, "get") and self.sound_manager.sound_effects.get("menu_click"):
                self.sound_manager.play_sound_effect("menu_click")

    def start_game(self):
        """Start the game, either in classic or timed mode."""
        self.set_state("closed")
        self.total_score = 0
        self.scoring_zones.reset_scored_balls()
        if self.mode == "timed":
            self.timer_active = True
            self.timer_start = time.time()
        print(f"Game started in {self.mode} mode")

    def reset_score(self):
        """Reset the score and scored balls."""
        self.total_score = 0
        self.scoring_zones.reset_scored_balls()
        print("Score reset to 0")

    def calibrate_zones(self):
        """Trigger zone calibration."""
        self.set_state("closed")

    def change_mode(self):
        """Toggle between classic and timed modes."""
        self.mode = "classic" if self.mode == "timed" else "timed"
        self.settings.save_settings(mode=self.mode)
        print(f"Game mode changed to: {self.mode}")

    def show_settings(self):
        """Show the settings menu."""
        self.set_state("settings")

    def show_leaderboard(self):
        """Show the leaderboard."""
        self.set_state("leaderboard")

    def show_help(self):
        """Show the help page."""
        self.set_state("help")

    def show_about(self):
        """Show the about page."""
        self.set_state("about")

    def quit_game(self):
        """Quit the game."""
        self.set_state("game_over")

    def is_menu_active(self):
        """Check if the menu is currently active."""
        return self.state != "closed"

    def update_timer(self):
        """Update the game timer for timed mode."""
        # Remove the frame rate limit
        current_time = time.time()
        # if current_time - self.last_timer_update < 0.1:  # 0.1 seconds = 10 FPS
        #     return
        self.last_timer_update = current_time

        if not self.timer_active or self.mode != "timed":
            self.timer_text = None
            return

        elapsed = current_time - self.timer_start
        remaining = max(0, self.game_duration - elapsed)
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        self.timer_text = f"Time: {minutes:02d}:{seconds:02d}"

        if remaining <= 0:
            self.timer_active = False
            self.set_state("game_over")
            if self.sound_manager:
                self.sound_manager.play_sound_effect("game_over")

    def mouse_callback(self, event, x, y, flags, param=None):
        """Handle mouse events by delegating to the input handler."""
        self.input_handler.mouse_callback(event, x, y, flags, param)

    def handle_input(self, key):
        """Handle keyboard input by delegating to the input handler."""
        return self.input_handler.handle_input(key)

    def draw_menu_bar(self, frame):
        """Draw the menu bar by delegating to the renderer."""
        return self.renderer.draw_menu_bar(frame)

    def draw_menu(self, frame):
        """Draw the menu by delegating to the renderer."""
        return self.renderer.draw_menu(frame)