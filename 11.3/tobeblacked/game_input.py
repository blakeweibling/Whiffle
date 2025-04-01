# game_input.py
import cv2
import logging
import string
from typing import Optional, Any
import pygame # Keep for constants like K_RETURN etc. used in menu/game over logic

# Import constants, utils, and specific game states/functions
from constants import UIConstants, GameConstants, ScoringConstants, PlayerConstants
# Import clean_exit from the correct location
from cleanup_utils import clean_exit
from game_state import CurrentGameState
from menu import reset_game # Required for 'n' key in GAME_OVER

logger = logging.getLogger(__name__)

def _handle_input(game_state: Any) -> Optional[int]:
    """Handles keyboard input using cv2.waitKey."""
    raw_key = -1 # Store raw value before mask
    key = -1
    try:
        # Check if the window is still valid before calling waitKey
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 1:
            raw_key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY)
            key = raw_key & 0xFF # Apply mask for standard ASCII checks
        else:
            logger.debug("Skipping waitKey, window seems closed or closing.")
            return key # Return -1 if window closed

    except cv2.error as e:
        logger.warning(f"cv2.error during waitKey or getWindowProperty (window likely closed): {e}")
        return -1 # Return -1 on error

    key_handled = False # Flag to check if input was processed in a specific context

    # --- Handle Truly Global Quit Key First (using masked key) ---
    if key == ord('q'):
        logger.info("Quit key ('q') pressed.")
        # Call clean_exit from cleanup_utils
        clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
        return None # Signal immediate exit

    # --- State-Specific Input Handling ---
    # Use 4 spaces for this level
    if key != -1 and key != 255:

        # --- Handle input for GETTING_PLAYER_NAME state ---
        # Use 8 spaces for this level
        if game_state.current_state == CurrentGameState.GETTING_PLAYER_NAME:
            # Use 12 spaces for this level
            if key == 13: # Enter Key
                logger.debug("Enter key (13) detected during initial name input.")
                entered_name = game_state.current_player_name_input.strip()
                if not entered_name:
                    # Use 16 spaces for this level
                    game_state.show_notification("Player name cannot be empty!", is_error=True, duration=2.0)
                else:
                    try:
                        # Use 20 spaces for this level
                        if game_state.players:
                            # Use 24 spaces for this level
                            game_state.players[0].name = entered_name
                            logger.info(f"Player 1 name set to: '{entered_name}'")
                            game_state.show_notification(f"Welcome, {entered_name}!", duration=2.0)
                            game_state.player_name_input_active = False
                            game_state.current_state = CurrentGameState.PLAYING
                            if game_state.background_music_on and game_state.background_music:
                                # Use 28 spaces for this level
                                game_state.background_music.play(-1)
                                logger.info("Background music started.")
                        else:
                            logger.error("Cannot set name: players list is empty or None.")
                            game_state.show_notification("Error: Player list missing!", is_error=True)
                    except Exception as e:
                        logger.exception(f"Error setting player name or changing state: {e}")
                        game_state.show_notification("Error starting game!", is_error=True)
                key_handled = True
            elif key == 27: # Escape Key
                logger.debug("Escape key (27) detected during initial name input.")
                logger.info("Using default name 'Player 1'.")
                if game_state.players:
                    game_state.players[0].name = "Player 1"
                    game_state.player_name_input_active = False
                    game_state.current_state = CurrentGameState.PLAYING
                    game_state.show_notification("Using default name 'Player 1'", duration=2.0)
                    if game_state.background_music_on and game_state.background_music:
                        game_state.background_music.play(-1)
                        logger.info("Background music started.")
                else:
                     logger.error("Cannot set default name: players list is empty or None.")
                     game_state.show_notification("Error: Player list missing!", is_error=True)
                key_handled = True
            elif key == 8: # Backspace Key
                logger.debug("Backspace key (8) detected during initial name input.")
                if game_state.current_player_name_input:
                    game_state.current_player_name_input = game_state.current_player_name_input[:-1]
                    logger.debug(f"Name input buffer: {game_state.current_player_name_input}")
                key_handled = True
            elif key >= 32 and key <= 126: # Printable characters
                char = chr(key)
                if char in PlayerConstants.ALLOWED_PLAYER_NAME_CHARS:
                    if len(game_state.current_player_name_input) < PlayerConstants.MAX_PLAYER_NAME_LENGTH:
                        game_state.current_player_name_input += char
                        logger.debug(f"Name input buffer: {game_state.current_player_name_input}")
                    else:
                        game_state.show_notification(f"Max name length ({PlayerConstants.MAX_PLAYER_NAME_LENGTH}) reached", is_error=True, duration=1.5)
                    key_handled = True
                else:
                    logger.debug(f"Character '{char}' not allowed for player name.")
                    game_state.show_notification(f"Character '{char}' not allowed", is_error=True, duration=1.5)
                key_handled = True

        # --- Handle input for MENU state ---
        # Use 8 spaces for this level
        elif game_state.current_state == CurrentGameState.MENU:
            menu_key_handled = False # Flag specific to menu actions

            # --- Player Name Editing Logic ---
            # Use 12 spaces for this level
            if game_state.submenu_active == "players" and game_state.editing_player_mode == "edit_name" and game_state.editing_player_index is not None:
                # Use 16 spaces for this level
                player_idx = game_state.editing_player_index
                if key == 13: # Enter Key - Save Name
                    # Use 20 spaces for this level
                    logger.debug("Enter key (13) detected during menu player name edit.")
                    new_name = game_state.editing_player_name_input.strip()
                    if not new_name:
                        game_state.show_notification("Player name cannot be empty!", is_error=True, duration=2.0)
                    elif 0 <= player_idx < len(game_state.players):
                        old_name = game_state.players[player_idx].name
                        game_state.players[player_idx].name = new_name
                        logger.info(f"Player {player_idx + 1} name changed from '{old_name}' to '{new_name}'")
                        game_state.show_notification(f"Player {player_idx + 1} name updated", duration=2.0)
                        game_state.editing_player_index = None
                        game_state.editing_player_mode = None
                        game_state.editing_player_name_input = None
                        game_state.menu_cache = None
                    else:
                        logger.error(f"Invalid player index {player_idx} during name save.")
                        game_state.show_notification("Error saving name!", is_error=True)
                        game_state.editing_player_index = None
                        game_state.editing_player_mode = None
                        game_state.editing_player_name_input = None
                        game_state.menu_cache = None
                    menu_key_handled = True
                elif key == 27: # Escape Key - Cancel Edit
                    logger.debug("Escape key (27) detected during menu player name edit.")
                    game_state.editing_player_index = None
                    game_state.editing_player_mode = None
                    game_state.editing_player_name_input = None
                    game_state.menu_cache = None
                    game_state.show_notification("Name edit cancelled", duration=1.5)
                    menu_key_handled = True
                elif key == 8: # Backspace Key
                    logger.debug("Backspace key (8) detected during menu player name edit.")
                    if game_state.editing_player_name_input:
                        game_state.editing_player_name_input = game_state.editing_player_name_input[:-1]
                        game_state.menu_cache = None
                    menu_key_handled = True
                elif key >= 32 and key <= 126: # Printable characters
                    char = chr(key)
                    if char in PlayerConstants.ALLOWED_PLAYER_NAME_CHARS:
                        if len(game_state.editing_player_name_input) < PlayerConstants.MAX_PLAYER_NAME_LENGTH:
                             game_state.editing_player_name_input += char
                             game_state.menu_cache = None
                        else:
                              game_state.show_notification(f"Max {PlayerConstants.MAX_PLAYER_NAME_LENGTH} chars", is_error=True, duration=1.5)
                        menu_key_handled = True
                    else:
                        logger.debug(f"Character '{char}' not allowed for player name.")
                        game_state.show_notification(f"Character '{char}' not allowed", is_error=True, duration=1.5)
                    menu_key_handled = True

                if menu_key_handled:
                    key_handled = True

            # --- Zone Points Editing Logic ---
            # Use 12 spaces for this level
            elif game_state.submenu_active == "edit_zones" and game_state.editing_zone_mode == "edit_points" and game_state.editing_zone_index is not None:
                # Use 16 spaces for this level
                zone_idx = game_state.editing_zone_index
                if key == 13: # Enter Key - Save Points
                    # Use 20 spaces for this level
                    logger.debug("Enter key (13) detected during menu zone points edit.")
                    try:
                        # Use 24 spaces for this level
                        new_points_str = game_state.editing_zone_points_input.strip()
                        if not new_points_str:
                            game_state.show_notification("Points cannot be empty!", is_error=True)
                        else:
                            new_points = int(new_points_str)
                            if not (1 <= new_points <= ScoringConstants.MAX_POINTS):
                                game_state.show_notification(f"Points must be 1-{ScoringConstants.MAX_POINTS}", is_error=True)
                            elif 0 <= zone_idx < len(game_state.scoring_zones):
                                x, y, w, h, _ = game_state.scoring_zones[zone_idx]
                                game_state.scoring_zones[zone_idx] = (x, y, w, h, new_points)
                                logger.info(f"Zone {zone_idx + 1} points updated to {new_points}")
                                game_state.show_notification(f"Zone {zone_idx + 1} points updated", duration=2.0)
                                game_state.editing_zone_index = None
                                game_state.editing_zone_mode = None
                                game_state.editing_zone_points_input = None
                                game_state.menu_cache = None
                            else:
                                logger.error(f"Invalid zone index {zone_idx} during points save.")
                                game_state.show_notification("Error saving points!", is_error=True)
                                game_state.editing_zone_index = None
                                game_state.editing_zone_mode = None
                                game_state.editing_zone_points_input = None
                                game_state.menu_cache = None
                    except ValueError:
                        game_state.show_notification("Invalid points value!", is_error=True)
                    except Exception as e:
                        logger.exception(f"Error saving zone points: {e}")
                        game_state.show_notification("Error saving points!", is_error=True)
                        game_state.editing_zone_index = None
                        game_state.editing_zone_mode = None
                        game_state.editing_zone_points_input = None
                        game_state.menu_cache = None
                    menu_key_handled = True # 20 spaces indent
                elif key == 27: # Escape Key - Cancel Edit
                    # Use 20 spaces for this level
                    logger.debug("Escape key (27) detected during menu zone points edit.")
                    game_state.editing_zone_index = None
                    game_state.editing_zone_mode = None
                    game_state.editing_zone_points_input = None
                    game_state.menu_cache = None
                    game_state.show_notification("Points edit cancelled", duration=1.5)
                    menu_key_handled = True # 20 spaces indent
                elif key == 8: # Backspace Key
                    # Use 20 spaces for this level
                    logger.debug("Backspace key (8) detected during menu zone points edit.")
                    if game_state.editing_zone_points_input:
                        # Use 24 spaces for this level
                        game_state.editing_zone_points_input = game_state.editing_zone_points_input[:-1]
                        game_state.menu_cache = None
                    menu_key_handled = True # 20 spaces indent
                elif ord('0') <= key <= ord('9'): # Numeric input
                    # Use 20 spaces for this level
                    logger.debug(f"Numeric key {key} detected during points edit.")
                    char = chr(key)
                    if game_state.editing_zone_points_input is None:
                        # Use 24 spaces for this level
                        game_state.editing_zone_points_input = ""
                    if len(game_state.editing_zone_points_input) < 4:
                        game_state.editing_zone_points_input += char
                        game_state.menu_cache = None
                    else:
                        game_state.show_notification(f"Max points {ScoringConstants.MAX_POINTS}", is_error=True, duration=1.5)
                    menu_key_handled = True # 20 spaces indent <<< Line 157 should be this one

                # Use 16 spaces for this level
                if menu_key_handled:
                    # Use 20 spaces for this level
                    key_handled = True

            # --- General Menu Navigation ---
            # Use 12 spaces for this level
            if not key_handled:
                # Use 16 spaces for this level
                if key == ord('m'): # Toggle menu OFF (Resume)
                    logger.debug("Menu key ('m') pressed in menu, resuming game.")
                    game_state.current_state = CurrentGameState.PLAYING
                    game_state.editing_player_index = None
                    game_state.editing_player_mode = None
                    game_state.editing_player_name_input = None
                    game_state.editing_zone_index = None
                    game_state.editing_zone_mode = None
                    game_state.editing_zone_points_input = None
                    game_state.submenu_active = None
                    game_state.menu_cache = None
                    key_handled = True
                elif key == 8: # Backspace Key - Go Back or Close Menu
                    logger.debug("Backspace key (8) detected for menu navigation.")
                    if game_state.submenu_active == "edit_zones":
                        # Use 20 spaces for this level
                        game_state.submenu_active = "manage_zones"
                        game_state.editing_zone_index = None
                        game_state.editing_zone_mode = None
                        game_state.editing_zone_points_input = None
                        game_state.menu_cache = None
                        key_handled = True
                    elif game_state.submenu_active:
                        game_state.submenu_active = None
                        game_state.editing_player_index = None
                        game_state.editing_player_mode = None
                        game_state.editing_player_name_input = None
                        game_state.editing_zone_index = None
                        game_state.editing_zone_mode = None
                        game_state.editing_zone_points_input = None
                        game_state.menu_cache = None
                        key_handled = True
                    else: # If already on main menu, close it
                        game_state.current_state = CurrentGameState.PLAYING
                        game_state.editing_player_index = None
                        game_state.editing_player_mode = None
                        game_state.editing_player_name_input = None
                        game_state.editing_zone_index = None
                        game_state.editing_zone_mode = None
                        game_state.editing_zone_points_input = None
                        game_state.submenu_active = None
                        game_state.menu_cache = None
                        key_handled = True
                elif key == 27: # Escape Key - Close Menu
                     logger.debug("Escape key (27) detected in menu, resuming game.")
                     game_state.current_state = CurrentGameState.PLAYING
                     game_state.editing_player_index = None
                     game_state.editing_player_mode = None
                     game_state.editing_player_name_input = None
                     game_state.editing_zone_index = None
                     game_state.editing_zone_mode = None
                     game_state.editing_zone_points_input = None
                     game_state.submenu_active = None
                     game_state.menu_cache = None
                     key_handled = True

        # --- Handle input for PLAYING state ---
        # Use 8 spaces for this level
        elif game_state.current_state == CurrentGameState.PLAYING:
            # Use 12 spaces for this level
            if key == ord('m'): # Toggle menu ON
                logger.info("Menu key ('m') pressed while playing.")
                game_state.current_state = CurrentGameState.MENU
                game_state.submenu_active = None
                game_state.menu_cache = None
                game_state.editing_zone_index = None
                game_state.editing_zone_mode = None
                game_state.editing_zone_points_input = None
                game_state.editing_player_index = None
                game_state.editing_player_mode = None
                game_state.editing_player_name_input = None
                key_handled = True
            elif key == ord('s'): # Toggle drawing mode
                game_state.drawing = not game_state.drawing
                if game_state.drawing:
                    logger.info("Drawing mode enabled. Click and drag to draw zone.")
                    game_state.show_notification("Drawing Mode: ON")
                    game_state.start_x = None
                    game_state.start_y = None
                    game_state.temp_zone = None
                else:
                    logger.info("Drawing mode disabled.")
                    game_state.show_notification("Drawing Mode: OFF")
                    game_state.temp_zone = None
                    game_state.start_x = None
                    game_state.start_y = None
                key_handled = True
            elif key == ord('p'): # Pause game
                logger.info("Pause key ('p') pressed.")
                game_state.current_state = CurrentGameState.PAUSED
                game_state.show_notification("Game Paused", duration=0)
                key_handled = True
            elif key == 27: # ESC quits immediately
                logger.info("Escape key (27) pressed while playing, exiting.")
                clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
                return None

        # --- Handle input for PAUSED state ---
        # Use 8 spaces for this level
        elif game_state.current_state == CurrentGameState.PAUSED:
            # Use 12 spaces for this level
            if key == ord('p'): # Resume game
                logger.info("Resume key ('p') pressed.")
                game_state.current_state = CurrentGameState.PLAYING
                game_state.show_notification("Resuming...", duration=1.0)
                key_handled = True
            elif key == 27: # ESC quits immediately
                logger.info("Escape key (27) pressed while paused, exiting.")
                clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
                return None

        # --- Handle input for GAME_OVER state ---
        # Use 8 spaces for this level
        elif game_state.current_state == CurrentGameState.GAME_OVER:
            # Use 12 spaces for this level
            if key == ord('n'): # Start New Game
                logger.info("'n' key pressed on game over screen. Starting new game.")
                reset_game(game_state)
                game_state.current_state = CurrentGameState.GETTING_PLAYER_NAME
                game_state.win_condition_met = False
                key_handled = True
            elif key == ord('l'): # Show Leaderboard
                logger.info("'l' key pressed on game over screen. Showing leaderboard.")
                game_state.current_state = CurrentGameState.MENU
                game_state.submenu_active = "leaderboard"
                game_state.menu_cache = None
                game_state.win_condition_met = False
                key_handled = True
            elif key == 27: # ESC quits immediately
                logger.info("Escape key (27) pressed on game over screen, exiting.")
                clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
                return None

        # --- Global Toggles ---
        # Use 8 spaces for this level
        if not key_handled:
            # Use 12 spaces for this level
            if key == ord('d'):
                game_state.debug_mode = not game_state.debug_mode
                log_level = logging.DEBUG if game_state.debug_mode else logging.INFO
                logging.getLogger().setLevel(log_level)
                for handler in logging.getLogger().handlers:
                    handler.setLevel(log_level)
                logger.info(f"General Debug Mode toggled {'ON' if game_state.debug_mode else 'OFF'}")
                game_state.show_notification(f"Debug Mode: {'ON' if game_state.debug_mode else 'OFF'}")
                key_handled = True
            elif key == ord('b'):
                game_state.show_debug_overlay = not game_state.show_debug_overlay
                logger.info(f"Visual Debug Overlay toggled {'ON' if game_state.show_debug_overlay else 'OFF'}")
                game_state.show_notification(f"Debug Overlay: {'ON' if game_state.show_debug_overlay else 'OFF'}")
                key_handled = True

    # Return the masked key code, or None if quit was triggered
    # Use 4 spaces for this level
    return key