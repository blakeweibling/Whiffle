# game_input.py
import logging
from typing import Any, Optional

import cv2
import string
import pygame  # Keep for key constants like K_RETURN, K_ESCAPE if needed elsewhere

# Import clean_exit from the correct location
from cleanup_utils import clean_exit

# Import constants, utils, and specific game states/functions
from constants import GameConstants, PlayerConstants, ScoringConstants, UIConstants

# Import necessary utility functions from the CORRECT files
from game_state_helpers import (
    set_special_hole,
    show_notification,  # Import relevant helpers
)
from game_state_utils import reset_game  # Import reset_game

# Import GameState enum from the NEW location
from game_types import CurrentGameState  # Correct location

logger = logging.getLogger(__name__)


def _handle_input(game_state: Any) -> Optional[int]:
    """Handles keyboard input using cv2.waitKey, including heatmap dismissal."""
    raw_key = -1
    key = -1  # Default value if no key is pressed or window is closed

    # Get key press
    try:
        # Check if window is valid before waiting for key
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME,
                                 cv2.WND_PROP_VISIBLE) >= 1:
            raw_key = cv2.waitKey(
                GameConstants.WAIT_KEY_DELAY)  # Get raw key code
            if raw_key != -1:  # Only process if a key was actually pressed
                key = raw_key & 0xFF  # Get the significant byte
        else:
            # Window is closed or not visible, no input can be processed
            logger.debug("Window closed or not visible, skipping input.")
            return -1  # Return -1 to indicate no valid input / potential closure
    except cv2.error as e:
        # Handle potential errors if window disappears unexpectedly
        logger.warning(
            f"Error getting window property or waiting for key: {e}")
        return -1  # Indicate error or closure

    # --- >>> ADDED: Handle Heatmap Dismissal <<< ---
    # Check if heatmap is currently shown. This takes priority over other input.
    if getattr(game_state, "show_heatmap", False):
        # Any key press (including ESC, which is 27) or any valid key != -1 dismisses heatmap
        if (
                key != -1 and key != 255
        ):  # Check if a valid key was pressed (waitKey returns -1 if no key)
            logger.info(f"Heatmap dismissed by keyboard input (key: {key}).")
            game_state.show_heatmap = False
            # No further action needed for this key press in terms of game logic
            # Return the key itself, or -1 to signify handled without further game action?
            # Let's return the key, the main loop will continue.
            return key  # Indicate a key was pressed, but heatmap handled it.
        else:
            # If heatmap is shown but no key was pressed, return the current key value (-1)
            # This allows the main loop to continue checking window status etc.
            return key  # Which is likely -1 if no key was pressed
    # --- >>> END ADDED <<< ---

    # If heatmap wasn't active or wasn't dismissed by a key press, proceed with normal input handling.
    key_handled_globally = (
        False  # Flag to prevent redundant processing in different states
    )

    # Handle global 'q' for quit confirmation (unless heatmap was showing)
    if key == ord("q"):
        # Only trigger confirmation if not already confirming or in name input
        if game_state.current_state not in [
                CurrentGameState.CONFIRM_QUIT,
                CurrentGameState.GETTING_PLAYER_NAME,
        ]:
            # Store the state we were in before prompting for quit
            game_state.previous_state_before_quit_confirm = game_state.current_state
            game_state.current_state = CurrentGameState.CONFIRM_QUIT
            key_handled_globally = True
            logger.debug(
                "Quit key ('q') pressed, entering CONFIRM_QUIT state.")
        # If 'q' is pressed while already confirming, let the CONFIRM_QUIT block handle it below (treat as cancel)

    # Process other keys only if a valid key was pressed and not handled globally yet
    # (key != -1 implies a key was actually pressed)
    if key != -1 and key != 255 and not key_handled_globally:

        # Handle input in CONFIRM_QUIT state
        if game_state.current_state == CurrentGameState.CONFIRM_QUIT:
            if key == ord("y"):  # Confirm quit
                logger.info("Quit confirmed via 'y'.")
                # Call clean exit
                clean_exit(
                    getattr(game_state, "cap", None),
                    getattr(game_state, "background_music", None),
                    getattr(game_state, "background_music_on", True),
                    game_state,
                )
                # clean_exit usually calls sys.exit, but return None just in case
                return None  # Signal exit to main loop
            elif key in [
                    ord("n"),
                    27,
                    8,
                    ord("q"),
            ]:  # N, Esc, Backspace, or Q again cancels quit
                logger.debug("Quit confirmation cancelled.")
                # Restore the previous state safely
                game_state.current_state = getattr(
                    game_state,
                    "previous_state_before_quit_confirm",
                    CurrentGameState.
                    PLAYING,  # Default to PLAYING if somehow unset
                )
                game_state.previous_state_before_quit_confirm = (
                    None  # Clear the stored state
                )
                key_handled_globally = True  # Mark handled
            # Ignore other keys in this specific state
            # If handled (cancelled), return the key so loop continues
            # If not handled (ignored key), return key so loop continues
            return key  # Loop continues unless 'y' was pressed

        # Handle input in GETTING_PLAYER_NAME state
        elif game_state.current_state == CurrentGameState.GETTING_PLAYER_NAME:
            player_name_key_handled = False
            if key == 13:  # Enter key
                entered_name = getattr(game_state, "current_player_name_input",
                                       "").strip()
                if not entered_name:
                    show_notification(
                        game_state,
                        "Player name cannot be empty!",
                        is_error=True,
                        duration=2.0,
                    )
                else:
                    # Safely update player name
                    if hasattr(game_state, "players") and game_state.players:
                        try:
                            game_state.players[0].name = entered_name
                            show_notification(game_state,
                                              f"Welcome, {entered_name}!",
                                              duration=2.0)
                            game_state.player_name_input_active = (
                                False  # Flag to stop drawing input screen
                            )
                            game_state.current_state = (
                                CurrentGameState.PLAYING)  # Proceed to game
                        except IndexError:
                            show_notification(game_state,
                                              "Error: Player list invalid!",
                                              is_error=True)
                        except Exception as e:
                            logger.error(f"Error setting player name: {e}")
                            show_notification(game_state,
                                              "Error starting game!",
                                              is_error=True)
                    else:
                        show_notification(game_state,
                                          "Error: Player list missing!",
                                          is_error=True)
                player_name_key_handled = True
            elif key == 27:  # Escape key (use default name)
                if hasattr(game_state, "players") and game_state.players:
                    try:
                        game_state.players[0].name = "Player 1"  # Use default
                        game_state.player_name_input_active = False
                        game_state.current_state = CurrentGameState.PLAYING
                        show_notification(game_state,
                                          "Using default name 'Player 1'",
                                          duration=2.0)
                    except IndexError:
                        show_notification(game_state,
                                          "Error: Player list invalid!",
                                          is_error=True)
                    except Exception as e:
                        logger.error(f"Error setting default player name: {e}")
                        show_notification(game_state,
                                          "Error starting game!",
                                          is_error=True)
                else:
                    show_notification(game_state,
                                      "Error: Player list missing!",
                                      is_error=True)
                player_name_key_handled = True
            elif key == 8:  # Backspace key
                current_input = getattr(game_state,
                                        "current_player_name_input", "")
                if current_input:
                    game_state.current_player_name_input = current_input[:-1]
                player_name_key_handled = True
            elif key >= 32 and key <= 126:  # Printable ASCII characters
                char = chr(key)
                allowed_chars = getattr(
                    PlayerConstants,
                    "ALLOWED_PLAYER_NAME_CHARS",
                    string.ascii_letters + string.digits + " _-",
                )  # Default allowed chars
                max_len = getattr(PlayerConstants, "MAX_PLAYER_NAME_LENGTH",
                                  15)
                current_input = getattr(game_state,
                                        "current_player_name_input", "")

                if char in allowed_chars:
                    if len(current_input) < max_len:
                        game_state.current_player_name_input += char
                    else:
                        show_notification(
                            game_state,
                            f"Max name length ({max_len}) reached",
                            is_error=True,
                            duration=1.5,
                        )
                else:
                    show_notification(
                        game_state,
                        f"Character '{char}' not allowed",
                        is_error=True,
                        duration=1.5,
                    )
                player_name_key_handled = True

            if player_name_key_handled:
                key_handled_globally = True

        # Handle input in MENU state
        elif game_state.current_state == CurrentGameState.MENU:
            menu_key_handled = False  # Flag for specific menu input processing

            # --- Handle Specific Input Modes within Menu (like editing name/points) ---
            # Player Name Editing Logic...
            if (getattr(game_state, "submenu_active", None) == "players"
                    and getattr(game_state, "editing_player_mode", None)
                    == "edit_name" and getattr(
                        game_state, "editing_player_index", None) is not None):

                player_idx = game_state.editing_player_index
                current_edit_input = getattr(game_state,
                                             "editing_player_name_input", "")

                if key == 13:  # Enter - Save Name
                    new_name = current_edit_input.strip()
                    if not new_name:
                        show_notification(
                            game_state,
                            "Player name cannot be empty!",
                            is_error=True,
                            duration=2.0,
                        )
                    elif 0 <= player_idx < len(
                            getattr(game_state, "players", [])):
                        try:
                            game_state.players[player_idx].name = new_name
                            show_notification(
                                game_state,
                                f"Player {player_idx+1} name updated",
                                duration=2.0,
                            )
                            # Reset editing state
                            game_state.editing_player_index = None
                            game_state.editing_player_mode = None
                            game_state.editing_player_name_input = None
                            game_state.menu_cache = None  # Redraw menu
                        except Exception as e:
                            logger.error(
                                f"Error updating player name in list: {e}")
                            show_notification(game_state,
                                              "Error saving name!",
                                              is_error=True)
                            # Reset state even on error
                            game_state.editing_player_index = None
                            game_state.editing_player_mode = None
                            game_state.editing_player_name_input = None
                            game_state.menu_cache = None
                    else:  # Invalid index somehow
                        show_notification(
                            game_state,
                            "Error saving name (invalid index?)!",
                            is_error=True,
                        )
                        game_state.editing_player_index = None
                        game_state.editing_player_mode = None
                        game_state.editing_player_name_input = None
                        game_state.menu_cache = None
                    menu_key_handled = True

                elif key == 27:  # Escape - Cancel Edit
                    game_state.editing_player_index = None
                    game_state.editing_player_mode = None
                    game_state.editing_player_name_input = None
                    game_state.menu_cache = None
                    show_notification(game_state,
                                      "Name edit cancelled",
                                      duration=1.5)
                    menu_key_handled = True

                elif key == 8:  # Backspace
                    if current_edit_input:
                        game_state.editing_player_name_input = current_edit_input[:
                                                                                  -1]
                        game_state.menu_cache = None  # Redraw menu to show change
                    menu_key_handled = True

                elif key >= 32 and key <= 126:  # Printable ASCII for Name Input
                    char = chr(key)
                    allowed_chars = getattr(
                        PlayerConstants,
                        "ALLOWED_PLAYER_NAME_CHARS",
                        string.ascii_letters + string.digits + " _-",
                    )
                    max_len = getattr(PlayerConstants,
                                      "MAX_PLAYER_NAME_LENGTH", 15)
                    if char in allowed_chars:
                        if len(current_edit_input) < max_len:
                            game_state.editing_player_name_input += char
                            game_state.menu_cache = None  # Redraw
                        else:
                            show_notification(
                                game_state,
                                f"Max {max_len} chars",
                                is_error=True,
                                duration=1.5,
                            )
                    else:
                        show_notification(
                            game_state,
                            f"Character '{char}' not allowed",
                            is_error=True,
                            duration=1.5,
                        )
                    menu_key_handled = True

                # If any key was handled within player name edit mode, mark it globally
                if menu_key_handled:
                    key_handled_globally = True

            # Zone Points Editing Logic... (Only if not already handled by name edit)
            elif (not key_handled_globally and getattr(
                    game_state, "submenu_active", None) == "edit_zones"
                  and getattr(game_state, "editing_zone_mode", None)
                  == "edit_points" and getattr(
                      game_state, "editing_zone_index", None) is not None):

                zone_idx = game_state.editing_zone_index
                current_points_input = getattr(game_state,
                                               "editing_zone_points_input", "")

                if key == 13:  # Enter - Save Points
                    try:
                        new_points_str = current_points_input.strip()
                        if not new_points_str:
                            show_notification(game_state,
                                              "Points cannot be empty!",
                                              is_error=True)
                        else:
                            new_points = int(new_points_str)
                            max_pts = getattr(ScoringConstants, "MAX_POINTS",
                                              999)
                            if not (1 <= new_points <= max_pts):
                                show_notification(
                                    game_state,
                                    f"Points must be 1-{max_pts}",
                                    is_error=True,
                                )
                            elif (0 <= zone_idx < len(
                                    getattr(game_state, "scoring_zones", []))):
                                # Update points in the zone tuple (tuples are immutable, so create new one)
                                x, y, w, h, _ = game_state.scoring_zones[
                                    zone_idx]
                                game_state.scoring_zones[zone_idx] = (
                                    x,
                                    y,
                                    w,
                                    h,
                                    new_points,
                                )
                                show_notification(
                                    game_state,
                                    f"Zone {zone_idx+1} points updated",
                                    duration=2.0,
                                )
                                # Reset editing state on success
                                game_state.editing_zone_index = None
                                game_state.editing_zone_mode = None
                                game_state.editing_zone_points_input = None
                                game_state.menu_cache = None
                            else:  # Invalid index
                                show_notification(
                                    game_state,
                                    "Error saving points (invalid index?)!",
                                    is_error=True,
                                )
                                game_state.editing_zone_index = None
                                game_state.editing_zone_mode = None
                                game_state.editing_zone_points_input = None
                                game_state.menu_cache = None
                    except ValueError:
                        show_notification(game_state,
                                          "Invalid points value!",
                                          is_error=True)
                        # Optionally clear input on error: game_state.editing_zone_points_input = ""
                    except Exception as e:
                        logger.error(f"Error saving zone points: {e}")
                        show_notification(game_state,
                                          "Error saving points!",
                                          is_error=True)
                        # Reset state on other errors
                        game_state.editing_zone_index = None
                        game_state.editing_zone_mode = None
                        game_state.editing_zone_points_input = None
                        game_state.menu_cache = None
                    menu_key_handled = True

                elif key == 27:  # Escape - Cancel Edit
                    game_state.editing_zone_index = None
                    game_state.editing_zone_mode = None
                    game_state.editing_zone_points_input = None
                    game_state.menu_cache = None
                    show_notification(game_state,
                                      "Points edit cancelled",
                                      duration=1.5)
                    menu_key_handled = True

                elif key == 8:  # Backspace
                    if current_points_input:
                        game_state.editing_zone_points_input = current_points_input[:
                                                                                    -1]
                        game_state.menu_cache = None  # Redraw
                    menu_key_handled = True

                elif ord("0") <= key <= ord("9"):  # Numeric Input for Points
                    char = chr(key)
                    max_digits = len(
                        str(getattr(ScoringConstants, "MAX_POINTS", 999)))
                    # Initialize if None, prevent multiple leading zeros unless it's the only digit
                    if current_points_input is None:
                        current_points_input = ""
                    if (char == "0" and not current_points_input
                        ):  # Prevent leading zero if input is empty
                        pass  # Do nothing
                    elif len(current_points_input) < max_digits:
                        game_state.editing_zone_points_input += char
                        game_state.menu_cache = None  # Redraw
                    else:
                        max_pts_val = getattr(ScoringConstants, "MAX_POINTS",
                                              999)
                        show_notification(
                            game_state,
                            f"Max points {max_pts_val}",
                            is_error=True,
                            duration=1.5,
                        )
                    menu_key_handled = True

                # If any key was handled within zone points edit mode
                if menu_key_handled:
                    key_handled_globally = True

            # --- General Menu Navigation (if not in specific edit mode handled above) ---
            if not key_handled_globally:
                if key == ord("m"):  # 'm' always resumes from menu
                    game_state.current_state = CurrentGameState.PLAYING
                    # Reset any lingering menu/edit state just in case
                    from utils import (
                        _reset_all_menu_editing_states,
                    )  # Import locally if needed

                    _reset_all_menu_editing_states(game_state)
                    game_state.submenu_active = None
                    key_handled_globally = True
                elif key == 8:  # Backspace (general menu back navigation)
                    submenu = getattr(game_state, "submenu_active", None)
                    # If in edit zones list, go back to manage zones submenu
                    if submenu == "edit_zones":
                        game_state.submenu_active = "manage_zones"
                        game_state.menu_cache = None
                    # If in any other submenu, go back to main menu
                    elif submenu is not None:
                        game_state.submenu_active = None
                        game_state.menu_cache = None
                    # If in main menu, backspace does nothing (or could resume?) - current behavior: nothing
                    # else: game_state.current_state = CurrentGameState.PLAYING ...
                    key_handled_globally = True
                elif key == 27:  # Escape always resumes from menu
                    game_state.current_state = CurrentGameState.PLAYING
                    # Reset any lingering menu/edit state
                    from utils import _reset_all_menu_editing_states

                    _reset_all_menu_editing_states(game_state)
                    game_state.submenu_active = None
                    key_handled_globally = True

        # Handle input in PLAYING state
        elif game_state.current_state == CurrentGameState.PLAYING:
            key_handled_in_playing = False

            # Zone drawing input... (only relevant if drawing mode is active)
            if getattr(game_state, "drawing", False):
                if (ord("0") <= key <=
                        ord("9")):  # Numeric input for points while drawing
                    max_digits = len(
                        str(getattr(ScoringConstants, "MAX_POINTS", 999)))
                    current_draw_input = getattr(game_state,
                                                 "drawing_points_input", "")
                    char = chr(key)
                    if char == "0" and not current_draw_input:
                        pass  # Ignore leading zero
                    elif len(current_draw_input) < max_digits:
                        game_state.drawing_points_input += char
                    else:
                        show_notification(
                            game_state,
                            f"Max points {ScoringConstants.MAX_POINTS}",
                            is_error=True,
                            duration=1.5,
                        )
                    key_handled_in_playing = True
                elif key == 8:  # Backspace for points while drawing
                    current_draw_input = getattr(game_state,
                                                 "drawing_points_input", "")
                    if current_draw_input:
                        game_state.drawing_points_input = current_draw_input[:
                                                                             -1]
                    key_handled_in_playing = True
                # Note: Enter/confirm for drawing is handled by mouse up event in utils.py

            # Standard playing keys (if not handled by drawing input)
            if not key_handled_in_playing:
                if key == ord("m"):  # 'm' opens menu
                    game_state.current_state = CurrentGameState.MENU
                    game_state.submenu_active = None  # Ensure starting at main menu
                    game_state.menu_cache = None  # Clear menu cache
                    # Reset drawing state if menu is opened
                    game_state.drawing = False
                    game_state.temp_zone = None
                    game_state.start_x = None
                    game_state.start_y = None
                    game_state.drawing_points_input = ""
                    key_handled_in_playing = True
                elif key == ord("s"):  # 's' toggles drawing mode
                    game_state.drawing = not getattr(game_state, "drawing",
                                                     False)
                    show_notification(
                        game_state,
                        f"Drawing Mode: {'ON' if game_state.drawing else 'OFF'}",
                    )
                    # Reset drawing state variables whenever toggling
                    game_state.temp_zone = None
                    game_state.start_x = None
                    game_state.start_y = None
                    game_state.drawing_points_input = ""
                    key_handled_in_playing = True
                elif key == ord("p"):  # 'p' pauses game
                    game_state.current_state = CurrentGameState.PAUSED
                    show_notification(game_state, "Game Paused",
                                      duration=0)  # Persistent notification
                    key_handled_in_playing = True
                elif key == 27:  # Escape (in PLAYING state) -> Go to CONFIRM_QUIT
                    game_state.previous_state_before_quit_confirm = (
                        CurrentGameState.PLAYING)
                    game_state.current_state = CurrentGameState.CONFIRM_QUIT
                    # Reset drawing state if quitting
                    game_state.drawing = False
                    game_state.temp_zone = None
                    game_state.start_x = None
                    game_state.start_y = None
                    game_state.drawing_points_input = ""
                    key_handled_in_playing = True
                    logger.debug(
                        "Escape key in PLAYING state, entering CONFIRM_QUIT.")

            if key_handled_in_playing:
                key_handled_globally = True

        # Handle input in PAUSED state
        elif game_state.current_state == CurrentGameState.PAUSED:
            if key == ord("p"):  # 'p' resumes from pause
                game_state.current_state = CurrentGameState.PLAYING
                show_notification(game_state, "Resuming...", duration=1.0)
                key_handled_globally = True
            elif key == 27:  # Escape (in PAUSED state) -> Go to CONFIRM_QUIT
                game_state.previous_state_before_quit_confirm = CurrentGameState.PAUSED
                game_state.current_state = CurrentGameState.CONFIRM_QUIT
                key_handled_globally = True
                logger.debug(
                    "Escape key in PAUSED state, entering CONFIRM_QUIT.")

        # Handle input in GAME_OVER state
        elif game_state.current_state == CurrentGameState.GAME_OVER:
            if key == ord("n"):  # 'n' starts new game
                reset_game(
                    game_state)  # Resets score, timer, logger session, etc.
                game_state.current_state = (
                    CurrentGameState.PLAYING
                )  # Changed to go directly to PLAYING instead of name input
                game_state.win_condition_met = False  # Reset win flag
                key_handled_globally = True
            elif key == ord("m"):  # 'm' goes to main menu (previously 'l' for leaderboard)
                game_state.current_state = CurrentGameState.MENU
                game_state.submenu_active = None  # Go to main menu
                game_state.menu_cache = None  # Clear menu cache
                game_state.win_condition_met = False  # Reset win flag
                key_handled_globally = True
            elif key == ord("h"):  # 'h' shows heatmap
                try:
                    from ui_screens import display_heatmap_modal
                    # Get the mouse callback function for restoring after modal
                    from utils import mouse_callback
                    display_heatmap_modal(game_state, mouse_callback, game_state)
                    key_handled_globally = True
                except Exception as e:
                    logger.exception(f"Error showing heatmap from keyboard shortcut: {e}")
                    show_notification(game_state, "Error displaying heatmap", is_error=True)
            elif key == 27:  # Escape (in GAME_OVER state) -> Go to CONFIRM_QUIT
                game_state.previous_state_before_quit_confirm = (
                    CurrentGameState.GAME_OVER)
                game_state.current_state = CurrentGameState.CONFIRM_QUIT
                key_handled_globally = True
                logger.debug(
                    "Escape key in GAME_OVER state, entering CONFIRM_QUIT.")

        # Handle input in ZONE_EDITING state (Interactive move/resize)
        # Primarily mouse-driven, but ESC cancels
        elif game_state.current_state == CurrentGameState.ZONE_EDITING:
            if key == 27:  # Escape cancels interactive editing
                logger.debug(
                    "Escape pressed during interactive zone edit. Cancelling.")
                # Revert potentially modified zone if dragging was in progress
                if (getattr(game_state, "drag_start_pos", None) and getattr(
                        game_state, "original_zone_on_drag_start", None)
                        and getattr(game_state, "selected_zone_for_edit",
                                    None) is not None
                        and 0 <= game_state.selected_zone_for_edit < len(
                            getattr(game_state, "scoring_zones", []))):
                    # Revert to original zone state before drag started
                    game_state.scoring_zones[
                        game_state.selected_zone_for_edit] = (
                            game_state.original_zone_on_drag_start)
                    # Recalculate special hole in case the reverted zone was it
                    game_state.special_hole = set_special_hole(
                        game_state.scoring_zones)

                # Reset all interactive editing state variables
                game_state.zone_editing_action = None
                game_state.drag_start_pos = None
                game_state.selected_zone_for_edit = None
                game_state.original_zone_on_drag_start = None

                # Return to previous state (likely MENU)
                try:
                    prev_state = getattr(game_state, "previous_state", None)
                    game_state.current_state = (prev_state if prev_state else
                                                CurrentGameState.MENU)
                except AttributeError:
                    game_state.current_state = CurrentGameState.MENU
                game_state.previous_state = None  # Clear the stored previous state

                show_notification(game_state, "Zone Edit Cancelled")
                game_state.menu_cache = None  # Force menu redraw if returning to menu
                key_handled_globally = True

        # --- Global Toggles (Can be used in multiple states, check not handled yet) ---
        if not key_handled_globally:
            # Allow debug toggles even when paused or in menu? Yes.
            if key == ord("d"):  # Toggle debug logging
                game_state.debug_mode = not getattr(game_state, "debug_mode",
                                                    False)
                log_level = logging.DEBUG if game_state.debug_mode else logging.INFO
                logging.getLogger().setLevel(log_level)
                # Apply level to handlers too
                for h in logging.getLogger().handlers:
                    h.setLevel(log_level)
                show_notification(
                    game_state,
                    f"Debug Mode: {'ON' if game_state.debug_mode else 'OFF'}",
                )
                key_handled_globally = True  # Mark handled
            elif key == ord("b"):  # Toggle debug overlay
                game_state.show_debug_overlay = not getattr(
                    game_state, "show_debug_overlay", False)
                show_notification(
                    game_state,
                    f"Debug Overlay: {'ON' if game_state.show_debug_overlay else 'OFF'}",
                )
                key_handled_globally = True  # Mark handled

    # Return the key code that was pressed (or -1 if none / window closed)
    # The main loop can use this for general checks (like window closing independent of game state)
    # A return value of None specifically indicates clean_exit was called.
    return key
