# game_logic.txt

import pygame
import time
import logging
import os
import json
import numpy as np
from typing import Optional, List, Tuple, Dict, Any, TYPE_CHECKING

# Import constants used by the logic here
from constants import UIConstants, GameConstants, ScoringConstants

# Import utility functions used by the logic here
from game_state_utils import (
    is_ball_at_rest,
    is_ball_zone_stable,
    save_achievements, # Used by check_achievements
    # Other utils might be needed depending on exact implementation details moved
)
from scoring import is_in_scoring_zone # Needed for update_scoring

# Use TYPE_CHECKING to avoid circular import errors with GameState
if TYPE_CHECKING:
    from game_state import GameState, CurrentGameState


logger = logging.getLogger(__name__)

class GameLogicHandler:
    """
    Handles game logic subsystems like scoring, sound playback,
    achievements, and notifications, operating on a GameState instance.
    """
    def __init__(self, game_state: 'GameState'):
        self.game_state: 'GameState' = game_state # Reference to the main state object

    def initialize_and_load_sounds(self):
        """Loads all sound files and assigns them to the GameState."""
        try:
            # Assuming initialize_sounds now returns a dictionary or specific sounds
            # Adjust based on the actual return value of initialize_sounds
            from game_state_utils import initialize_sounds
            sound_results = initialize_sounds()

            # Example: Assign based on a dictionary return
            if isinstance(sound_results, dict):
                 self.game_state.score_sound = sound_results.get('score')
                 self.game_state.background_music = sound_results.get('background')
                 self.game_state.low_time_sound = sound_results.get('low_time')
                 # Achievement sound might be loaded separately or included
                 self.game_state.achievement_sound = sound_results.get('achievement')
                 logger.info("Sounds loaded via dictionary.")
            # Example: Assign based on tuple return (as before)
            elif isinstance(sound_results, tuple) and len(sound_results) >= 3:
                 self.game_state.score_sound = sound_results[0]
                 self.game_state.background_music = sound_results[1]
                 self.game_state.low_time_sound = sound_results[2]
                 # Handle achievement sound if it's part of the tuple or loaded elsewhere
                 self.game_state.achievement_sound = None # Assign if available
                 logger.info("Sounds loaded via tuple.")
            else:
                 raise TypeError("initialize_sounds returned unexpected type or structure.")

            # Ensure flags reflect reality if loading fails partially/fully
            if not any([self.game_state.score_sound, self.game_state.low_time_sound, self.game_state.achievement_sound]):
                 self.game_state.game_sounds_on = False
            if not self.game_state.background_music:
                 self.game_state.background_music_on = False

            # Apply initial volume settings
            self.set_volume()
            # Start background music if enabled and loaded
            if self.game_state.background_music and self.game_state.background_music_on:
                 self.game_state.background_music.play(-1) # Loop indefinitely
                 logger.info("Background music started.")

        except ImportError:
            logger.error("Could not import initialize_sounds. Sounds disabled.")
            self._disable_all_sounds()
        except Exception as e:
            logger.exception(f"Error initializing sounds: {e}. Sounds disabled.")
            self._disable_all_sounds()

    def _disable_all_sounds(self):
        """Helper to set all sound objects to None and flags to False."""
        self.game_state.score_sound = None
        self.game_state.background_music = None
        self.game_state.low_time_sound = None
        self.game_state.achievement_sound = None
        self.game_state.game_sounds_on = False
        self.game_state.background_music_on = False
        logger.warning("All game sounds have been disabled due to an error.")


    def set_volume(self):
        """Sets volume on the GameState's sound objects based on flags."""
        if self.game_state.score_sound:
            self.game_state.score_sound.set_volume(GameConstants.DEFAULT_SOUND_VOLUME if self.game_state.game_sounds_on else 0.0)
        if self.game_state.low_time_sound:
            self.game_state.low_time_sound.set_volume(GameConstants.DEFAULT_SOUND_VOLUME if self.game_state.game_sounds_on else 0.0)
        if self.game_state.achievement_sound:
             self.game_state.achievement_sound.set_volume(GameConstants.DEFAULT_SOUND_VOLUME if self.game_state.game_sounds_on else 0.0)
        if self.game_state.background_music:
             self.game_state.background_music.set_volume(GameConstants.DEFAULT_MUSIC_VOLUME if self.game_state.background_music_on else 0.0)
        # logger.debug(f"Volumes set: Sounds={self.game_state.game_sounds_on}, Music={self.game_state.background_music_on}") # Less noisy log


    def toggle_background_music(self) -> None:
        """Toggles background music playback based on the GameState flag."""
        # Assumes the flag self.game_state.background_music_on has already been flipped by the caller (e.g., menu)
        if self.game_state.background_music:
            if self.game_state.background_music_on:
                self.game_state.background_music.set_volume(GameConstants.DEFAULT_MUSIC_VOLUME)
                self.game_state.background_music.play(-1) # Loop indefinitely
                logger.info("Background music started/resumed.")
            else:
                 # Fading out might be smoother: pygame.mixer.music.fadeout(1000)
                 self.game_state.background_music.set_volume(0.0)
                 self.game_state.background_music.stop() # Stop playback
                 logger.info("Background music stopped.")
        else:
            logger.warning("Cannot toggle: Background music not loaded.")


    def play_sound(self, sound: Optional[pygame.mixer.Sound]) -> None:
        """Plays a specific sound object if sounds are enabled in GameState."""
        if self.game_state.game_sounds_on and sound:
            try:
                # Ensure volume is correct before playing (in case set_volume wasn't called recently)
                sound.set_volume(GameConstants.DEFAULT_SOUND_VOLUME)
                sound.play()
            except pygame.error as e:
                logger.error(f"Sound play error: {e}")
        # Optional: Add debug logs for sounds off or sound is None

    def play_sound_by_type(self, sound_type: str) -> None:
         """Plays a sound based on its type string."""
         sound_to_play = None
         if sound_type == 'score':
              sound_to_play = self.game_state.score_sound
         elif sound_type == 'achievement':
              sound_to_play = self.game_state.achievement_sound
         elif sound_type == 'low_time':
              sound_to_play = self.game_state.low_time_sound
         # Add other sound types as needed
         else:
              logger.warning(f"Unknown sound type requested: {sound_type}")

         if sound_to_play:
              self.play_sound(sound_to_play)
         else:
              logger.debug(f"Sound object for type '{sound_type}' not loaded or found.")


    def update_scoring(self) -> None:
        """Processes tracked balls to determine scores using ZONE-BASED cooldown."""
        gs = self.game_state # Alias for brevity
        newly_scored_pts_this_frame = 0
        current_time = time.time()

        tracked_ids_this_frame = {b[3] for b in gs.tracked_balls if len(b) >= 6}

        # --- Cleanup dictionaries for balls no longer tracked ---
        keys_to_remove = set(gs.ball_states.keys()) - tracked_ids_this_frame
        if keys_to_remove:
             # logger.debug(f"Cleaning up state for untracked ball IDs: {keys_to_remove}")
             dicts_to_clean = [
                  gs.ball_states, gs.previous_ball_states, gs.ball_positions_history,
                  gs.ball_zone_history, gs.balls_in_zone, gs.ball_scored_zones,
                  gs.ball_trails
             ]
             for ball_id in keys_to_remove:
                  for d in dicts_to_clean:
                       d.pop(ball_id, None)
        # --- End Cleanup ---

        for ball in gs.tracked_balls:
            # Simplified: assumes ball format is correct after tracker
            x, y, r, ball_id, age, b_type = ball
            center = (int(x), int(y))

            # Update position history (managed in GameState)
            if ball_id not in gs.ball_positions_history:
                gs.ball_positions_history[ball_id] = []
            gs.ball_positions_history[ball_id].append(center)
            if len(gs.ball_positions_history[ball_id]) > GameConstants.POSITION_HISTORY_LENGTH:
                gs.ball_positions_history[ball_id].pop(0)

            # Find current zone
            zone, zone_idx = None, -1
            for i, z in enumerate(gs.scoring_zones):
                if is_in_scoring_zone((x, y, r, ball_id), z):
                    zone, zone_idx = z, i
                    break

            # Calculate Ball State (using utils, passing necessary state)
            rest = is_ball_at_rest(ball_id, gs.ball_positions_history, gs.debug_mode)
            stable = is_ball_zone_stable(ball_id, zone, gs.ball_zone_history, gs.debug_mode) # Pass gs.ball_zone_history

            # Update ball state dictionary (managed in GameState)
            gs.previous_ball_states[ball_id] = gs.ball_states.get(ball_id, {}).copy()
            gs.ball_states[ball_id] = {"at_rest": rest, "stable": stable, "zone": zone, "idx": zone_idx, "time": current_time}

            # Update ball zone history (managed in GameState)
            if ball_id not in gs.ball_zone_history:
                 gs.ball_zone_history[ball_id] = []
            # Add current zone index (or None)
            gs.ball_zone_history[ball_id].append(zone_idx if zone else None)
            # Limit history
            if len(gs.ball_zone_history[ball_id]) > GameConstants.STABILITY_FRAME_COUNT:
                 gs.ball_zone_history[ball_id].pop(0)


            # --- Scoring Logic ---
            if zone and stable:
                zone_cooldown_time = gs.zone_cooldown.get(zone_idx, 0)
                if current_time >= zone_cooldown_time:
                    if gs.ball_scored_zones.get(ball_id) != zone_idx: # Check if already scored in this zone entry

                        _, _, _, _, base_pts = zone
                        is_sp = (zone == gs.special_hole)

                        current_score_pts = 100 if is_sp else base_pts
                        if is_sp and not gs.special_hole_hit_this_session:
                             logger.info("*** First Special Hole hit this session! Score doubles. ***")
                             self.show_notification("Special Hole! Score x2!", 3.0)
                        if is_sp: # Set flag on any special hole hit
                             gs.special_hole_hit_this_session = True

                        score_multiplier = {"red": 2.0, "half": 1.5}.get(b_type, 1.0)
                        points_to_add = int(current_score_pts * score_multiplier)

                        # Update scores in GameState
                        gs.score += points_to_add
                        gs.get_current_player().add_score(points_to_add)
                        newly_scored_pts_this_frame += points_to_add

                        # Update tracking states in GameState
                        gs.balls_in_zone[ball_id] = zone
                        gs.ball_scored_zones[ball_id] = zone_idx

                        # Set ZONE cooldown in GameState
                        cooldown_duration = GameConstants.SCORE_COOLDOWN_DURATION / 1000.0
                        gs.zone_cooldown[zone_idx] = current_time + cooldown_duration

                        logger.info(f"Ball {ball_id}({b_type}) scored {points_to_add}pts in Zone:{zone_idx}{' (SP)' if is_sp else ''}. Total:{gs.score}. Cooldown: {cooldown_duration:.1f}s.")

                        # Check win condition (accessing GameState state)
                        # Make sure CurrentGameState is accessible or passed if needed
                        from game_state import CurrentGameState # Local import if needed
                        if (
                             gs.game_mode == "timed"
                             and gs.score >= gs.win_score
                             and gs.current_state != CurrentGameState.GAME_OVER
                         ):
                             gs.win_condition_met = True
                             gs.current_state = CurrentGameState.GAME_OVER
                             logger.info(f"Win condition met! Score {gs.score} >= {gs.win_score}")
                             # Save score immediately (calls method below)
                             self.save_score(gs.get_current_player().name, gs.game_mode)


            # Logic for when ball leaves a zone it previously scored in
            elif ball_id in gs.ball_scored_zones:
                 last_scored_zone_idx = gs.ball_scored_zones[ball_id]
                 if not stable or zone_idx != last_scored_zone_idx:
                      del gs.ball_scored_zones[ball_id]
                      gs.balls_in_zone.pop(ball_id, None)
                      # logger.debug(f"Ball {ball_id} left zone {last_scored_zone_idx}. Cleared scored status.")


        if newly_scored_pts_this_frame > 0:
            self.play_sound(gs.score_sound)


    def save_score(self, player_name: str, mode: Optional[str] = None) -> None:
        """Handles final score processing: doubling, leaderboard, high score file."""
        gs = self.game_state
        final_score = gs.score # Score at time of call
        doubled = False

        if gs.special_hole_hit_this_session:
            logger.info(f"Doubling final score {final_score} for {player_name} due to special hole hit.")
            final_score *= 2
            doubled = True

        current_mode = mode or gs.game_mode
        score_to_save = final_score # Use potentially doubled score

        if score_to_save > 0:
            logger.info(f"Saving score for {player_name}: {score_to_save} (Mode: {current_mode}){' (Doubled)' if doubled else ''}")

            # Submit to Leaderboard (accessing GameState's leaderboard object)
            if hasattr(gs, 'leaderboard') and gs.leaderboard:
                 gs.leaderboard.submit_score(player_name, score_to_save, current_mode)
            else:
                 logger.error("Leaderboard object not available. Cannot submit score online.")

            # Trigger high score file save (which checks against this final score)
            # Pass the final score for checking, although _save_high_score accesses gs.score directly.
            # This ensures the check uses the potentially doubled score logic.
            # Correction: _save_high_score now checks gs.score and gs.special_hole_hit_this_session itself.
            gs._save_high_score()

        else:
            logger.info(f"Final score is {score_to_save}, not saving to leaderboard or high score file.")


    def check_achievements(self) -> None:
        """Checks achievements based on GameState and updates status."""
        gs = self.game_state
        if not hasattr(gs, 'achievements'): return
        newly_unlocked = False
        for ach in gs.achievements:
            # Check condition only if not already unlocked
            # The ach.check function needs the GameState instance
            if not ach.unlocked and ach.check(gs):
                ach.unlocked = True
                logger.info(f"Achieved: {ach.name} - {ach.description}")
                self.show_notification(f"Unlocked: {ach.name}", duration=5.0)
                self.play_sound(gs.achievement_sound)
                newly_unlocked = True

        if newly_unlocked:
            # Save updated achievement status
            save_achievements(gs, GameConstants.ACHIEVEMENTS_FILE)


    def update_achievement_notification(self, dt: float) -> None:
        """Updates timer for achievement popup in GameState."""
        if self.game_state.achievement_notification_timer > 0:
            self.game_state.achievement_notification_timer -= dt
            if self.game_state.achievement_notification_timer <= 0:
                self.game_state.achievement_notification = None


    def show_notification(
        self, text: str, duration: float = 2.0, is_error: bool = False
    ) -> None:
        """Displays a notification message by setting GameState variables."""
        gs = self.game_state
        gs.notification_text = text
        gs.notification_timer = duration
        gs.notification_color = UIConstants.RED if is_error else UIConstants.GREEN
        log_level = logging.WARNING if is_error else logging.INFO
        logger.log(log_level, f"Notify: {text}")


    def update_notifications(self, dt: float) -> None:
        """Updates the general notification timer in GameState."""
        if self.game_state.notification_timer > 0:
            self.game_state.notification_timer -= dt
            if self.game_state.notification_timer <= 0:
                self.game_state.notification_text = None

    def reset_notifications(self):
         """Clears active notifications."""
         self.game_state.notification_text = None
         self.game_state.notification_timer = 0.0
         self.game_state.achievement_notification = None
         self.game_state.achievement_notification_timer = 0.0
         logger.debug("Notifications reset.")