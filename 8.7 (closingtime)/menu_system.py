# menu_system.py
import cv2
import time
from menu_renderer import MenuRenderer
from menu_input_handler import MenuInputHandler
from menu_settings import MenuSettings
from sound_manager import SoundManager
from leaderboard import Leaderboard  # Import the new Leaderboard class

class MenuSystem:
    """Manages the game's menu system, including state, navigation, settings, and dragging."""
    def __init__(self, scoring_zones, game_duration=120):
        # Menu states: "main_menu", "settings", "help", "about", "game_over", "closed", "leaderboard"
        self.state = "closed"
        self.options = {
            "File": {
                "New Game": self.new_game,
                "Mode": {
                    "Classic": lambda: self.set_mode("classic"),
                    "Timed": lambda: self.set_mode("timed")
                },
                "Settings": lambda: self.set_state("settings"),
                "Leaderboard": lambda: self.set_state("leaderboard"),  # New option
                "Help": lambda: self.set_state("help"),
                "About": lambda: self.set_state("about")
            },
            "Exit": lambda: self.set_state("closed")
        }
        self.current_menu = self.options
        self.menu_stack = []
        self.selection = 0
        self.mode = "classic"
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
        self.back_button_text = "Back"
        self.close_button_rect = None
        self.close_button_text = "X"
        # Dragging state
        self.menu_pos_x = None
        self.menu_pos_y = None
        self.is_dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.header_rect = None

        self.settings = MenuSettings()
        self.sound_manager = SoundManager(self.settings)
        self.renderer = MenuRenderer(self)
        self.input_handler = MenuInputHandler(self)
        self.leaderboard = Leaderboard()  # Initialize the leaderboard
        self.load_settings()
        self.sound_manager.update_settings()

    def set_state(self, state):
        """Set the current menu state and reset selection."""
        self.state = state
        self.selection = 0
        if state != "closed":
            self.sound_manager.play_sound_effect("menu_click")

    def is_menu_active(self):
        """Check if any menu is currently active."""
        return self.state in ["main_menu", "settings", "help", "about", "leaderboard"]

    def load_settings(self):
        """Load game settings and initialize the mode."""
        self.settings.load_settings()
        self.mode = self.settings.config.mode

    def save_settings(self):
        """Save the current game settings."""
        self.settings.save_settings(self.mode)

    def new_game(self):
        """Start a new game, resetting the score and starting the timer if in timed mode."""
        self.total_score = 0
        self.scoring_zones.scored_balls.clear()
        self.game_start_time = time.time() if self.mode == "timed" else None
        self.timer_active = self.mode == "timed"
        print("New game started")
        self.set_state("closed")
        self.sound_manager.update_settings()

    def set_mode(self, mode):
        """Set the game mode and update the timer state."""
        self.mode = mode
        self.save_settings()
        self.game_start_time = time.time() if self.mode == "timed" else None
        self.timer_active = self.mode == "timed"
        print(f"Game mode set to: {mode}")
        self.set_state("closed")
        self.sound_manager.update_settings()

    def update_timer(self):
        """Update the game timer for timed mode."""
        if self.timer_active and self.game_start_time:
            elapsed = time.time() - self.game_start_time
            remaining = max(0, self.game_duration - elapsed)
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            self.timer_text = f"Time: {minutes:02d}:{seconds:02d}"
            if remaining <= 0:
                self.timer_active = False
                self.set_state("game_over")
                self.sound_manager.play_sound_effect("game_over")
                print("Time's up! Game Over")
        else:
            self.timer_text = ""

    def draw_menu_bar(self, frame):
        """Draw the menu bar at the top of the frame."""
        return self.renderer.draw_menu_bar(frame)

    def draw_menu(self, frame):
        """Draw the current menu based on the state."""
        return self.renderer.draw_menu(frame)

    def handle_input(self, key):
        """Handle keyboard input for the menu."""
        return self.input_handler.handle_input(key)

    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse input for the menu."""
        self.input_handler.mouse_callback(event, x, y, flags, param)