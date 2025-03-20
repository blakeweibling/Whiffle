# config.py (updated)
import json
import os
from pydantic import BaseModel
import shutil

class GameConfig(BaseModel):
    base_frame_width: int = 1920
    base_frame_height: int = 1080
    ball_radius: int = 10
    gravity: float = 9.8
    friction: float = 0.99
    time_step: float = 0.033
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
            print(f"Error loading configuration from {filename}: {e}. Creating backup and using default settings.")
            # Create a backup of the original file
            backup_filename = f"{filename}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy(filename, backup_filename)
            print(f"Created backup: {backup_filename}")
            save_config(config, filename)  # Save default settings
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