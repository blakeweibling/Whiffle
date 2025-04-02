# game_scoring.py

import time
import logging
import os
import json
from typing import TYPE_CHECKING, Tuple, Dict, Any, Optional

# Import constants and utility functions
# Assuming game_constants.py is in the same directory or accessible
from game_constants import GameConstants, ScoringConstants, UIConstants
from game_state_utils import is_ball_at_rest, is_ball_zone_stable
from scoring import is_in_scoring_zone # Assuming this is still needed from original structure

# Use forward reference for GameState to avoid circular imports
if TYPE_CHECKING:
    from game_state import GameState, CurrentGameState


logger = logging.getLogger(__name__)


def update_scoring(game_state: 'GameState') -> None:
    """
    Processes tracked balls to determine scores using ZONE-BASED cooldown.
    Updates the game_state object directly.
    """
    newly_scored_pts_this_frame = 0
    current_time = time.time()

    tracked_ids_this_frame = {b[3] for b in game_state.tracked_balls if len(b) >= 6}

    # --- Cleanup dictionaries for balls no longer tracked ---
    keys_to_remove = set()
    # Combine keys from all relevant dictionaries
    keys_to_remove.update(set(game_state.ball_states.keys()) - tracked_ids_this_frame)
    keys_to_remove.update(set(game_state.previous_ball_states.keys()) - tracked_ids_this_frame)
    keys_to_remove.update(set(game_state.ball_positions_history.keys()) - tracked_ids_this_frame)
    keys_to_remove.update(set(game_state.ball_zone_history.keys()) - tracked_ids_this_frame)
    keys_to_remove.update(set(game_state.balls_in_zone.keys()) - tracked_ids_this_frame)
    keys_to_remove.update(set(game_state.ball_scored_zones.keys()) - tracked_ids_this_frame)
    keys_to_remove.update(set(game_state.ball_trails.keys()) - tracked_ids_this_frame) # Also clean trails

    if keys_to_remove:
        logger.debug(f"Cleaning up state for untracked ball IDs: {keys_to_remove}")
        dicts_to_clean = [
            game_state.ball_states, game_state.previous_ball_states,
            game_state.ball_positions_history, game_state.ball_zone_history,
            game_state.balls_in_zone, game_state.ball_scored_zones,
            game_state.ball_trails
        ]
        for ball_id in keys_to_remove:
            for d in dicts_to_clean:
                d.pop(ball_id, None)
    # --- End Cleanup ---

    for ball in game_state.tracked_balls:
        try:
            if len(ball) < 6:
                logger.warning(f"Skipping scoring malformed ball data (length < 6): {ball}")
                continue
            x, y, r, ball_id, age, b_type = ball
            center = (int(x), int(y))
        except (ValueError, TypeError, IndexError) as e:
            logger.warning(f"Skipping scoring due to invalid ball data {ball}: {e}")
            continue

        # Update position history
        if ball_id not in game_state.ball_positions_history:
            game_state.ball_positions_history[ball_id] = []
        game_state.ball_positions_history[ball_id].append(center)
        if len(game_state.ball_positions_history[ball_id]) > GameConstants.POSITION_HISTORY_LENGTH:
            game_state.ball_positions_history[ball_id].pop(0)

        # Find current zone
        zone, zone_idx = None, -1
        for i, z in enumerate(game_state.scoring_zones):
            try:
                if is_in_scoring_zone((x, y, r, ball_id), z):
                    zone, zone_idx = z, i
                    break
            except Exception as e:
                 logger.error(f"Error checking if ball {ball_id} is in zone {i}: {e}")
                 continue

        # --- Ball State Calculation ---
        rest = is_ball_at_rest(ball_id, game_state.ball_positions_history, game_state.debug_mode)
        # Update zone history *before* checking stability
        if ball_id not in game_state.ball_zone_history:
            game_state.ball_zone_history[ball_id] = []
        # Add current zone index (or None) to history
        current_zone_idx_for_history = zone_idx if zone is not None else None
        game_state.ball_zone_history[ball_id].append(current_zone_idx_for_history)
        if len(game_state.ball_zone_history[ball_id]) > GameConstants.ZONE_HISTORY_LENGTH:
             game_state.ball_zone_history[ball_id].pop(0)
        # Now check stability
        stable = is_ball_zone_stable(ball_id, zone, game_state.ball_zone_history, game_state.debug_mode) # Pass zone object

        # Update ball state dictionary
        game_state.previous_ball_states[ball_id] = game_state.ball_states.get(ball_id, {}).copy()
        game_state.ball_states[ball_id] = {
            "at_rest": rest,
            "stable": stable,
            "zone": zone, # Store the actual zone tuple or None
            "idx": zone_idx, # Store zone index or -1
            "time": current_time,
        }
        # --- End Ball State Calculation ---

        # --- Scoring Logic ---
        if zone and stable: # Score only if ball is stable IN a defined zone
            # Check 1: Is this specific ZONE on cooldown?
            zone_cooldown_time = game_state.zone_cooldown.get(zone_idx, 0)
            if current_time < zone_cooldown_time:
                if game_state.debug_mode:
                    logger.debug(f"Zone {zone_idx} is on cooldown ({zone_cooldown_time - current_time:.1f}s left). Skipping score check for ball {ball_id}.")
                continue # Skip scoring checks if zone is on cooldown

            # Check 2: Has this specific ball ALREADY scored in this specific zone *session*?
            if game_state.ball_scored_zones.get(ball_id) == zone_idx:
                if game_state.debug_mode:
                    logger.debug(f"Ball {ball_id} already scored in zone {zone_idx} this entry. Skipping.")
                continue # Skip if already scored in this zone instance

            # --- If passed checks, proceed with scoring ---
            _, _, _, _, base_pts = zone # Original points
            is_sp = zone == game_state.special_hole

            # Special Hole Logic
            if is_sp:
                current_score_pts = ScoringConstants.SPECIAL_HOLE_POINTS
                if not game_state.special_hole_hit_this_session:
                    logger.info("*** First hit in Special Hole this session! End score will be doubled. ***")
                    # Notification should be handled by GameState based on flag change
                    # game_state.show_notification("Special Hole Hit! Score will double!", duration=3.0) # Moved to GameState watcher potentially
                game_state.special_hole_hit_this_session = True # Set flag
            else:
                current_score_pts = base_pts # Normal points

            # Apply ball type multiplier
            score_multiplier = ScoringConstants.MULTIPLIER_DEFAULT
            if b_type == "red":
                score_multiplier = ScoringConstants.MULTIPLIER_RED_BALL
            elif b_type == "half":
                 score_multiplier = ScoringConstants.MULTIPLIER_HALF_BALL
            points_to_add = int(current_score_pts * score_multiplier)

            # Update scores in GameState
            game_state.score += points_to_add
            game_state.get_current_player().add_score(points_to_add)
            newly_scored_pts_this_frame += points_to_add

            # Update tracking states
            game_state.scored_balls.append(ball_id) # Legacy list
            game_state.balls_in_zone[ball_id] = zone # Track which zone ball is in
            game_state.ball_scored_zones[ball_id] = zone_idx # Mark as scored in this zone

            # Set ZONE cooldown
            cooldown_duration = ScoringConstants.SCORE_COOLDOWN_DURATION / 1000.0 # ms to s
            game_state.zone_cooldown[zone_idx] = current_time + cooldown_duration

            logger.info(
                f"Ball {ball_id}({b_type}) scored {points_to_add}pts [Base:{base_pts}, Mult:{score_multiplier}] in Zone:{zone_idx}{' (Special Hole)' if is_sp else ''}. Total Score:{game_state.score}. Zone {zone_idx} cooldown until T+{cooldown_duration:.1f}s."
            )

            # Play score sound (triggered from GameState after this function returns)
            # Check win conditions (triggered from GameState after this function returns)

        # --- Logic for when ball leaves a zone it previously scored in ---
        elif ball_id in game_state.ball_scored_zones: # Check if ball *was* scored
             last_scored_zone_idx = game_state.ball_scored_zones[ball_id]
             # If ball is no longer stable in that zone OR is now in a different zone/no zone
             if not stable or zone_idx != last_scored_zone_idx:
                  # Clear the 'scored' status for this ball, allowing it to score again
                  del game_state.ball_scored_zones[ball_id]
                  game_state.balls_in_zone.pop(ball_id, None) # Remove from current zone tracking
                  logger.debug(f"Ball {ball_id} left/became unstable in zone {last_scored_zone_idx}. Cleared its scored status for this entry.")
                  # Optional: Remove from legacy scored_balls list
                  if ball_id in game_state.scored_balls:
                       try:
                           game_state.scored_balls.remove(ball_id)
                       except ValueError:
                            pass # Ignore if already removed

        # --- End Scoring Logic ---

    # Return flag indicating if a score happened (for sound trigger)
    return newly_scored_pts_this_frame > 0


def save_score(game_state: 'GameState', player_name: str, mode: Optional[str] = None) -> None:
    """
    Checks for special hole bonus, saves score to leaderboard, and updates high score file.
    Operates on the game_state object.
    """
    final_score = game_state.score # Score at time of call
    doubled = False
    if game_state.special_hole_hit_this_session:
        logger.info(f"Special hole was hit! Doubling final score {final_score} for {player_name}.")
        final_score *= ScoringConstants.SPECIAL_HOLE_BONUS_MULTIPLIER
        doubled = True

    score_to_save = final_score # Use potentially doubled score
    current_mode = mode or game_state.game_mode # Use specified or current mode

    if score_to_save > 0:
        logger.info(f"Saving score for {player_name}: {score_to_save} (Mode: {current_mode}){' (Doubled)' if doubled else ''}")
        # Submit score to leaderboard (if available)
        if hasattr(game_state, 'leaderboard') and game_state.leaderboard:
             game_state.leaderboard.submit_score(player_name, score_to_save, current_mode)
        else:
             logger.error("Leaderboard object not available in game_state. Cannot submit score online.")

        # --- Local High Score File Update ---
        _update_local_high_score(game_state, score_to_save, player_name, current_mode)

    else:
        logger.info(f"Score is {score_to_save}, not saving.")


def _update_local_high_score(game_state: 'GameState', current_session_score: int, player_name: str, game_mode: str) -> None:
    """
    Handles reading, updating, and writing the local high score JSON file.
    """
    data = {}
    high_score_file = GameConstants.HIGH_SCORE_FILE
    try:
        if os.path.exists(high_score_file) and os.path.getsize(high_score_file) > 0:
            with open(high_score_file, "r") as f:
                data = json.load(f)
        else:
            # Initialize structure if file missing or empty
            data = {"classic": {"high_score": 0, "player": "N/A", "date": ""},
                    "timed": {"high_score": 0, "player": "N/A", "date": ""}}
            if not os.path.exists(high_score_file):
                logger.info(f"High score file not found: {high_score_file}. Will create.")
            elif os.path.getsize(high_score_file) == 0:
                 logger.warning(f"High score file exists but is empty: {high_score_file}. Will overwrite.")

    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Could not read/parse high score file ({high_score_file}): {e}. Will overwrite.")
        data = {"classic": {"high_score": 0, "player": "N/A", "date": ""},
                "timed": {"high_score": 0, "player": "N/A", "date": ""}} # Reset structure
    except Exception as e:
        logger.exception(f"Unexpected error reading high score file: {e}")
        data = {"classic": {"high_score": 0, "player": "N/A", "date": ""},
                "timed": {"high_score": 0, "player": "N/A", "date": ""}} # Reset structure

    # Ensure current game mode structure exists
    if game_mode not in data:
        data[game_mode] = {"high_score": 0, "player": "N/A", "date": ""}
        logger.warning(f"Game mode '{game_mode}' not found in high score data. Initializing.")

    current_saved_high = data.get(game_mode, {}).get("high_score", 0)

    # Check if the current session score beats the saved high score for this mode
    if current_session_score > current_saved_high:
        logger.info(f"New high score for mode '{game_mode}': {current_session_score} by {player_name}")
        data[game_mode]["high_score"] = current_session_score
        data[game_mode]["player"] = player_name
        data[game_mode]["date"] = time.strftime("%Y-%m-%d %H:%M:%S")

        # Also update the game_state's high_score if it's the current mode
        if game_mode == game_state.game_mode:
             game_state.high_score = current_session_score

    else:
        logger.debug(f"Current session score ({current_session_score}) not greater than saved high score ({current_saved_high}) for mode '{game_mode}'. No update needed.")

    # Save the updated data back to the file
    try:
        with open(high_score_file, "w") as f:
            json.dump(data, f, indent=4)
        logger.debug(f"Saved high scores file: {high_score_file}")
    except IOError as e:
        logger.error(f"Failed to save high score file ({high_score_file}): {e}")
    except Exception as e:
         logger.exception(f"Unexpected error writing high score file: {e}")


def check_win_condition(game_state: 'GameState') -> bool:
    """
    Checks if the win condition for the current mode is met.
    Returns True if the game should end due to win condition, False otherwise.
    """
    # Import here to avoid circular dependency at module level if CurrentGameState is in game_state.py
    from game_state import CurrentGameState

    if game_state.win_condition_met: # Already met
        return True

    if game_state.game_mode == "timed":
        # Win if score reaches target OR timer runs out (timer check is handled in main loop usually)
        if game_state.score >= game_state.win_score:
             logger.info(f"Win condition met! Score {game_state.score} >= {game_state.win_score}")
             game_state.win_condition_met = True
             # Transition state (usually handled in the main loop after this check)
             # game_state.current_state = CurrentGameState.GAME_OVER
             return True
    # Add checks for other game modes if necessary
    # elif game_state.game_mode == "classic":
    #     # No score target, maybe win after X balls? Or never wins automatically?
    #     pass

    return False