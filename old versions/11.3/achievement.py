"""
Achievement management for the Whiffle Tracker project.
Defines the Achievement class to manage achievements.
"""

from typing import Callable, Any


class Achievement:
    def __init__(
        self, name: str, description: str, condition: Callable[[Any], bool]
    ) -> None:
        self.name = name
        self.description = description
        self.condition = condition
        self.unlocked = False

    def check(self, game_state: Any) -> bool:
        """Check if the achievement condition is met."""
        if not self.unlocked and self.condition(game_state):
            self.unlocked = True
            return True
        return False
