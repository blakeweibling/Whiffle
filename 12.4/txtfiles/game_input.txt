# game_input.py
import cv2
import logging
import string
from typing import Optional, Any
import pygame  # Keep for constants like K_RETURN etc. used in menu/game over logic

# Import constants, utils, and specific game states/functions
from constants import UIConstants, GameConstants, ScoringConstants, PlayerConstants

# Import clean_exit from the correct location
from cleanup_utils import clean_exit

# Import GameState enum and necessary functions/classes
from game_state import CurrentGameState  # Ensure CurrentGameState includes ZONE_EDITING
from menu import reset_game  # Required for 'n' key in GAME_OVER

# Import necessary functions if used within this file's logic
from menu import save_zones
from game_state_utils import set_special_hole  # Needed for ZONE_EDITING ESC handler

logger = logging.getLogger(__name__)


def _handle_input(game_state: Any) -> Optional[int]:
    """Handles keyboard input using cv2.waitKey."""
    raw_key = -1  # Store raw value before mask
    key = -1
    try:
        # Check if the window is still valid before calling waitKey
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 1:
            raw_key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY)
            key = raw_key & 0xFF  # Apply mask for standard ASCII checks
        else:
            logger.debug("Skipping waitKey, window seems closed or closing.")
            return key  # Return -1 if window closed

    except cv2.error as e:
        logger.warning(
            f"cv2.error during waitKey or getWindowProperty (window likely closed): {e}"
        )
        return -1  # Return -1 on error

    key_handled_globally = False  # Flag to check if input was processed overall

    # --- Handle Truly Global Quit Key First (using masked key) ---
    if key == ord("q"):
        logger.info("Quit key ('q') pressed.")
        # Call clean_exit from cleanup_utils
        clean_exit(
            game_state.cap,
            game_state.background_music,
            game_state.background_music_on,
            game_state,
        )
        return None  # Signal immediate exit

    # --- State-Specific Input Handling ---
    if key != -1 and key != 255:  # Ignore no-input/-1 and potential 255 spam

        # --- Handle input for GETTING_PLAYER_NAME state ---
        if game_state.current_state == CurrentGameState.GETTING_PLAYER_NAME:
            if key == 13:  # Enter Key
                logger.debug("Enter key (13) detected during initial name input.")
                entered_name = game_state.current_player_name_input.strip()
                if not entered_name:
                    game_state.show_notification(
                        "Player name cannot be empty!", is_error=True, duration=2.0
                    )
                else:
                    try:
                        if game_state.players:
                            game_state.players[0].name = entered_name
                            logger.info(f"Player 1 name set to: '{entered_name}'")
                            game_state.show_notification(
                                f"Welcome, {entered_name}!", duration=2.0
                            )
                            game_state.player_name_input_active = False
                            game_state.current_state = CurrentGameState.PLAYING
                            # <<< REMOVED redundant music start >>>
                            # if (
                            #     game_state.background_music_on
                            #     and game_state.background_music
                            # ):
                            #     game_state.background_music.play(-1)
                            #     logger.info("Background music started.")
                            # <<< END REMOVAL >>>
                        else:
                            logger.error(
                                "Cannot set name: players list is empty or None."
                            )
                            game_state.show_notification(
                                "Error: Player list missing!", is_error=True
                            )
                    except Exception as e:
                        logger.exception(
                            f"Error setting player name or changing state: {e}"
                        )
                        game_state.show_notification(
                            "Error starting game!", is_error=True
                        )
                key_handled_globally = True
            elif key == 27:  # Escape Key
                logger.debug("Escape key (27) detected during initial name input.")
                logger.info("Using default name 'Player 1'.")
                if game_state.players:
                    game_state.players[0].name = "Player 1"
                    game_state.player_name_input_active = False
                    game_state.current_state = CurrentGameState.PLAYING
                    game_state.show_notification(
                        "Using default name 'Player 1'", duration=2.0
                    )
                    # <<< REMOVED redundant music start >>>
                    # if (
                    #     game_state.background_music_on and game_state.background_music
                    # ):
                    #     game_state.background_music.play(-1)
                    #     logger.info("Background music started.")
                    # <<< END REMOVAL >>>
                else:
                    logger.error(
                        "Cannot set default name: players list is empty or None."
                    )
                    game_state.show_notification(
                        "Error: Player list missing!", is_error=True
                    )
                key_handled_globally = True
            elif key == 8:  # Backspace Key
                logger.debug("Backspace key (8) detected during initial name input.")
                if game_state.current_player_name_input:
                    game_state.current_player_name_input = (
                        game_state.current_player_name_input[:-1]
                    )
                    logger.debug(
                        f"Name input buffer: {game_state.current_player_name_input}"
                    )
                key_handled_globally = True
            elif key >= 32 and key <= 126:  # Printable characters
                char = chr(key)
                if char in PlayerConstants.ALLOWED_PLAYER_NAME_CHARS:
                    if (
                        len(game_state.current_player_name_input)
                        < PlayerConstants.MAX_PLAYER_NAME_LENGTH
                    ):
                        game_state.current_player_name_input += char
                        logger.debug(
                            f"Name input buffer: {game_state.current_player_name_input}"
                        )
                    else:
                        game_state.show_notification(
                            f"Max name length ({PlayerConstants.MAX_PLAYER_NAME_LENGTH}) reached",
                            is_error=True,
                            duration=1.5,
                        )
                    key_handled_globally = True
                else:
                    logger.debug(f"Character '{char}' not allowed for player name.")
                    game_state.show_notification(
                        f"Character '{char}' not allowed", is_error=True, duration=1.5
                    )
                    key_handled_globally = True

        # --- Handle input for MENU state ---
        elif game_state.current_state == CurrentGameState.MENU:
            # (Menu input handling - unchanged)
            menu_key_handled = False

            # Player Name Editing Logic
            if (
                game_state.submenu_active == "players"
                and game_state.editing_player_mode == "edit_name"
                and game_state.editing_player_index is not None
            ):
                player_idx = game_state.editing_player_index
                if key == 13:  # Enter Key - Save Name
                    logger.debug(
                        "Enter key (13) detected during menu player name edit."
                    )
                    new_name = game_state.editing_player_name_input.strip()
                    if not new_name:
                        game_state.show_notification(
                            "Player name cannot be empty!", is_error=True, duration=2.0
                        )
                    elif 0 <= player_idx < len(game_state.players):
                        old_name = game_state.players[player_idx].name
                        game_state.players[player_idx].name = new_name
                        logger.info(
                            f"Player {player_idx + 1} name changed from '{old_name}' to '{new_name}'"
                        )
                        game_state.show_notification(
                            f"Player {player_idx + 1} name updated", duration=2.0
                        )
                        game_state.editing_player_index = None
                        game_state.editing_player_mode = None
                        game_state.editing_player_name_input = None
                        game_state.menu_cache = None  # Invalidate cache
                    else:
                        logger.error(
                            f"Invalid player index {player_idx} during name save."
                        )
                        game_state.show_notification(
                            "Error saving name!", is_error=True
                        )
                        game_state.editing_player_index = None
                        game_state.editing_player_mode = None
                        game_state.editing_player_name_input = None
                        game_state.menu_cache = None  # Invalidate cache
                    menu_key_handled = True
                elif key == 27:  # Escape Key - Cancel Edit
                    logger.debug(
                        "Escape key (27) detected during menu player name edit."
                    )
                    game_state.editing_player_index = None
                    game_state.editing_player_mode = None
                    game_state.editing_player_name_input = None
                    game_state.menu_cache = None  # Invalidate cache
                    game_state.show_notification("Name edit cancelled", duration=1.5)
                    menu_key_handled = True
                elif key == 8:  # Backspace Key
                    logger.debug(
                        "Backspace key (8) detected during menu player name edit."
                    )
                    if game_state.editing_player_name_input:
                        game_state.editing_player_name_input = (
                            game_state.editing_player_name_input[:-1]
                        )
                        game_state.menu_cache = None  # Invalidate cache
                    menu_key_handled = True
                elif key >= 32 and key <= 126:  # Printable characters
                    char = chr(key)
                    if char in PlayerConstants.ALLOWED_PLAYER_NAME_CHARS:
                        if (
                            len(game_state.editing_player_name_input)
                            < PlayerConstants.MAX_PLAYER_NAME_LENGTH
                        ):
                            game_state.editing_player_name_input += char
                            game_state.menu_cache = None  # Invalidate cache
                        else:
                            game_state.show_notification(
                                f"Max {PlayerConstants.MAX_PLAYER_NAME_LENGTH} chars",
                                is_error=True,
                                duration=1.5,
                            )
                            # Note: Menu key not handled if max length reached, allowing other keys
                    else:
                        logger.debug(f"Character '{char}' not allowed for player name.")
                        game_state.show_notification(
                            f"Character '{char}' not allowed",
                            is_error=True,
                            duration=1.5,
                        )
                        menu_key_handled = True  # Handle invalid char input

                if menu_key_handled:
                    key_handled_globally = True

            # Zone Points Editing Logic
            elif (
                game_state.submenu_active == "edit_zones"
                and game_state.editing_zone_mode == "edit_points"
                and game_state.editing_zone_index is not None
            ):
                zone_idx = game_state.editing_zone_index
                if key == 13:  # Enter Key - Save Points
                    logger.debug(
                        "Enter key (13) detected during menu zone points edit."
                    )
                    try:
                        new_points_str = game_state.editing_zone_points_input.strip()
                        if not new_points_str:
                            game_state.show_notification(
                                "Points cannot be empty!", is_error=True
                            )
                        else:
                            new_points = int(new_points_str)
                            if not (1 <= new_points <= ScoringConstants.MAX_POINTS):
                                game_state.show_notification(
                                    f"Points must be 1-{ScoringConstants.MAX_POINTS}",
                                    is_error=True,
                                )
                            elif 0 <= zone_idx < len(game_state.scoring_zones):
                                x, y, w, h, _ = game_state.scoring_zones[zone_idx]
                                game_state.scoring_zones[zone_idx] = (
                                    x,
                                    y,
                                    w,
                                    h,
                                    new_points,
                                )
                                logger.info(
                                    f"Zone {zone_idx + 1} points updated to {new_points}"
                                )
                                game_state.show_notification(
                                    f"Zone {zone_idx + 1} points updated", duration=2.0
                                )
                                game_state.editing_zone_index = None
                                game_state.editing_zone_mode = None
                                game_state.editing_zone_points_input = None
                                game_state.menu_cache = None  # Invalidate cache
                            else:
                                logger.error(
                                    f"Invalid zone index {zone_idx} during points save."
                                )
                                game_state.show_notification(
                                    "Error saving points!", is_error=True
                                )
                                game_state.editing_zone_index = None
                                game_state.editing_zone_mode = None
                                game_state.editing_zone_points_input = None
                                game_state.menu_cache = None  # Invalidate cache
                    except ValueError:
                        game_state.show_notification(
                            "Invalid points value!", is_error=True
                        )
                    except Exception as e:
                        logger.exception(f"Error saving zone points: {e}")
                        game_state.show_notification(
                            "Error saving points!", is_error=True
                        )
                        game_state.editing_zone_index = None
                        game_state.editing_zone_mode = None
                        game_state.editing_zone_points_input = None
                        game_state.menu_cache = None  # Invalidate cache
                    menu_key_handled = True
                elif key == 27:  # Escape Key - Cancel Edit
                    logger.debug(
                        "Escape key (27) detected during menu zone points edit."
                    )
                    game_state.editing_zone_index = None
                    game_state.editing_zone_mode = None
                    game_state.editing_zone_points_input = None
                    game_state.menu_cache = None  # Invalidate cache
                    game_state.show_notification("Points edit cancelled", duration=1.5)
                    menu_key_handled = True
                elif key == 8:  # Backspace Key
                    logger.debug(
                        "Backspace key (8) detected during menu zone points edit."
                    )
                    if game_state.editing_zone_points_input:
                        game_state.editing_zone_points_input = (
                            game_state.editing_zone_points_input[:-1]
                        )
                        game_state.menu_cache = None  # Invalidate cache
                    menu_key_handled = True
                elif ord("0") <= key <= ord("9"):  # Numeric input
                    logger.debug(f"Numeric key {chr(key)} detected during points edit.")
                    char = chr(key)
                    if game_state.editing_zone_points_input is None:
                        game_state.editing_zone_points_input = ""
                    max_digits = len(str(ScoringConstants.MAX_POINTS))
                    if len(game_state.editing_zone_points_input) < max_digits:
                        game_state.editing_zone_points_input += char
                        game_state.menu_cache = None  # Invalidate cache
                    else:
                        game_state.show_notification(
                            f"Max points {ScoringConstants.MAX_POINTS}",
                            is_error=True,
                            duration=1.5,
                        )
                        # Input ignored, allow other keys if max digits reached
                    menu_key_handled = True  # Handle numeric input

                if menu_key_handled:
                    key_handled_globally = True

            # General Menu Navigation
            if (
                not key_handled_globally
            ):  # Check if not handled by specific editing modes
                if key == ord("m"):  # Toggle menu OFF (Resume)
                    logger.debug("Menu key ('m') pressed in menu, resuming game.")
                    game_state.current_state = CurrentGameState.PLAYING
                    # Ensure all editing modes are cancelled when leaving menu via 'm'
                    game_state.editing_player_index = None
                    game_state.editing_player_mode = None
                    game_state.editing_player_name_input = None
                    game_state.editing_zone_index = None
                    game_state.editing_zone_mode = None
                    game_state.editing_zone_points_input = None
                    game_state.submenu_active = None
                    game_state.menu_cache = None
                    key_handled_globally = True
                elif key == 8:  # Backspace Key - Go Back or Close Menu
                    logger.debug("Backspace key (8) detected for menu navigation.")
                    # Handle back specifically from editing modes first
                    if game_state.editing_zone_mode:
                        game_state.editing_zone_index = None
                        game_state.editing_zone_mode = None
                        game_state.editing_zone_points_input = None
                        game_state.menu_cache = None
                        logger.debug("Cancelled zone editing via backspace.")
                        key_handled_globally = True
                    elif game_state.editing_player_mode:
                        game_state.editing_player_index = None
                        game_state.editing_player_mode = None
                        game_state.editing_player_name_input = None
                        game_state.menu_cache = None
                        logger.debug("Cancelled player editing via backspace.")
                        key_handled_globally = True
                    # Handle back from submenus
                    elif game_state.submenu_active == "edit_zones":
                        game_state.submenu_active = "manage_zones"
                        game_state.menu_cache = None
                        key_handled_globally = True
                    elif (
                        game_state.submenu_active
                    ):  # Back from any other submenu to main menu
                        game_state.submenu_active = None
                        game_state.menu_cache = None
                        key_handled_globally = True
                    else:  # If already on main menu, backspace closes it
                        game_state.current_state = CurrentGameState.PLAYING
                        game_state.submenu_active = None
                        game_state.menu_cache = None
                        logger.debug("Closed main menu via backspace.")
                        key_handled_globally = True
                elif key == 27:  # Escape Key - Close Menu entirely
                    logger.debug("Escape key (27) detected in menu, resuming game.")
                    game_state.current_state = CurrentGameState.PLAYING
                    # Ensure all editing modes are cancelled
                    game_state.editing_player_index = None
                    game_state.editing_player_mode = None
                    game_state.editing_player_name_input = None
                    game_state.editing_zone_index = None
                    game_state.editing_zone_mode = None
                    game_state.editing_zone_points_input = None
                    game_state.submenu_active = None
                    game_state.menu_cache = None
                    key_handled_globally = True

        # --- Handle input for PLAYING state ---
        elif game_state.current_state == CurrentGameState.PLAYING:
            key_handled_in_playing = False  # Use local flag for PLAYING state

            # Handle input during zone drawing
            if game_state.drawing:
                if ord("0") <= key <= ord("9"):
                    # Limit input length (e.g., 3 digits for 1-999)
                    if len(game_state.drawing_points_input) < 3:
                        game_state.drawing_points_input += chr(key)
                        logger.debug(
                            f"Drawing points input: {game_state.drawing_points_input}"
                        )
                    else:
                        game_state.show_notification(
                            f"Max 3 digits for points", duration=1.0
                        )
                    key_handled_in_playing = True
                elif key == 8:  # Backspace
                    if game_state.drawing_points_input:
                        game_state.drawing_points_input = (
                            game_state.drawing_points_input[:-1]
                        )
                        logger.debug(
                            f"Drawing points input (backspace): {game_state.drawing_points_input}"
                        )
                    key_handled_in_playing = True

            # Handle standard PLAYING keys if not handled by drawing input
            if not key_handled_in_playing:
                if key == ord("m"):  # Toggle menu ON
                    logger.info("Menu key ('m') pressed while playing.")
                    game_state.current_state = CurrentGameState.MENU
                    game_state.submenu_active = None
                    game_state.menu_cache = None
                    # Cancel drawing if menu is opened
                    if game_state.drawing:
                        game_state.drawing = False
                        game_state.temp_zone = None
                        game_state.start_x = None
                        game_state.start_y = None
                        game_state.drawing_points_input = ""
                        logger.info("Drawing cancelled due to menu open.")
                    key_handled_in_playing = True  # Mark as handled
                elif key == ord("s"):  # Toggle drawing mode
                    game_state.drawing = not game_state.drawing
                    if game_state.drawing:
                        logger.info(
                            "Drawing mode enabled. Click and drag to draw zone. Enter digits for points."
                        )
                        game_state.show_notification("Drawing Mode: ON")
                        # Reset state associated with drawing
                        game_state.start_x = None
                        game_state.start_y = None
                        game_state.temp_zone = None
                        game_state.drawing_points_input = ""  # Reset points input
                    else:
                        logger.info("Drawing mode disabled.")
                        game_state.show_notification("Drawing Mode: OFF")
                        # Clear drawing state
                        game_state.temp_zone = None
                        game_state.start_x = None
                        game_state.start_y = None
                        game_state.drawing_points_input = ""
                    key_handled_in_playing = True  # Mark as handled
                elif key == ord("p"):  # Pause game
                    logger.info("Pause key ('p') pressed.")
                    # Cancel drawing if pausing
                    if game_state.drawing:
                        game_state.drawing = False
                        game_state.temp_zone = None
                        game_state.start_x = None
                        game_state.start_y = None
                        game_state.drawing_points_input = ""
                        logger.info("Drawing cancelled due to pause.")
                    game_state.current_state = CurrentGameState.PAUSED
                    game_state.show_notification(
                        "Game Paused", duration=0
                    )  # Persistent
                    key_handled_in_playing = True  # Mark as handled
                elif key == 27:  # ESC quits immediately while playing
                    logger.info("Escape key (27) pressed while playing, exiting.")
                    clean_exit(
                        game_state.cap,
                        game_state.background_music,
                        game_state.background_music_on,
                        game_state,
                    )
                    return None  # Signal exit

            # If key was handled within PLAYING state (either drawing or standard keys)
            if key_handled_in_playing:
                key_handled_globally = True

        # --- Handle input for PAUSED state ---
        elif game_state.current_state == CurrentGameState.PAUSED:
            if key == ord("p"):  # Resume game
                logger.info("Resume key ('p') pressed.")
                game_state.current_state = CurrentGameState.PLAYING
                game_state.show_notification("Resuming...", duration=1.0)
                key_handled_globally = True
            elif key == 27:  # ESC quits immediately while paused
                logger.info("Escape key (27) pressed while paused, exiting.")
                clean_exit(
                    game_state.cap,
                    game_state.background_music,
                    game_state.background_music_on,
                    game_state,
                )
                return None  # Signal exit

        # --- Handle input for GAME_OVER state ---
        elif game_state.current_state == CurrentGameState.GAME_OVER:
            if key == ord("n"):  # Start New Game
                logger.info("'n' key pressed on game over screen. Starting new game.")
                reset_game(game_state)
                # Transition to name input for the new game
                game_state.current_state = CurrentGameState.GETTING_PLAYER_NAME
                game_state.win_condition_met = False
                key_handled_globally = True
            elif key == ord("l"):  # Show Leaderboard
                logger.info("'l' key pressed on game over screen. Showing leaderboard.")
                game_state.current_state = CurrentGameState.MENU
                game_state.submenu_active = "leaderboard"
                game_state.menu_cache = None
                game_state.win_condition_met = False
                key_handled_globally = True
            elif key == 27:  # ESC quits immediately from game over
                logger.info("Escape key (27) pressed on game over screen, exiting.")
                clean_exit(
                    game_state.cap,
                    game_state.background_music,
                    game_state.background_music_on,
                    game_state,
                )
                return None  # Signal exit

        # --- Handle input for ZONE_EDITING state (ESC key) ---
        elif game_state.current_state == CurrentGameState.ZONE_EDITING:
            if key == 27:  # ESC cancels editing action
                logger.info("Escape key (27) pressed during ZONE_EDITING.")
                # If currently dragging, revert to original zone state
                if (
                    game_state.drag_start_pos
                    and game_state.original_zone_on_drag_start
                    and game_state.selected_zone_for_edit is not None
                ):
                    logger.info("Reverting zone to pre-drag state.")
                    game_state.scoring_zones[game_state.selected_zone_for_edit] = (
                        game_state.original_zone_on_drag_start
                    )
                    game_state.special_hole = set_special_hole(
                        game_state.scoring_zones
                    )  # Update special hole

                # Reset editing state and return to previous state (usually MENU)
                game_state.zone_editing_action = None
                game_state.drag_start_pos = None
                game_state.selected_zone_for_edit = None
                game_state.original_zone_on_drag_start = None
                game_state.current_state = (
                    game_state.previous_state or CurrentGameState.MENU
                )  # Revert state
                game_state.previous_state = None  # Clear previous state marker
                game_state.show_notification("Zone Edit Cancelled")
                game_state.menu_cache = (
                    None  # Invalidate menu cache as we are likely returning to menu
                )
                key_handled_globally = True

        # --- Global Toggles (Only if not handled by specific states above) ---
        if not key_handled_globally:
            if key == ord("d"):  # Toggle General Debug Logging
                game_state.debug_mode = not game_state.debug_mode
                log_level = logging.DEBUG if game_state.debug_mode else logging.INFO
                # Update root logger level AND handler levels
                logging.getLogger().setLevel(log_level)
                for handler in logging.getLogger().handlers:
                    handler.setLevel(log_level)
                logger.info(
                    f"General Debug Mode toggled {'ON' if game_state.debug_mode else 'OFF'} (Level: {logging.getLevelName(log_level)})"
                )
                game_state.show_notification(
                    f"Debug Mode: {'ON' if game_state.debug_mode else 'OFF'}"
                )
                key_handled_globally = True
            elif key == ord("b"):  # Toggle Visual Debug Overlay
                game_state.show_debug_overlay = not game_state.show_debug_overlay
                logger.info(
                    f"Visual Debug Overlay toggled {'ON' if game_state.show_debug_overlay else 'OFF'}"
                )
                game_state.show_notification(
                    f"Debug Overlay: {'ON' if game_state.show_debug_overlay else 'OFF'}"
                )
                key_handled_globally = True

    # Return the masked key code, or None if quit was triggered
    return key
