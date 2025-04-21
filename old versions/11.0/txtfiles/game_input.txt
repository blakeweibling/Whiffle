import cv2
import logging
import string  # Needed for allowed_name_chars
from typing import Optional, Any

# Import constants, utils, and specific game states/functions needed for input handling
from constants import UIConstants, GameConstants, ScoringConstants
from utils import clean_exit
from game_state import CurrentGameState
from menu import reset_game  # Required for 'n' key in GAME_OVER

logger = logging.getLogger(__name__)


def _handle_input(game_state: Any) -> Optional[int]:
    """Handles keyboard input."""
    key = -1  # Default to -1 if window closed
    try:
        # Check if window exists before waitKey
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_AUTOSIZE) != -1:
            key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY) & 0xFF
        else:
            logger.debug("Skipping waitKey, window seems closed.")
            return None  # Signal exit if window is closed before waitKey

    except cv2.error as e:
        logger.warning(
            f"cv2.error during waitKey (Window '{UIConstants.WINDOW_NAME}' may already be destroyed): {e}"
        )
        # If waitKey fails, likely window is closed, signal exit
        clean_exit(
            game_state.cap,
            game_state.background_music,
            game_state.background_music_on,
            game_state,
        )
        return None

    key_handled = False
    # Define allowed characters for player names (alphanumeric + space)
    allowed_name_chars = string.ascii_letters + string.digits + " "
    max_name_length = 15  # Max length for player name

    # --- Quit Key ('q') ---
    if key == ord("q"):
        logger.info("Quit key ('q') pressed.")
        clean_exit(
            game_state.cap,
            game_state.background_music,
            game_state.background_music_on,
            game_state,
        )
        return None  # Signal exit

    # --- State-Specific Input Handling ---

    # Handle input for SHOWING_SPLASH state
    if game_state.current_state == CurrentGameState.SHOWING_SPLASH:
        if key != 255 and key != -1:  # Any key press
            logger.info(
                "Key press detected during splash, returning to previous state."
            )
            if game_state.previous_state:
                game_state.current_state = game_state.previous_state
            else:
                game_state.current_state = CurrentGameState.MENU
                logger.warning("Previous state was None...")
            game_state.previous_state = None
            game_state.menu_cache = None
            key_handled = True

    # Handle input for MENU state
    elif game_state.current_state == CurrentGameState.MENU:
        # Priority for Zone Point Editing Input
        if (
            game_state.submenu_active == "edit_zones"
            and game_state.editing_zone_mode == "edit_points"
            and game_state.editing_zone_index is not None
        ):
            if ord("0") <= key <= ord("9"):
                current_input = game_state.editing_zone_points_input or ""
                if len(current_input) < 3:
                    game_state.editing_zone_points_input = current_input + \
                        chr(key)
                    game_state.menu_cache = None
                    logger.debug(
                        f"Edit points input: {game_state.editing_zone_points_input}"
                    )
                else:
                    game_state.show_notification(
                        "Max 3 digits allowed", is_error=True, duration=1.5
                    )
                key_handled = True
            elif key == 8:  # Backspace
                current_input = game_state.editing_zone_points_input or ""
                if current_input:
                    game_state.editing_zone_points_input = current_input[:-1]
                    game_state.menu_cache = None
                    logger.debug(
                        f"Edit points input after backspace: {game_state.editing_zone_points_input}"
                    )
                key_handled = True
            elif key == 13:  # Enter
                input_str = game_state.editing_zone_points_input
                valid_points = False
                new_points = 0
                if input_str and input_str.isdigit():
                    try:
                        new_points = int(input_str)
                        if 1 <= new_points <= ScoringConstants.MAX_POINTS:
                            valid_points = True
                        else:
                            logger.warning(
                                f"Entered points {new_points} out of range (1-{ScoringConstants.MAX_POINTS})"
                            )
                    except ValueError:
                        logger.error(
                            f"Could not convert input '{input_str}' to integer."
                        )
                if valid_points:
                    try:
                        zone_idx = game_state.editing_zone_index
                        zone_data = game_state.scoring_zones[zone_idx]
                        updated_zone = (
                            zone_data[0],
                            zone_data[1],
                            zone_data[2],
                            zone_data[3],
                            new_points,
                        )
                        game_state.scoring_zones[zone_idx] = updated_zone
                        logger.info(
                            f"Updated Zone {zone_idx + 1} points to {new_points}"
                        )
                        game_state.show_notification(
                            f"Zone {zone_idx + 1} points set to {new_points}"
                        )
                        game_state.editing_zone_points_input = None
                        game_state.editing_zone_index = None
                        game_state.editing_zone_mode = None
                        game_state.menu_cache = None
                    except IndexError:
                        logger.error(
                            f"Error accessing scoring_zones index {zone_idx} during point update."
                        )
                        game_state.show_notification(
                            "Error updating points!", is_error=True
                        )
                        game_state.editing_zone_points_input = None
                        game_state.editing_zone_index = None
                        game_state.editing_zone_mode = None
                        game_state.menu_cache = None
                else:
                    game_state.show_notification(
                        f"Invalid points: Enter 1-{ScoringConstants.MAX_POINTS}",
                        is_error=True,
                    )
                key_handled = True
            elif key == 27:  # ESC cancels editing
                logger.info("ESC pressed during point edit, cancelling edit.")
                game_state.editing_zone_points_input = None
                game_state.editing_zone_index = None
                game_state.editing_zone_mode = None
                game_state.menu_cache = None
                game_state.show_notification("Point editing cancelled")
                key_handled = True

        # Player Name Editing Input Handling
        elif (
            game_state.submenu_active == "players"
            and game_state.editing_player_mode == "edit_name"
            and game_state.editing_player_index is not None
        ):

            char = (
                chr(key) if key < 256 else None
            )  # Get character if it's a standard key

            # Append allowed characters (letters, digits, space)
            if char is not None and char in allowed_name_chars:
                current_input = game_state.editing_player_name_input or ""
                if len(current_input) < max_name_length:
                    game_state.editing_player_name_input = current_input + char
                    game_state.menu_cache = None  # Redraw menu
                    logger.debug(
                        f"Edit name input: {game_state.editing_player_name_input}"
                    )
                else:
                    game_state.show_notification(
                        f"Max name length {max_name_length} reached",
                        is_error=True,
                        duration=1.5,
                    )
                key_handled = True

            elif key == 8:  # Backspace
                current_input = game_state.editing_player_name_input or ""
                if current_input:
                    game_state.editing_player_name_input = current_input[:-1]
                    game_state.menu_cache = None  # Redraw menu
                    logger.debug(
                        f"Edit name input after backspace: {game_state.editing_player_name_input}"
                    )
                key_handled = True

            elif key == 13:  # Enter - Save Name
                new_name = (
                    game_state.editing_player_name_input or ""
                ).strip()  # Remove leading/trailing whitespace
                if new_name:  # Check if name is not empty
                    try:
                        player_idx = game_state.editing_player_index
                        game_state.players[player_idx].name = new_name
                        logger.info(
                            f"Updated Player {player_idx + 1} name to '{new_name}'"
                        )
                        game_state.show_notification(
                            f"Player {player_idx + 1} name updated"
                        )
                        # Reset editing state
                        game_state.editing_player_index = None
                        game_state.editing_player_mode = None
                        game_state.editing_player_name_input = None
                        game_state.menu_cache = None
                    except IndexError:
                        logger.error(
                            f"Error accessing players index {player_idx} during name update."
                        )
                        game_state.show_notification(
                            "Error updating name!", is_error=True
                        )
                        game_state.editing_player_index = None
                        game_state.editing_player_mode = None
                        game_state.editing_player_name_input = None
                        game_state.menu_cache = None
                else:
                    # Invalid name (empty)
                    game_state.show_notification(
                        "Player name cannot be empty", is_error=True
                    )
                key_handled = True

            elif key == 27:  # ESC - Cancel Edit
                logger.info("ESC pressed during name edit, cancelling edit.")
                game_state.editing_player_index = None
                game_state.editing_player_mode = None
                game_state.editing_player_name_input = None
                game_state.menu_cache = None  # Redraw menu
                game_state.show_notification("Name editing cancelled")
                key_handled = True

        # General Menu Input (if not editing points/name or key wasn't handled)
        if not key_handled:
            if key == ord("m"):
                logger.debug("Menu key ('m') pressed, closing menu.")
                game_state.current_state = CurrentGameState.PLAYING
                game_state.submenu_active = None
                game_state.menu_cache = None
                game_state.editing_zone_index = None
                game_state.editing_zone_mode = None
                game_state.editing_zone_points_input = None
                game_state.editing_player_index = None
                game_state.editing_player_mode = None
                game_state.editing_player_name_input = None
                key_handled = True
            elif key == 8:  # Backspace (Menu Navigation)
                if game_state.submenu_active is not None:
                    previous_submenu = game_state.submenu_active
                    if game_state.submenu_active == "edit_zones":
                        game_state.submenu_active = "manage_zones"
                    elif game_state.submenu_active == "players":
                        game_state.submenu_active = None  # Go back to main from players
                    else:
                        game_state.submenu_active = None
                    game_state.editing_zone_index = None
                    game_state.editing_zone_mode = None
                    game_state.editing_zone_points_input = None
                    game_state.editing_player_index = None
                    game_state.editing_player_mode = None
                    game_state.editing_player_name_input = None
                    game_state.menu_cache = None
                    logger.debug(
                        f"Backspace: back from {previous_submenu} to {game_state.submenu_active or 'main menu'}."
                    )
                else:
                    game_state.current_state = CurrentGameState.PLAYING
                    game_state.menu_cache = None
                    logger.debug("Backspace: closing menu.")
                key_handled = True
            elif key == 27:  # ESC key (Menu Navigation)
                if game_state.submenu_active is not None:
                    previous_submenu = game_state.submenu_active
                    if game_state.submenu_active == "edit_zones":
                        game_state.submenu_active = "manage_zones"
                    else:
                        game_state.submenu_active = None  # Go to main menu
                    game_state.editing_zone_index = None
                    game_state.editing_zone_mode = None
                    game_state.editing_zone_points_input = None
                    game_state.editing_player_index = None
                    game_state.editing_player_mode = None
                    game_state.editing_player_name_input = None
                    game_state.menu_cache = None
                    logger.debug(
                        f"ESC: back from {previous_submenu} to {game_state.submenu_active or 'main menu'}."
                    )
                else:
                    logger.debug("ESC pressed in main menu, closing menu.")
                    game_state.current_state = CurrentGameState.PLAYING
                    game_state.menu_cache = None
                    game_state.editing_zone_index = None
                    game_state.editing_zone_mode = None
                    game_state.editing_zone_points_input = None
                    game_state.editing_player_index = None
                    game_state.editing_player_mode = None
                    game_state.editing_player_name_input = None
                key_handled = True

    # Handle input for PLAYING state
    elif game_state.current_state == CurrentGameState.PLAYING:
        if key == ord("m"):
            game_state.current_state = CurrentGameState.MENU
            game_state.submenu_active = None
            game_state.menu_cache = None
            key_handled = True
        elif key == ord("s"):
            if not game_state.drawing:
                game_state.drawing = True
                logger.info("Start drawing ('s').")
                game_state.show_notification("Click and drag to draw zone")
            else:
                game_state.drawing = False
                game_state.temp_zone = None
                logger.info("Drawing cancelled ('s').")
                game_state.show_notification("Drawing cancelled")
            key_handled = True
        elif key == ord("p"):
            game_state.current_state = CurrentGameState.PAUSED
            logger.info("Game Paused")
            key_handled = True
        elif key == 27:  # ESC quits
            logger.info("ESC key pressed while playing, exiting.")
            clean_exit(
                game_state.cap,
                game_state.background_music,
                game_state.background_music_on,
                game_state,
            )
            return None

    # Handle input for PAUSED state
    elif game_state.current_state == CurrentGameState.PAUSED:
        if key == ord("p"):
            game_state.current_state = CurrentGameState.PLAYING
            logger.info("Game Resumed")
            key_handled = True
        elif key == 27:  # ESC quits
            logger.info("ESC key pressed while paused, exiting.")
            clean_exit(
                game_state.cap,
                game_state.background_music,
                game_state.background_music_on,
                game_state,
            )
            return None

    # Handle input for GAME_OVER state
    elif game_state.current_state == CurrentGameState.GAME_OVER:
        if key == ord("n"):
            logger.info("New Game key ('n') from game over.")
            try:
                # from menu import reset_game # Now imported at the top

                reset_game(game_state)
                game_state.current_state = CurrentGameState.PLAYING
                game_state.win_condition_met = False
            except ImportError:
                logger.error(
                    "Failed to import reset_game function in _handle_input.")
            key_handled = True
        elif key == ord("l"):
            logger.info("Leaderboard key ('l') from game over.")
            game_state.current_state = CurrentGameState.MENU
            game_state.submenu_active = "leaderboard"
            game_state.menu_cache = None
            game_state.win_condition_met = False
            key_handled = True
        elif key == 27:  # ESC quits
            logger.info("ESC key pressed on game over screen, exiting.")
            clean_exit(
                game_state.cap,
                game_state.background_music,
                game_state.background_music_on,
                game_state,
            )
            return None

    # Handle global keys if not handled by state-specific logic
    if not key_handled:
        if key == ord("d"):
            game_state.debug_mode = not game_state.debug_mode
            logger.info(
                f"General Debug toggled {'ON' if game_state.debug_mode else 'OFF'}"
            )
            key_handled = True
        elif key == ord("b"):
            game_state.show_debug_overlay = not game_state.show_debug_overlay
            logger.info(
                f"Visual Debug Overlay toggled {'ON' if game_state.show_debug_overlay else 'OFF'}"
            )
            key_handled = True

    # Return key code (or None if exit was triggered, or -1 if window closed)
    # Check for -1 explicitly which might come from waitKey if window closed before key press
    if key == -1:
        logger.debug(
            "waitKey returned -1, potentially indicating closed window or no key press."
        )
        # We rely on _check_window_close in the main loop to handle actual closure detection
        pass  # Don't treat -1 alone as an exit signal here

    return key
