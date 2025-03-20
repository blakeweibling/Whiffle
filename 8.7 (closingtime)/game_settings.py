# game_settings.py
from config import GameConfig, load_config, save_config

class GameSettings:
    """Manages game settings using a centralized configuration."""
    def __init__(self):
        self.config = load_config()
        self.balls = {
            "red": {"color": (0, 0, 255)},
            "white": {"color": (255, 255, 255)},
            "half": {"color": None}  # Special case, handled in BallTracker
        }

    def scale_value(self, value, current_width, current_height):
        """Scale a value based on the current frame dimensions."""
        scale = min(current_width / self.config.base_frame_width, current_height / self.config.base_frame_height)
        return value * scale