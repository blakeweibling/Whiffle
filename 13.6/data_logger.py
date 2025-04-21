# data_logger.py
"""
Handles logging of game events and session statistics for the Whiffle Tracker.
"""

import logging
import time
import json
import os
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime

# Assuming constants.py will define these later
STATS_HISTORY_FILE = "data/sessions/session_stats_history.json"
MAX_HISTORY_ENTRIES = 50  # Limit the number of past sessions stored

logger = logging.getLogger(__name__)


class SessionData:
    """Holds statistics for a single game session."""

    def __init__(self, player_name: str, game_mode: str):
        self.player_name: str = player_name
        self.game_mode: str = game_mode
        self.start_time: float = time.time()
        self.end_time: Optional[float] = None
        self.final_score: int = 0
        self.score_events: List[Dict[str, Any]] = (
            []
        )  # {timestamp, zone_id, points, ball_type}
        self.zone_definitions: List[Tuple[int, int, int, int, int]] = []
        self.ball_position_history: Dict[int, List[Tuple[int, int, float]]] = (
            defaultdict(list)
        )  # ball_id -> [(x, y, timestamp), ...]
        self.has_position_data: bool = (
            False  # Flag to track if we have any position data
        )

    def log_score(self, zone_id: int, points: int, ball_type: str):
        """Logs a scoring event."""
        self.score_events.append(
            {
                "timestamp": time.time(),
                "zone_id": zone_id,
                "points": points,
                "ball_type": ball_type,
            }
        )
        logger.debug(
            f"Logged score event: Zone {zone_id}, Pts {points}, Type {ball_type}"
        )

    def log_ball_position(self, ball_id: int, x: int, y: int):
        """Logs the position of a ball at the current time."""
        timestamp = time.time()
        self.ball_position_history[ball_id].append((x, y, timestamp))
        self.has_position_data = True  # Set flag to indicate we have position data
        # Optional: Limit history length per ball to save memory
        if len(self.ball_position_history[ball_id]) > 1000:
            self.ball_position_history[ball_id].pop(0)

    def finalize_session(
        self, final_score: int, zones: List[Tuple[int, int, int, int, int]]
    ):
        """Marks the session end time and sets final score and zones."""
        self.end_time = time.time()
        self.final_score = final_score
        self.zone_definitions = zones[:]  # Store a copy
        logger.info(
            f"Finalizing session. Score: {self.final_score}, Duration: {self.get_duration():.1f}s"
        )

    def get_duration(self) -> float:
        """Calculates the session duration in seconds."""
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        """Converts session data to a dictionary for saving."""
        return {
            "player_name": self.player_name,
            "game_mode": self.game_mode,
            "start_timestamp_iso": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_timestamp_iso": (
                datetime.fromtimestamp(self.end_time).isoformat()
                if self.end_time
                else None
            ),
            "duration_seconds": self.get_duration(),
            "final_score": self.final_score,
            "score_events": self.score_events,
            "zone_definitions": self.zone_definitions,
            # Note: ball_position_history is likely too large to save historically
        }

    def has_ball_position_data(self) -> bool:
        """Returns True if this session has any ball position data recorded."""
        return self.has_position_data and any(
            len(positions) > 0 for positions in self.ball_position_history.values()
        )


class DataLogger:
    """Manages the current game session data and historical stats."""

    def __init__(self):
        self.current_session: Optional[SessionData] = None
        self.historical_stats: List[Dict[str, Any]] = self._load_historical_stats()

    def start_new_session(self, player_name: str, game_mode: str):
        """Starts logging a new game session."""
        # Save previous session if it exists and wasn't finalized properly
        self.end_current_session(
            0, []
        )  # Pass dummy values, score should be updated later

        logger.info(
            f"Starting new session for Player: {player_name}, Mode: {game_mode}"
        )
        self.current_session = SessionData(player_name, game_mode)

    def log_score_event(self, zone_id: int, points: int, ball_type: str):
        """Logs a score event in the current session."""
        if self.current_session:
            self.current_session.log_score(zone_id, points, ball_type)
        else:
            logger.warning("Attempted to log score event, but no active session.")

    def log_ball_positions(
        self, tracked_balls: List[Tuple[int, int, float, int, int, str]]
    ):
        """Logs positions of all currently tracked balls."""
        if self.current_session:
            for ball_data in tracked_balls:
                try:
                    if len(ball_data) >= 6:
                        x, y, _, ball_id, _, _ = ball_data
                        self.current_session.log_ball_position(ball_id, int(x), int(y))
                except (IndexError, ValueError, TypeError):
                    logger.warning(f"Could not log position for ball data: {ball_data}")
        # else: logger.debug("No active session to log ball positions.") # Can be noisy

    def end_current_session(
        self, final_score: int, zones: List[Tuple[int, int, int, int, int]]
    ):
        """Finalizes the current session and adds it to history."""
        if self.current_session:
            logger.info("Ending current session.")
            self.current_session.finalize_session(final_score, zones)
            session_dict = self.current_session.to_dict()
            self.historical_stats.append(session_dict)
            # Limit history size
            if len(self.historical_stats) > MAX_HISTORY_ENTRIES:
                self.historical_stats = self.historical_stats[-MAX_HISTORY_ENTRIES:]
            self._save_historical_stats()
            self.current_session = None
        # else: logger.debug("No active session to end.") # Can be noisy

    def get_current_session_data(self) -> Optional[SessionData]:
        """Returns the current active session data object."""
        return self.current_session

    def get_historical_stats(self) -> List[Dict[str, Any]]:
        """Returns the loaded historical session data."""
        return self.historical_stats

    def _load_historical_stats(self) -> List[Dict[str, Any]]:
        """Loads historical session data from the JSON file."""
        if os.path.exists(STATS_HISTORY_FILE):
            try:
                with open(STATS_HISTORY_FILE, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        logger.info(f"Loaded {len(data)} historical session records.")
                        return data
                    else:
                        logger.warning(
                            f"Historical stats file '{STATS_HISTORY_FILE}' has invalid format (not a list). Starting fresh."
                        )
                        return []
            except (json.JSONDecodeError, IOError) as e:
                logger.error(
                    f"Failed to load historical stats from '{STATS_HISTORY_FILE}': {e}. Starting fresh."
                )
                return []
        else:
            logger.info(
                f"Historical stats file '{STATS_HISTORY_FILE}' not found. Starting fresh."
            )
            return []

    def _save_historical_stats(self):
        """Saves the current historical session data to the JSON file."""
        try:
            with open(STATS_HISTORY_FILE, "w") as f:
                json.dump(self.historical_stats, f, indent=2)
            logger.info(
                f"Saved {len(self.historical_stats)} historical session records to '{STATS_HISTORY_FILE}'."
            )
        except IOError as e:
            logger.error(
                f"Failed to save historical stats to '{STATS_HISTORY_FILE}': {e}"
            )


# Example Usage (for testing purposes, remove later)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Testing DataLogger...")
    data_logger = DataLogger()

    # Simulate Session 1
    data_logger.start_new_session("Player1", "timed")
    data_logger.log_score_event(zone_id=0, points=100, ball_type="white")
    time.sleep(0.1)
    data_logger.log_ball_positions([(100, 200, 10.0, 1, 5, "white")])
    data_logger.log_score_event(zone_id=1, points=200, ball_type="red")
    time.sleep(0.1)
    data_logger.log_ball_positions(
        [(110, 210, 10.0, 1, 6, "white"), (500, 400, 12.0, 2, 1, "red")]
    )
    data_logger.end_current_session(300, [(0, 0, 50, 50, 100), (400, 400, 50, 50, 200)])

    # Simulate Session 2
    data_logger.start_new_session("Player1", "classic")
    data_logger.log_score_event(zone_id=0, points=50, ball_type="half")
    time.sleep(0.1)
    data_logger.end_current_session(50, [(0, 0, 50, 50, 100)])

    print("\n--- Current Session Data (should be None) ---")
    print(data_logger.get_current_session_data())

    print("\n--- Historical Stats ---")
    history = data_logger.get_historical_stats()
    for i, entry in enumerate(history):
        print(
            f"Session {i+1}: Player={entry.get('player_name')}, Mode={entry.get('game_mode')}, Score={entry.get('final_score')}, Events={len(entry.get('score_events', []))}"
        )

    logger.info("DataLogger test complete.")
