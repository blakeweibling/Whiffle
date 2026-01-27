"""
Player management for the Whiffle Tracker project.
Defines the Player class to manage player data.
"""

from typing import Optional, Tuple
from xp_system import xp_system

class Player:
    def __init__(self, name: str) -> None:
        self.name = name
        self.score = 0
        self.games_played = 0
        self.total_score = 0
        self.consecutive_scores = 0
        self.consecutive_double_balls = 0
        self.last_zone = None
        
        # Load player's XP data
        self.level, self.xp, self.next_level_xp = xp_system.get_player_level(name)

    def reset_score(self) -> None:
        """Reset the player's score for a new game."""
        self.score = 0
        self.consecutive_scores = 0
        self.consecutive_double_balls = 0
        self.last_zone = None

    def add_score(self, points: int, zone: Optional[Tuple] = None, is_special_hole: bool = False) -> None:
        """Add points to the player's score and handle XP calculations."""
        self.score += points
        self.total_score += points
        
        # Track consecutive scores
        if zone == self.last_zone:
            self.consecutive_scores += 1
        else:
            self.consecutive_scores = 1
            self.consecutive_double_balls = 0
        
        self.last_zone = zone
        
        # Calculate and add XP
        is_double_ball = False  # This should be set based on game state
        is_consecutive_double_ball = self.consecutive_double_balls > 0
        
        xp_earned = xp_system.calculate_xp(
            base_points=points,
            is_special_hole=is_special_hole,
            consecutive_scores=self.consecutive_scores,
            is_double_ball=is_double_ball,
            is_consecutive_double_ball=is_consecutive_double_ball
        )
        
        new_level, new_xp, did_level_up = xp_system.add_xp(self.name, xp_earned)
        self.level = new_level
        self.xp = new_xp
        self.next_level_xp = xp_system.get_player_level(self.name)[2]
        
        return did_level_up

    def increment_games_played(self) -> None:
        """Increment the number of games played."""
        self.games_played += 1
    
    def refresh_xp(self) -> None:
        """Refresh player's XP data from the XP system."""
        self.level, self.xp, self.next_level_xp = xp_system.get_player_level(self.name)
