# game_types.py
"""
Contains shared enums and type definitions for the Whiffle Tracker project
to avoid circular imports.
"""
from enum import Enum, auto
from typing import Dict, Callable, Any


class CurrentGameState(Enum):
    GETTING_PLAYER_NAME = auto()
    PLAYING = auto()
    MENU = auto()
    ZONE_EDITING = auto()
    GAME_OVER = auto()
    PAUSED = auto()
    FUN = auto()  # Added previously
    CONFIRM_QUIT = auto()  # <-- Added this line


# Define MouseEventHandlers type for use in interaction_utils.py
MouseEventHandlers = Dict[
    CurrentGameState, Dict[int, Callable[[int, int, int, Any], bool]]
]
