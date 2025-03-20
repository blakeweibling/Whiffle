# config.py
import json
import os
from pydantic import BaseModel, Field

class GameConfig(BaseModel):
    base_frame_width: int = Field(default=1920, ge=1)
    base_frame_height: int = Field(default=1080, ge=1)
    ball_radius: int = Field(default=10, ge=1)
    gravity: float = Field(default=9.8, ge=0.0)
    friction: float = Field(default=0.99, ge=0.0, le=1.0)
    time_step: float = Field(default=0.033, ge=0.0)
    game_duration: int = Field(default=120, ge=1)
    white_ball_detection: bool = True
    red_ball_detection: bool = True
    game_sounds: bool = True
    background_music: bool = True
    mode: str = "classic"
    # Removed CNN-related settings
    # detection_confidence_threshold, detection_radius_tolerance, etc.

# Cache the config to reduce I/O
_config_cache = None

def load_config(filename="config.json"):
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    config = GameConfig()
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                data = json.load(f)
                config = GameConfig(**data)
            print(f"Loaded configuration from {filename}")
        except Exception as e:
            print(f"Error loading configuration from {filename}: {e}. Using default settings.")
            save_config(config, filename)
    else:
        print(f"Configuration file {filename} not found. Using default settings.")
        save_config(config, filename)
    _config_cache = config
    return config

def save_config(config, filename="config.json"):
    global _config_cache
    try:
        with open(filename, "w") as f:
            json.dump(config.dict(), f, indent=4)
        print(f"Saved configuration to {filename}")
        _config_cache = config
    except Exception as e:
        print(f"Error saving configuration to {filename}: {e}")