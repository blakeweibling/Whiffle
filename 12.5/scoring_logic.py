# scoring_logic.py
"""
Contains the core game scoring logic, processing tracked balls
to determine scores based on zones and game state.
"""

import logging
import time
from typing import Any

# Import necessary constants and classes from the project
from constants import GameConstants
from effects import BallTrail, Explosion
# Import utility functions it depends on
from game_state_helpers import (  # Import helpers from new file; <--- CORRECTED IMPORT
    is_ball_at_rest, is_ball_zone_stable, play_sound, save_score,
    show_notification)
from game_types import CurrentGameState  # Import from new location
from scoring import is_in_scoring_zone  # Assumes this is the correct location

# Player class is used via game_state.get_current_player()
# from player import Player # Not directly imported, accessed via game_state

logger = logging.getLogger(__name__)


def update_scoring(game_state: Any) -> None:
    """Processes tracked balls to determine scores using ZONE-BASED cooldown."""
    newly_scored_pts_this_frame = 0
    current_time = time.time()
    # Ensure tracked_balls exists and is a list
    tracked_balls_list = getattr(game_state, "tracked_balls", [])
    if not isinstance(tracked_balls_list, list):
        logger.error(
            "game_state.tracked_balls is not a list. Cannot update scoring.")
        return

    tracked_ids_this_frame = {b[3] for b in tracked_balls_list if len(b) >= 6}

    # --- Clean up state for balls that are no longer tracked ---
    # Define state dictionaries to clean (ensure they exist on game_state)
    state_dicts_to_clean_names = [
        "ball_states",
        "previous_ball_states",
        "ball_positions_history",
        "ball_zone_history",
        "balls_in_zone",
        "ball_scored_zones",
        "active_trails",  # Include if fun mode exists and uses it
    ]
    keys_to_remove = set()

    for dict_name in state_dicts_to_clean_names:
        state_dict = getattr(game_state, dict_name, None)
        if isinstance(state_dict, dict):
            keys_to_remove.update(
                set(state_dict.keys()) - tracked_ids_this_frame)
        elif dict_name == "active_trails" and not hasattr(
                game_state, "active_trails"):
            pass  # Ignore if fun mode effects aren't present
        else:
            logger.warning(
                f"Expected dictionary '{dict_name}' not found or not a dict in game_state during cleanup."
            )

    if keys_to_remove:
        logger.debug(
            f"Cleaning up state for untracked ball IDs: {keys_to_remove}")
        for dict_name in state_dicts_to_clean_names:
            state_dict = getattr(game_state, dict_name, None)
            if isinstance(state_dict, dict):
                for ball_id in keys_to_remove:
                    state_dict.pop(ball_id, None)
    # --- End Cleanup ---

    # --- Process currently tracked balls ---
    for ball in tracked_balls_list:
        try:
            if len(ball) < 6:
                logger.warning(
                    f"Skipping scoring update for malformed ball data: {ball}")
                continue
            x, y, r, ball_id, age, b_type = ball
            center = (int(x), int(y))
        except (ValueError, TypeError, IndexError) as e:
            logger.warning(
                f"Error unpacking ball data in scoring update: {ball} - {e}")
            continue

        # Update position history (ensure dict exists)
        if not hasattr(game_state, "ball_positions_history") or not isinstance(
                game_state.ball_positions_history, dict):
            logger.error(
                "game_state.ball_positions_history missing or not a dict.")
            continue  # Skip processing if history cannot be stored
        if ball_id not in game_state.ball_positions_history:
            game_state.ball_positions_history[ball_id] = []
        game_state.ball_positions_history[ball_id].append(center)
        # Limit history length
        if (len(game_state.ball_positions_history[ball_id])
                > GameConstants.POSITION_HISTORY_LENGTH):
            game_state.ball_positions_history[ball_id].pop(0)

        # Update trail (Fun Mode - check attribute exists)
        if (game_state.game_mode == "fun"
                and hasattr(game_state, "active_trails")
                and isinstance(game_state.active_trails, dict)):
            if ball_id not in game_state.active_trails:
                game_state.active_trails[ball_id] = BallTrail(ball_id)
            game_state.active_trails[ball_id].add_position(center)

        # Check current zone (ensure scoring_zones exists)
        zone, zone_idx = None, -1
        current_scoring_zones = getattr(game_state, "scoring_zones", [])
        if not isinstance(current_scoring_zones, list):
            logger.error("game_state.scoring_zones is not a list.")
            continue  # Skip if zones are invalid

        for i, z in enumerate(current_scoring_zones):
            try:
                # Validate zone format before check
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

        rest = is_ball_at_rest(ball_id, game_state.ball_positions_history,
                               game_state.debug_mode)
        stable = is_ball_zone_stable(ball_id, zone, ball_zone_hist_dict,
                                     game_state.debug_mode)

        # Store current state and check against previous (ensure dicts exist)
        if not hasattr(game_state, "ball_states") or not isinstance(
                game_state.ball_states, dict):
            logger.error("game_state.ball_states missing or not a dict.")
            continue
        if not hasattr(game_state, "previous_ball_states") or not isinstance(
                game_state.previous_ball_states, dict):
            game_state.previous_ball_states = {}  # Initialize if missing

        game_state.previous_ball_states[ball_id] = game_state.ball_states.get(
            ball_id, {}).copy()
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
                    game_state.zone_cooldown, dict):
                logger.error("game_state.zone_cooldown missing or not a dict.")
                continue
            if not hasattr(game_state, "ball_scored_zones") or not isinstance(
                    game_state.ball_scored_zones, dict):
                logger.error(
                    "game_state.ball_scored_zones missing or not a dict.")
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

            # --- Score Calculation ---
            _, _, _, _, base_pts = zone  # Assumes zone has 5 elements
            is_sp = zone == game_state.special_hole
            if is_sp:
                current_score_pts = 100  # Special hole base points
                if not game_state.special_hole_hit_this_session:
                    logger.info(
                        "*** First hit in Special Hole this session! End score will be doubled. ***"
                    )
                    show_notification(game_state,
                                      "Special Hole Hit! Score will double!",
                                      duration=3.0)
                game_state.special_hole_hit_this_session = True
            else:
                current_score_pts = base_pts

            score_multiplier = 1.0
            if b_type == "red":
                score_multiplier = 2.0
            elif b_type == "half":
                score_multiplier = 1.5
            points_to_add = int(current_score_pts * score_multiplier)

            # --- Update Score & State ---
            game_state.score += points_to_add
            # Safely get current player and add score
            try:
                current_player = game_state.get_current_player()
                if current_player:
                    current_player.add_score(points_to_add)
                else:
                    logger.error("Could not get current player to add score.")
            except Exception as e:
                logger.error(f"Error adding score to player object: {e}")

            newly_scored_pts_this_frame += points_to_add

            # Survival Mode Time Gain
            if game_state.game_mode == "survival":
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
                        "Attempted to add survival time, but timer is None.")

            # Record score event (ensure dicts exist)
            if hasattr(game_state, "scored_balls") and isinstance(
                    game_state.scored_balls, list):
                game_state.scored_balls.append(ball_id)  # Potentially legacy
            if hasattr(game_state, "balls_in_zone") and isinstance(
                    game_state.balls_in_zone, dict):
                game_state.balls_in_zone[ball_id] = zone
            if hasattr(game_state, "ball_scored_zones") and isinstance(
                    game_state.ball_scored_zones, dict):
                game_state.ball_scored_zones[ball_id] = zone_idx
            # Set zone cooldown
            cooldown_duration = GameConstants.SCORE_COOLDOWN_DURATION / 1000.0
            game_state.zone_cooldown[zone_idx] = current_time + \
                cooldown_duration

            logger.info(
                f"Ball {ball_id}({b_type}) scored {points_to_add}pts [Base:{base_pts}, Mult:{score_multiplier}] in Zone:{zone_idx}{' (Special Hole)' if is_sp else ''}. Total:{game_state.score}. Zone {zone_idx} cooldown:{cooldown_duration:.1f}s."
            )

            # Fun Mode Explosion
            if (game_state.game_mode == "fun"
                    and hasattr(game_state, "active_explosions")
                    and isinstance(game_state.active_explosions, list)):
                zone_x, zone_y, zone_w, zone_h, _ = zone
                explosion_center_x = int(zone_x + zone_w / 2)
                explosion_center_y = int(zone_y + zone_h / 2)
                game_state.active_explosions.append(
                    Explosion(explosion_center_x, explosion_center_y))
                logger.debug(
                    f"Created explosion at ({explosion_center_x}, {explosion_center_y}) for score in zone {zone_idx}"
                )

            # Check Timed Mode Win Condition
            if (game_state.game_mode == "timed"
                    and game_state.score >= game_state.win_score and
                    game_state.current_state != CurrentGameState.GAME_OVER):
                game_state.win_condition_met = True
                game_state.current_state = CurrentGameState.GAME_OVER
                logger.info(
                    f"Win condition met! Score {game_state.score} >= {game_state.win_score}"
                )
                # Save score using utility function
                try:
                    save_score(game_state,
                               game_state.get_current_player().name)
                except Exception as e:
                    logger.error(f"Error saving score on win condition: {e}")

        # --- Ball Left/Became Unstable After Scoring ---
        elif (ball_id in game_state.ball_scored_zones
              ):  # Check if ball HAD scored previously
            # Ensure necessary dicts exist before modifying
            if not hasattr(game_state, "ball_scored_zones") or not isinstance(
                    game_state.ball_scored_zones, dict):
                continue
            if not hasattr(game_state, "balls_in_zone") or not isinstance(
                    game_state.balls_in_zone, dict):
                continue
            if not hasattr(game_state, "scored_balls") or not isinstance(
                    game_state.scored_balls, list):
                continue

            last_scored_zone_idx = game_state.ball_scored_zones[ball_id]
            # Ball is no longer stable OR it's not in the same zone it scored in
            if not stable or zone_idx != last_scored_zone_idx:
                del game_state.ball_scored_zones[
                    ball_id]  # Clear score status for this entry
                game_state.balls_in_zone.pop(
                    ball_id, None)  # Remove from current zone tracking
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
        play_sound(game_state, game_state.score_sound)  # Call helper
