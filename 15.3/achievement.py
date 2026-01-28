"""
Achievement management for the Whiffle Tracker project.
Defines the Achievement class to manage achievements.
"""

from typing import Any, Callable, Optional


class Achievement:

    def __init__(
        self, name: str, description: str, condition: Callable[[Any], bool]
    ) -> None:
        self.name = name
        self.description = description
        self.condition = condition
        self.unlocked = False
        self.unlocked_layout: Optional[str] = None  # "whiffle" or "fivestar" when unlocked

    def check(self, game_state: Any) -> bool:
        """Check if the achievement condition is met."""
        if not self.unlocked and self.condition(game_state):
            self.unlocked = True
            return True
        return False
