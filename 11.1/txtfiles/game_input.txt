import cv2
import logging
import string
from typing import Optional, Any
import pygame # Keep for constants like K_RETURN etc. used in menu/game over logic

# Import constants, utils, and specific game states/functions
from constants import UIConstants, GameConstants, ScoringConstants, PlayerConstants
from utils import clean_exit
from game_state import CurrentGameState
from menu import reset_game # Required for 'n' key in GAME_OVER

logger = logging.getLogger(__name__)

def _handle_input(game_state: Any) -> Optional[int]:
    """Handles keyboard input using cv2.waitKey."""
    raw_key = -1 # Store raw value before mask
    key = -1
    try:
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_AUTOSIZE) != -1:
            # Get the raw key code from waitKey
            raw_key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY)
            key = raw_key & 0xFF # Apply mask for standard ASCII checks

            # --- VERY BASIC DEBUG PRINT ---
            if raw_key != -1: # Print any key press detected
                 # Use print directly to ensure it appears on console even if logging is redirected
                 print(f"RAW waitKey returned: {raw_key}, Masked (key): {key}")
            # --- END DEBUG PRINT ---

        else:
            logger.debug("Skipping waitKey, window seems closed.")
            return None

    except cv2.error as e:
        logger.warning(f"cv2.error during waitKey: {e}")
        clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
        return None

    key_handled = False
    # Quit requested flag removed, just return None on quit

    # --- Handle Truly Global Keys First (using masked key) ---
    if key == ord('q'):
        logger.info("Quit key ('q') pressed.")
        clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state)
        return None # Signal immediate exit
    elif key == ord('d'):
        if game_state.current_state != CurrentGameState.SHOWING_SPLASH:
             game_state.debug_mode = not game_state.debug_mode
             logger.info(f"Debug toggled {'ON' if game_state.debug_mode else 'OFF'}")
             key_handled = True
    elif key == ord('b'):
        if game_state.current_state != CurrentGameState.SHOWING_SPLASH:
            game_state.show_debug_overlay = not game_state.show_debug_overlay
            logger.info(f"Overlay toggled {'ON' if game_state.show_debug_overlay else 'OFF'}")
            key_handled = True

    # --- State-Specific Input Handling (Only if key wasn't handled globally) ---
    if not key_handled:
        # --- Handle input for GETTING_PLAYER_NAME state ---
        if game_state.current_state == CurrentGameState.GETTING_PLAYER_NAME:
            # Check special keys using MASKED value (common standard codes)
            # Check for Enter (13)
            if key == 13:
                logger.debug("Enter key (13) detected.")
                entered_name = game_state.current_player_name_input.strip()
                if not entered_name:
                    game_state.show_notification("Player name cannot be empty!", is_error=True, duration=2.0)
                else:
                    try:
                        if game_state.players: game_state.players[0].name = entered_name
                        else: logger.error("No players list found"); raise ValueError("No player list")
                        logger.info(f"Player 1 name set: '{entered_name}'"); game_state.show_notification(f"Welcome, {entered_name}!", duration=2.0)
                        game_state.player_name_input_active = False; game_state.current_state = CurrentGameState.PLAYING
                        if game_state.background_music_on and game_state.background_music: game_state.background_music.play(-1); logger.info("BG music started.")
                    except Exception as e: logger.exception(f"Error setting name/state: {e}"); game_state.show_notification("Error starting!", is_error=True)
                key_handled = True

            # Check for Escape (27)
            elif key == 27:
                 logger.debug("Escape key (27) detected.")
                 logger.info("ESC during name input. Using default 'Player 1'.")
                 game_state.player_name_input_active = False; game_state.current_state = CurrentGameState.PLAYING
                 game_state.show_notification("Using default name 'Player 1'", duration=2.0)
                 if game_state.background_music_on and game_state.background_music: game_state.background_music.play(-1); logger.info("BG music started.")
                 key_handled = True

            # Check for Backspace (8)
            elif key == 8:
                logger.debug("Backspace key (8) detected.")
                if game_state.current_player_name_input:
                    game_state.current_player_name_input = game_state.current_player_name_input[:-1]
                    logger.debug(f"Name input after backspace: {game_state.current_player_name_input}")
                key_handled = True

            # Check for allowed printable characters (using masked key)
            elif key >= 32 and key <= 126: # Range for printable ASCII
                char = chr(key)
                if char in PlayerConstants.ALLOWED_PLAYER_NAME_CHARS:
                    if len(game_state.current_player_name_input) < PlayerConstants.MAX_PLAYER_NAME_LENGTH:
                        game_state.current_player_name_input += char
                        logger.debug(f"Name input: {game_state.current_player_name_input}")
                    else: game_state.show_notification(f"Max {PlayerConstants.MAX_PLAYER_NAME_LENGTH} chars", is_error=True, duration=1.5)
                    key_handled = True
                # else: logger.debug(f"Printable key '{char}' not allowed.") # Optional log

        # --- Other state handling (MENU, PLAYING, etc.) using masked key ---
        elif game_state.current_state == CurrentGameState.SHOWING_SPLASH:
             if key != 255 and key != -1:
                 logger.info("Key during splash, return."); game_state.current_state = game_state.previous_state or CurrentGameState.MENU
                 game_state.previous_state = None; game_state.menu_cache = None

        elif game_state.current_state == CurrentGameState.MENU:
            menu_key_handled = False
            # (Keeping menu logic brief for clarity - use previous full version)
            if (game_state.submenu_active == "edit_zones" and game_state.editing_zone_mode == "edit_points") or \
               (game_state.submenu_active == "players" and game_state.editing_player_mode == "edit_name"):
                 # Delegate to specific editor logic (using key, backspace, enter, esc)
                 # ... see previous versions for full menu editing logic ...
                 # Remember to set menu_key_handled = True if processed
                 pass # Placeholder for brevity
            elif not menu_key_handled: # General menu nav
                if key == ord('m'): menu_key_handled = True # resume
                elif key == 8: menu_key_handled = True # backspace nav
                elif key == 27: menu_key_handled = True # escape nav
            if menu_key_handled: key_handled = True


        elif game_state.current_state == CurrentGameState.PLAYING:
            if key == ord('m'): key_handled = True # menu
            elif key == ord('s'): key_handled = True # draw toggle
            elif key == ord('p'): key_handled = True # pause
            elif key == 27: # ESC quits
                logger.info("ESC playing, exiting."); clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state); return None

        elif game_state.current_state == CurrentGameState.PAUSED:
            if key == ord('p'): key_handled = True # resume
            elif key == 27: # ESC quits
                logger.info("ESC paused, exiting."); clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state); return None

        elif game_state.current_state == CurrentGameState.GAME_OVER:
            if key == ord('n'): key_handled = True # new game
            elif key == ord('l'): key_handled = True # leaderboard
            elif key == 27: # ESC quits
                logger.info("ESC game over, exiting."); clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state); return None


    # Fallback logging
    # if not key_handled and key != -1 and key != 255:
    #      logger.debug(f"Key {key} unhandled in state {game_state.current_state}")

    # Return the masked key code, or None if quit was triggered
    return key # Return the masked key, main loop handles None return from error/q