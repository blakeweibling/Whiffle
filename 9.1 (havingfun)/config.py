# config.py
import json
import os
from pydantic import BaseModel, Field
import shutil
from datetime import datetime

class GameConfig(BaseModel):
    """Configuration class for game settings with validation."""
    # Game settings (from game_settings.py)
    base_frame_width: int = Field(default=1920, ge=1)
    base_frame_height: int = Field(default=1080, ge=1)
    ball_radius: int = Field(default=10, ge=1)
    gravity: float = Field(default=9.8, ge=0.0)
    friction: float = Field(default=0.99, ge=0.0, le=1.0)
    time_step: float = Field(default=0.033, ge=0.0)
    # Menu settings (from menu_settings.py)
    game_duration: int = Field(default=120, ge=1)
    white_ball_detection: bool = True
    red_ball_detection: bool = True
    game_sounds: bool = True
    background_music: bool = True
    mode: str = "classic"
    # Ball detection settings (new)
    detection_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    detection_radius_tolerance: float = Field(default=20.0, ge=0.0)
    detection_area_min: float = Field(default=100.0, ge=0.0)
    detection_area_max: float = Field(default=2000.0, ge=0.0)
    detection_circularity_min: float = Field(default=0.7, ge=0.0, le=1.0)
    detection_circularity_max: float = Field(default=1.2, ge=0.0, le=2.0)

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