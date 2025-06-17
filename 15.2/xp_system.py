"""
XP System for Whiffle Tracker.
Handles player leveling, XP calculations, and persistence.
"""

import json
import os
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# XP System Constants
BASE_XP_PER_HOLE = 10
CONSECUTIVE_SCORE_BONUS = 50  # Base bonus for consecutive scores
DOUBLE_BALL_BONUS = 100  # Bonus for two balls in same hole
CONSECUTIVE_DOUBLE_BALL_BONUS = 500  # Bonus for consecutive double ball scores
SPECIAL_HOLE_MULTIPLIER = 2.0  # XP multiplier for special hole

# Level thresholds calculation
def calculate_level_thresholds(max_level: int = 20) -> List[int]:
    """Calculate XP thresholds for each level."""
    thresholds = []
    base_threshold = 100  # Starting threshold
    increment = 50  # Base increment
    
    for level in range(max_level):
        if level == 0:
            thresholds.append(base_threshold)
        else:
            # Each level requires previous threshold + (previous threshold/2) + increment
            prev_threshold = thresholds[-1]
            new_threshold = prev_threshold + (prev_threshold // 2) + increment
            thresholds.append(new_threshold)
            increment += 10  # Increase increment for next level
    
    return thresholds

# Initialize level thresholds
LEVEL_THRESHOLDS = calculate_level_thresholds()

class XPSystem:
    def __init__(self):
        self.player_data: Dict[str, Dict] = {}
        self.load_player_data()
    
    def load_player_data(self) -> None:
        """Load player XP data from JSON file."""
        try:
            if os.path.exists('player_xp.json'):
                with open('player_xp.json', 'r') as f:
                    self.player_data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading player XP data: {e}")
            self.player_data = {}
    
    def save_player_data(self) -> None:
        """Save player XP data to JSON file."""
        try:
            with open('player_xp.json', 'w') as f:
                json.dump(self.player_data, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving player XP data: {e}")
    
    def get_player_level(self, player_name: str) -> Tuple[int, int, int]:
        """Get player's current level, XP, and XP needed for next level."""
        if player_name not in self.player_data:
            return 1, 0, LEVEL_THRESHOLDS[0]
        
        current_xp = self.player_data[player_name]['xp']
        current_level = self.player_data[player_name]['level']
        next_level_xp = LEVEL_THRESHOLDS[current_level] if current_level < len(LEVEL_THRESHOLDS) else LEVEL_THRESHOLDS[-1]
        
        return current_level, current_xp, next_level_xp
    
    def calculate_xp(self, 
                    base_points: int,
                    is_special_hole: bool,
                    consecutive_scores: int,
                    is_double_ball: bool,
                    is_consecutive_double_ball: bool) -> int:
        """Calculate XP earned for a scoring event."""
        xp = BASE_XP_PER_HOLE + base_points  # Base XP + points from scoring zone
        
        # Apply special hole multiplier
        if is_special_hole:
            xp = int(xp * SPECIAL_HOLE_MULTIPLIER)
        
        # Add consecutive score bonus
        if consecutive_scores > 1:
            xp += CONSECUTIVE_SCORE_BONUS * (consecutive_scores - 1)
        
        # Add double ball bonus
        if is_double_ball:
            xp += DOUBLE_BALL_BONUS
        
        # Add consecutive double ball bonus
        if is_consecutive_double_ball:
            xp += CONSECUTIVE_DOUBLE_BALL_BONUS
        
        return xp
    
    def add_xp(self, player_name: str, xp_earned: int) -> Tuple[int, int, bool]:
        """
        Add XP to player and handle level up.
        Returns: (new_level, new_xp, did_level_up)
        """
        if player_name not in self.player_data:
            self.player_data[player_name] = {'xp': 0, 'level': 1}
        
        current_data = self.player_data[player_name]
        current_data['xp'] += xp_earned
        
        # Check for level up
        old_level = current_data['level']
        while (current_data['level'] < len(LEVEL_THRESHOLDS) and 
               current_data['xp'] >= LEVEL_THRESHOLDS[current_data['level'] - 1]):
            current_data['level'] += 1
        
        did_level_up = current_data['level'] > old_level
        self.save_player_data()
        
        return current_data['level'], current_data['xp'], did_level_up

# Create global XP system instance
xp_system = XPSystem() 