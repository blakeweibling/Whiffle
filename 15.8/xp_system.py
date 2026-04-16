"""
XP System for Whiffle Tracker.
Handles player leveling, XP calculations, and persistence.

XP is now persistent across sessions. The JSON file is anchored to the
application directory (handles PyInstaller frozen builds), loaded with
defensive type validation, and written atomically to survive crashes.
"""

import json
import os
from typing import Dict, List, Optional, Tuple
import logging

from io_utils import atomic_write_json, get_app_dir

logger = logging.getLogger(__name__)

# XP System Constants
BASE_XP_PER_HOLE = 10
CONSECUTIVE_SCORE_BONUS = 50  # Base bonus for consecutive scores
DOUBLE_BALL_BONUS = 100  # Bonus for two balls in same hole
CONSECUTIVE_DOUBLE_BALL_BONUS = 500  # Bonus for consecutive double ball scores
SPECIAL_HOLE_MULTIPLIER = 2.0  # XP multiplier for special hole


def _xp_file_path() -> str:
    """Return the absolute path to player_xp.json in the app directory."""
    return os.path.join(get_app_dir(), "player_xp.json")


def calculate_level_thresholds(max_level: int = 20) -> List[int]:
    """Calculate XP thresholds for each level."""
    thresholds = []
    base_threshold = 100
    increment = 50

    for level in range(max_level):
        if level == 0:
            thresholds.append(base_threshold)
        else:
            prev_threshold = thresholds[-1]
            new_threshold = prev_threshold + (prev_threshold // 2) + increment
            thresholds.append(new_threshold)
            increment += 10

    return thresholds


LEVEL_THRESHOLDS = calculate_level_thresholds()


def _coerce_entry(raw: object) -> Optional[Dict[str, int]]:
    """Return a sanitized {'xp': int, 'level': int} or None if unrecoverable."""
    if not isinstance(raw, dict):
        return None
    try:
        xp = int(raw.get("xp", 0))
        level = int(raw.get("level", 1))
    except (TypeError, ValueError):
        return None
    if xp < 0:
        xp = 0
    if level < 1:
        level = 1
    return {"xp": xp, "level": level}


class XPSystem:
    def __init__(self):
        self.player_data: Dict[str, Dict[str, int]] = {}
        self.load_player_data()

    def load_player_data(self) -> None:
        """Load player XP data from JSON file with defensive validation."""
        path = _xp_file_path()
        try:
            if not os.path.exists(path):
                self.player_data = {}
                return
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Corrupt player_xp.json ({path}): {e}. Starting fresh.")
            self.player_data = {}
            return
        except (IOError, OSError) as e:
            logger.error(f"Error reading player_xp.json: {e}")
            self.player_data = {}
            return

        if not isinstance(raw, dict):
            logger.warning(
                f"player_xp.json root is {type(raw).__name__}, expected dict. Resetting."
            )
            self.player_data = {}
            return

        cleaned: Dict[str, Dict[str, int]] = {}
        for name, entry in raw.items():
            if not isinstance(name, str):
                continue
            normalized = _coerce_entry(entry)
            if normalized is not None:
                cleaned[name] = normalized
            else:
                logger.warning(f"Dropping malformed XP entry for '{name}': {entry!r}")
        self.player_data = cleaned

    def save_player_data(self) -> None:
        """Save player XP data atomically."""
        atomic_write_json(_xp_file_path(), self.player_data, indent=4)

    def clear_player_xp(self, player_name: str) -> None:
        """Clear a single player's XP (used for admin/reset flows)."""
        if player_name in self.player_data:
            del self.player_data[player_name]
            self.save_player_data()
            logger.info(f"Cleared XP for player '{player_name}'.")

    def clear_all_xp(self) -> None:
        """Clear all player XP data. Destructive — use sparingly."""
        self.player_data = {}
        atomic_write_json(_xp_file_path(), {}, indent=4)
        logger.warning("Cleared ALL player XP data.")

    def get_player_level(self, player_name: str) -> Tuple[int, int, int]:
        """Get player's current level, XP, and XP needed for next level."""
        entry = self.player_data.get(player_name)
        if not entry:
            return 1, 0, LEVEL_THRESHOLDS[0]

        current_xp = int(entry.get("xp", 0))
        current_level = int(entry.get("level", 1))
        next_level_xp = (
            LEVEL_THRESHOLDS[current_level]
            if current_level < len(LEVEL_THRESHOLDS)
            else LEVEL_THRESHOLDS[-1]
        )

        return current_level, current_xp, next_level_xp

    def calculate_xp(self,
                    base_points: int,
                    is_special_hole: bool,
                    consecutive_scores: int,
                    is_double_ball: bool,
                    is_consecutive_double_ball: bool) -> int:
        """Calculate XP earned for a scoring event."""
        xp = BASE_XP_PER_HOLE + base_points

        if is_special_hole:
            xp = int(xp * SPECIAL_HOLE_MULTIPLIER)

        if consecutive_scores > 1:
            xp += CONSECUTIVE_SCORE_BONUS * (consecutive_scores - 1)

        if is_double_ball:
            xp += DOUBLE_BALL_BONUS

        if is_consecutive_double_ball:
            xp += CONSECUTIVE_DOUBLE_BALL_BONUS

        return xp

    def add_xp(self, player_name: str, xp_earned: int) -> Tuple[int, int, bool]:
        """
        Add XP to player and handle level up.
        Returns: (new_level, new_xp, did_level_up)
        """
        entry = self.player_data.get(player_name)
        if not isinstance(entry, dict) or "xp" not in entry or "level" not in entry:
            entry = {"xp": 0, "level": 1}
            self.player_data[player_name] = entry

        entry["xp"] = int(entry.get("xp", 0)) + int(xp_earned)

        old_level = int(entry.get("level", 1))
        while (entry["level"] < len(LEVEL_THRESHOLDS) and
               entry["xp"] >= LEVEL_THRESHOLDS[entry["level"] - 1]):
            entry["level"] += 1

        did_level_up = entry["level"] > old_level
        self.save_player_data()

        return entry["level"], entry["xp"], did_level_up


xp_system = XPSystem()
