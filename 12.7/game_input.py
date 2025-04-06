# game_input.py
import logging
from typing import Any, Optional

import cv2
import pygame  # Keep for constants like K_RETURN etc. used in menu/game over logic

# Import clean_exit from the correct location
from cleanup_utils import clean_exit

# Import constants, utils, and specific game states/functions
from constants import GameConstants, PlayerConstants, ScoringConstants, UIConstants

# Import necessary utility functions from the CORRECT files
from game_state_helpers import (  # Helpers that were moved; Removed reset_game from here
    set_special_hole,
    show_notification,
)
from game_state_utils import (
    reset_game,
)  # Utils that remained (or need to be here); Add other imports from utils if needed directly here

# Import GameState enum from the NEW location
from game_types import CurrentGameState  # Correct location

logger = logging.getLogger(__name__)


def _handle_input(game_state: Any) -> Optional[int]:
    """Handles keyboard input using cv2.waitKey."""
    # (Function body unchanged - it will now use reset_game imported from game_state_utils)
    raw_key = -1
    key = -1
    try:
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 1:
            raw_key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY)
            key = raw_key & 0xFF
        else:
            # Window closed, return -1 or None to signal loop exit?
            # Returning -1 for now, game loop checks window property anyway.
            return key # -1 or 255
    except cv2.error as e:
        logger.warning(f"waitKey/getWindowProperty error: {e}")
        return -1 # Error occurred

    key_handled_globally = False # Flag to prevent redundant processing

    # <<< MODIFIED: Handle 'q' - Go to CONFIRM_QUIT state >>>
    if key == ord("q"):
        # Only trigger confirmation if not already confirming or in name input
        if game_state.current_state not in [CurrentGameState.CONFIRM_QUIT, CurrentGameState.GETTING_PLAYER_NAME]:
            game_state.previous_state_before_quit_confirm = game_state.current_state
            game_state.current_state = CurrentGameState.CONFIRM_QUIT
            key_handled_globally = True
            logger.debug("Quit key pressed, entering CONFIRM_QUIT state.")
        # If 'q' is pressed while already confirming, let the CONFIRM_QUIT block handle it (treat as 'cancel')
        # Or potentially handle it as 'confirm'? Decided to let it be handled as cancel below.
    # <<< END MODIFICATION >>>

    if key != -1 and key != 255 and not key_handled_globally: # Process other keys if not handled globally

        # <<< ADDED: Handle input in CONFIRM_QUIT state >>>
        if game_state.current_state == CurrentGameState.CONFIRM_QUIT:
            if key == ord('y'):
                logger.info("Quit confirmed via 'y'.")
                clean_exit(
                    game_state.cap,
                    game_state.background_music,
                    game_state.background_music_on,
                    game_state,
                )
                return None # Signal exit
            elif key == ord('n') or key == 27 or key == 8 or key == ord('q'): # N, Esc, Backspace, or Q again cancels
                logger.debug("Quit cancelled.")
                # Restore the previous state
                game_state.current_state = getattr(game_state, 'previous_state_before_quit_confirm', CurrentGameState.PLAYING)
                key_handled_globally = True # Mark handled
            # Ignore other keys in this state
            # Return the key so the loop continues if quit wasn't confirmed
            return key

        # <<< END ADDED BLOCK >>>

        # --- Existing Input Handling (ensure key_handled_globally is respected) ---
        # (Wrap existing state-specific logic in checks like 'if not key_handled_globally:')
        # OR rely on the fact that CONFIRM_QUIT block returns early or sets the flag

        if not key_handled_globally and game_state.current_state == CurrentGameState.GETTING_PLAYER_NAME:
            if key == 13:  # Enter
                entered_name = game_state.current_player_name_input.strip()
                if not entered_name:
                    show_notification(
                        game_state,
                        "Player name cannot be empty!",
                        is_error=True,
                        duration=2.0,
                    )
                else:
                    try:
                        if game_state.players:
                            game_state.players[0].name = entered_name
                            show_notification(
                                game_state, f"Welcome, {entered_name}!", duration=2.0
                            )
                            game_state.player_name_input_active = False
                            game_state.current_state = CurrentGameState.PLAYING
                        else:
                            show_notification(
                                game_state, "Error: Player list missing!", is_error=True
                            )
                    except Exception as e:
                        show_notification(
                            game_state, "Error starting game!", is_error=True
                        )
                key_handled_globally = True
            elif key == 27:  # Escape
                if game_state.players:
                    game_state.players[0].name = "Player 1" # Use default
                    game_state.player_name_input_active = False
                    game_state.current_state = CurrentGameState.PLAYING
                    show_notification(
                        game_state, "Using default name 'Player 1'", duration=2.0
                    )
                else:
                    show_notification(
                        game_state, "Error: Player list missing!", is_error=True
                    )
                key_handled_globally = True
            elif key == 8:  # Backspace
                if game_state.current_player_name_input:
                    game_state.current_player_name_input = (
                        game_state.current_player_name_input[:-1]
                    )
                key_handled_globally = True
            elif key >= 32 and key <= 126:  # Printable ASCII
                char = chr(key)
                if char in PlayerConstants.ALLOWED_PLAYER_NAME_CHARS:
                    if (
                        len(game_state.current_player_name_input)
                        < PlayerConstants.MAX_PLAYER_NAME_LENGTH
                    ):
                        game_state.current_player_name_input += char
                    else:
                        show_notification(
                            game_state,
                            f"Max name length ({PlayerConstants.MAX_PLAYER_NAME_LENGTH}) reached",
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
                key_handled_globally = True

        elif not key_handled_globally and game_state.current_state == CurrentGameState.MENU:
            menu_key_handled = False # Flag for specific menu input processing

            # Player Name Editing Logic...
            if (
                game_state.submenu_active == "players"
                and game_state.editing_player_mode == "edit_name"
                and game_state.editing_player_index is not None
            ):
                player_idx = game_state.editing_player_index
                if key == 13:  # Enter
                    new_name = game_state.editing_player_name_input.strip()
                    if not new_name:
                        show_notification(
                            game_state,
                            "Player name cannot be empty!",
                            is_error=True,
                            duration=2.0,
                        )
                    elif 0 <= player_idx < len(game_state.players):
                        game_state.players[player_idx].name = new_name
                        show_notification(
                            game_state,
                            f"Player {player_idx+1} name updated",
                            duration=2.0,
                        )
                        game_state.editing_player_index = None
                        game_state.editing_player_mode = None
                        game_state.editing_player_name_input = None
                        game_state.menu_cache = None # Redraw menu
                    else:
                        show_notification(
                            game_state, "Error saving name!", is_error=True
                        )
                        # Reset state even on error
                        game_state.editing_player_index = None
                        game_state.editing_player_mode = None
                        game_state.editing_player_name_input = None
                        game_state.menu_cache = None
                    menu_key_handled = True
                elif key == 27: # Escape
                    game_state.editing_player_index = None
                    game_state.editing_player_mode = None
                    game_state.editing_player_name_input = None
                    game_state.menu_cache = None
                    show_notification(game_state, "Name edit cancelled", duration=1.5)
                    menu_key_handled = True
                elif key == 8:  # Backspace
                    if game_state.editing_player_name_input:
                        game_state.editing_player_name_input = (
                            game_state.editing_player_name_input[:-1]
                        )
                        game_state.menu_cache = None # Redraw
                    menu_key_handled = True
                elif key >= 32 and key <= 126:  # Printable ASCII
                    char = chr(key)
                    if char in PlayerConstants.ALLOWED_PLAYER_NAME_CHARS:
                        if (
                            len(game_state.editing_player_name_input)
                            < PlayerConstants.MAX_PLAYER_NAME_LENGTH
                        ):
                            game_state.editing_player_name_input += char
                            game_state.menu_cache = None # Redraw
                        else:
                            show_notification(
                                game_state,
                                f"Max {PlayerConstants.MAX_PLAYER_NAME_LENGTH} chars",
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

                if menu_key_handled:
                    key_handled_globally = True

            # Zone Points Editing Logic...
            elif not key_handled_globally and ( # Check flag again
                game_state.submenu_active == "edit_zones"
                and game_state.editing_zone_mode == "edit_points"
                and game_state.editing_zone_index is not None
            ):
                zone_idx = game_state.editing_zone_index
                if key == 13:  # Enter
                    try:
                        new_points_str = game_state.editing_zone_points_input.strip()
                        if not new_points_str:
                            show_notification(
                                game_state, "Points cannot be empty!", is_error=True
                            )
                        else:
                            new_points = int(new_points_str)
                            if not (1 <= new_points <= ScoringConstants.MAX_POINTS):
                                show_notification(
                                    game_state,
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
                                show_notification(
                                    game_state,
                                    f"Zone {zone_idx+1} points updated",
                                    duration=2.0,
                                )
                                # Reset state on success
                                game_state.editing_zone_index = None
                                game_state.editing_zone_mode = None
                                game_state.editing_zone_points_input = None
                                game_state.menu_cache = None
                            else:
                                show_notification(
                                    game_state, "Error saving points (invalid index?)!", is_error=True
                                )
                                # Reset state even on error
                                game_state.editing_zone_index = None
                                game_state.editing_zone_mode = None
                                game_state.editing_zone_points_input = None
                                game_state.menu_cache = None
                    except ValueError:
                        show_notification(
                            game_state, "Invalid points value!", is_error=True
                        )
                        # Don't reset input on ValueError? Or do? Let's reset.
                        # game_state.editing_zone_points_input = "" # Clear input
                        # game_state.menu_cache = None
                    except Exception as e:
                        show_notification(
                            game_state, "Error saving points!", is_error=True
                        )
                        # Reset state on other errors
                        game_state.editing_zone_index = None
                        game_state.editing_zone_mode = None
                        game_state.editing_zone_points_input = None
                        game_state.menu_cache = None
                    menu_key_handled = True
                elif key == 27: # Escape
                    game_state.editing_zone_index = None
                    game_state.editing_zone_mode = None
                    game_state.editing_zone_points_input = None
                    game_state.menu_cache = None
                    show_notification(game_state, "Points edit cancelled", duration=1.5)
                    menu_key_handled = True
                elif key == 8:  # Backspace
                    if game_state.editing_zone_points_input:
                        game_state.editing_zone_points_input = (
                            game_state.editing_zone_points_input[:-1]
                        )
                        game_state.menu_cache = None # Redraw
                    menu_key_handled = True
                elif ord("0") <= key <= ord("9"):  # Numeric input
                    char = chr(key)
                    # Avoid leading zeros unless it's the only digit
                    # if char == '0' and not game_state.editing_zone_points_input:
                    #    pass # Ignore leading zero
                    # else:
                    max_digits = len(str(ScoringConstants.MAX_POINTS))
                    if game_state.editing_zone_points_input is None:
                        game_state.editing_zone_points_input = "" # Initialize if None
                    if len(game_state.editing_zone_points_input) < max_digits:
                         game_state.editing_zone_points_input += char
                         game_state.menu_cache = None # Redraw
                    else:
                         show_notification(
                             game_state,
                             f"Max points {ScoringConstants.MAX_POINTS}",
                             is_error=True,
                             duration=1.5,
                         )
                    menu_key_handled = True

                if menu_key_handled:
                    key_handled_globally = True


            # General Menu Navigation...
            if not key_handled_globally:
                if key == ord("m"): # 'm' always resumes from menu
                    game_state.current_state = CurrentGameState.PLAYING
                    # Reset any lingering menu/edit state
                    game_state.editing_player_index = None
                    game_state.editing_player_mode = None
                    game_state.editing_player_name_input = None
                    game_state.editing_zone_index = None
                    game_state.editing_zone_mode = None
                    game_state.editing_zone_points_input = None
                    game_state.submenu_active = None
                    game_state.menu_cache = None
                    key_handled_globally = True
                elif key == 8:  # Backspace (general menu back navigation)
                    if game_state.editing_zone_mode: # If editing zone points/etc.
                        game_state.editing_zone_index = None
                        game_state.editing_zone_mode = None
                        game_state.editing_zone_points_input = None
                        game_state.menu_cache = None # Redraw parent menu
                    elif game_state.editing_player_mode: # If editing player name
                         game_state.editing_player_index = None
                         game_state.editing_player_mode = None
                         game_state.editing_player_name_input = None
                         game_state.menu_cache = None # Redraw parent menu
                    elif game_state.submenu_active == "edit_zones": # If in edit list, go back to manage zones
                         game_state.submenu_active = "manage_zones"
                         game_state.menu_cache = None
                    elif game_state.submenu_active: # If in any other submenu, go back to main menu
                        game_state.submenu_active = None
                        game_state.menu_cache = None
                    else: # If in main menu, backspace resumes game
                        game_state.current_state = CurrentGameState.PLAYING
                        game_state.submenu_active = None
                        game_state.menu_cache = None
                    key_handled_globally = True
                elif key == 27: # Escape always resumes from menu
                    game_state.current_state = CurrentGameState.PLAYING
                    # Reset any lingering menu/edit state
                    game_state.editing_player_index = None
                    game_state.editing_player_mode = None
                    game_state.editing_player_name_input = None
                    game_state.editing_zone_index = None
                    game_state.editing_zone_mode = None
                    game_state.editing_zone_points_input = None
                    game_state.submenu_active = None
                    game_state.menu_cache = None
                    key_handled_globally = True

        elif not key_handled_globally and game_state.current_state == CurrentGameState.PLAYING:
            key_handled_in_playing = False

            # Zone drawing input...
            if game_state.drawing:
                if ord("0") <= key <= ord("9"):
                    # Limit points input length (e.g., max 3 digits)
                    if len(game_state.drawing_points_input) < 3:
                        game_state.drawing_points_input += chr(key)
                    else:
                        show_notification(
                            game_state, "Max 3 digits for points", duration=1.0
                        )
                    key_handled_in_playing = True
                elif key == 8:  # Backspace
                    if game_state.drawing_points_input:
                        game_state.drawing_points_input = (
                            game_state.drawing_points_input[:-1]
                        )
                    key_handled_in_playing = True

            # Standard playing keys...
            if not key_handled_in_playing:
                if key == ord("m"): # 'm' opens menu
                    game_state.current_state = CurrentGameState.MENU
                    game_state.submenu_active = None
                    game_state.menu_cache = None # Clear menu cache
                    key_handled_in_playing = True
                elif key == ord("s"): # 's' toggles drawing mode
                    game_state.drawing = not game_state.drawing
                    show_notification(
                        game_state,
                        f"Drawing Mode: {'ON' if game_state.drawing else 'OFF'}",
                    )
                    # Reset drawing state variables when toggling
                    game_state.temp_zone = None
                    game_state.start_x = None
                    game_state.start_y = None
                    game_state.drawing_points_input = ""
                    key_handled_in_playing = True
                elif key == ord("p"): # 'p' pauses game
                    game_state.current_state = CurrentGameState.PAUSED
                    show_notification(game_state, "Game Paused", duration=0) # Persistent
                    key_handled_in_playing = True
                elif key == 27: # Escape (in PLAYING state) -> Go to CONFIRM_QUIT
                    game_state.previous_state_before_quit_confirm = CurrentGameState.PLAYING
                    game_state.current_state = CurrentGameState.CONFIRM_QUIT
                    key_handled_in_playing = True
                    logger.debug("Escape key in PLAYING state, entering CONFIRM_QUIT.")

            if key_handled_in_playing:
                key_handled_globally = True

        elif not key_handled_globally and game_state.current_state == CurrentGameState.PAUSED:
            if key == ord("p"): # 'p' resumes from pause
                game_state.current_state = CurrentGameState.PLAYING
                show_notification(game_state, "Resuming...", duration=1.0)
                key_handled_globally = True
            elif key == 27: # Escape (in PAUSED state) -> Go to CONFIRM_QUIT
                game_state.previous_state_before_quit_confirm = CurrentGameState.PAUSED
                game_state.current_state = CurrentGameState.CONFIRM_QUIT
                key_handled_globally = True
                logger.debug("Escape key in PAUSED state, entering CONFIRM_QUIT.")


        elif not key_handled_globally and game_state.current_state == CurrentGameState.GAME_OVER:
            if key == ord("n"): # 'n' starts new game
                reset_game(game_state) # Resets score, timer, etc.
                game_state.current_state = CurrentGameState.GETTING_PLAYER_NAME # Go back to name input
                game_state.win_condition_met = False # Reset win flag
                key_handled_globally = True
            elif key == ord("l"): # 'l' goes to leaderboard menu
                game_state.current_state = CurrentGameState.MENU
                game_state.submenu_active = "leaderboard"
                game_state.menu_cache = None
                game_state.win_condition_met = False # Reset win flag
                key_handled_globally = True
            elif key == 27: # Escape (in GAME_OVER state) -> Go to CONFIRM_QUIT
                game_state.previous_state_before_quit_confirm = CurrentGameState.GAME_OVER
                game_state.current_state = CurrentGameState.CONFIRM_QUIT
                key_handled_globally = True
                logger.debug("Escape key in GAME_OVER state, entering CONFIRM_QUIT.")


        elif not key_handled_globally and game_state.current_state == CurrentGameState.ZONE_EDITING:
            if key == 27:  # Escape cancels interactive editing
                # Revert potentially modified zone if dragging
                if (
                    game_state.drag_start_pos
                    and game_state.original_zone_on_drag_start
                    and game_state.selected_zone_for_edit is not None
                    and 0
                    <= game_state.selected_zone_for_edit
                    < len(game_state.scoring_zones)
                ):
                    # Revert to original zone state before drag started
                    game_state.scoring_zones[game_state.selected_zone_for_edit] = (
                        game_state.original_zone_on_drag_start
                    )
                    # Recalculate special hole in case the reverted zone was it
                    game_state.special_hole = set_special_hole(
                        game_state.scoring_zones
                    ) # Use helper

                # Reset all editing state variables
                game_state.zone_editing_action = None
                game_state.drag_start_pos = None
                game_state.selected_zone_for_edit = None
                game_state.original_zone_on_drag_start = None

                # Return to previous state (likely MENU)
                try:
                    game_state.current_state = (
                        game_state.previous_state # Restore state before editing started
                        if game_state.previous_state
                        else CurrentGameState.MENU # Fallback to MENU
                    )
                except AttributeError:
                     game_state.current_state = CurrentGameState.MENU

                game_state.previous_state = None # Clear the stored previous state
                show_notification(game_state, "Zone Edit Cancelled") # Use helper
                game_state.menu_cache = None # Force menu redraw if returning to menu
                key_handled_globally = True

        # Global Toggles (Check not handled globally already)
        if not key_handled_globally:
            if key == ord("d"): # Toggle debug logging
                game_state.debug_mode = not game_state.debug_mode
                log_level = logging.DEBUG if game_state.debug_mode else logging.INFO
                logging.getLogger().setLevel(log_level)
                # Apply level to handlers too
                for h in logging.getLogger().handlers:
                    h.setLevel(log_level)
                show_notification(
                    game_state,
                    f"Debug Mode: {'ON' if game_state.debug_mode else 'OFF'}",
                ) # Use helper
                key_handled_globally = True
            elif key == ord("b"): # Toggle debug overlay
                game_state.show_debug_overlay = not game_state.show_debug_overlay
                show_notification(
                    game_state,
                    f"Debug Overlay: {'ON' if game_state.show_debug_overlay else 'OFF'}",
                ) # Use helper
                key_handled_globally = True

    # Return the key code so the main loop can check for window close events etc.
    # Return None only if clean_exit was called.
    return key