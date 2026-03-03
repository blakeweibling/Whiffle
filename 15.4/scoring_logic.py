# scoring_logic.py
"""
Contains the core game scoring logic, processing tracked balls
to determine scores based on zones and game state. Also logs data for stats.
"""

import logging
import time
from typing import Any, Tuple, List, Dict
import numpy as np

# Import necessary constants and classes from the project
from constants import GameConstants
from effects import BallTrail, Explosion

# Import utility functions it depends on
from game_state_helpers import (
    is_ball_at_rest,
    is_ball_zone_stable,
    play_sound,
    save_score,
    show_notification,
)
from game_types import CurrentGameState
from scoring import is_in_scoring_zone

# Import the DataLogger class for type hinting (optional but good practice)
# This assumes data_logger.py is in the same directory or accessible via Python path
try:
    from data_logger import DataLogger
except ImportError:
    DataLogger = Any  # Fallback type if import fails during type checking

logger = logging.getLogger(__name__)


def update_scoring(game_state: Any) -> None:
    """
    Processes tracked balls to determine scores using ZONE-BASED cooldown.
    Logs scoring events and ball positions to the data_logger in game_state.
    """
    newly_scored_pts_this_frame = 0
    current_time = time.time()
    # Ensure tracked_balls exists and is a list
    tracked_balls_list = getattr(game_state, "tracked_balls", [])
    if not isinstance(tracked_balls_list, list):
        logger.error("game_state.tracked_balls is not a list. Cannot update scoring.")
        return

    # --- Log current ball positions for heatmap data ---
    # Ensure data_logger exists on game_state
    if hasattr(game_state, "data_logger") and game_state.data_logger:
        try:
            # Use the tracked_balls_list directly since it's already in the correct format
            if tracked_balls_list:
                game_state.data_logger.log_ball_positions(tracked_balls_list)
        except Exception as e:
            logger.error(f"Error logging ball positions: {e}")
    # --- End position logging ---

    tracked_ids_this_frame = {b[3] for b in tracked_balls_list if len(b) >= 6}

    # --- Clean up state for balls that are no longer tracked ---
    state_dicts_to_clean_names = [
        "ball_states",
        "previous_ball_states",
        "ball_positions_history",
        "ball_zone_history",
        "balls_in_zone",
        "ball_scored_zones",
        "active_trails",
    ]
    keys_to_remove = set()

    # Optimize cleanup by doing it less frequently
    if game_state.frame_count % 30 == 0:  # Clean up every 30 frames
        for dict_name in state_dicts_to_clean_names:
            state_dict = getattr(game_state, dict_name, None)
            if isinstance(state_dict, dict):
                keys_to_remove.update(set(state_dict.keys()) - tracked_ids_this_frame)
            elif dict_name == "active_trails" and not hasattr(
                game_state, "active_trails"
            ):
                pass
            else:
                logger.warning(
                    f"Expected dictionary '{dict_name}' not found or not a dict in game_state during cleanup."
                )

        if keys_to_remove:
            logger.debug(f"Cleaning up state for untracked ball IDs: {keys_to_remove}")
            for dict_name in state_dicts_to_clean_names:
                state_dict = getattr(game_state, dict_name, None)
                if isinstance(state_dict, dict):
                    for ball_id in keys_to_remove:
                        state_dict.pop(ball_id, None)
    # --- End Cleanup ---

    # Track balls in each zone for double ball detection
    zone_balls: Dict[int, List[str]] = {}
    
    for ball in tracked_balls_list:
        try:
            if len(ball) < 6:
                logger.warning(
                    f"Skipping scoring update for malformed ball data: {ball}"
                )
                continue
            x, y, r, ball_id, age, b_type = ball
            center = (int(x), int(y))
        except (ValueError, TypeError, IndexError) as e:
            logger.warning(f"Error unpacking ball data in scoring update: {ball} - {e}")
            continue

        # Update position history (ensure dict exists)
        if not hasattr(game_state, "ball_positions_history"):
            game_state.ball_positions_history = {}

        if not isinstance(game_state.ball_positions_history, dict):
            logger.error("game_state.ball_positions_history is not a dict.")
            game_state.ball_positions_history = {}

        if ball_id not in game_state.ball_positions_history:
            game_state.ball_positions_history[ball_id] = []

        # Add current position to history
        game_state.ball_positions_history[ball_id].append((center, current_time))

        # Limit history length and remove old entries
        while len(
            game_state.ball_positions_history[ball_id]
        ) > GameConstants.POSITION_HISTORY_LENGTH or (
            len(game_state.ball_positions_history[ball_id]) > 0
            and current_time - game_state.ball_positions_history[ball_id][0][1] > 5.0
        ):  # Keep 5 seconds of history
            game_state.ball_positions_history[ball_id].pop(0)

        # Update trail (Fun Mode / Retro Mode)
        if (
            game_state.game_mode in ["fun", "retro"]
            and hasattr(game_state, "active_trails")
            and isinstance(game_state.active_trails, dict)
        ):
            if ball_id not in game_state.active_trails:
                game_state.active_trails[ball_id] = BallTrail(ball_id)
            game_state.active_trails[ball_id].add_position(center)

        # Check current zone (ensure scoring_zones exists)
        zone, zone_idx = None, -1
        current_scoring_zones = getattr(game_state, "scoring_zones", [])
        if not isinstance(current_scoring_zones, list):
            logger.error("game_state.scoring_zones is not a list.")
            continue

        for i, z in enumerate(current_scoring_zones):
            try:
                if isinstance(z, (list, tuple)) and len(z) == 5:
                    if is_in_scoring_zone((x, y, r, ball_id), z):
                        zone, zone_idx = z, i
                        break
                else:
                    logger.warning(f"Invalid zone format encountered: {z}")
            except Exception as e:
                logger.error(
                    f"Error checking if ball {ball_id} is in zone {i} ({z}): {e}"
                )
                continue

        # Check rest and stability (ensure necessary dicts exist)
        ball_zone_hist_dict = getattr(game_state, "ball_zone_history", {})
        if not isinstance(ball_zone_hist_dict, dict):
            logger.error("game_state.ball_zone_history is not a dict.")
            continue

        rest = is_ball_at_rest(
            ball_id, game_state.ball_positions_history, game_state.debug_mode
        )
        stable = is_ball_zone_stable(
            ball_id, zone, ball_zone_hist_dict, game_state.debug_mode
        )

        # Store current state and check against previous (ensure dicts exist)
        if not hasattr(game_state, "ball_states") or not isinstance(
            game_state.ball_states, dict
        ):
            logger.error("game_state.ball_states missing or not a dict.")
            continue
        if not hasattr(game_state, "previous_ball_states") or not isinstance(
            game_state.previous_ball_states, dict
        ):
            game_state.previous_ball_states = {}

        game_state.previous_ball_states[ball_id] = game_state.ball_states.get(
            ball_id, {}
        ).copy()
        game_state.ball_states[ball_id] = {
            "at_rest": rest,
            "stable": stable,
            "zone": zone,
            "idx": zone_idx,
            "time": current_time,
        }

        # --- Scoring Logic ---
        if zone and stable:  # Must be in a zone and stable
            # Ensure necessary dicts exist
            if not hasattr(game_state, "zone_cooldown") or not isinstance(
                game_state.zone_cooldown, dict
            ):
                logger.error("game_state.zone_cooldown missing or not a dict.")
                continue
            if not hasattr(game_state, "ball_scored_zones") or not isinstance(
                game_state.ball_scored_zones, dict
            ):
                logger.error("game_state.ball_scored_zones missing or not a dict.")
                continue

            # Check zone cooldown
            zone_cooldown_time = game_state.zone_cooldown.get(zone_idx, 0)
            if current_time < zone_cooldown_time:
                if game_state.debug_mode:
                    logger.debug(
                        f"Ball {ball_id} in zone {zone_idx}, but zone is on cooldown."
                    )
                continue  # Zone is on cooldown

            # Check if this ball already scored in this zone *this entry*
            if game_state.ball_scored_zones.get(ball_id) == zone_idx:
                if game_state.debug_mode:
                    logger.debug(
                        f"Ball {ball_id} already scored in zone {zone_idx} this entry."
                    )
                continue  # Already scored here

            # Track ball in zone for double ball detection
            if zone_idx not in zone_balls:
                zone_balls[zone_idx] = []
            zone_balls[zone_idx].append(ball_id)

            # --- Score Calculation ---
            _, _, _, _, base_pts = zone  # Assumes zone has 5 elements
            is_sp = zone == game_state.special_hole
            if is_sp:
                current_score_pts = 100  # Special hole base points
                if not game_state.special_hole_hit_this_session:
                    logger.info(
                        "*** First hit in Special Hole this session! End score will be doubled. ***"
                    )
                    show_notification(
                        game_state, "Special Hole Hit! Score will double!", duration=3.0
                    )
                game_state.special_hole_hit_this_session = True
                game_state.special_hole_hits_this_session = (
                    getattr(game_state, "special_hole_hits_this_session", 0) + 1
                )
            else:
                current_score_pts = base_pts

            score_multiplier = 1.0
            # Check ball type and set multiplier accordingly
            b_type_lower = b_type.lower() if b_type else ""
            if b_type_lower in ["gold", "red"]:
                score_multiplier = 2.0
            elif b_type_lower in ["half-red", "half_red", "half", "halfred"]:
                score_multiplier = 1.5
            elif b_type_lower in ["silver", "white"]:
                score_multiplier = 1.0
            # Default to 1.0 for unknown types
            points_to_add = int(current_score_pts * score_multiplier)

            # Achievement tracking: multiplier points and ball-type flags
            if score_multiplier > 1.0:
                game_state.points_from_multiplier_balls_this_game = (
                    getattr(game_state, "points_from_multiplier_balls_this_game", 0)
                    + points_to_add
                )
            if b_type_lower in ["gold", "red"]:
                game_state.scored_red_ball_this_session = True
            elif b_type_lower in ["half-red", "half_red", "half", "halfred"]:
                game_state.scored_half_red_this_session = True

            # --- Update Score & State ---
            game_state.score += points_to_add
            
            # Safely get current player and add score
            try:
                current_player = game_state.get_current_player()
                if current_player:
                    # Check for double ball in this zone
                    is_double_ball = len(zone_balls[zone_idx]) > 1
                    if is_double_ball:
                        current_player.consecutive_double_balls += 1
                    else:
                        current_player.consecutive_double_balls = 0

                    # For static-image games (no live camera), keep per-run score
                    # visible but do not award persistent XP or levels.
                    if getattr(game_state, "camera_available", True):
                        did_level_up = current_player.add_score(
                            points_to_add,
                            zone=zone,
                            is_special_hole=is_sp
                        )

                        # Show level up notification if applicable
                        if did_level_up:
                            show_notification(
                                game_state,
                                f"Level Up! Now level {current_player.level}",
                                duration=3.0
                            )
                    else:
                        # Static-image mode: mirror per-game score locally without XP.
                        if hasattr(current_player, "score"):
                            current_player.score += points_to_add
                        if hasattr(current_player, "total_score"):
                            current_player.total_score += points_to_add
                else:
                    logger.error("Could not get current player to add score.")
            except Exception as e:
                logger.error(f"Error adding score to player object: {e}")

            newly_scored_pts_this_frame += points_to_add

            # --- >>> ADDED: Log Score Event <<< ---
            if hasattr(game_state, "data_logger") and game_state.data_logger:
                try:
                    game_state.data_logger.log_score_event(
                        zone_id=zone_idx, points=points_to_add, ball_type=b_type
                    )
                except Exception as e:
                    logger.error(f"Error logging score event: {e}")

            # Record score event in replay system if active (only for live-camera games)
            if (
                getattr(game_state, "camera_available", True)
                and hasattr(game_state, "replay_manager")
                and game_state.replay_manager
            ):
                try:
                    game_state.replay_manager.record_score(
                        zone_id=zone_idx, points=points_to_add, ball_type=b_type
                    )
                except Exception as e:
                    logger.error(f"Error recording score in replay: {e}")
            # --- >>> END ADDED <<< ---

            # Survival Mode Time Gain
            if game_state.game_mode == "survival":
                try:
                    time_gain = GameConstants.SURVIVAL_MODE_TIME_GAIN_PER_SCORE
                    if game_state.game_timer is not None:
                        game_state.game_timer += time_gain
                        logger.info(
                            f"Survival Mode: Gained {time_gain:.1f}s. New time: {game_state.game_timer:.1f}s"
                        )
                        show_notification(
                            game_state,
                            f"+{time_gain:.0f} Secs!",
                            duration=1.0,
                            is_error=False,
                        )
                    else:
                        logger.warning(
                            "Attempted to add survival time, but timer is None."
                        )
                except AttributeError:
                    logger.error(
                        "SURVIVAL_MODE_TIME_GAIN_PER_SCORE constant not found in GameConstants"
                    )
                    time_gain = 5.0  # Default fallback value
                    if game_state.game_timer is not None:
                        game_state.game_timer += time_gain
                        logger.info(
                            f"Survival Mode: Using fallback time gain of {time_gain:.1f}s. New time: {game_state.game_timer:.1f}s"
                        )
                        show_notification(
                            game_state,
                            f"+{time_gain:.0f} Secs!",
                            duration=1.0,
                            is_error=False,
                        )

            # Record score event (ensure dicts exist)
            if hasattr(game_state, "scored_balls") and isinstance(
                game_state.scored_balls, list
            ):
                game_state.scored_balls.append(ball_id)
            if hasattr(game_state, "balls_in_zone") and isinstance(
                game_state.balls_in_zone, dict
            ):
                game_state.balls_in_zone[ball_id] = zone
            if hasattr(game_state, "ball_scored_zones") and isinstance(
                game_state.ball_scored_zones, dict
            ):
                game_state.ball_scored_zones[ball_id] = zone_idx
            # Set zone cooldown
            cooldown_duration = GameConstants.SCORE_COOLDOWN_DURATION / 1000.0
            game_state.zone_cooldown[zone_idx] = current_time + cooldown_duration

            logger.info(
                f"Ball {ball_id}({b_type}) scored {points_to_add}pts [Base:{base_pts}, Mult:{score_multiplier}] in Zone:{zone_idx}{' (Special Hole)' if is_sp else ''}. Total:{game_state.score}. Zone {zone_idx} cooldown:{cooldown_duration:.1f}s."
            )

            # Fun Mode / Retro Mode Explosion
            if (
                game_state.game_mode in ["fun", "retro"]
                and hasattr(game_state, "active_explosions")
                and isinstance(game_state.active_explosions, list)
            ):
                zone_x, zone_y, zone_w, zone_h, _ = zone
                explosion_center_x = int(zone_x + zone_w / 2)
                explosion_center_y = int(zone_y + zone_h / 2)
                game_state.active_explosions.append(
                    Explosion(explosion_center_x, explosion_center_y)
                )
                logger.debug(
                    f"Created explosion at ({explosion_center_x}, {explosion_center_y}) for score in zone {zone_idx}"
                )

            # Check Win Condition (timed, survival only). Classic has no score cap — play as long as you like.
            # Game over is only for timed mode when time runs out (see game_state_utils).
            if (
                game_state.game_mode in ["timed", "survival"]
                and game_state.score >= game_state.win_score
                and game_state.current_state != CurrentGameState.GAME_OVER
            ):
                game_state.win_condition_met = True
                logger.info(
                    f"Win condition met! Score {game_state.score} >= {game_state.win_score}"
                )
                try:
                    from game_state_utils import record_game_completed

                    record_game_completed(game_state)
                except Exception as rec_e:
                    logger.warning(f"record_game_completed error: {rec_e}")
                try:
                    player_name = "Unknown"
                    if hasattr(game_state, "get_current_player"):
                        player = game_state.get_current_player()
                        if player and hasattr(player, "name"):
                            player_name = player.name
                    save_score(game_state, player_name)
                except Exception as e:
                    logger.error(f"Error saving score on win condition: {e}")

        # --- Ball Left/Became Unstable After Scoring ---
        elif ball_id in getattr(
            game_state, "ball_scored_zones", {}
        ):  # Check dict exists before access  # Check if ball HAD scored previously
            # Ensure necessary dicts exist before modifying
            if not hasattr(game_state, "ball_scored_zones") or not isinstance(
                game_state.ball_scored_zones, dict
            ):
                continue
            if not hasattr(game_state, "balls_in_zone") or not isinstance(
                game_state.balls_in_zone, dict
            ):
                continue
            if not hasattr(game_state, "scored_balls") or not isinstance(
                game_state.scored_balls, list
            ):
                continue

            last_scored_zone_idx = game_state.ball_scored_zones[ball_id]
            # Ball is no longer stable OR it's not in the same zone it scored in
            if not stable or zone_idx != last_scored_zone_idx:
                del game_state.ball_scored_zones[
                    ball_id
                ]  # Clear score status for this entry
                game_state.balls_in_zone.pop(
                    ball_id, None
                )  # Remove from current zone tracking
                logger.debug(
                    f"Ball {ball_id} left/became unstable in zone {last_scored_zone_idx}. Cleared score status."
                )
                # Also remove from legacy list if present
                if ball_id in game_state.scored_balls:
                    try:
                        game_state.scored_balls.remove(ball_id)
                    except ValueError:
                        pass  # Ignore if not found
    # --- End Ball Loop ---

    # Play score sound if any points were scored this frame
    if newly_scored_pts_this_frame > 0:
        play_sound(game_state, game_state.score_sound)

    def _process_frame(
        self, frame: np.ndarray, game_state: "GameState"
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """Process a frame and update game state."""
        # Track balls in the frame
        tracked_balls = self.ball_tracker.track(frame)

        # Log ball positions if tracking is active
        game_state.log_ball_positions(tracked_balls)

        # Draw tracking visualization
        annotated_frame = self._draw_tracking(frame, tracked_balls)

        return annotated_frame, tracked_balls
