"""
Player management for the Whiffle Tracker project.
Defines the Player class to manage player data.
"""


class Player:

    def __init__(self, name: str) -> None:
        self.name = name
        self.score = 0
        self.games_played = 0
        self.total_score = 0

    def reset_score(self) -> None:
        """Reset the player's score for a new game."""
        self.score = 0

    def add_score(self, points: int) -> None:
        """Add points to the player's score."""
        self.score += points
        self.total_score += points

    def increment_games_played(self) -> None:
        """Increment the number of games played."""
        self.games_played += 1
