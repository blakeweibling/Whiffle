# game_settings.py
from config import GameConfig, load_config, save_config

class GameSettings:
    """Manages game settings using a centralized configuration."""
    def __init__(self):
        self.config = load_config()
        self.balls = {
            "red": {"color": (0, 0, 255)},  # BGR color for red balls
            "white": {"color": (255, 255, 255)},  # BGR color for white balls
            "half": {"color": None}  # Special case for half red/half white, handled in BallTracker
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

    # New properties for ball detection settings
    @property
    def detection_confidence_threshold(self):
        return self.config.detection_confidence_threshold

    @property
    def detection_radius_tolerance(self):
        return self.config.detection_radius_tolerance

    @property
    def detection_area_min(self):
        return self.config.detection_area_min

    @property
    def detection_area_max(self):
        return self.config.detection_area_max

    @property
    def detection_circularity_min(self):
        return self.config.detection_circularity_min

    @property
    def detection_circularity_max(self):
        return self.config.detection_circularity_max

    def scale_value(self, value, current_width, current_height):
        """Scale a value based on the current frame dimensions."""
        scale = min(current_width / self.base_frame_width, current_height / self.base_frame_height)
        return value * scale