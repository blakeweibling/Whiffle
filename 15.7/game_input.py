# game_input.py
import logging
from typing import Any, Optional

import cv2
import string
import pygame  # Keep for key constants like K_RETURN, K_ESCAPE if needed elsewhere
import time
import ctypes

# Import clean_exit from the correct location
from cleanup_utils import clean_exit

# Import constants, utils, and specific game states/functions
from constants import (
    GameConstants,
    PlayerConstants,
    ScoringConstants,
    UIConstants,
    MenuConstants,
    ReplayConstants,
)

# Import necessary utility functions from the CORRECT files
from game_state_helpers import (
    set_special_hole,
    show_notification,  # Import relevant helpers
    save_zones,
    load_zones,
    clear_zones,
)
from game_state_utils import reset_game, save_settings  # Import reset_game, save_settings

# Import GameState enum from the NEW location
from game_types import CurrentGameState  # Correct location

# Import interaction_utils functions
from interaction_utils import _process_menu_or_modal_click, _process_zone_editing_event
from menu import draw_menu_window
from ui_screens import display_modal_splash

logger = logging.getLogger(__name__)

# Constants for arrow key codes
# OpenCV key codes can vary across systems, so we need to be comprehensive
LEFT_ARROW = 81  # Common OpenCV code
RIGHT_ARROW = 83  # Common OpenCV code
UP_ARROW = 82  # Common OpenCV code
DOWN_ARROW = 84  # Common OpenCV code

# More arrow key codes (some systems use these)
ALT_LEFT_ARROW = 2424832  # Extended code sometimes returned
ALT_RIGHT_ARROW = 2555904
ALT_UP_ARROW = 2490368
ALT_DOWN_ARROW = 2621440

# Additional common arrow key codes
LEFT_ARROW_ALT2 = 37  # Common arrow key code on some systems
RIGHT_ARROW_ALT2 = 39
UP_ARROW_ALT2 = 38
DOWN_ARROW_ALT2 = 40

# Special arrow key codes for some systems
LEFT_ARROW_ALT3 = 65361  # Linux/X11 systems
RIGHT_ARROW_ALT3 = 65363
UP_ARROW_ALT3 = 65362
DOWN_ARROW_ALT3 = 65364


# Function to check if a key is an arrow key
def is_left_arrow(key: int) -> bool:
    """Check if the key code represents a left arrow key."""
    return key in [LEFT_ARROW, ALT_LEFT_ARROW, LEFT_ARROW_ALT2, LEFT_ARROW_ALT3]


def is_right_arrow(key: int) -> bool:
    """Check if the key code represents a right arrow key."""
    return key in [RIGHT_ARROW, ALT_RIGHT_ARROW, RIGHT_ARROW_ALT2, RIGHT_ARROW_ALT3]


def is_up_arrow(key: int) -> bool:
    """Check if the key code represents an up arrow key."""
    return key in [UP_ARROW, ALT_UP_ARROW, UP_ARROW_ALT2, UP_ARROW_ALT3]


def is_down_arrow(key: int) -> bool:
    """Check if the key code represents a down arrow key."""
    return key in [DOWN_ARROW, ALT_DOWN_ARROW, DOWN_ARROW_ALT2, DOWN_ARROW_ALT3]


# Function to initialize player input attributes
def init_player_name_input(game_state: Any) -> None:
    """Initialize player name input attributes in game state."""
    if not hasattr(game_state, "player_name_cursor_pos"):
        game_state.player_name_cursor_pos = 0
    current_input = getattr(game_state, "current_player_name_input", "")
    game_state.player_name_cursor_pos = len(current_input)


def _process_replay_timeline_drag(x: int, y: int, game_state: Any) -> bool:
    """Process dragging on the replay timeline scrubber."""
    # Make sure we have an active replay
    if not hasattr(game_state, "replay_playback") or not game_state.replay_playback:
        return False

    replay = game_state.replay_playback.get("current_replay")
    if not replay or not replay.frames:
        return False

    # Check if we're in replay playback menu
    if (
        game_state.current_state != CurrentGameState.MENU
        or game_state.submenu_active != "replay_playback"
    ):
        return False

    # Get timeline dimensions from our menu (these match what's drawn in the UI)
    from submenu_draw_functions import _draw_replay_playback_submenu

    # Find the timeline in the submenu items
    timeline_rect = None
    for rect, action, _ in game_state.submenu_items:
        if action == "replay_timeline":
            timeline_rect = rect
            break

    if not timeline_rect:
        return False

    timeline_x, timeline_y, timeline_width, timeline_height = timeline_rect

    # Calculate the position within the timeline
    if (
        x < timeline_x
        or x > timeline_x + timeline_width
        or y < timeline_y
        or y > timeline_y + timeline_height
    ):
        game_state.replay_playback["timeline_dragging"] = False
        return False

    # Calculate relative position (0.0 to 1.0)
    relative_pos = (x - timeline_x) / timeline_width

    # Map to frame index
    frame_index = min(
        len(replay.frames) - 1, max(0, int(relative_pos * len(replay.frames)))
    )

    # Update frame index
    game_state.replay_playback["current_frame_idx"] = frame_index
    game_state.menu_cache = None  # Force UI redraw

    # Update timeline_dragging flag
    game_state.replay_playback["timeline_dragging"] = True

    return True


def _handle_input(game_state: Any) -> Optional[int]:
    """Handles keyboard input using cv2.waitKey, including heatmap dismissal."""
    # Make sure we have access to UIConstants at function level
    from constants import (
        UIConstants,
    )  # Define it at the function scope to ensure it's available

    raw_key = -1
    key = -1  # Default value if no key is pressed or window is closed

    # Get key press
    try:
        # Check if window is valid before waiting for key
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 1:
            raw_key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY)  # Get raw key code
            if raw_key != -1:  # Only process if a key was actually pressed
                key = raw_key & 0xFF  # Get the significant byte

                # Special handling for extended keys (like arrow keys)
                # Check if this is an extended key (first byte is 0, but raw_key != 0)
                if key == 0 and raw_key != 0:
                    # This is an extended key, use the full raw_key value
                    key = raw_key

                # Special direct handling for arrow keys based on common values
                if (
                    raw_key == 0x250000 or raw_key == 0xFF51 or raw_key == 2424832
                ):  # Left arrow variations
                    key = LEFT_ARROW
                elif (
                    raw_key == 0x270000 or raw_key == 0xFF53 or raw_key == 2555904
                ):  # Right arrow variations
                    key = RIGHT_ARROW
                elif (
                    raw_key == 0x260000 or raw_key == 0xFF52 or raw_key == 2490368
                ):  # Up arrow variations
                    key = UP_ARROW
                elif (
                    raw_key == 0x280000 or raw_key == 0xFF54 or raw_key == 2621440
                ):  # Down arrow variations
                    key = DOWN_ARROW
                # Handle Windows-specific arrow keys that appear as key=0
                elif key == 0:
                    # Windows often reports arrow keys as raw_key=0 with special handling needed
                    # Check for these keys in GETTING_PLAYER_NAME state
                    if (
                        getattr(game_state, "current_state", None)
                        == CurrentGameState.GETTING_PLAYER_NAME
                    ):
                        # For simplicity, always treat key=0 as LEFT arrow (most commonly needed for editing)
                        logger.debug(
                            f"Detected potential arrow key: key=0, raw_key={raw_key}, treating as LEFT arrow"
                        )

                        current_input = getattr(
                            game_state, "current_player_name_input", ""
                        )
                        cursor_pos = getattr(game_state, "player_name_cursor_pos", 0)

                        # Always treat as LEFT ARROW for consistency and because it's more commonly needed
                        if cursor_pos > 0:
                            game_state.player_name_cursor_pos = cursor_pos - 1
                            logger.debug(
                                f"Simulated left arrow, moved cursor to {cursor_pos-1}"
                            )

                # Debug log for key presses when in username input screen
                if (
                    getattr(game_state, "current_state", None)
                    == CurrentGameState.GETTING_PLAYER_NAME
                ):
                    logger.debug(
                        f"Key pressed in username input: key={key}, raw_key={raw_key}"
                    )
                else:
                    logger.debug(f"Key pressed: {key} (raw: {raw_key})")
        else:
            # Window is closed or not visible, no input can be processed
            logger.debug("Window closed or not visible, skipping input.")
            return -1  # Return -1 to indicate no valid input / potential closure
    except cv2.error as e:
        # Handle potential errors if window disappears unexpectedly
        logger.warning(f"Error getting window property or waiting for key: {e}")
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

    # --- Handle Versus Results Dismissal ---
    if getattr(game_state, "showing_versus_results", False):
        if key == ord("r") or key == ord("R"):
            logger.info("Versus mode rematch requested with 'R' key")
            from versus_mode import start_rematch
            start_rematch(game_state)
            return key
        if key == ord("m") or key == ord("M") or key == 27:
            logger.info("Versus mode results dismissed")
            game_state.current_state = getattr(
                game_state, "previous_state", CurrentGameState.MENU
            )
            game_state.previous_state = None
            game_state.versus_mode_active = False
            game_state.showing_versus_results = False
            game_state.versus_results_frame = None
            game_state.versus_results_buttons = {}
            return key
        return key

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
            CurrentGameState.GETTING_PLAYFIELD,
        ]:
            # Store the state we were in before prompting for quit
            game_state.previous_state_before_quit_confirm = game_state.current_state
            game_state.current_state = CurrentGameState.CONFIRM_QUIT
            key_handled_globally = True
            logger.debug("Quit key ('q') pressed, entering CONFIRM_QUIT state.")
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
                    CurrentGameState.PLAYING,  # Default to PLAYING if somehow unset
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

            # Initialize cursor position if not already set
            if not hasattr(game_state, "player_name_cursor_pos"):
                init_player_name_input(game_state)

            if key == 13:  # Enter key
                entered_name = getattr(
                    game_state, "current_player_name_input", ""
                ).strip()
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
                            game_state.last_player_name = entered_name
                            save_settings(game_state)
                            show_notification(
                                game_state, f"Welcome, {entered_name}!", duration=2.0
                            )
                            game_state.player_name_input_active = (
                                False  # Flag to stop drawing input screen
                            )
                            game_state.current_state = (
                                CurrentGameState.GETTING_PLAYFIELD
                            )  # Proceed to playfield selection
                        except IndexError:
                            show_notification(
                                game_state, "Error: Player list invalid!", is_error=True
                            )
                        except Exception as e:
                            logger.error(f"Error setting player name: {e}")
                            show_notification(
                                game_state, "Error starting game!", is_error=True
                            )
                    else:
                        show_notification(
                            game_state, "Error: Player list missing!", is_error=True
                        )
                player_name_key_handled = True
            elif key == 27:  # Escape key (use default name)
                if hasattr(game_state, "players") and game_state.players:
                    try:
                        game_state.players[0].name = "Player 1"  # Use default
                        game_state.last_player_name = "Player 1"
                        save_settings(game_state)
                        game_state.player_name_input_active = False
                        game_state.current_state = CurrentGameState.GETTING_PLAYFIELD
                        show_notification(
                            game_state, "Using default name 'Player 1'", duration=2.0
                        )
                    except IndexError:
                        show_notification(
                            game_state, "Error: Player list invalid!", is_error=True
                        )
                    except Exception as e:
                        logger.error(f"Error setting default player name: {e}")
                        show_notification(
                            game_state, "Error starting game!", is_error=True
                        )
                else:
                    show_notification(
                        game_state, "Error: Player list missing!", is_error=True
                    )
                player_name_key_handled = True
            elif key == 8:  # Backspace key
                current_input = getattr(game_state, "current_player_name_input", "")
                cursor_pos = getattr(
                    game_state, "player_name_cursor_pos", len(current_input)
                )

                if current_input and cursor_pos > 0:
                    # Delete character before cursor
                    game_state.current_player_name_input = (
                        current_input[: cursor_pos - 1] + current_input[cursor_pos:]
                    )
                    game_state.player_name_cursor_pos = cursor_pos - 1
                player_name_key_handled = True
            # Handle left and right arrow keys for cursor movement
            elif (
                is_left_arrow(key) or key == 2 or key == 75
            ):  # 2,75 are common numpad/directional key codes
                cursor_pos = getattr(game_state, "player_name_cursor_pos", 0)
                if cursor_pos > 0:
                    game_state.player_name_cursor_pos = cursor_pos - 1
                    logger.debug(
                        f"Left arrow detected (key={key}), moved cursor to {cursor_pos-1}"
                    )
                player_name_key_handled = True
            elif (
                is_right_arrow(key) or key == 3 or key == 77 or key == 102
            ):  # 3,77,102 are common numpad/directional key codes
                current_input = getattr(game_state, "current_player_name_input", "")
                cursor_pos = getattr(game_state, "player_name_cursor_pos", 0)
                if cursor_pos < len(current_input):
                    game_state.player_name_cursor_pos = cursor_pos + 1
                    logger.debug(
                        f"Right arrow detected (key={key}), moved cursor to {cursor_pos+1}"
                    )
                player_name_key_handled = True
            elif key >= 32 and key <= 126:  # Printable ASCII characters
                char = chr(key)
                allowed_chars = getattr(
                    PlayerConstants,
                    "ALLOWED_PLAYER_NAME_CHARS",
                    string.ascii_letters + string.digits + " _-",
                )  # Default allowed chars
                max_len = getattr(PlayerConstants, "MAX_PLAYER_NAME_LENGTH", 15)
                current_input = getattr(game_state, "current_player_name_input", "")
                cursor_pos = getattr(
                    game_state, "player_name_cursor_pos", len(current_input)
                )

                if char in allowed_chars:
                    if len(current_input) < max_len:
                        # Insert character at cursor position
                        new_input = (
                            current_input[:cursor_pos]
                            + char
                            + current_input[cursor_pos:]
                        )
                        game_state.current_player_name_input = new_input
                        game_state.player_name_cursor_pos = cursor_pos + 1
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
        # Handle input in GETTING_PLAYFIELD state
        elif game_state.current_state == CurrentGameState.GETTING_PLAYFIELD:
            selection_key_handled = False
            if key in [ord("1"), ord("w"), ord("W"), 13]:  # 1/W/Enter = Whiffle
                if game_state.set_playfield("whiffle"):
                    game_state.current_state = CurrentGameState.PLAYING
                selection_key_handled = True
            elif key in [ord("2"), ord("f"), ord("F")]:  # 2/F = Five Star
                if game_state.set_playfield("fivestar"):
                    game_state.current_state = CurrentGameState.PLAYING
                selection_key_handled = True
            elif key == 27:  # Escape key defaults to Whiffle
                if game_state.set_playfield("whiffle"):
                    game_state.current_state = CurrentGameState.PLAYING
                selection_key_handled = True

            if selection_key_handled:
                return key

        # Handle input in MENU state
        elif game_state.current_state == CurrentGameState.MENU:
            menu_key_handled = False  # Flag for specific menu input processing

            # --- Handle Specific Input Modes within Menu (like editing name/points) ---
            # Player Name Editing Logic...
            if (
                getattr(game_state, "submenu_active", None) == "players"
                and getattr(game_state, "editing_player_mode", None) == "edit_name"
                and getattr(game_state, "editing_player_index", None) is not None
            ):

                player_idx = game_state.editing_player_index
                current_edit_input = getattr(
                    game_state, "editing_player_name_input", ""
                )

                if key == 13:  # Enter - Save Name
                    new_name = current_edit_input.strip()
                    if not new_name:
                        show_notification(
                            game_state,
                            "Player name cannot be empty!",
                            is_error=True,
                            duration=2.0,
                        )
                    elif 0 <= player_idx < len(getattr(game_state, "players", [])):
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
                            logger.error(f"Error updating player name in list: {e}")
                            show_notification(
                                game_state, "Error saving name!", is_error=True
                            )
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
                    show_notification(game_state, "Name edit cancelled", duration=1.5)
                    menu_key_handled = True

                elif key == 8:  # Backspace
                    if current_edit_input:
                        game_state.editing_player_name_input = current_edit_input[:-1]
                        game_state.menu_cache = None  # Redraw menu to show change
                    menu_key_handled = True

                elif key >= 32 and key <= 126:  # Printable ASCII for Name Input
                    char = chr(key)
                    allowed_chars = getattr(
                        PlayerConstants,
                        "ALLOWED_PLAYER_NAME_CHARS",
                        string.ascii_letters + string.digits + " _-",
                    )
                    max_len = getattr(PlayerConstants, "MAX_PLAYER_NAME_LENGTH", 15)
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
            elif (
                not key_handled_globally
                and getattr(game_state, "submenu_active", None) == "edit_zones"
                and getattr(game_state, "editing_zone_mode", None) == "edit_points"
                and getattr(game_state, "editing_zone_index", None) is not None
            ):

                zone_idx = game_state.editing_zone_index
                current_points_input = getattr(
                    game_state, "editing_zone_points_input", ""
                )

                if key == 13:  # Enter - Save Points
                    try:
                        new_points_str = current_points_input.strip()
                        if not new_points_str:
                            show_notification(
                                game_state, "Points cannot be empty!", is_error=True
                            )
                        else:
                            new_points = int(new_points_str)
                            max_pts = getattr(ScoringConstants, "MAX_POINTS", 999)
                            if not (1 <= new_points <= max_pts):
                                show_notification(
                                    game_state,
                                    f"Points must be 1-{max_pts}",
                                    is_error=True,
                                )
                            elif (
                                0
                                <= zone_idx
                                < len(getattr(game_state, "scoring_zones", []))
                            ):
                                # Update points in the zone tuple (tuples are immutable, so create new one)
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
                        show_notification(
                            game_state, "Invalid points value!", is_error=True
                        )
                        # Optionally clear input on error: game_state.editing_zone_points_input = ""
                    except Exception as e:
                        logger.error(f"Error saving zone points: {e}")
                        show_notification(
                            game_state, "Error saving points!", is_error=True
                        )
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
                    show_notification(game_state, "Points edit cancelled", duration=1.5)
                    menu_key_handled = True

                elif key == 8:  # Backspace
                    current_points_input = getattr(
                        game_state, "editing_zone_points_input", ""
                    )
                    if current_points_input:
                        game_state.editing_zone_points_input = current_points_input[:-1]
                        game_state.menu_cache = None
                    menu_key_handled = True

                elif key == 13:  # Enter key to save
                    # Trigger the save_zone_points action
                    from interaction_utils import _process_menu_or_modal_click

                    # Simulate a click on a save button by calling the action directly
                    _process_menu_or_modal_click(
                        0, 0, game_state, override_action="save_zone_points"
                    )
                    menu_key_handled = True

                # Handle digit input for zone points
                elif ord("0") <= key <= ord("9"):
                    char = chr(key)
                    max_digits = len(str(getattr(ScoringConstants, "MAX_POINTS", 999)))
                    # Initialize if None, prevent multiple leading zeros unless it's the only digit
                    if current_points_input is None:
                        current_points_input = ""
                    if (
                        char == "0" and not current_points_input
                    ):  # Prevent leading zero if input is empty
                        pass  # Do nothing
                    elif len(current_points_input) < max_digits:
                        game_state.editing_zone_points_input += char
                        game_state.menu_cache = None  # Redraw
                    else:
                        max_pts_val = getattr(ScoringConstants, "MAX_POINTS", 999)
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
                from interaction_utils import _reset_all_menu_editing_states

                if key == ord("m"):  # 'm' always resumes from menu
                    game_state.current_state = CurrentGameState.PLAYING
                    _reset_all_menu_editing_states(game_state)
                    game_state.submenu_active = None
                    game_state.menu_cache = None
                    key_handled_globally = True
                elif key in (8, 27):  # Backspace or Escape
                    submenu = getattr(game_state, "submenu_active", None)
                    if submenu == "edit_zones":
                        # If in edit zones list, go back to manage zones submenu
                        game_state.submenu_active = "manage_zones"
                        game_state.menu_cache = None
                    elif submenu is not None:
                        # If in any other submenu, go back to main menu
                        game_state.submenu_active = None
                        game_state.menu_cache = None
                    else:
                        # If already in main menu, close menu and resume game
                        game_state.current_state = CurrentGameState.PLAYING
                        _reset_all_menu_editing_states(game_state)
                        game_state.submenu_active = None
                        game_state.menu_cache = None
                    key_handled_globally = True

        # Handle input in PLAYING state
        elif game_state.current_state == CurrentGameState.PLAYING:
            key_handled_in_playing = False

            # Zone drawing input... (only relevant if drawing mode is active)
            if getattr(game_state, "drawing", False):
                if (
                    ord("0") <= key <= ord("9")
                ):  # Numeric input for points while drawing
                    max_digits = len(str(getattr(ScoringConstants, "MAX_POINTS", 999)))
                    current_draw_input = getattr(game_state, "drawing_points_input", "")
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
                    current_draw_input = getattr(game_state, "drawing_points_input", "")
                    if current_draw_input:
                        game_state.drawing_points_input = current_draw_input[:-1]
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
                    game_state.drawing = not getattr(game_state, "drawing", False)
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
                    show_notification(
                        game_state, "Game Paused", duration=0
                    )  # Persistent notification
                    key_handled_in_playing = True
                elif key == 27:  # Escape (in PLAYING state) -> Go to CONFIRM_QUIT
                    game_state.previous_state_before_quit_confirm = (
                        CurrentGameState.PLAYING
                    )
                    game_state.current_state = CurrentGameState.CONFIRM_QUIT
                    # Reset drawing state if quitting
                    game_state.drawing = False
                    game_state.temp_zone = None
                    game_state.start_x = None
                    game_state.start_y = None
                    game_state.drawing_points_input = ""
                    key_handled_in_playing = True
                    logger.debug("Escape key in PLAYING state, entering CONFIRM_QUIT.")

            if key_handled_in_playing:
                key_handled_globally = True

        # Handle input in PAUSED state
        elif game_state.current_state == CurrentGameState.PAUSED:
            if key == ord("p"):  # 'p' resumes from pause
                game_state.current_state = CurrentGameState.PLAYING
                game_state.has_paused_and_resumed = True
                show_notification(game_state, "Resuming...", duration=1.0)
                key_handled_globally = True
            elif key == 27:  # Escape (in PAUSED state) -> Go to CONFIRM_QUIT
                game_state.previous_state_before_quit_confirm = CurrentGameState.PAUSED
                game_state.current_state = CurrentGameState.CONFIRM_QUIT
                key_handled_globally = True
                logger.debug("Escape key in PAUSED state, entering CONFIRM_QUIT.")

        # Handle input in GAME_OVER state
        elif game_state.current_state == CurrentGameState.GAME_OVER:
            if key == ord("n"):  # 'n' starts new game
                # Upload pending scores (screenshot + score) to leaderboard before starting new game
                if hasattr(game_state, "leaderboard") and game_state.leaderboard:
                    if hasattr(game_state.leaderboard, "flush_pending_scores"):
                        try:
                            n = game_state.leaderboard.flush_pending_scores()
                            if n > 0:
                                show_notification(
                                    game_state,
                                    "Score submitted to leaderboard",
                                    duration=2.0,
                                )
                        except Exception as e:
                            logger.error(f"Error flushing leaderboard on new game: {e}")
                reset_game(game_state)  # Resets score, timer, logger session, etc.
                game_state.current_state = (
                    CurrentGameState.PLAYING
                )  # Changed to go directly to PLAYING instead of name input
                game_state.win_condition_met = False  # Reset win flag
                key_handled_globally = True
            elif key == ord(
                "m"
            ):  # 'm' goes to main menu (previously 'l' for leaderboard)
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
                    logger.exception(
                        f"Error showing heatmap from keyboard shortcut: {e}"
                    )
                    show_notification(
                        game_state, "Error displaying heatmap", is_error=True
                    )
            elif key == 27:  # Escape (in GAME_OVER state) -> Go to CONFIRM_QUIT
                game_state.previous_state_before_quit_confirm = (
                    CurrentGameState.GAME_OVER
                )
                game_state.current_state = CurrentGameState.CONFIRM_QUIT
                key_handled_globally = True
                logger.debug("Escape key in GAME_OVER state, entering CONFIRM_QUIT.")

        # Handle input in ZONE_EDITING state (Interactive move/resize)
        # Primarily mouse-driven, but ESC cancels
        elif game_state.current_state == CurrentGameState.ZONE_EDITING:
            if key == 27:  # Escape cancels interactive editing
                logger.debug("Escape pressed during interactive zone edit. Cancelling.")
                # Revert if "move all" drag was in progress
                if getattr(game_state, "move_all_zones", False) and getattr(
                    game_state, "original_zones_on_drag_start", None
                ):
                    game_state.scoring_zones[:] = list(
                        game_state.original_zones_on_drag_start
                    )
                    if hasattr(game_state, "is_fivestar_playfield") and game_state.is_fivestar_playfield():
                        game_state.special_hole = None
                    else:
                        game_state.special_hole = set_special_hole(
                            game_state.scoring_zones
                        )
                    game_state.original_zones_on_drag_start = None
                # Revert single-zone drag if in progress
                elif (
                    getattr(game_state, "drag_start_pos", None)
                    and getattr(game_state, "original_zone_on_drag_start", None)
                    and getattr(game_state, "selected_zone_for_edit", None) is not None
                    and 0
                    <= game_state.selected_zone_for_edit
                    < len(getattr(game_state, "scoring_zones", []))
                ):
                    game_state.scoring_zones[game_state.selected_zone_for_edit] = (
                        game_state.original_zone_on_drag_start
                    )
                    if hasattr(game_state, "is_fivestar_playfield"):
                        is_fivestar = game_state.is_fivestar_playfield()
                    else:
                        is_fivestar = (
                            getattr(game_state, "playfield_type", "whiffle") == "fivestar"
                        )
                    if is_fivestar:
                        game_state.special_hole = None
                    else:
                        game_state.special_hole = set_special_hole(
                            game_state.scoring_zones
                        )

                # Reset all interactive editing state variables
                game_state.zone_editing_action = None
                game_state.drag_start_pos = None
                game_state.selected_zone_for_edit = None
                game_state.original_zone_on_drag_start = None
                game_state.move_all_zones = False
                game_state.original_zones_on_drag_start = None

                # Return to previous state (likely MENU)
                try:
                    prev_state = getattr(game_state, "previous_state", None)
                    game_state.current_state = (
                        prev_state if prev_state else CurrentGameState.MENU
                    )
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
                game_state.debug_mode = not getattr(game_state, "debug_mode", False)
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
                    game_state, "show_debug_overlay", False
                )
                show_notification(
                    game_state,
                    f"Debug Overlay: {'ON' if game_state.show_debug_overlay else 'OFF'}",
                )
                key_handled_globally = True  # Mark handled

    # Mouse input handling
    try:
        # Important: Use pygame.event.get() without filtering to capture ALL events
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                logger.info("Pygame QUIT event received")
                # Handle window closure here
                clean_exit(
                    getattr(game_state, "cap", None),
                    getattr(game_state, "background_music", None),
                    getattr(game_state, "background_music_on", True),
                    game_state,
                )
                return None  # Signal exit to main loop

            elif event.type == pygame.MOUSEWHEEL:
                # Achievements submenu: scroll with mouse wheel
                if (
                    game_state.current_state == CurrentGameState.MENU
                    and getattr(game_state, "submenu_active", None) == "achievements"
                ):
                    scroll = getattr(game_state, "achievements_scroll_offset", 0)
                    step = 50
                    game_state.achievements_scroll_offset = max(
                        0, scroll - int(event.y) * step
                    )
                    game_state.menu_cache = None
                    return key

            elif event.type == pygame.MOUSEBUTTONDOWN:
                x, y = pygame.mouse.get_pos()
                logger.debug(
                    f"Mouse button down at ({x}, {y}) in state {game_state.current_state}"
                )

                # Handle mouse press for menu button in PLAYING state
                if game_state.current_state == CurrentGameState.PLAYING:
                    # Check if we're in drawing mode first
                    if getattr(game_state, "drawing", False):
                        _process_drawing_event(cv2.EVENT_LBUTTONDOWN, x, y, game_state)
                        return key

                    menu_button_rect = (
                        UIConstants.MENU_BUTTON_X,
                        UIConstants.MENU_BUTTON_Y,
                        UIConstants.MENU_BUTTON_WIDTH,
                        UIConstants.MENU_BUTTON_HEIGHT,
                    )
                    menu_btn_x, menu_btn_y, menu_btn_w, menu_btn_h = menu_button_rect
                    if (
                        menu_btn_x <= x < menu_btn_x + menu_btn_w
                        and menu_btn_y <= y < menu_btn_y + menu_btn_h
                    ):
                        logger.debug(f"Menu button clicked at ({x}, {y})")
                        game_state.click_feedback_state = (
                            menu_button_rect,
                            time.time(),
                        )
                        game_state.current_state = CurrentGameState.MENU
                        game_state.menu_cache = None  # Force menu redraw
                        return key

                # Handle mouse press for timeline scrubber
                if (
                    game_state.current_state == CurrentGameState.MENU
                    and game_state.submenu_active == "replay_playback"
                    and hasattr(game_state, "replay_playback")
                    and _process_replay_timeline_drag(x, y, game_state)
                ):
                    return key

                # Handle mouse press for menu or modal
                if game_state.current_state in [
                    CurrentGameState.MENU,
                    CurrentGameState.CONFIRM_QUIT,
                ]:
                    logger.debug(f"Processing menu click at ({x}, {y})")
                    # No need to import UIConstants here as it's already imported at the top
                    if _process_menu_or_modal_click(x, y, game_state):
                        logger.debug("Menu click was processed successfully")
                        return key
                    else:
                        logger.debug("Menu click was not handled by any menu item")

                # Handle mouse press for zone editing (dragging/resizing)
                if (
                    game_state.current_state == CurrentGameState.PLAYING
                    and game_state.submenu_active == "edit_zones"
                    and _process_zone_editing_event(x, y, game_state)
                ):
                    return key

            elif event.type == pygame.MOUSEBUTTONUP:
                x, y = pygame.mouse.get_pos()

                # Handle drawing mode MOUSEUP
                if game_state.current_state == CurrentGameState.PLAYING and getattr(
                    game_state, "drawing", False
                ):
                    _process_drawing_event(cv2.EVENT_LBUTTONUP, x, y, game_state)
                    return key

                # Handle replay timeline
                if (
                    hasattr(game_state, "replay_playback")
                    and game_state.replay_playback
                    and game_state.replay_playback.get("timeline_dragging", False)
                ):
                    game_state.replay_playback["timeline_dragging"] = False
                    return key

                # The rest of the event handling for MOUSEBUTTONUP
                if game_state.drag_start_pos is not None:
                    if game_state.current_state == CurrentGameState.ZONE_EDITING:
                        _process_zone_editing_event(
                            cv2.EVENT_LBUTTONUP, x, y, game_state
                        )
                    elif (
                        game_state.current_state == CurrentGameState.PLAYING
                        and game_state.submenu_active == "edit_zones"
                    ):
                        _process_zone_editing_event(
                            cv2.EVENT_LBUTTONUP, x, y, game_state
                        )
                    game_state.drag_start_pos = None
                    return key

            elif event.type == pygame.MOUSEMOTION:
                x, y = pygame.mouse.get_pos()

                # Handle mouse motion for drawing zones
                if game_state.current_state == CurrentGameState.PLAYING and getattr(
                    game_state, "drawing", False
                ):
                    _process_drawing_event(cv2.EVENT_MOUSEMOVE, x, y, game_state)
                    return key

                # Handle mouse motion for timeline scrubbing
                if (
                    hasattr(game_state, "replay_playback")
                    and game_state.replay_playback
                    and game_state.replay_playback.get("timeline_dragging", False)
                ):
                    _process_replay_timeline_drag(x, y, game_state)

                # Handle mouse motion for zone editing
                if (
                    game_state.current_state == CurrentGameState.ZONE_EDITING
                    and game_state.drag_start_pos is not None
                ):
                    _process_zone_editing_event(
                        cv2.EVENT_MOUSEMOVE, x, y, game_state, is_dragging=True
                    )
                    return key

                # Also catch mouse move for regular zone editing mode
                if (
                    game_state.current_state == CurrentGameState.PLAYING
                    and game_state.submenu_active == "edit_zones"
                    and game_state.drag_start_pos is not None
                ):
                    _process_zone_editing_event(
                        cv2.EVENT_MOUSEMOVE, x, y, game_state, is_dragging=True
                    )
                    return key
    except pygame.error as e:
        logger.warning(
            f"Pygame event handling error: {e}. Mouse events will be handled through OpenCV."
        )
        # Mouse events will be handled through OpenCV's mouse callback instead
    except Exception as e:
        logger.error(f"Unexpected error in mouse event handling: {e}")

    # Return the key code that was pressed (or -1 if none / window closed)
    # The main loop can use this for general checks (like window closing independent of game state)
    # A return value of None specifically indicates clean_exit was called.
    return key


# Add a function for handling text input that can be imported by interaction_utils.py
def _handle_text_input(event: Optional[int], game_state: Any) -> None:
    """
    Initializes text input editing mode for player names.
    This function is called when entering player name editing mode.
    """
    # Initialize player editing attributes if needed
    if not hasattr(game_state, "editing_player_mode"):
        game_state.editing_player_mode = None
    if not hasattr(game_state, "editing_player_index"):
        game_state.editing_player_index = None
    if not hasattr(game_state, "editing_player_name_input"):
        game_state.editing_player_name_input = None

    # Make sure menu is redrawn
    game_state.menu_cache = None
