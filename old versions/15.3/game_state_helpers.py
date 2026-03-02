# game_state_helpers.py
"""
Contains lower-level helper functions used by game state logic,
separated to avoid circular imports. Includes zone file management.
"""
import json  # Needed for zone/score saving/loading
import logging
import os  # Needed for zone/score saving/loading
import time  # Needed for save_high_score
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pygame  # Needed for play_sound

# Import necessary constants directly
from constants import GameConstants, UIConstants

# Import screenshot utilities
from screenshot_utils import capture_and_upload_game_screenshot

# Import Player class if needed for type hints (though not strictly necessary here)
# from player import Player

logger = logging.getLogger(__name__)

# --- Ball State Helpers ---


def is_ball_at_rest(
    ball_id: int,
    ball_positions_history: Dict[int, List[Tuple[Tuple[int, int], float]]],
    debug_mode: bool = False,
) -> bool:
    """Check if a ball has remained relatively still."""
    history = ball_positions_history.get(ball_id, [])
    history_len_needed = GameConstants.POSITION_HISTORY_LENGTH
    if len(history) < history_len_needed:
        return False
    relevant_history = history[-history_len_needed:]
    # Extract just x,y coordinates from the (center, time) tuples
    start_pos = np.array(relevant_history[0][0])  # First element is the center tuple
    max_dist_sq = GameConstants.REST_THRESHOLD_DISTANCE**2
    for pos in relevant_history[1:]:
        current_pos = np.array(pos[0])  # First element is the center tuple
        dist_sq = np.sum((current_pos - start_pos) ** 2)
        if dist_sq > max_dist_sq:
            return False
    return True


def is_ball_zone_stable(
    ball_id: int,
    current_zone: Optional[Tuple],
    ball_zone_history: Dict[int, List[Optional[int]]],
    debug_mode: bool = False,
) -> bool:
    """Check if a ball has been consistently in the same zone (or None)."""
    if ball_id not in ball_zone_history:
        ball_zone_history[ball_id] = []
    current_zone_id = id(current_zone) if current_zone else None
    ball_zone_history[ball_id].append(current_zone_id)
    stability_frames_needed = GameConstants.ZONE_STABILITY_FRAMES
    if len(ball_zone_history[ball_id]) > stability_frames_needed:
        ball_zone_history[ball_id].pop(0)
    if len(ball_zone_history[ball_id]) < stability_frames_needed:
        return False
    if all(zone_id == current_zone_id for zone_id in ball_zone_history[ball_id]):
        return current_zone_id is not None
    else:
        return False


# --- Sound/Notification/Score Helpers ---


def play_sound(game_state: Any, sound: Optional[pygame.mixer.Sound]) -> None:
    """Play sound effect if enabled and sound exists."""
    if game_state.game_sounds_on and sound:
        try:
            sound.play()
        except pygame.error as e:
            logger.error(f"Sound play error: {e}")


def show_notification(
    game_state: Any, text: str, duration: float = 2.0, is_error: bool = False
) -> None:
    """Display a notification message by updating game_state attributes."""
    game_state.notification_text = text
    game_state.notification_timer = duration
    game_state.notification_color = UIConstants.RED if is_error else UIConstants.GREEN
    log_level = logging.WARNING if is_error else logging.INFO
    logger.log(log_level, f"Notify: {text}")


def save_high_score(game_state: Any):
    """Saves high score data for all modes based on game_state."""
    data = {}
    high_score_file = GameConstants.HIGH_SCORE_FILE
    try:
        if os.path.exists(high_score_file) and os.path.getsize(high_score_file) > 0:
            with open(high_score_file, "r") as f:
                data = json.load(f)
        else:
            data = {
                mode: {} for mode in ["classic", "timed", "fun", "practice", "survival"]
            }
        if game_state.game_mode not in data:
            data[game_state.game_mode] = {}
    except Exception as e:
        logger.error(f"Read high score fail: {e}")
        data = {
            mode: {} for mode in ["classic", "timed", "fun", "practice", "survival"]
        }
    player_name = "Unknown"
    try:
        player = game_state.get_current_player()
        player_name = player.name if player and hasattr(player, "name") else "Unknown"
    except Exception as e:
        logger.error(f"Error getting player name for high score: {e}")
    current_saved_high = data.get(game_state.game_mode, {}).get("high_score", 0)
    if game_state.score > current_saved_high:
        data[game_state.game_mode]["high_score"] = game_state.score
        data[game_state.game_mode]["player"] = player_name
        data[game_state.game_mode]["date"] = time.strftime("%Y-%m-%d %H:%M:%S")
        logger.info(
            f"Updating high score for '{game_state.game_mode}' to {game_state.score} by {player_name}"
        )
        game_state.high_score = game_state.score  # Update attribute too
    try:
        with open(high_score_file, "w") as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        logger.error(f"Save high score file failed: {e}")


def save_score(game_state: Any, player_name: str, mode: Optional[str] = None) -> None:
    """Checks bonus, submits to leaderboard, updates high score file."""
    final_score = game_state.score
    doubled = False
    if game_state.special_hole_hit_this_session:
        final_score *= 2
        doubled = True
    score_to_save = final_score
    game_state.final_score = final_score  # Set the final_score attribute
    current_mode = mode or game_state.game_mode
    if hasattr(game_state, "is_fivestar_playfield"):
        is_fivestar = game_state.is_fivestar_playfield()
    else:
        is_fivestar = getattr(game_state, "playfield_type", "whiffle") == "fivestar"
    playfield_type = "fivestar" if is_fivestar else "whiffle"

    # Variable to hold screenshot URL
    screenshot_url = None

    # Determine if we are running in "static image" mode (no live camera)
    is_static_image_mode = not getattr(game_state, "camera_available", True)

    if score_to_save > 0:
        logger.info(
            f"Saving score {player_name}: {score_to_save} Mode:{current_mode}{' (D)' if doubled else ''}"
        )

        # Only capture/upload screenshots, submit to Supabase-based leaderboard,
        # and update persistent per-game records when we are running with a live
        # camera feed. In static-image mode we treat runs as non-official:
        # no Supabase, no leaderboard queue, and no high-score file updates.
        if not is_static_image_mode:
            try:
                current_frame = None
                # Check if there's a current frame we can capture from different potential sources
                if (
                    hasattr(game_state, "current_frame")
                    and game_state.current_frame is not None
                ):
                    current_frame = game_state.current_frame
                elif (
                    hasattr(game_state, "display_frame")
                    and game_state.display_frame is not None
                ):
                    current_frame = game_state.display_frame
                elif (
                    hasattr(game_state, "static_frame")
                    and game_state.static_frame is not None
                ):
                    current_frame = game_state.static_frame

                if (
                    current_frame is not None
                    and hasattr(game_state, "supabase_url")
                    and hasattr(game_state, "supabase_key")
                ):
                    screenshot_url = capture_and_upload_game_screenshot(
                        current_frame,
                        player_name,
                        score_to_save,
                        current_mode,
                        game_state.supabase_url,
                        game_state.supabase_key,
                    )
                    if screenshot_url:
                        game_state.has_uploaded_screenshot = True
                        logger.info(f"Screenshot captured and uploaded: {screenshot_url}")
                    else:
                        logger.warning("Failed to capture or upload screenshot")
                else:
                    logger.warning(
                        "Missing frame data or Supabase credentials for screenshot capture"
                    )
            except Exception as e:
                logger.error(f"Error during screenshot capture: {e}")

            if hasattr(game_state, "leaderboard") and game_state.leaderboard:
                try:
                    # If we have a screenshot URL, include it in the score submission
                    if screenshot_url:
                        game_state.leaderboard.submit_score(
                            player_name,
                            score_to_save,
                            current_mode,
                            screenshot_url,
                            playfield_type=playfield_type,
                        )
                    else:
                        game_state.leaderboard.submit_score(
                            player_name,
                            score_to_save,
                            current_mode,
                            playfield_type=playfield_type,
                        )
                except Exception as e:
                    logger.error(f"Leaderboard submit error: {e}")
            else:
                logger.error("Leaderboard missing.")
        else:
            logger.info(
                "Static image mode detected (no live camera). "
                "Skipping Supabase screenshot upload, leaderboard submission, "
                "and high-score persistence."
            )
        # Persist high scores only for live-camera games
        if not is_static_image_mode:
            if (
                current_mode == game_state.game_mode
                and score_to_save > game_state.high_score
            ):
                logger.info(f"New high score '{current_mode}': {score_to_save}. Saving.")
                game_state.score = score_to_save  # Ensure score attribute has final value
                save_high_score(game_state)
            else:
                # Save anyway to ensure file consistency
                save_high_score(game_state)
    else:
        logger.info(f"Score {score_to_save}, not saving.")


def set_special_hole(
    scoring_zones: List[Tuple[int, int, int, int, int]],
) -> Optional[Tuple[int, int, int, int, int]]:
    """Identify the leftmost scoring zone as the special hole."""
    if not scoring_zones:
        return None
    try:
        valid_zones = [
            z for z in scoring_zones if isinstance(z, (list, tuple)) and len(z) >= 1
        ]
        if not valid_zones:
            return None
        special_hole = min(valid_zones, key=lambda zone: zone[0])
        return special_hole
    except Exception as e:
        logger.error(f"Error finding special hole: {e}")
        return None


# --- Zone Management Helpers ---


def save_zones(game_state: Any, zones_file_path: Optional[str] = None) -> None:
    """Save the current scoring zones to a JSON file."""
    try:
        zones_file = zones_file_path or getattr(
            game_state, "zones_file_path", GameConstants.ZONES_FILE
        )
        with open(zones_file, "w") as f:
            json.dump(game_state.scoring_zones, f, indent=4)
        logger.info(f"Scoring zones saved to {zones_file}")
        show_notification(game_state, "Zones Saved")  # Uses helper
    except IOError as e:
        logger.error(f"Error saving scoring zones: {e}")
        show_notification(
            game_state, "Error Saving Zones", is_error=True
        )  # Uses helper


def load_zones(game_state: Any, zones_file_path: Optional[str] = None) -> None:
    """Load scoring zones from a JSON file."""
    zones_file_path = zones_file_path or getattr(
        game_state, "zones_file_path", GameConstants.ZONES_FILE
    )
    if os.path.exists(zones_file_path):
        try:
            if os.path.getsize(zones_file_path) == 0:
                logger.warning(f"{zones_file_path} is empty. Clearing zones.")
                game_state.scoring_zones = []
                game_state.special_hole = None
                show_notification(
                    game_state, "Zones File Empty, Cleared Zones"
                )  # Uses helper
                return

            with open(zones_file_path, "r") as f:
                loaded_data = json.load(f)
            if isinstance(loaded_data, list) and all(
                isinstance(z, (list, tuple))
                and len(z) == 5
                and all(isinstance(v, (int, float)) for v in z)
                for z in loaded_data
            ):
                game_state.scoring_zones = [
                    (int(z[0]), int(z[1]), int(z[2]), int(z[3]), int(z[4]))
                    for z in loaded_data
                ]
                logger.info(f"Scoring zones loaded from {zones_file_path}")
                show_notification(game_state, "Zones Loaded")  # Uses helper
                if hasattr(game_state, "is_fivestar_playfield"):
                    is_fivestar = game_state.is_fivestar_playfield()
                else:
                    is_fivestar = (
                        getattr(game_state, "playfield_type", "whiffle") == "fivestar"
                    )
                if is_fivestar:
                    game_state.special_hole = None
                else:
                    game_state.special_hole = set_special_hole(
                        game_state.scoring_zones
                    )  # Calls helper above
            else:
                logger.error(f"Invalid format in {zones_file_path}.")
                show_notification(
                    game_state, "Invalid Zone File Format", is_error=True
                )  # Uses helper
                game_state.scoring_zones = []
                game_state.special_hole = None
        except Exception as e:
            logger.exception(f"Error loading/processing {zones_file_path}: {e}")
            show_notification(
                game_state, "Error Loading Zones", is_error=True
            )  # Uses helper
            game_state.scoring_zones = []
            game_state.special_hole = None
    else:
        logger.warning(f"Scoring zones file '{zones_file_path}' not found.")
        game_state.scoring_zones = []
        game_state.special_hole = None
        show_notification(
            game_state,
            "No zones file found. Define zones in Menu > Manage Zones.",
            duration=3.0,
        )


def clear_zones(game_state: Any, zones_file_path: Optional[str] = None) -> None:
    """Clear all scoring zones and remove the file."""
    game_state.scoring_zones.clear()
    game_state.special_hole = None
    zones_file_path = zones_file_path or getattr(
        game_state, "zones_file_path", GameConstants.ZONES_FILE
    )
    if os.path.exists(zones_file_path):
        try:
            os.remove(zones_file_path)
            logger.info(f"Removed zones file: {zones_file_path}")
        except OSError as e:
            logger.error(f"Failed remove zones file {zones_file_path}: {e}")
            show_notification(
                game_state, "Error Removing Zone File", is_error=True
            )  # Uses helper
    logger.info("All scoring zones cleared.")
    show_notification(game_state, "All Zones Cleared")  # Uses helper


def flush_scoring_zones(game_state: Any) -> None:
    """Write current scoring zones to disk. Called during clean exit."""
    logger.debug("Flushing scoring zones (calling save_zones)...")
    save_zones(game_state)  # Calls helper above
