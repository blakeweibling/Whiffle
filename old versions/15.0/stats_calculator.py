# stats_calculator.py
"""
Calculates summary statistics from logged session data.
"""

import logging
import time
from collections import defaultdict
from typing import Dict, Any

# Import SessionData for type hinting
try:
    from data_logger import SessionData
except ImportError:
    SessionData = Any  # Fallback type if import fails during type checking

logger = logging.getLogger(__name__)


def calculate_session_stats(session_data: SessionData) -> Dict[str, Any]:
    """
    Calculates summary statistics for a given session.

    Args:
        session_data: The SessionData object containing logged events.

    Returns:
        A dictionary containing calculated statistics:
        - duration_seconds: Total session duration.
        - total_score: Final score for the session.
        - score_rate_per_min: Average score per minute.
        - points_by_ball_type: Dict mapping ball type ('white', 'red', 'half') to total points.
        - top_3_zones: List of tuples [(zone_id, points_scored)], sorted descending by points.
    """
    if not session_data:
        logger.warning("calculate_session_stats called with None session_data.")
        return {}

    stats = {}

    # Basic Info
    stats["duration_seconds"] = session_data.get_duration()
    stats["total_score"] = session_data.final_score

    # Score Rate
    duration_min = (
        stats["duration_seconds"] / 60.0 if stats["duration_seconds"] > 0 else 0
    )
    stats["score_rate_per_min"] = (
        (stats["total_score"] / duration_min) if duration_min > 0 else 0
    )

    # Points by Ball Type and Zone
    points_by_ball_type = defaultdict(int)
    points_by_zone = defaultdict(int)

    if hasattr(session_data, "score_events") and session_data.score_events:
        for event in session_data.score_events:
            try:
                ball_type = event.get("ball_type", "unknown")
                points = event.get("points", 0)
                zone_id = event.get("zone_id", -1)

                if isinstance(points, (int, float)):
                    points_by_ball_type[ball_type] += points
                    if zone_id != -1:
                        points_by_zone[zone_id] += points
                else:
                    logger.warning(f"Invalid points type in score event: {event}")

            except Exception as e:
                logger.error(f"Error processing score event: {event} - {e}")

    stats["points_by_ball_type"] = dict(points_by_ball_type)

    # Top 3 Zones
    # Sort zones by points scored, descending
    sorted_zones = sorted(
        points_by_zone.items(), key=lambda item: item[1], reverse=True
    )
    stats["top_3_zones"] = sorted_zones[:3]  # Get the top 3

    logger.debug(
        f"Calculated stats: Duration={stats['duration_seconds']:.1f}s, Score={stats['total_score']}, Rate={stats['score_rate_per_min']:.1f}/min, TopZones={stats['top_3_zones']}"
    )

    return stats


# Example Usage (for testing purposes, remove later)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Testing StatsCalculator...")

    # Create dummy session data
    class MockSessionData:

        def __init__(self):
            self.start_time = time.time() - 125  # Session started 125 seconds ago
            self.end_time = time.time() - 5  # Session ended 5 seconds ago
            self.final_score = 1150
            self.score_events = [
                {
                    "timestamp": self.start_time + 10,
                    "zone_id": 0,
                    "points": 100,
                    "ball_type": "white",
                },
                {
                    "timestamp": self.start_time + 25,
                    "zone_id": 1,
                    "points": 200,
                    "ball_type": "red",
                },
                {
                    "timestamp": self.start_time + 40,
                    "zone_id": 0,
                    "points": 100,
                    "ball_type": "white",
                },
                {
                    "timestamp": self.start_time + 60,
                    "zone_id": 2,
                    "points": 150,
                    "ball_type": "half",
                },
                {
                    "timestamp": self.start_time + 80,
                    "zone_id": 1,
                    "points": 200,
                    "ball_type": "red",
                },
                {
                    "timestamp": self.start_time + 100,
                    "zone_id": 0,
                    "points": 100,
                    "ball_type": "white",
                },
                {
                    "timestamp": self.start_time + 115,
                    "zone_id": 1,
                    "points": 300,
                    "ball_type": "half",
                },  # Higher points for half this time
            ]
            # Ball position history not needed for these calculations
            self.ball_position_history = {}
            self.zone_definitions = []

        def get_duration(self):
            if self.end_time is None:
                return time.time() - self.start_time
            return self.end_time - self.start_time

    mock_data = MockSessionData()
    calculated_stats = calculate_session_stats(mock_data)

    print("\n--- Calculated Session Stats ---")
    print(f"Duration: {calculated_stats.get('duration_seconds', 0):.1f} seconds")
    print(f"Total Score: {calculated_stats.get('total_score', 0)}")
    print(f"Score Rate: {calculated_stats.get('score_rate_per_min', 0):.1f} points/min")
    print(f"Points by Ball Type: {calculated_stats.get('points_by_ball_type', {})}")
    print(f"Top 3 Zones (Zone ID, Points): {calculated_stats.get('top_3_zones', [])}")

    logger.info("StatsCalculator test complete.")
