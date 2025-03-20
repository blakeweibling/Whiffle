# game_settings.py (updated)
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

    @property
    def base_frame_width(self):
        return self.config.base_frame_width

    @property
    def base_frame_height(self):
        return self.config.base_frame_height

    @property
    def ball_radius(self):
        return self.config.ball_radius

    @property
    def gravity(self):
        return self.config.gravity

    @property
    def friction(self):
        return self.config.friction

    @property
    def time_step(self):
        return self.config.time_step

    def scale_value(self, value, current_width, current_height):
        """Scale a value based on the current frame dimensions."""
        scale = min(current_width / self.base_frame_width, current_height / self.base_frame_height)
        return value * scale