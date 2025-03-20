# menu_settings.py
from config import GameConfig, load_config, save_config

class MenuSettings:
    """Manages menu settings using the centralized GameConfig."""
    def __init__(self):
        self.config = load_config()

    def load_settings(self):
        """Load settings from the centralized configuration."""
        self.config = load_config()
        print("Loaded menu settings from GameConfig")

    def save_settings(self, mode=None):
        """Save settings to the centralized configuration."""
        if mode is not None:
            self.config.mode = mode
        save_config(self.config)

    def toggle(self, key):
        """Toggle the boolean value of a setting in the configuration."""
        if hasattr(self.config, key):
            current_value = getattr(self.config, key)
            if isinstance(current_value, bool):
                setattr(self.config, key, not current_value)
                print(f"Toggled {key} to {getattr(self.config, key)}")
                save_config(self.config)  # Save after toggling
            else:
                print(f"Cannot toggle {key}: Value is not a boolean")
        else:
            print(f"Setting {key} not found in GameConfig")