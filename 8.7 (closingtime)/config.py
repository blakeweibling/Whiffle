# config.py
import json
import os
from pydantic import BaseModel

class GameConfig(BaseModel):
    """Configuration class for game settings with validation."""
    # Game settings (from game_settings.py)
    base_frame_width: int = 1920
    base_frame_height: int = 1080
    ball_radius: int = 10
    gravity: float = 9.8
    friction: float = 0.99
    time_step: float = 0.033
    # Menu settings (from menu_settings.py)
    game_duration: int = 120
    white_ball_detection: bool = True
    red_ball_detection: bool = True
    game_sounds: bool = True
    background_music: bool = True
    mode: str = "classic"

def load_config(filename="config.json"):
    """Load the game configuration from a JSON file."""
    config = GameConfig()
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                data = json.load(f)
                config = GameConfig(**data)
            print(f"Loaded configuration from {filename}")
        except Exception as e:
            print(f"Error loading configuration from {filename}: {e}. Using default settings.")
            save_config(config, filename)  # Save default settings if loading fails
    else:
        print(f"Configuration file {filename} not found. Using default settings.")
        save_config(config, filename)  # Create the file with default settings
    return config

def save_config(config, filename="config.json"):
    """Save the game configuration to a JSON file."""
    try:
        with open(filename, "w") as f:
            json.dump(config.dict(), f, indent=4)
        print(f"Saved configuration to {filename}")
    except Exception as e:
        print(f"Error saving configuration to {filename}: {e}")