# game_types.py
"""
Contains shared enums and type definitions for the Whiffle Tracker project
to avoid circular imports.
"""
from enum import Enum, auto

class CurrentGameState(Enum):
    GETTING_PLAYER_NAME = auto()
    PLAYING = auto()
    MENU = auto()
    ZONE_EDITING = auto()
    GAME_OVER = auto()
    PAUSED = auto()
    FUN = auto() # Added previously