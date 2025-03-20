from config import GameConfig, load_config, save_config

class GameSettings:
    """Manages game settings using a centralized configuration."""
    def __init__(self):
        self.config = load_config()
        # Ensure base_frame_width and base_frame_height are defined
        self.base_frame_width = getattr(self.config, 'base_frame_width', 1920)
        self.base_frame_height = getattr(self.config, 'base_frame_height', 1080)
        # Define other game settings used in ball_tracker.py
        self.ball_radius = getattr(self.config, 'ball_radius', 10)
        self.gravity = getattr(self.config, 'gravity', 9.8)
        self.friction = getattr(self.config, 'friction', 0.99)
        self.time_step = getattr(self.config, 'time_step', 0.033)
        self.balls = {
            "red": {"color": (0, 0, 255)},
            "white": {"color": (255, 255, 255)},
            "half": {"color": None}  # Special case, handled in BallTracker
        }

    def scale_value(self, value, current_width, current_height):
        """Scale a value based on the current frame dimensions."""
        scale = min(current_width / self.base_frame_width, current_height / self.base_frame_height)
        return value * scale