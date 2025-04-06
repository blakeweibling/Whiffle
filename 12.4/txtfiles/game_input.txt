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

# Import GameState enum from the NEW location
from game_types import CurrentGameState # Correct location

# Import necessary utility functions from the CORRECT files
from game_state_helpers import ( # Helpers that were moved
    show_notification,
    set_special_hole
    # Removed reset_game from here
)
from game_state_utils import ( # Utils that remained (or need to be here)
    reset_game
    # Add other imports from utils if needed directly here
)

logger = logging.getLogger(__name__)


def _handle_input(game_state: Any) -> Optional[int]:
    """Handles keyboard input using cv2.waitKey."""
    # (Function body unchanged - it will now use reset_game imported from game_state_utils)
    raw_key = -1; key = -1
    try:
        if cv2.getWindowProperty(UIConstants.WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 1:
            raw_key = cv2.waitKey(GameConstants.WAIT_KEY_DELAY); key = raw_key & 0xFF
        else: return key
    except cv2.error as e: logger.warning(f"waitKey/getWindowProperty error: {e}"); return -1
    key_handled_globally = False
    if key == ord("q"):
        clean_exit(game_state.cap, game_state.background_music, game_state.background_music_on, game_state); return None
    if key != -1 and key != 255:
        if game_state.current_state == CurrentGameState.GETTING_PLAYER_NAME:
            if key == 13: # Enter
                entered_name = game_state.current_player_name_input.strip()
                if not entered_name: show_notification(game_state, "Player name cannot be empty!", is_error=True, duration=2.0)
                else:
                    try:
                        if game_state.players: game_state.players[0].name=entered_name; show_notification(game_state, f"Welcome, {entered_name}!", duration=2.0); game_state.player_name_input_active=False; game_state.current_state=CurrentGameState.PLAYING
                        else: show_notification(game_state, "Error: Player list missing!", is_error=True)
                    except Exception as e: show_notification(game_state, "Error starting game!", is_error=True)
                key_handled_globally = True
            elif key == 27: # Escape
                if game_state.players: game_state.players[0].name="Player 1"; game_state.player_name_input_active=False; game_state.current_state=CurrentGameState.PLAYING; show_notification(game_state, "Using default name 'Player 1'", duration=2.0)
                else: show_notification(game_state, "Error: Player list missing!", is_error=True)
                key_handled_globally = True
            elif key == 8: # Backspace
                if game_state.current_player_name_input: game_state.current_player_name_input=game_state.current_player_name_input[:-1]
                key_handled_globally = True
            elif key>=32 and key<=126: # Printable
                char = chr(key)
                if char in PlayerConstants.ALLOWED_PLAYER_NAME_CHARS:
                    if len(game_state.current_player_name_input)<PlayerConstants.MAX_PLAYER_NAME_LENGTH: game_state.current_player_name_input+=char
                    else: show_notification(game_state, f"Max name length ({PlayerConstants.MAX_PLAYER_NAME_LENGTH}) reached", is_error=True, duration=1.5)
                else: show_notification(game_state, f"Character '{char}' not allowed", is_error=True, duration=1.5)
                key_handled_globally = True
        elif game_state.current_state == CurrentGameState.MENU:
             menu_key_handled = False # Player Name Editing Logic...
             if game_state.submenu_active=="players" and game_state.editing_player_mode=="edit_name" and game_state.editing_player_index is not None:
                  player_idx=game_state.editing_player_index
                  if key==13: # Enter
                      new_name=game_state.editing_player_name_input.strip()
                      if not new_name: show_notification(game_state,"Player name cannot be empty!",is_error=True,duration=2.0)
                      elif 0<=player_idx<len(game_state.players): game_state.players[player_idx].name=new_name; show_notification(game_state,f"Player {player_idx+1} name updated",duration=2.0); game_state.editing_player_index=None; game_state.editing_player_mode=None; game_state.editing_player_name_input=None; game_state.menu_cache=None
                      else: show_notification(game_state,"Error saving name!",is_error=True); game_state.editing_player_index=None; game_state.editing_player_mode=None; game_state.editing_player_name_input=None; game_state.menu_cache=None
                      menu_key_handled=True
                  elif key==27: game_state.editing_player_index=None; game_state.editing_player_mode=None; game_state.editing_player_name_input=None; game_state.menu_cache=None; show_notification(game_state,"Name edit cancelled",duration=1.5); menu_key_handled=True # Esc
                  elif key==8: # Backspace
                      if game_state.editing_player_name_input: game_state.editing_player_name_input=game_state.editing_player_name_input[:-1]; game_state.menu_cache=None
                      menu_key_handled=True
                  elif key>=32 and key<=126: # Printable
                      char=chr(key)
                      if char in PlayerConstants.ALLOWED_PLAYER_NAME_CHARS:
                          if len(game_state.editing_player_name_input)<PlayerConstants.MAX_PLAYER_NAME_LENGTH: game_state.editing_player_name_input+=char; game_state.menu_cache=None
                          else: show_notification(game_state,f"Max {PlayerConstants.MAX_PLAYER_NAME_LENGTH} chars",is_error=True,duration=1.5)
                      else: show_notification(game_state,f"Character '{char}' not allowed",is_error=True,duration=1.5); menu_key_handled=True
                  if menu_key_handled: key_handled_globally=True
             # Zone Points Editing Logic...
             elif game_state.submenu_active=="edit_zones" and game_state.editing_zone_mode=="edit_points" and game_state.editing_zone_index is not None:
                  zone_idx=game_state.editing_zone_index
                  if key==13: # Enter
                       try:
                           new_points_str=game_state.editing_zone_points_input.strip()
                           if not new_points_str: show_notification(game_state,"Points cannot be empty!",is_error=True)
                           else:
                               new_points=int(new_points_str)
                               if not(1<=new_points<=ScoringConstants.MAX_POINTS): show_notification(game_state,f"Points must be 1-{ScoringConstants.MAX_POINTS}",is_error=True)
                               elif 0<=zone_idx<len(game_state.scoring_zones): x,y,w,h,_=game_state.scoring_zones[zone_idx]; game_state.scoring_zones[zone_idx]=(x,y,w,h,new_points); show_notification(game_state,f"Zone {zone_idx+1} points updated",duration=2.0); game_state.editing_zone_index=None; game_state.editing_zone_mode=None; game_state.editing_zone_points_input=None; game_state.menu_cache=None
                               else: show_notification(game_state,"Error saving points!",is_error=True); game_state.editing_zone_index=None; game_state.editing_zone_mode=None; game_state.editing_zone_points_input=None; game_state.menu_cache=None
                       except ValueError: show_notification(game_state,"Invalid points value!",is_error=True)
                       except Exception as e: show_notification(game_state,"Error saving points!",is_error=True); game_state.editing_zone_index=None; game_state.editing_zone_mode=None; game_state.editing_zone_points_input=None; game_state.menu_cache=None
                       menu_key_handled=True
                  elif key==27: game_state.editing_zone_index=None; game_state.editing_zone_mode=None; game_state.editing_zone_points_input=None; game_state.menu_cache=None; show_notification(game_state,"Points edit cancelled",duration=1.5); menu_key_handled=True # Esc
                  elif key==8: # Backspace
                      if game_state.editing_zone_points_input: game_state.editing_zone_points_input=game_state.editing_zone_points_input[:-1]; game_state.menu_cache=None
                      menu_key_handled=True
                  elif ord('0')<=key<=ord('9'): # Numeric
                      char=chr(key); max_digits=len(str(ScoringConstants.MAX_POINTS))
                      if game_state.editing_zone_points_input is None: game_state.editing_zone_points_input=""
                      if len(game_state.editing_zone_points_input)<max_digits: game_state.editing_zone_points_input+=char; game_state.menu_cache=None
                      else: show_notification(game_state,f"Max points {ScoringConstants.MAX_POINTS}",is_error=True,duration=1.5)
                      menu_key_handled=True
                  if menu_key_handled: key_handled_globally=True
             # General Menu Navigation...
             if not key_handled_globally:
                  if key==ord('m'): game_state.current_state=CurrentGameState.PLAYING; game_state.editing_player_index=None; game_state.editing_player_mode=None; game_state.editing_player_name_input=None; game_state.editing_zone_index=None; game_state.editing_zone_mode=None; game_state.editing_zone_points_input=None; game_state.submenu_active=None; game_state.menu_cache=None; key_handled_globally=True # Resume
                  elif key==8: # Backspace
                      if game_state.editing_zone_mode: game_state.editing_zone_index=None; game_state.editing_zone_mode=None; game_state.editing_zone_points_input=None; game_state.menu_cache=None
                      elif game_state.editing_player_mode: game_state.editing_player_index=None; game_state.editing_player_mode=None; game_state.editing_player_name_input=None; game_state.menu_cache=None
                      elif game_state.submenu_active=="edit_zones": game_state.submenu_active="manage_zones"; game_state.menu_cache=None
                      elif game_state.submenu_active: game_state.submenu_active=None; game_state.menu_cache=None
                      else: game_state.current_state=CurrentGameState.PLAYING; game_state.submenu_active=None; game_state.menu_cache=None
                      key_handled_globally=True
                  elif key==27: game_state.current_state=CurrentGameState.PLAYING; game_state.editing_player_index=None; game_state.editing_player_mode=None; game_state.editing_player_name_input=None; game_state.editing_zone_index=None; game_state.editing_zone_mode=None; game_state.editing_zone_points_input=None; game_state.submenu_active=None; game_state.menu_cache=None; key_handled_globally=True # Esc
        elif game_state.current_state == CurrentGameState.PLAYING:
            key_handled_in_playing = False # Zone drawing input...
            if game_state.drawing:
                if ord('0')<=key<=ord('9'):
                    if len(game_state.drawing_points_input)<3: game_state.drawing_points_input+=chr(key)
                    else: show_notification(game_state,"Max 3 digits for points",duration=1.0)
                    key_handled_in_playing=True
                elif key==8: # Backspace
                    if game_state.drawing_points_input: game_state.drawing_points_input=game_state.drawing_points_input[:-1]
                    key_handled_in_playing=True
            # Standard playing keys...
            if not key_handled_in_playing:
                if key==ord('m'): game_state.current_state=CurrentGameState.MENU; game_state.submenu_active=None; game_state.menu_cache=None; key_handled_in_playing=True
                elif key==ord('s'): game_state.drawing=not game_state.drawing; show_notification(game_state,f"Drawing Mode: {'ON' if game_state.drawing else 'OFF'}"); game_state.temp_zone=None; game_state.start_x=None; game_state.start_y=None; game_state.drawing_points_input=""; key_handled_in_playing=True
                elif key==ord('p'): game_state.current_state=CurrentGameState.PAUSED; show_notification(game_state,"Game Paused",duration=0); key_handled_in_playing=True
                elif key==27: clean_exit(game_state.cap,game_state.background_music,game_state.background_music_on,game_state); return None
            if key_handled_in_playing: key_handled_globally=True
        elif game_state.current_state == CurrentGameState.PAUSED:
            if key==ord('p'): game_state.current_state=CurrentGameState.PLAYING; show_notification(game_state,"Resuming...",duration=1.0); key_handled_globally=True
            elif key==27: clean_exit(game_state.cap,game_state.background_music,game_state.background_music_on,game_state); return None
        elif game_state.current_state == CurrentGameState.GAME_OVER:
            if key==ord('n'): reset_game(game_state); game_state.current_state=CurrentGameState.GETTING_PLAYER_NAME; game_state.win_condition_met=False; key_handled_globally=True # Use reset_game from utils
            elif key==ord('l'): game_state.current_state=CurrentGameState.MENU; game_state.submenu_active="leaderboard"; game_state.menu_cache=None; game_state.win_condition_met=False; key_handled_globally=True
            elif key==27: clean_exit(game_state.cap,game_state.background_music,game_state.background_music_on,game_state); return None
        elif game_state.current_state == CurrentGameState.ZONE_EDITING:
            if key==27: # Esc cancels editing
                 if game_state.drag_start_pos and game_state.original_zone_on_drag_start and game_state.selected_zone_for_edit is not None and 0<=game_state.selected_zone_for_edit<len(game_state.scoring_zones):
                      game_state.scoring_zones[game_state.selected_zone_for_edit]=game_state.original_zone_on_drag_start
                      game_state.special_hole=set_special_hole(game_state.scoring_zones) # Use helper
                 game_state.zone_editing_action=None; game_state.drag_start_pos=None; game_state.selected_zone_for_edit=None; game_state.original_zone_on_drag_start=None
                 try: game_state.current_state=(game_state.previous_state if game_state.previous_state else CurrentGameState.MENU)
                 except AttributeError: game_state.current_state=CurrentGameState.MENU
                 game_state.previous_state=None; show_notification(game_state,"Zone Edit Cancelled"); game_state.menu_cache=None; key_handled_globally=True # Use helper
        # Global Toggles...
        if not key_handled_globally:
            if key==ord('d'): game_state.debug_mode=not game_state.debug_mode; log_level=logging.DEBUG if game_state.debug_mode else logging.INFO; logging.getLogger().setLevel(log_level); [h.setLevel(log_level) for h in logging.getLogger().handlers]; show_notification(game_state,f"Debug Mode: {'ON' if game_state.debug_mode else 'OFF'}"); key_handled_globally=True # Use helper
            elif key==ord('b'): game_state.show_debug_overlay=not game_state.show_debug_overlay; show_notification(game_state,f"Debug Overlay: {'ON' if game_state.show_debug_overlay else 'OFF'}"); key_handled_globally=True # Use helper
    return key