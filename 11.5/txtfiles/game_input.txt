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
# Import GameState enum and necessary functions/classes
from game_state import CurrentGameState # Ensure CurrentGameState includes ZONE_EDITING
from menu import reset_game # Required for 'n' key in GAME_OVER
# Import necessary functions if used within this file's logic
from menu import save_zones
from game_state_utils import set_special_hole # Needed for ZONE_EDITING ESC handler

logger = logging.getLogger(__name__)


def _handle_input(game_state: Any) -> Optional[int]:
    """Handles keyboard input using cv2.waitKey."""
    raw_key = -1 # Store raw value before mask
    key = -1
    try:
        # Check if the window is still valid before calling waitKey [cite: 2]
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 1:
            raw_key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY)
            key = raw_key & 0xFF # Apply mask for standard ASCII checks [cite: 2]
        else:
            logger.debug("Skipping waitKey, window seems closed or closing.")
            return key # Return -1 if window closed [cite: 2]

    except cv2.error as e:
        logger.warning(
            f"cv2.error during waitKey or getWindowProperty (window likely closed): {e}" # [cite: 3]
        )
        return -1 # Return -1 on error [cite: 3]

    key_handled_globally = False # Flag to check if input was processed overall [cite: 3]

    # --- Handle Truly Global Quit Key First (using masked key) ---
    if key == ord("q"): # [cite: 3]
        logger.info("Quit key ('q') pressed.") # [cite: 4]
        # Call clean_exit from cleanup_utils [cite: 4]
        clean_exit(
            game_state.cap,
            game_state.background_music,
            game_state.background_music_on,
            game_state,
        )
        return None # Signal immediate exit [cite: 4]

    # --- State-Specific Input Handling ---
    if key != -1 and key != 255: # Ignore no-input/-1 and potential 255 spam [cite: 5]

        # --- Handle input for GETTING_PLAYER_NAME state ---
        if game_state.current_state == CurrentGameState.GETTING_PLAYER_NAME: # [cite: 5]
            if key == 13: # Enter Key [cite: 6]
                logger.debug("Enter key (13) detected during initial name input.") # [cite: 6]
                entered_name = game_state.current_player_name_input.strip() # [cite: 6]
                if not entered_name: # [cite: 6]
                    game_state.show_notification( # [cite: 7]
                        "Player name cannot be empty!", is_error=True, duration=2.0
                    )
                else:
                    try: # [cite: 8]
                        if game_state.players: # [cite: 8]
                            game_state.players[0].name = entered_name # [cite: 9]
                            logger.info(f"Player 1 name set to: '{entered_name}'") # [cite: 9]
                            game_state.show_notification( # [cite: 9]
                                f"Welcome, {entered_name}!", duration=2.0
                            )
                            game_state.player_name_input_active = False # [cite: 10]
                            game_state.current_state = CurrentGameState.PLAYING # [cite: 11]
                            # Start music only after name confirmed and state is PLAYING [cite: 11]
                            if ( # [cite: 11]
                                game_state.background_music_on # [cite: 12]
                                and game_state.background_music
                            ):
                                game_state.background_music.play(-1) # [cite: 13]
                                logger.info("Background music started.") # [cite: 13]
                        else:
                            logger.error( # [cite: 14]
                                "Cannot set name: players list is empty or None."
                            )
                            game_state.show_notification( # [cite: 15]
                                "Error: Player list missing!", is_error=True
                            )
                    except Exception as e: # [cite: 16]
                        logger.exception(
                            f"Error setting player name or changing state: {e}" # [cite: 16]
                        )
                        game_state.show_notification( # [cite: 17]
                            "Error starting game!", is_error=True
                        )
                key_handled_globally = True # [cite: 17]
            elif key == 27: # Escape Key [cite: 18]
                logger.debug("Escape key (27) detected during initial name input.") # [cite: 18]
                logger.info("Using default name 'Player 1'.") # [cite: 18]
                if game_state.players: # [cite: 18]
                    game_state.players[0].name = "Player 1" # [cite: 18]
                    game_state.player_name_input_active = False # [cite: 19]
                    game_state.current_state = CurrentGameState.PLAYING # [cite: 19]
                    game_state.show_notification( # [cite: 19]
                        "Using default name 'Player 1'", duration=2.0
                    )
                    if game_state.background_music_on and game_state.background_music: # [cite: 20]
                        game_state.background_music.play(-1) # [cite: 20]
                        logger.info("Background music started.") # [cite: 20]
                else:
                    logger.error( # [cite: 21]
                        "Cannot set default name: players list is empty or None."
                    )
                    game_state.show_notification( # [cite: 21]
                        "Error: Player list missing!", is_error=True
                    )
                key_handled_globally = True # [cite: 22]
            elif key == 8: # Backspace Key [cite: 22]
                logger.debug("Backspace key (8) detected during initial name input.") # [cite: 22]
                if game_state.current_player_name_input: # [cite: 23]
                    game_state.current_player_name_input = ( # [cite: 23]
                        game_state.current_player_name_input[:-1]
                    )
                    logger.debug( # [cite: 23]
                        f"Name input buffer: {game_state.current_player_name_input}"
                    )
                key_handled_globally = True # [cite: 24]
            elif key >= 32 and key <= 126: # Printable characters [cite: 24]
                char = chr(key) # [cite: 24]
                if char in PlayerConstants.ALLOWED_PLAYER_NAME_CHARS: # [cite: 25]
                    if ( # [cite: 25]
                        len(game_state.current_player_name_input) # [cite: 25]
                        < PlayerConstants.MAX_PLAYER_NAME_LENGTH
                    ):
                        game_state.current_player_name_input += char # [cite: 26]
                        logger.debug( # [cite: 26]
                            f"Name input buffer: {game_state.current_player_name_input}"
                        )
                    else:
                        game_state.show_notification( # [cite: 27]
                            f"Max name length ({PlayerConstants.MAX_PLAYER_NAME_LENGTH}) reached",
                            is_error=True, # [cite: 28]
                            duration=1.5,
                        )
                    key_handled_globally = True # [cite: 28]
                else:
                    logger.debug(f"Character '{char}' not allowed for player name.") # [cite: 29]
                    game_state.show_notification( # [cite: 29]
                        f"Character '{char}' not allowed", is_error=True, duration=1.5
                    )
                    key_handled_globally = True # [cite: 30]


        # --- Handle input for MENU state ---
        elif game_state.current_state == CurrentGameState.MENU: # [cite: 30]
            menu_key_handled = False # Flag specific to menu actions [cite: 30]

            # Player Name Editing Logic [cite: 30]
            if ( # [cite: 31]
                game_state.submenu_active == "players"
                and game_state.editing_player_mode == "edit_name"
                and game_state.editing_player_index is not None
            ):
                player_idx = game_state.editing_player_index # [cite: 32]
                if key == 13: # Enter Key - Save Name [cite: 32]
                    logger.debug( # [cite: 33]
                        "Enter key (13) detected during menu player name edit."
                    )
                    new_name = game_state.editing_player_name_input.strip() # [cite: 33]
                    if not new_name: # [cite: 34]
                        game_state.show_notification(
                            "Player name cannot be empty!", is_error=True, duration=2.0 # [cite: 34]
                        )
                    elif 0 <= player_idx < len(game_state.players): # [cite: 35]
                        old_name = game_state.players[player_idx].name # [cite: 35]
                        game_state.players[player_idx].name = new_name # [cite: 35]
                        logger.info( # [cite: 35]
                            f"Player {player_idx + 1} name changed from '{old_name}' to '{new_name}'"
                        )
                        game_state.show_notification( # [cite: 36]
                            f"Player {player_idx + 1} name updated", duration=2.0
                        )
                        # Reset editing state after successful save [cite: 37]
                        game_state.editing_player_index = None # [cite: 37]
                        game_state.editing_player_mode = None # [cite: 38]
                        game_state.editing_player_name_input = None # [cite: 38]
                        game_state.menu_cache = None # Invalidate cache [cite: 38]
                    else:
                        logger.error( # [cite: 39]
                            f"Invalid player index {player_idx} during name save."
                        )
                        game_state.show_notification( # [cite: 39]
                            "Error saving name!", is_error=True
                        )
                        # Reset editing state even on error [cite: 40]
                        game_state.editing_player_index = None # [cite: 40]
                        game_state.editing_player_mode = None # [cite: 41]
                        game_state.editing_player_name_input = None # [cite: 41]
                        game_state.menu_cache = None # Invalidate cache [cite: 41]
                    menu_key_handled = True # [cite: 42]
                elif key == 27: # Escape Key - Cancel Edit [cite: 42]
                    logger.debug(
                        "Escape key (27) detected during menu player name edit." # [cite: 42]
                    )
                    game_state.editing_player_index = None # [cite: 43]
                    game_state.editing_player_mode = None # [cite: 43]
                    game_state.editing_player_name_input = None # [cite: 43]
                    game_state.menu_cache = None # Invalidate cache [cite: 43]
                    game_state.show_notification("Name edit cancelled", duration=1.5) # [cite: 44]
                    menu_key_handled = True # [cite: 44]
                elif key == 8: # Backspace Key [cite: 44]
                    logger.debug( # [cite: 45]
                        "Backspace key (8) detected during menu player name edit."
                    )
                    if game_state.editing_player_name_input: # [cite: 45]
                        game_state.editing_player_name_input = ( # [cite: 45]
                            game_state.editing_player_name_input[:-1] # [cite: 46]
                        )
                        game_state.menu_cache = None # Invalidate cache [cite: 46]
                    menu_key_handled = True # [cite: 46]
                elif key >= 32 and key <= 126: # Printable characters [cite: 47]
                    char = chr(key) # [cite: 47]
                    if char in PlayerConstants.ALLOWED_PLAYER_NAME_CHARS: # [cite: 47]
                        if ( # [cite: 48]
                            len(game_state.editing_player_name_input) # [cite: 48]
                            < PlayerConstants.MAX_PLAYER_NAME_LENGTH
                        ):
                            game_state.editing_player_name_input += char # [cite: 48]
                            game_state.menu_cache = None # Invalidate cache [cite: 49]
                        else:
                            game_state.show_notification( # [cite: 49]
                                f"Max {PlayerConstants.MAX_PLAYER_NAME_LENGTH} chars", # [cite: 50]
                                is_error=True, # [cite: 50]
                                duration=1.5,
                            )
                            menu_key_handled = True # [cite: 51]
                    else:
                        logger.debug(f"Character '{char}' not allowed for player name.") # [cite: 51]
                        game_state.show_notification( # [cite: 51]
                            f"Character '{char}' not allowed", # [cite: 52]
                            is_error=True, # [cite: 52]
                            duration=1.5,
                        )
                    menu_key_handled = True # [cite: 53]

                if menu_key_handled: # [cite: 53]
                    key_handled_globally = True # [cite: 53]

            # Zone Points Editing Logic [cite: 53]
            elif ( # [cite: 54]
                game_state.submenu_active == "edit_zones"
                and game_state.editing_zone_mode == "edit_points"
                and game_state.editing_zone_index is not None
            ):
                zone_idx = game_state.editing_zone_index # [cite: 55]
                if key == 13: # Enter Key - Save Points [cite: 55]
                    logger.debug( # [cite: 55]
                        "Enter key (13) detected during menu zone points edit."
                    )
                    try: # [cite: 56]
                        new_points_str = game_state.editing_zone_points_input.strip() # [cite: 57]
                        if not new_points_str: # [cite: 57]
                            game_state.show_notification( # [cite: 57]
                                "Points cannot be empty!", is_error=True
                            )
                        else:
                            new_points = int(new_points_str) # [cite: 58]
                            # Use constant for max points validation [cite: 59]
                            if not (1 <= new_points <= ScoringConstants.MAX_POINTS): # [cite: 59]
                                game_state.show_notification( # [cite: 59]
                                    f"Points must be 1-{ScoringConstants.MAX_POINTS}", # [cite: 60]
                                    is_error=True, # [cite: 60]
                                )
                            elif 0 <= zone_idx < len(game_state.scoring_zones): # [cite: 61]
                                x, y, w, h, _ = game_state.scoring_zones[zone_idx] # [cite: 61]
                                game_state.scoring_zones[zone_idx] = ( # [cite: 62]
                                    x,
                                    y,
                                    w, # [cite: 63]
                                    h,
                                    new_points,
                                ) # [cite: 64]
                                logger.info(
                                    f"Zone {zone_idx + 1} points updated to {new_points}" # [cite: 64]
                                )
                                game_state.show_notification( # [cite: 65]
                                    f"Zone {zone_idx + 1} points updated", duration=2.0
                                )
                                # Reset editing state after successful save [cite: 66]
                                game_state.editing_zone_index = None # [cite: 67]
                                game_state.editing_zone_mode = None # [cite: 67]
                                game_state.editing_zone_points_input = None # [cite: 67]
                                game_state.menu_cache = None # Invalidate cache [cite: 68]
                            else:
                                logger.error( # [cite: 68]
                                    f"Invalid zone index {zone_idx} during points save."
                                )
                                game_state.show_notification( # [cite: 69]
                                    "Error saving points!", is_error=True
                                )
                                # Reset editing state even on error [cite: 70]
                                game_state.editing_zone_index = None # [cite: 71]
                                game_state.editing_zone_mode = None # [cite: 71]
                                game_state.editing_zone_points_input = None # [cite: 71]
                                game_state.menu_cache = None # Invalidate cache [cite: 72]
                    except ValueError: # [cite: 72]
                        game_state.show_notification( # [cite: 72]
                            "Invalid points value!", is_error=True
                        )
                    except Exception as e: # [cite: 73]
                        logger.exception(f"Error saving zone points: {e}") # [cite: 73]
                        game_state.show_notification( # [cite: 74]
                            "Error saving points!", is_error=True
                        )
                        # Reset editing state on unexpected error [cite: 74]
                        game_state.editing_zone_index = None # [cite: 75]
                        game_state.editing_zone_mode = None # [cite: 75]
                        game_state.editing_zone_points_input = None # [cite: 75]
                        game_state.menu_cache = None # Invalidate cache [cite: 75]
                    menu_key_handled = True # 20 spaces indent [cite: 76]
                elif key == 27: # Escape Key - Cancel Edit [cite: 76]
                    logger.debug( # [cite: 76]
                        "Escape key (27) detected during menu zone points edit."
                    )
                    game_state.editing_zone_index = None # [cite: 77]
                    game_state.editing_zone_mode = None # [cite: 77]
                    game_state.editing_zone_points_input = None # [cite: 78]
                    game_state.menu_cache = None # Invalidate cache [cite: 78]
                    game_state.show_notification("Points edit cancelled", duration=1.5) # [cite: 78]
                    menu_key_handled = True # 20 spaces indent [cite: 78]
                elif key == 8: # Backspace Key [cite: 79]
                    logger.debug( # [cite: 79]
                        "Backspace key (8) detected during menu zone points edit."
                    )
                    if game_state.editing_zone_points_input: # [cite: 80]
                        game_state.editing_zone_points_input = ( # [cite: 80]
                            game_state.editing_zone_points_input[:-1] # [cite: 81]
                        )
                        game_state.menu_cache = None # Invalidate cache [cite: 81]
                    menu_key_handled = True # 20 spaces indent [cite: 81]
                elif ord("0") <= key <= ord("9"): # Numeric input [cite: 82]
                    logger.debug(f"Numeric key {chr(key)} detected during points edit.") # [cite: 82]
                    char = chr(key) # [cite: 82]
                    if game_state.editing_zone_points_input is None: # [cite: 83]
                        game_state.editing_zone_points_input = "" # [cite: 83]
                    # Limit length based on MAX_POINTS (e.g., 3 digits for 999) [cite: 83]
                    max_digits = len(str(ScoringConstants.MAX_POINTS)) # [cite: 84]
                    if len(game_state.editing_zone_points_input) < max_digits: # [cite: 84]
                        game_state.editing_zone_points_input += char # [cite: 84]
                        game_state.menu_cache = None # Invalidate cache [cite: 84]
                    else:
                        game_state.show_notification( # [cite: 85]
                            f"Max points {ScoringConstants.MAX_POINTS}", # [cite: 85]
                            is_error=True, # [cite: 85]
                            duration=1.5, # [cite: 86]
                        )
                    menu_key_handled = True # 20 spaces indent [cite: 86]

                if menu_key_handled: # [cite: 87]
                    key_handled_globally = True # [cite: 87]


            # General Menu Navigation [cite: 87]
            if not key_handled_globally: # Check if not handled by specific editing modes [cite: 88]
                if key == ord("m"): # Toggle menu OFF (Resume) [cite: 88]
                    logger.debug("Menu key ('m') pressed in menu, resuming game.") # [cite: 88]
                    game_state.current_state = CurrentGameState.PLAYING # [cite: 89]
                    # Ensure all editing modes are cancelled when leaving menu via 'm' [cite: 89]
                    game_state.editing_player_index = None # [cite: 89]
                    game_state.editing_player_mode = None # [cite: 89]
                    game_state.editing_player_name_input = None # [cite: 90]
                    game_state.editing_zone_index = None # [cite: 90]
                    game_state.editing_zone_mode = None # [cite: 90]
                    game_state.editing_zone_points_input = None # [cite: 90]
                    game_state.submenu_active = None # [cite: 90]
                    game_state.menu_cache = None # [cite: 91]
                    key_handled_globally = True # [cite: 91]
                elif key == 8: # Backspace Key - Go Back or Close Menu [cite: 91]
                    logger.debug("Backspace key (8) detected for menu navigation.") # [cite: 91]
                    # Handle back specifically from editing modes first [cite: 92]
                    if game_state.editing_zone_mode: # [cite: 92]
                         game_state.editing_zone_index = None # [cite: 92]
                         game_state.editing_zone_mode = None # [cite: 92]
                         game_state.editing_zone_points_input = None # [cite: 93]
                         game_state.menu_cache = None # [cite: 93]
                         logger.debug("Cancelled zone editing via backspace.") # [cite: 93]
                         key_handled_globally = True # [cite: 94]
                    elif game_state.editing_player_mode: # [cite: 94]
                         game_state.editing_player_index = None # [cite: 94]
                         game_state.editing_player_mode = None # [cite: 94]
                         game_state.editing_player_name_input = None # [cite: 95]
                         game_state.menu_cache = None # [cite: 95]
                         logger.debug("Cancelled player editing via backspace.") # [cite: 95]
                         key_handled_globally = True # [cite: 95]
                    # Handle back from submenus [cite: 96]
                    elif game_state.submenu_active == "edit_zones": # [cite: 96]
                        game_state.submenu_active = "manage_zones" # [cite: 96]
                        game_state.menu_cache = None # [cite: 97]
                        key_handled_globally = True # [cite: 97]
                    elif game_state.submenu_active: # Back from any other submenu to main menu [cite: 97]
                        game_state.submenu_active = None # [cite: 98]
                        game_state.menu_cache = None # [cite: 98]
                        key_handled_globally = True # [cite: 98]
                    else: # If already on main menu, backspace closes it [cite: 98]
                        game_state.current_state = CurrentGameState.PLAYING # [cite: 99]
                        game_state.submenu_active = None # [cite: 99]
                        game_state.menu_cache = None # [cite: 99]
                        logger.debug("Closed main menu via backspace.") # [cite: 99]
                        key_handled_globally = True # [cite: 100]
                elif key == 27: # Escape Key - Close Menu entirely [cite: 100]
                    logger.debug("Escape key (27) detected in menu, resuming game.") # [cite: 100]
                    game_state.current_state = CurrentGameState.PLAYING # [cite: 100]
                    # Ensure all editing modes are cancelled [cite: 101]
                    game_state.editing_player_index = None # [cite: 101]
                    game_state.editing_player_mode = None # [cite: 101]
                    game_state.editing_player_name_input = None # [cite: 101]
                    game_state.editing_zone_index = None # [cite: 102]
                    game_state.editing_zone_mode = None # [cite: 102]
                    game_state.editing_zone_points_input = None # [cite: 102]
                    game_state.submenu_active = None # [cite: 102]
                    game_state.menu_cache = None # [cite: 102]
                    key_handled_globally = True # [cite: 103]


        # --- Handle input for PLAYING state ---
        elif game_state.current_state == CurrentGameState.PLAYING: # [cite: 103]
            key_handled_in_playing = False # Use local flag for PLAYING state [cite: 103]

            # Handle input during zone drawing [cite: 103]
            if game_state.drawing: # [cite: 104]
                if ord('0') <= key <= ord('9'): # [cite: 104]
                    # Limit input length (e.g., 3 digits for 1-999) [cite: 104]
                    if len(game_state.drawing_points_input) < 3: # [cite: 104]
                        game_state.drawing_points_input += chr(key) # [cite: 105]
                        logger.debug(f"Drawing points input: {game_state.drawing_points_input}") # [cite: 105]
                    else:
                         game_state.show_notification(f"Max 3 digits for points", duration=1.0) # [cite: 105]
                    key_handled_in_playing = True # [cite: 106]
                elif key == 8: # Backspace [cite: 106]
                    if game_state.drawing_points_input: # [cite: 106]
                        game_state.drawing_points_input = game_state.drawing_points_input[:-1] # [cite: 106]
                        logger.debug(f"Drawing points input (backspace): {game_state.drawing_points_input}") # [cite: 106]
                    key_handled_in_playing = True # [cite: 107]

            # Handle standard PLAYING keys if not handled by drawing input [cite: 110]
            if not key_handled_in_playing: # [cite: 110]
                if key == ord("m"): # Toggle menu ON [cite: 110]
                    logger.info("Menu key ('m') pressed while playing.") # [cite: 110]
                    game_state.current_state = CurrentGameState.MENU # [cite: 111]
                    game_state.submenu_active = None # [cite: 111]
                    game_state.menu_cache = None # [cite: 111]
                    # Cancel drawing if menu is opened [cite: 111]
                    game_state.drawing = False # [cite: 112]
                    game_state.temp_zone = None # [cite: 112]
                    game_state.start_x = None # [cite: 112]
                    game_state.start_y = None # [cite: 112]
                    game_state.drawing_points_input = "" # [cite: 113]
                    key_handled_in_playing = True # Mark as handled [cite: 113]
                elif key == ord("s"): # Toggle drawing mode [cite: 113]
                    game_state.drawing = not game_state.drawing # [cite: 114]
                    if game_state.drawing: # [cite: 114]
                        logger.info("Drawing mode enabled. Click and drag to draw zone. Enter digits for points.") # [cite: 114]
                        game_state.show_notification("Drawing Mode: ON") # [cite: 115]
                        # Reset state associated with drawing [cite: 115]
                        game_state.start_x = None # [cite: 115]
                        game_state.start_y = None # [cite: 116]
                        game_state.temp_zone = None # [cite: 116]
                        game_state.drawing_points_input = "" # Reset points input [cite: 116]
                    else:
                        logger.info("Drawing mode disabled.") # [cite: 117]
                        game_state.show_notification("Drawing Mode: OFF") # [cite: 117]
                        # Clear drawing state [cite: 117]
                        game_state.temp_zone = None # [cite: 117]
                        game_state.start_x = None # [cite: 118]
                        game_state.start_y = None # [cite: 118]
                        game_state.drawing_points_input = "" # [cite: 118]
                    key_handled_in_playing = True # Mark as handled [cite: 118]
                elif key == ord("p"): # Pause game [cite: 119]
                    logger.info("Pause key ('p') pressed.") # [cite: 119]
                    # Cancel drawing if pausing [cite: 119]
                    if game_state.drawing: # [cite: 119]
                         game_state.drawing = False # [cite: 120]
                         game_state.temp_zone = None # [cite: 120]
                         game_state.start_x = None # [cite: 120]
                         game_state.start_y = None # [cite: 120]
                         game_state.drawing_points_input = "" # [cite: 121]
                         logger.info("Drawing cancelled due to pause.") # [cite: 121]
                    game_state.current_state = CurrentGameState.PAUSED # [cite: 121]
                    game_state.show_notification("Game Paused", duration=0) # Persistent [cite: 121]
                    key_handled_in_playing = True # Mark as handled [cite: 122]
                elif key == 27: # ESC quits immediately while playing [cite: 122]
                    logger.info("Escape key (27) pressed while playing, exiting.") # [cite: 122]
                    clean_exit( # [cite: 122]
                        game_state.cap, # [cite: 123]
                        game_state.background_music,
                        game_state.background_music_on,
                        game_state,
                    ) # [cite: 124]
                    return None # Signal exit [cite: 124]

            # If key was handled within PLAYING state (either drawing or standard keys) [cite: 124]
            if key_handled_in_playing: # [cite: 124]
                key_handled_globally = True # [cite: 124]


        # --- Handle input for PAUSED state ---
        elif game_state.current_state == CurrentGameState.PAUSED: # [cite: 125]
            if key == ord("p"): # Resume game [cite: 125]
                logger.info("Resume key ('p') pressed.") # [cite: 125]
                game_state.current_state = CurrentGameState.PLAYING # [cite: 126]
                game_state.show_notification("Resuming...", duration=1.0) # [cite: 126]
                key_handled_globally = True # [cite: 126]
            elif key == 27: # ESC quits immediately while paused [cite: 126]
                logger.info("Escape key (27) pressed while paused, exiting.") # [cite: 126]
                clean_exit( # [cite: 127]
                    game_state.cap,
                    game_state.background_music,
                    game_state.background_music_on,
                    game_state,
                )
                return None # [cite: 128]


        # --- Handle input for GAME_OVER state ---
        elif game_state.current_state == CurrentGameState.GAME_OVER: # [cite: 128]
            if key == ord("n"): # Start New Game [cite: 128]
                logger.info("'n' key pressed on game over screen. Starting new game.") # [cite: 129]
                reset_game(game_state) # [cite: 130]
                # Transition to name input for the new game [cite: 130]
                game_state.current_state = CurrentGameState.GETTING_PLAYER_NAME # [cite: 130]
                game_state.win_condition_met = False # [cite: 130]
                key_handled_globally = True # [cite: 130]
            elif key == ord("l"): # Show Leaderboard [cite: 131]
                logger.info("'l' key pressed on game over screen. Showing leaderboard.") # [cite: 131]
                game_state.current_state = CurrentGameState.MENU # [cite: 131]
                game_state.submenu_active = "leaderboard" # [cite: 131]
                game_state.menu_cache = None # [cite: 131]
                game_state.win_condition_met = False # [cite: 132]
                key_handled_globally = True # [cite: 132]
            elif key == 27: # ESC quits immediately from game over [cite: 132]
                logger.info("Escape key (27) pressed on game over screen, exiting.") # [cite: 132]
                clean_exit( # [cite: 132]
                    game_state.cap, # [cite: 133]
                    game_state.background_music,
                    game_state.background_music_on,
                    game_state,
                )
                return None # [cite: 134]


        # --- Global Toggles (Only if not handled by specific states above) ---
        if not key_handled_globally: # [cite: 134]
            if key == ord("d"): # [cite: 134]
                game_state.debug_mode = not game_state.debug_mode # [cite: 134]
                log_level = logging.DEBUG if game_state.debug_mode else logging.INFO # [cite: 135]
                # Update root logger level AND handler levels [cite: 135]
                logging.getLogger().setLevel(log_level) # [cite: 135]
                for handler in logging.getLogger().handlers: # [cite: 135]
                    handler.setLevel(log_level) # [cite: 135]
                logger.info( # [cite: 136]
                    f"General Debug Mode toggled {'ON' if game_state.debug_mode else 'OFF'} (Level: {logging.getLevelName(log_level)})"
                )
                game_state.show_notification( # [cite: 136]
                    f"Debug Mode: {'ON' if game_state.debug_mode else 'OFF'}" # [cite: 137]
                )
                key_handled_globally = True # [cite: 137]
            elif key == ord("b"): # [cite: 137]
                game_state.show_debug_overlay = not game_state.show_debug_overlay # [cite: 137]
                logger.info( # [cite: 137]
                    f"Visual Debug Overlay toggled {'ON' if game_state.show_debug_overlay else 'OFF'}" # [cite: 138]
                )
                game_state.show_notification( # [cite: 138]
                    f"Debug Overlay: {'ON' if game_state.show_debug_overlay else 'OFF'}" # [cite: 138]
                )
                key_handled_globally = True # [cite: 139]

    # Return the masked key code, or None if quit was triggered
    return key # [cite: 139]