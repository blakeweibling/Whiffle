class GameSettings:
    def __init__(self):
        # Physics constants
        self.gravity = 9.81  # m/s^2 (scaled for pixel space later)
        self.friction = 0.98  # Damping factor for velocity
        self.time_step = 0.033  # ~30 FPS

        # Ball properties
        self.ball_radius = 10  # pixels (base radius for 1080p)
        self.num_balls = 10
        self.balls = {
            "white": {"count": 8, "color": (255, 255, 255)},
            "red": {"count": 1, "color": (0, 0, 255)},  # OpenCV uses BGR
            "half_red_white": {"count": 1, "color": None}  # Special case
        }

        # Base camera settings (720p as reference)
        self.base_frame_width = 1280
        self.base_frame_height = 720

    def get_ball_properties(self):
        return self.balls

    def scale_value(self, value, current_width, current_height):
        """Scale a value based on the current window dimensions relative to base 1080p."""
        scale_x = current_width / self.base_frame_width
        scale_y = current_height / self.base_frame_height
        return value * min(scale_x, scale_y)  # Use the smaller scale to maintain aspect ratio