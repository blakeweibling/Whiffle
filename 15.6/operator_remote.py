import ipaddress
import json
import logging
import os
import queue
import secrets
import socket
import threading
import time
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np

from constants import GameConstants, PlayerConstants
from game_state_helpers import save_score, show_notification
from game_state_utils import (
    _reset_all_menu_editing_states,
    change_music_track,
    load_achievements,
    reset_game,
    save_settings,
    toggle_background_music,
    toggle_colorblind_mode,
    toggle_game_sounds,
)
from game_types import CurrentGameState
from player import Player

logger = logging.getLogger(__name__)

DEFAULT_REMOTE_PIN = "1234"
DEFAULT_REMOTE_PORT = 8765
SESSION_COOKIE_NAME = "whiffle_operator_session"
SESSION_TTL_SECONDS = 30 * 60
ACTION_TIMEOUT_SECONDS = 2.0
APP_THEME_COLOR = "#7c442b"
APP_BACKGROUND_COLOR = "#2c170f"
_icon_cache: Dict[int, bytes] = {}
PINBALL_ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "pinball_icon.png")


def _get_local_ip() -> str:
    """Best-effort local LAN IP for the remote URL display."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def _is_local_client(client_ip: str) -> bool:
    """Allow loopback and private-network clients only."""
    try:
        parsed_ip = ipaddress.ip_address(client_ip)
        return parsed_ip.is_loopback or parsed_ip.is_private
    except ValueError:
        return False


def _build_remote_icon_png(size: int) -> bytes:
    """Serve the pinball icon asset resized for installable PWA surfaces."""
    if size in _icon_cache:
        return _icon_cache[size]

    source_image = cv2.imread(PINBALL_ICON_PATH, cv2.IMREAD_UNCHANGED)
    if source_image is None:
        raise FileNotFoundError(f"Could not load PWA icon asset: {PINBALL_ICON_PATH}")

    interpolation = cv2.INTER_AREA if source_image.shape[0] >= size else cv2.INTER_LINEAR
    canvas = cv2.resize(source_image, (size, size), interpolation=interpolation)

    success, encoded = cv2.imencode(".png", canvas)
    if not success:
        raise RuntimeError("Failed to encode operator remote icon.")
    _icon_cache[size] = encoded.tobytes()
    return _icon_cache[size]


def _manifest_json() -> str:
    return json.dumps(
        {
            "name": "Whiffle Operator Remote",
            "short_name": "Whiffle Remote",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": APP_BACKGROUND_COLOR,
            "theme_color": APP_THEME_COLOR,
            "description": "Operator remote control for the Whiffle game system.",
            "icons": [
                {
                    "src": "/icon.png?size=192",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": "/icon.png?size=512",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
            ],
        }
    )


def _offline_html() -> str:
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Whiffle Operator Remote</title>
  <meta name="theme-color" content="#7c442b">
  <style>
    body { margin: 0; padding: 24px; font-family: Arial, sans-serif; background: #2c170f; color: #f7efe6; }
    .card { max-width: 520px; margin: 40px auto; background: #52301f; border-radius: 16px; padding: 24px; box-shadow: 0 12px 40px rgba(0,0,0,0.35); }
    h1 { margin-top: 0; }
    p { color: #eadbcf; line-height: 1.5; }
    .pill { display: inline-block; margin-top: 12px; padding: 8px 12px; border-radius: 999px; background: #7c442b; color: #fff8f0; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Whiffle Operator Remote</h1>
    <p>The remote cannot currently reach the game host. Reopen the app when the Whiffle game is running and the device is back on the same local network.</p>
    <div class="pill">Offline shell loaded</div>
  </div>
</body>
</html>"""


def _service_worker_js() -> str:
    return """const CACHE_NAME = 'whiffle-operator-remote-v1';
const OFFLINE_URL = '/offline';
const STATIC_ASSETS = [
  OFFLINE_URL,
  '/manifest.webmanifest',
  '/icon.png?size=192',
  '/icon.png?size=512',
  '/icon.png?size=64'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method !== 'GET') {
    return;
  }

  if (url.pathname.startsWith('/api/')) {
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response && response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(async () => (await caches.match(request)) || (await caches.match(OFFLINE_URL)))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        return cached;
      }
      return fetch(request).then((response) => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return response;
      });
    })
  );
});"""


def _state_name(game_state: Any) -> str:
    state = getattr(game_state, "current_state", None)
    if hasattr(state, "name"):
        return state.name.replace("_", " ").title()
    return "Unknown"


def _source_name(game_state: Any) -> str:
    return "Live Camera" if getattr(game_state, "camera_available", False) else "Static Image"


def _format_mode(mode_name: str) -> str:
    if mode_name == "fivestar":
        return "Five Star"
    return str(mode_name or "").replace("_", " ").title()


def _record_remote_action(game_state: Any, action_name: str, result: Dict[str, Any]) -> None:
    status_prefix = "OK" if result.get("ok") else "ERR"
    message = str(result.get("message", "") or action_name).strip()
    game_state.remote_last_action_text = f"{status_prefix}: {message}"
    game_state.remote_last_action_timestamp = time.time()
    logger.info(f"Operator remote action '{action_name}': {message}")


def update_remote_status_snapshot(game_state: Any) -> None:
    """Cache a thread-safe snapshot for the remote web UI to poll."""
    try:
        current_player = (
            game_state.get_current_player() if hasattr(game_state, "get_current_player") else None
        )
        players = list(getattr(game_state, "players", []) or [])
        player_names = [str(getattr(player, "name", "") or f"Player {index + 1}") for index, player in enumerate(players)]
        player_name = ""
        if current_player is not None and hasattr(current_player, "name"):
            player_name = str(current_player.name)

        pending_name = getattr(game_state, "pending_remote_player_name", "") or ""
        if getattr(game_state, "current_state", None) == CurrentGameState.GETTING_PLAYER_NAME:
            player_name = pending_name or getattr(game_state, "current_player_name_input", "") or player_name

        replay_manager = getattr(game_state, "replay_manager", None)
        leaderboard = getattr(game_state, "leaderboard", None)
        pending_scores = len(getattr(leaderboard, "pending_scores", []) or []) if leaderboard else 0
        remote_service = getattr(game_state, "operator_remote_service", None)
        active_remote_sessions = (
            remote_service.get_active_session_count() if remote_service is not None else 0
        )
        current_width, current_height = (
            game_state.get_current_resolution_dimensions()
            if hasattr(game_state, "get_current_resolution_dimensions")
            else (0, 0)
        )

        game_state.remote_status_snapshot = {
            "state": _state_name(game_state),
            "state_key": getattr(getattr(game_state, "current_state", None), "name", "UNKNOWN"),
            "player_name": player_name or "Player 1",
            "players": player_names,
            "current_player_index": int(getattr(game_state, "current_player_index", 0)),
            "score": int(getattr(game_state, "score", 0)),
            "mode": _format_mode(str(getattr(game_state, "game_mode", "classic"))),
            "mode_key": str(getattr(game_state, "game_mode", "classic")),
            "playfield": "Five Star"
            if getattr(game_state, "playfield_type", "whiffle") == "fivestar"
            else "Whiffle",
            "playfield_key": str(getattr(game_state, "playfield_type", "whiffle")),
            "source": _source_name(game_state),
            "paused": getattr(game_state, "current_state", None) == CurrentGameState.PAUSED,
            "menu_open": getattr(game_state, "current_state", None) == CurrentGameState.MENU,
            "remote_url": getattr(game_state, "operator_remote_url", ""),
            "resolution": f"{current_width}x{current_height}",
            "resolution_key": str(getattr(game_state, "current_resolution_key", "")),
            "fps": round(float(getattr(game_state, "fps", 0.0)), 1),
            "model_path": str(getattr(game_state, "model_path", "")),
            "zones_file_path": str(getattr(game_state, "zones_file_path", "")),
            "debug_overlay": bool(getattr(game_state, "show_debug_overlay", False)),
            "colorblind_mode": bool(getattr(game_state, "colorblind_mode", False)),
            "auto_record": bool(getattr(game_state, "auto_record_replays", False)),
            "show_scoring_zones": bool(getattr(game_state, "show_scoring_zones", False)),
            "background_music_on": bool(getattr(game_state, "background_music_on", True)),
            "game_sounds_on": bool(getattr(game_state, "game_sounds_on", True)),
            "selected_music_track_index": int(getattr(game_state, "selected_music_track_index", 0)),
            "music_track_count": len(getattr(GameConstants, "BACKGROUND_MUSIC_TRACKS", [])),
            "replay_recording": bool(getattr(game_state, "replay_recording", False)),
            "pending_scores": pending_scores,
            "remote_connected": active_remote_sessions > 0,
            "active_remote_sessions": active_remote_sessions,
            "remote_last_action": str(getattr(game_state, "remote_last_action_text", "")),
            "remote_last_action_age": max(
                0,
                int(time.time() - float(getattr(game_state, "remote_last_action_timestamp", 0.0) or 0.0)),
            ),
            "replay_system_ready": replay_manager is not None,
        }
    except Exception as exc:
        logger.debug(f"Failed to update remote status snapshot: {exc}")


def _validate_player_name(player_name: str) -> Tuple[bool, str]:
    cleaned_name = (player_name or "").strip()
    max_len = getattr(PlayerConstants, "MAX_PLAYER_NAME_LENGTH", 15)
    allowed_chars = getattr(
        PlayerConstants,
        "ALLOWED_PLAYER_NAME_CHARS",
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-",
    )

    if not cleaned_name:
        return False, "Player name cannot be empty."
    if len(cleaned_name) > max_len:
        return False, f"Player name must be {max_len} characters or fewer."
    if any(ch not in allowed_chars for ch in cleaned_name):
        return False, "Player name contains unsupported characters."
    return True, cleaned_name


def _set_player_name(game_state: Any, player_name: str) -> Tuple[bool, str]:
    is_valid, validated_name = _validate_player_name(player_name)
    if not is_valid:
        return False, validated_name

    try:
        player = game_state.get_current_player()
        player.name = validated_name
        game_state.last_player_name = validated_name
        game_state.current_player_name_input = validated_name
        game_state.pending_remote_player_name = validated_name
        save_settings(game_state)
        return True, validated_name
    except Exception as exc:
        logger.error(f"Failed to set player name from operator remote: {exc}")
        return False, "Could not update player name."


def _add_player(game_state: Any, player_name: str) -> Dict[str, Any]:
    is_valid, validated_name = _validate_player_name(player_name)
    if not is_valid:
        return {"ok": False, "message": validated_name}

    players = getattr(game_state, "players", None)
    if players is None:
        game_state.players = []
        players = game_state.players

    max_players = 4
    if len(players) >= max_players:
        return {"ok": False, "message": f"Player limit reached. Max {max_players} players."}

    normalized_name = validated_name.casefold()
    for existing_player in players:
        existing_name = str(getattr(existing_player, "name", "") or "")
        if existing_name.casefold() == normalized_name:
            return {"ok": False, "message": f"Player {validated_name} already exists."}

    try:
        new_player = Player(validated_name)
        players.append(new_player)
        game_state.current_player_index = len(players) - 1
        game_state.last_player_name = validated_name
        game_state.current_player_name_input = validated_name
        game_state.pending_remote_player_name = ""
        game_state.player_name_input_active = False
        game_state.menu_cache = None

        try:
            load_achievements(game_state, GameConstants.ACHIEVEMENTS_FILE)
        except Exception as exc:
            logger.debug(f"Could not load achievements for added player: {exc}")

        save_settings(game_state)
        show_notification(game_state, f"Added player {validated_name}", duration=1.5)
        return {"ok": True, "message": f"Added player {validated_name}."}
    except Exception as exc:
        logger.error(f"Failed to add player from operator remote: {exc}")
        return {"ok": False, "message": "Could not add player."}


def _select_player(game_state: Any, player_index: Optional[int]) -> Dict[str, Any]:
    players = list(getattr(game_state, "players", []) or [])
    if not players:
        return {"ok": False, "message": "No players are available."}

    if player_index is None or not (0 <= player_index < len(players)):
        return {"ok": False, "message": "Select a valid player."}

    try:
        game_state.current_player_index = player_index
        selected_player = players[player_index]
        selected_name = str(getattr(selected_player, "name", "") or f"Player {player_index + 1}")
        game_state.last_player_name = selected_name
        game_state.current_player_name_input = selected_name
        game_state.pending_remote_player_name = ""
        game_state.player_name_input_active = False
        game_state.menu_cache = None

        try:
            load_achievements(game_state, GameConstants.ACHIEVEMENTS_FILE)
        except Exception as exc:
            logger.debug(f"Could not load achievements for selected player: {exc}")

        save_settings(game_state)
        show_notification(game_state, f"Selected player: {selected_name}", duration=1.5)
        return {"ok": True, "message": f"Selected player {selected_name}."}
    except Exception as exc:
        logger.error(f"Failed to select player from operator remote: {exc}")
        return {"ok": False, "message": "Could not change player."}


def _show_leaderboard(game_state: Any, current_state: Any) -> Dict[str, Any]:
    allowed_states = {
        CurrentGameState.PLAYING,
        CurrentGameState.PAUSED,
        CurrentGameState.MENU,
        CurrentGameState.GAME_OVER,
    }
    if current_state not in allowed_states:
        return {
            "ok": False,
            "message": "Leaderboard is only available during a round, while paused, in the menu, or after game over.",
        }

    if current_state == CurrentGameState.MENU and getattr(game_state, "submenu_active", None) == "leaderboard":
        return {"ok": True, "message": "Leaderboard is already open."}

    game_state.current_state = CurrentGameState.MENU
    _reset_all_menu_editing_states(game_state)
    game_state.submenu_active = "leaderboard"
    game_state.menu_cache = None
    game_state.drawing = False
    game_state.temp_zone = None
    game_state.start_x = None
    game_state.start_y = None
    game_state.drawing_points_input = ""
    show_notification(game_state, "Showing leaderboard", duration=1.5)
    return {"ok": True, "message": "Leaderboard opened."}


def _enter_waiting_for_player_state(game_state: Any) -> None:
    game_state.current_state = CurrentGameState.GETTING_PLAYER_NAME
    game_state.player_name_input_active = True
    game_state.current_player_name_input = ""
    game_state.pending_remote_player_name = ""
    game_state.player_name_cursor_pos = 0
    game_state.submenu_active = None
    game_state.menu_cache = None
    game_state.win_condition_met = False


def _restart_round(game_state: Any, current_state: Any) -> Dict[str, Any]:
    restartable_states = {
        CurrentGameState.PLAYING,
        CurrentGameState.PAUSED,
        CurrentGameState.MENU,
        CurrentGameState.GAME_OVER,
    }
    if current_state not in restartable_states:
        return {
            "ok": False,
            "message": "Restart Round is only available during a round, while paused, in the menu, or after game over.",
        }

    leaderboard = getattr(game_state, "leaderboard", None)
    if leaderboard and hasattr(leaderboard, "flush_pending_scores"):
        try:
            flushed_scores = leaderboard.flush_pending_scores()
            if flushed_scores > 0:
                show_notification(
                    game_state,
                    "Score submitted to leaderboard",
                    duration=2.0,
                )
        except Exception as exc:
            logger.error(f"Error flushing leaderboard on Restart Round: {exc}")

    reset_game(game_state)
    game_state.current_state = CurrentGameState.PLAYING
    game_state.player_name_input_active = False
    game_state.submenu_active = None
    game_state.menu_cache = None
    _reset_all_menu_editing_states(game_state)
    show_notification(game_state, "Round restarted", duration=1.5)
    return {"ok": True, "message": "Round restarted."}


def _change_game_mode(game_state: Any, new_mode: str) -> Dict[str, Any]:
    valid_modes = {"classic", "timed", "fun", "practice", "survival", "retro", "versus"}
    normalized_mode = (new_mode or "").strip().lower()
    if normalized_mode not in valid_modes:
        return {"ok": False, "message": "Unsupported game mode."}

    if getattr(game_state, "game_mode", "classic") == normalized_mode:
        return {"ok": True, "message": f"Mode already set to {_format_mode(normalized_mode)}."}

    previous_state = getattr(game_state, "current_state", None)
    try:
        save_score(
            game_state,
            game_state.get_current_player().name,
            mode=getattr(game_state, "game_mode", "classic"),
        )
    except Exception as exc:
        logger.debug(f"Skipping score save before remote mode change: {exc}")

    leaderboard = getattr(game_state, "leaderboard", None)
    if leaderboard and hasattr(leaderboard, "flush_pending_scores"):
        try:
            leaderboard.flush_pending_scores()
        except Exception as exc:
            logger.debug(f"Could not flush pending scores before remote mode change: {exc}")

    game_state.game_mode = normalized_mode
    game_state.menu_cache = None

    if normalized_mode == "versus":
        try:
            from versus_mode import start_versus_mode

            start_versus_mode(game_state)
        except Exception as exc:
            logger.error(f"Error starting versus mode from operator remote: {exc}")
            return {"ok": False, "message": "Could not start Versus mode."}
    else:
        reset_game(game_state)
        if previous_state == CurrentGameState.GETTING_PLAYER_NAME:
            _enter_waiting_for_player_state(game_state)

    if normalized_mode == "retro":
        try:
            change_music_track(game_state, 3)
        except Exception as exc:
            logger.debug(f"Could not switch retro track from operator remote: {exc}")

    save_settings(game_state)
    show_notification(game_state, f"Mode changed to {_format_mode(normalized_mode)}", duration=1.8)
    return {"ok": True, "message": f"Mode changed to {_format_mode(normalized_mode)}."}


def _change_playfield(game_state: Any, new_layout: str) -> Dict[str, Any]:
    valid_layouts = {"whiffle", "fivestar"}
    normalized_layout = (new_layout or "").strip().lower()
    if normalized_layout not in valid_layouts:
        return {"ok": False, "message": "Unsupported playfield."}

    if getattr(game_state, "playfield_type", "whiffle") == normalized_layout:
        layout_label = "Five Star" if normalized_layout == "fivestar" else "Whiffle"
        return {"ok": True, "message": f"Playfield already set to {layout_label}."}

    previous_state = getattr(game_state, "current_state", None)
    layout_key = "five star" if normalized_layout == "fivestar" else normalized_layout
    try:
        success = game_state.set_playfield(layout_key)
    except Exception as exc:
        logger.error(f"Error changing playfield from operator remote: {exc}")
        return {"ok": False, "message": "Could not change playfield."}

    if not success:
        return {"ok": False, "message": "Could not change playfield."}

    try:
        from xp_system import xp_system

        xp_system.clear_all_xp()
        current_player = game_state.get_current_player()
        if current_player and hasattr(current_player, "refresh_xp"):
            current_player.refresh_xp()
    except Exception as exc:
        logger.debug(f"Could not refresh XP after playfield change: {exc}")

    reset_game(game_state)
    if previous_state == CurrentGameState.GETTING_PLAYER_NAME:
        _enter_waiting_for_player_state(game_state)

    layout_label = "Five Star" if normalized_layout == "fivestar" else "Whiffle"
    show_notification(game_state, f"Layout changed to {layout_label}", duration=1.8)
    return {"ok": True, "message": f"Playfield changed to {layout_label}."}


def _toggle_auto_record(game_state: Any) -> Dict[str, Any]:
    game_state.auto_record_replays = not bool(getattr(game_state, "auto_record_replays", False))
    save_settings(game_state)
    label = "enabled" if game_state.auto_record_replays else "disabled"
    show_notification(game_state, f"Auto recording {label}", duration=1.5)
    return {"ok": True, "message": f"Auto recording {label}."}


def _toggle_debug_overlay(game_state: Any) -> Dict[str, Any]:
    game_state.show_debug_overlay = not bool(getattr(game_state, "show_debug_overlay", False))
    label = "ON" if game_state.show_debug_overlay else "OFF"
    show_notification(game_state, f"Debug Overlay: {label}", duration=1.5)
    return {"ok": True, "message": f"Debug overlay {label}."}


def _toggle_show_scoring_zones(game_state: Any) -> Dict[str, Any]:
    game_state.show_scoring_zones = not bool(getattr(game_state, "show_scoring_zones", False))
    label = "shown" if game_state.show_scoring_zones else "hidden"
    show_notification(game_state, f"Scoring UI {label}", duration=1.5)
    return {"ok": True, "message": f"Scoring zones/UI {label}."}


def _execute_remote_action(game_state: Any, action_name: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = payload or {}
    current_state = getattr(game_state, "current_state", None)
    requested_player_name = (payload.get("player_name") or "").strip()
    requested_add_player_name = (payload.get("add_player_name") or "").strip()
    requested_selected_player_index = payload.get("selected_player_index")
    if requested_selected_player_index is not None:
        try:
            requested_selected_player_index = int(requested_selected_player_index)
        except (TypeError, ValueError):
            requested_selected_player_index = None
    requested_mode = str(payload.get("mode") or "").strip().lower()
    requested_playfield = str(payload.get("playfield") or "").strip().lower()
    requested_track_index = payload.get("track_index")
    if requested_track_index is not None:
        try:
            requested_track_index = int(requested_track_index)
        except (TypeError, ValueError):
            requested_track_index = None

    if action_name == "set_player_name":
        ok, message = _set_player_name(game_state, requested_player_name)
        if ok:
            if current_state == CurrentGameState.GETTING_PLAYER_NAME:
                show_notification(game_state, f"Player ready: {message}", duration=1.5)
            else:
                show_notification(game_state, f"Player updated: {message}", duration=1.5)
            return {"ok": True, "message": f"Player set to {message}."}
        return {"ok": False, "message": message}

    if action_name == "add_player":
        return _add_player(game_state, requested_add_player_name)

    if action_name == "select_player":
        return _select_player(game_state, requested_selected_player_index)

    if action_name == "show_leaderboard":
        return _show_leaderboard(game_state, current_state)

    if action_name == "start_game":
        if current_state == CurrentGameState.PLAYING:
            return {"ok": True, "message": "Game is already running."}

        if current_state == CurrentGameState.PAUSED:
            game_state.current_state = CurrentGameState.PLAYING
            game_state.has_paused_and_resumed = True
            show_notification(game_state, "Resuming...", duration=1.0)
            return {"ok": True, "message": "Game resumed."}

        if current_state == CurrentGameState.MENU:
            game_state.current_state = CurrentGameState.PLAYING
            _reset_all_menu_editing_states(game_state)
            game_state.submenu_active = None
            game_state.menu_cache = None
            return {"ok": True, "message": "Menu closed. Back to game."}

        player_name_to_use = (
            requested_player_name
            or getattr(game_state, "pending_remote_player_name", "")
            or getattr(game_state, "current_player_name_input", "")
            or getattr(game_state, "last_player_name", "")
            or "Player 1"
        )
        ok, message = _set_player_name(game_state, player_name_to_use)
        if not ok:
            return {"ok": False, "message": message}

        reset_game(game_state)
        game_state.current_state = CurrentGameState.PLAYING
        game_state.player_name_input_active = False
        game_state.pending_remote_player_name = ""
        show_notification(game_state, f"Starting game for {message}", duration=1.5)
        return {"ok": True, "message": f"Started game for {message}."}

    if action_name == "pause":
        if current_state != CurrentGameState.PLAYING:
            return {"ok": False, "message": "Pause is only available during gameplay."}
        game_state.current_state = CurrentGameState.PAUSED
        show_notification(game_state, "Game Paused", duration=0)
        return {"ok": True, "message": "Game paused."}

    if action_name == "resume":
        if current_state != CurrentGameState.PAUSED:
            return {"ok": False, "message": "Resume is only available while paused."}
        game_state.current_state = CurrentGameState.PLAYING
        game_state.has_paused_and_resumed = True
        show_notification(game_state, "Resuming...", duration=1.0)
        return {"ok": True, "message": "Game resumed."}

    if action_name == "open_menu":
        if current_state == CurrentGameState.MENU:
            return {"ok": True, "message": "Menu is already open."}
        if current_state not in (CurrentGameState.PLAYING, CurrentGameState.GAME_OVER):
            return {"ok": False, "message": "Menu can only be opened from a live round or game over."}
        game_state.current_state = CurrentGameState.MENU
        game_state.submenu_active = None
        game_state.menu_cache = None
        game_state.drawing = False
        game_state.temp_zone = None
        game_state.start_x = None
        game_state.start_y = None
        game_state.drawing_points_input = ""
        return {"ok": True, "message": "Menu opened."}

    if action_name == "close_menu":
        if current_state != CurrentGameState.MENU:
            return {"ok": False, "message": "Menu is not currently open."}
        game_state.current_state = CurrentGameState.PLAYING
        _reset_all_menu_editing_states(game_state)
        game_state.submenu_active = None
        game_state.menu_cache = None
        return {"ok": True, "message": "Menu closed."}

    if action_name == "reset_for_next_player":
        _enter_waiting_for_player_state(game_state)
        show_notification(game_state, "Ready for next player", duration=1.5)
        return {"ok": True, "message": "Ready for next player. Enter a name, then tap Start Game."}

    if action_name == "restart_round":
        return _restart_round(game_state, current_state)

    if action_name == "set_mode":
        return _change_game_mode(game_state, requested_mode)

    if action_name == "set_playfield":
        return _change_playfield(game_state, requested_playfield)

    if action_name == "toggle_auto_record":
        return _toggle_auto_record(game_state)

    if action_name == "toggle_debug_overlay":
        return _toggle_debug_overlay(game_state)

    if action_name == "toggle_colorblind_mode":
        toggle_colorblind_mode(game_state)
        label = "enabled" if getattr(game_state, "colorblind_mode", False) else "disabled"
        return {"ok": True, "message": f"Colorblind mode {label}."}

    if action_name == "toggle_show_scoring_zones":
        return _toggle_show_scoring_zones(game_state)

    if action_name == "toggle_background_music":
        toggle_background_music(game_state)
        label = "ON" if getattr(game_state, "background_music_on", True) else "OFF"
        show_notification(game_state, f"Background music {label}", duration=1.5)
        return {"ok": True, "message": f"Background music {label}."}

    if action_name == "toggle_game_sounds":
        toggle_game_sounds(game_state)
        label = "ON" if getattr(game_state, "game_sounds_on", True) else "OFF"
        show_notification(game_state, f"Sound effects {label}", duration=1.5)
        return {"ok": True, "message": f"Sound effects {label}."}

    if action_name == "set_music_track":
        track_count = len(getattr(GameConstants, "BACKGROUND_MUSIC_TRACKS", []))
        if track_count == 0:
            return {"ok": False, "message": "No music tracks available."}
        if requested_track_index is None or not (0 <= requested_track_index < track_count):
            return {"ok": False, "message": f"Invalid track index. Use 0–{track_count - 1}."}
        change_music_track(game_state, requested_track_index)
        show_notification(game_state, f"Music track {requested_track_index + 1}", duration=1.5)
        return {"ok": True, "message": f"Music track set to {requested_track_index + 1}."}

    return {"ok": False, "message": f"Unknown action: {action_name}"}


def process_remote_actions(game_state: Any) -> None:
    """Execute queued remote actions on the main game thread."""
    action_queue = getattr(game_state, "remote_action_queue", None)
    if action_queue is None:
        return

    while True:
        try:
            queued_action = action_queue.get_nowait()
        except queue.Empty:
            break

        response_queue = queued_action.get("response_queue")
        try:
            result = _execute_remote_action(
                game_state,
                queued_action.get("action", ""),
                queued_action.get("payload", {}),
            )
        except Exception as exc:
            logger.exception(f"Operator remote action failed: {exc}")
            result = {"ok": False, "message": "The operator action failed."}

        _record_remote_action(game_state, queued_action.get("action", ""), result)
        update_remote_status_snapshot(game_state)
        if response_queue is not None:
            try:
                response_queue.put_nowait(result)
            except queue.Full:
                pass


class OperatorRemoteService:
    """Small local web server that exposes phase-1 operator controls."""

    def __init__(self, game_state: Any):
        self.game_state = game_state
        self.server: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.sessions: Dict[str, float] = {}
        self.session_lock = threading.Lock()
        self.failed_logins: Dict[str, Tuple[int, float]] = {}

    def start(self) -> None:
        port = int(getattr(self.game_state, "operator_remote_port", DEFAULT_REMOTE_PORT))
        handler_class = self._build_handler()
        self.server = ThreadingHTTPServer(("0.0.0.0", port), handler_class)
        self.server.daemon_threads = True
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            name="operator-remote-server",
            daemon=True,
        )
        self.thread.start()

        remote_url = f"http://{_get_local_ip()}:{port}"
        self.game_state.operator_remote_url = remote_url
        update_remote_status_snapshot(self.game_state)
        logger.info(f"Operator remote available at {remote_url}")

    def stop(self) -> None:
        if self.server is None:
            return
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception as exc:
            logger.debug(f"Operator remote shutdown issue: {exc}")
        finally:
            self.server = None

    def get_active_session_count(self) -> int:
        self._cleanup_sessions()
        with self.session_lock:
            return len(self.sessions)

    def get_session_seconds_remaining(self, session_id: Optional[str]) -> int:
        if not session_id:
            return 0
        self._cleanup_sessions()
        with self.session_lock:
            expiry = self.sessions.get(session_id, 0.0)
        return max(0, int(expiry - time.time()))

    def _build_handler(self):
        service = self

        class OperatorRemoteHandler(BaseHTTPRequestHandler):
            def log_message(self, format_str: str, *args: Any) -> None:
                logger.debug("Operator remote: " + format_str % args)

            def _client_ip(self) -> str:
                return self.client_address[0] if self.client_address else ""

            def _is_local_request(self) -> bool:
                return _is_local_client(self._client_ip())

            def _send_html(self, body: str, status_code: int = 200) -> None:
                encoded = body.encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def _send_json(self, payload: Dict[str, Any], status_code: int = 200) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def _send_bytes(self, body: bytes, content_type: str, status_code: int = 200) -> None:
                self.send_response(status_code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _read_json(self) -> Dict[str, Any]:
                content_length = int(self.headers.get("Content-Length", "0") or "0")
                raw_body = self.rfile.read(content_length) if content_length else b"{}"
                try:
                    decoded = json.loads(raw_body.decode("utf-8"))
                    return decoded if isinstance(decoded, dict) else {}
                except json.JSONDecodeError:
                    return {}

            def _cookies(self) -> Dict[str, str]:
                cookie_header = self.headers.get("Cookie", "")
                parsed: Dict[str, str] = {}
                for chunk in cookie_header.split(";"):
                    if "=" not in chunk:
                        continue
                    key, value = chunk.split("=", 1)
                    parsed[key.strip()] = value.strip()
                return parsed

            def _authenticated(self) -> bool:
                service._cleanup_sessions()
                session_id = self._cookies().get(SESSION_COOKIE_NAME)
                if not session_id:
                    return False
                with service.session_lock:
                    expiry = service.sessions.get(session_id)
                    if expiry is None or expiry < time.time():
                        service.sessions.pop(session_id, None)
                        return False
                    service.sessions[session_id] = time.time() + SESSION_TTL_SECONDS
                return True

            def _render_login(self, error_message: str = "") -> str:
                error_html = (
                    f"<p class='message error'>{escape(error_message)}</p>"
                    if error_message
                    else ""
                )
                return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Whiffle Operator Remote</title>
  <meta name="theme-color" content="{APP_THEME_COLOR}">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="Whiffle Remote">
  <link rel="manifest" href="/manifest.webmanifest">
  <link rel="icon" href="/icon.png?size=64" sizes="64x64" type="image/png">
  <link rel="apple-touch-icon" href="/icon.png?size=192">
  <style>
    body {{ font-family: Arial, sans-serif; background: #2c170f; color: #f7efe6; margin: 0; padding: 24px; }}
    .card {{ max-width: 420px; margin: 40px auto; background: #52301f; border-radius: 14px; padding: 24px; box-shadow: 0 12px 40px rgba(0,0,0,0.35); }}
    h1 {{ margin-top: 0; font-size: 28px; }}
    p {{ color: #eadbcf; }}
    input {{ width: 100%; box-sizing: border-box; padding: 14px; border-radius: 10px; border: 1px solid #8f6446; background: #2c170f; color: #fff8f0; font-size: 18px; }}
    button {{ width: 100%; margin-top: 14px; padding: 14px; border: 0; border-radius: 10px; background: #ff9f1c; color: #fffaf4; font-size: 16px; font-weight: bold; }}
    .message {{ margin-top: 14px; padding: 12px; border-radius: 10px; }}
    .error {{ background: #7f1d1d; color: #fecaca; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Operator Remote</h1>
    <p>Enter the operator PIN to manage the running game.</p>
    <form method="post" action="/login">
      <input type="password" name="pin" placeholder="PIN" autofocus>
      <button type="submit">Log In</button>
    </form>
    {error_html}
  </div>
</body>
</html>"""

            def _render_dashboard(self) -> str:
                snapshot = getattr(service.game_state, "remote_status_snapshot", {}) or {}
                player_name = escape(str(snapshot.get("player_name", "Player 1")))
                remote_url = escape(str(snapshot.get("remote_url", "")))
                return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Whiffle Operator Remote</title>
  <meta name="theme-color" content="{APP_THEME_COLOR}">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="Whiffle Remote">
  <link rel="manifest" href="/manifest.webmanifest">
  <link rel="icon" href="/icon.png?size=64" sizes="64x64" type="image/png">
  <link rel="apple-touch-icon" href="/icon.png?size=192">
  <style>
    body {{ font-family: Arial, sans-serif; background: #2c170f; color: #f7efe6; margin: 0; padding: 16px; }}
    .wrap {{ max-width: 1260px; margin: 0 auto; }}
    .topbar {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 16px; }}
    .status, .controls, .setup, .diagnostics {{ background: #52301f; border-radius: 14px; padding: 18px; box-shadow: 0 10px 30px rgba(0,0,0,0.28); }}
    .layout-columns {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: start; }}
    .column {{ display: flex; flex-direction: column; gap: 16px; align-self: start; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }}
    .tile {{ background: #7c442b; border-radius: 12px; padding: 14px; }}
    .label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: #f0d2bd; margin-bottom: 8px; }}
    .value {{ font-size: 22px; font-weight: bold; }}
    .muted {{ color: #eadbcf; font-size: 13px; }}
    input, select {{ width: 100%; box-sizing: border-box; margin: 12px 0 14px 0; padding: 14px; border-radius: 10px; border: 1px solid #8f6446; background: #2c170f; color: #fff8f0; font-size: 16px; }}
    .actions {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }}
    button {{ padding: 14px; border: 0; border-radius: 10px; color: #fffaf4; background: #ff9f1c; font-size: 15px; font-weight: bold; }}
    button.secondary {{ background: #7c442b; }}
    button.danger {{ background: #b91c1c; }}
    .message {{ min-height: 24px; margin-top: 12px; color: #ffe2a8; }}
    .section-title {{ margin: 0 0 10px 0; font-size: 20px; }}
    .subgrid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .tiny {{ font-size: 12px; color: #f0d2bd; }}
    .pill {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: #7c442b; color: #fff8f0; font-size: 12px; margin-top: 8px; }}
    .connection-banner {{ margin-bottom: 16px; padding: 12px 16px; border-radius: 12px; font-weight: bold; display: none; }}
    .connection-banner.online {{ display: block; background: #5b6f3a; color: #fff8f0; }}
    .connection-banner.reconnecting {{ display: block; background: #8a5a1f; color: #fff8f0; }}
    .connection-banner.offline {{ display: block; background: #7f1d1d; color: #fff8f0; }}
    .connection-banner.expired {{ display: block; background: #5f2f68; color: #fff8f0; }}
    .logout-form {{ margin: 0; }}
    .topbar-actions {{ display: flex; align-items: center; gap: 10px; }}
    #installAppButton {{ display: none; min-width: 120px; }}
    body.standalone {{ padding-top: max(16px, env(safe-area-inset-top)); padding-bottom: max(16px, env(safe-area-inset-bottom)); }}
    @media (max-width: 900px) {{
      .layout-columns {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div>
        <h1 style="margin:0;">Whiffle Operator Remote</h1>
        <div class="muted">Connected to {remote_url or "local operator server"}</div>
      </div>
      <div class="topbar-actions">
        <button id="installAppButton" type="button" class="secondary">Install App</button>
        <form class="logout-form" method="post" action="/logout">
          <button type="submit" class="secondary">Log Out</button>
        </form>
      </div>
    </div>

    <div id="connectionBanner" class="connection-banner online">Connected to the Whiffle host.</div>

    <div class="layout-columns">
      <div class="column">
        <div class="status">
        <h2 class="section-title">Live Status</h2>
        <div class="grid">
          <div class="tile"><div class="label">Player</div><div id="playerNameValue" class="value">{player_name}</div></div>
          <div class="tile"><div class="label">Score</div><div id="scoreValue" class="value">0</div></div>
          <div class="tile"><div class="label">State</div><div id="stateValue" class="value" style="font-size:18px;">-</div></div>
          <div class="tile"><div class="label">Mode</div><div id="modeValue" class="value" style="font-size:18px;">-</div></div>
          <div class="tile"><div class="label">Playfield</div><div id="playfieldValue" class="value" style="font-size:18px;">-</div></div>
          <div class="tile"><div class="label">Source</div><div id="sourceValue" class="value" style="font-size:18px;">-</div></div>
        </div>
        <div class="subgrid" style="margin-top:12px;">
          <div class="tile">
            <div class="label">Operator Session</div>
            <div id="remoteConnectedValue" class="value" style="font-size:18px;">-</div>
            <div id="sessionCountdownValue" class="tiny">-</div>
          </div>
          <div class="tile">
            <div class="label">Last Remote Action</div>
            <div id="lastRemoteActionValue" class="value" style="font-size:18px;">-</div>
            <div id="lastRemoteActionAgeValue" class="tiny">-</div>
          </div>
        </div>
        </div>

        <div class="setup">
        <h2 class="section-title">Setup Controls</h2>
        <div class="subgrid">
          <div class="tile">
            <div class="label">Game Mode</div>
            <select id="modeSelect">
              <option value="classic">Classic</option>
              <option value="timed">Timed</option>
              <option value="survival">Survival</option>
              <option value="fun">Fun</option>
              <option value="practice">Practice</option>
              <option value="retro">Retro</option>
              <option value="versus">Versus</option>
            </select>
            <button onclick="sendAction('set_mode')" class="secondary">Apply Mode</button>
          </div>
          <div class="tile">
            <div class="label">Playfield</div>
            <select id="playfieldSelect">
              <option value="whiffle">Whiffle</option>
              <option value="fivestar">Five Star</option>
            </select>
            <button onclick="sendAction('set_playfield')" class="secondary">Apply Playfield</button>
          </div>
          <div class="tile">
            <div class="label">Music Track</div>
            <select id="musicTrackSelect">
              <option value="0">Track 1</option>
              <option value="1">Track 2</option>
              <option value="2">Track 3</option>
              <option value="3">Track 4</option>
            </select>
            <button onclick="sendAction('set_music_track')" class="secondary">Apply Track</button>
          </div>
          <div class="tile">
            <div class="label">Current Player</div>
            <select id="playerSelect"></select>
            <button onclick="sendAction('select_player')" class="secondary">Switch Player</button>
          </div>
        </div>
        <div class="actions" style="margin-top:14px;">
          <button id="autoRecordButton" onclick="sendAction('toggle_auto_record')" class="secondary">Toggle Auto-Record</button>
          <button id="debugOverlayButton" onclick="sendAction('toggle_debug_overlay')" class="secondary">Toggle Debug Overlay</button>
          <button id="colorblindButton" onclick="sendAction('toggle_colorblind_mode')" class="secondary">Toggle Colorblind Mode</button>
          <button id="showZonesButton" onclick="sendAction('toggle_show_scoring_zones')" class="secondary">Toggle Scoring UI</button>
          <button id="musicButton" onclick="sendAction('toggle_background_music')" class="secondary">Music: ON</button>
          <button id="soundEffectsButton" onclick="sendAction('toggle_game_sounds')" class="secondary">Sound Effects: ON</button>
        </div>
        <div class="pill">Mode and playfield changes stay available even during a live round and may reset the active round state.</div>
        </div>
      </div>

      <div class="column">
        <div class="controls">
        <h2 class="section-title">Round Control</h2>
        <div class="label">Player Name</div>
        <input id="playerNameInput" type="text" maxlength="15" value="{player_name}" placeholder="Player name">
        <div class="label" style="margin-top:10px;">New Player Name</div>
        <input id="addPlayerNameInput" type="text" maxlength="15" value="" placeholder="New player name">
        <div class="actions">
          <button onclick="sendAction('set_player_name')">Update Player Name</button>
          <button onclick="sendAction('add_player')">Add Player</button>
          <button onclick="sendAction('start_game')">Start / Resume</button>
          <button onclick="sendAction('restart_round')" class="secondary">Restart Round</button>
          <button onclick="sendAction('pause')" class="secondary">Pause</button>
          <button onclick="sendAction('resume')" class="secondary">Resume</button>
          <button onclick="sendAction('show_leaderboard')" class="secondary">Show Leaderboard</button>
          <button onclick="sendAction('open_menu')" class="secondary">Open Menu</button>
          <button onclick="sendAction('close_menu')" class="secondary">Close Menu</button>
          <button onclick="sendAction('reset_for_next_player')" class="danger">Reset For Next Player</button>
        </div>
        <div id="message" class="message"></div>
        </div>

        <div class="diagnostics">
        <h2 class="section-title">Diagnostics</h2>
        <div class="grid">
          <div class="tile"><div class="label">Resolution</div><div id="resolutionValue" class="value" style="font-size:18px;">-</div></div>
          <div class="tile"><div class="label">FPS</div><div id="fpsValue" class="value" style="font-size:18px;">-</div></div>
          <div class="tile"><div class="label">Pending Scores</div><div id="pendingScoresValue" class="value" style="font-size:18px;">-</div></div>
          <div class="tile"><div class="label">Replay Recording</div><div id="replayRecordingValue" class="value" style="font-size:18px;">-</div></div>
          <div class="tile"><div class="label">Auto-Record</div><div id="autoRecordValue" class="value" style="font-size:18px;">-</div></div>
          <div class="tile"><div class="label">Scoring UI</div><div id="showZonesValue" class="value" style="font-size:18px;">-</div></div>
          <div class="tile"><div class="label">Music</div><div id="musicValue" class="value" style="font-size:18px;">-</div></div>
          <div class="tile"><div class="label">Sound Effects</div><div id="soundEffectsValue" class="value" style="font-size:18px;">-</div></div>
          <div class="tile"><div class="label">Music Track</div><div id="musicTrackValue" class="value" style="font-size:18px;">-</div></div>
        </div>
        <div class="subgrid" style="margin-top:12px;">
          <div class="tile">
            <div class="label">Model Path</div>
            <div id="modelPathValue" class="tiny">-</div>
          </div>
          <div class="tile">
            <div class="label">Zones File</div>
            <div id="zonesFileValue" class="tiny">-</div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <script>
    let playerInputDirty = false;
    let playerSelectDirty = false;
    const playerNameInput = document.getElementById('playerNameInput');
    const addPlayerNameInput = document.getElementById('addPlayerNameInput');
    const playerSelect = document.getElementById('playerSelect');
    playerNameInput.addEventListener('input', () => {{
      playerInputDirty = true;
    }});
    playerSelect.addEventListener('change', () => {{
      playerSelectDirty = true;
    }});

    function onOff(value) {{
      return value ? 'ON' : 'OFF';
    }}

    function yesNo(value) {{
      return value ? 'Connected' : 'Waiting';
    }}

    function setConnectionBanner(state, message) {{
      const banner = document.getElementById('connectionBanner');
      banner.className = 'connection-banner ' + state;
      banner.textContent = message;
    }}

    let deferredInstallPrompt = null;
    const installAppButton = document.getElementById('installAppButton');

    window.addEventListener('beforeinstallprompt', (event) => {{
      event.preventDefault();
      deferredInstallPrompt = event;
      installAppButton.style.display = 'inline-block';
    }});

    installAppButton.addEventListener('click', async () => {{
      if (!deferredInstallPrompt) {{
        return;
      }}
      deferredInstallPrompt.prompt();
      await deferredInstallPrompt.userChoice;
      deferredInstallPrompt = null;
      installAppButton.style.display = 'none';
    }});

    if (window.matchMedia('(display-mode: standalone)').matches) {{
      document.body.classList.add('standalone');
    }}

    if ('serviceWorker' in navigator) {{
      window.addEventListener('load', () => {{
        navigator.serviceWorker.register('/service-worker.js').catch(() => {{
          // Ignore service-worker registration issues; the remote still works without offline support.
        }});
      }});
    }}

    async function fetchStatus() {{
      try {{
        const response = await fetch('/api/status', {{
          credentials: 'same-origin',
          cache: 'no-store'
        }});

        if (response.status === 401) {{
          setConnectionBanner('expired', 'Session expired. Redirecting to login...');
          setTimeout(() => window.location.reload(), 900);
          return;
        }}

        if (!response.ok) {{
          throw new Error('Unexpected status ' + response.status);
        }}

        const data = await response.json();
        document.getElementById('playerNameValue').textContent = data.player_name;
        document.getElementById('scoreValue').textContent = data.score;
        document.getElementById('stateValue').textContent = data.state;
        document.getElementById('modeValue').textContent = data.mode;
        document.getElementById('playfieldValue').textContent = data.playfield;
        document.getElementById('sourceValue').textContent = data.source;
        document.getElementById('remoteConnectedValue').textContent = yesNo(data.remote_connected);
        document.getElementById('sessionCountdownValue').textContent = 'Session expires in ' + (data.session_seconds_remaining || 0) + 's';
        document.getElementById('lastRemoteActionValue').textContent = data.remote_last_action || 'No remote action yet';
        document.getElementById('lastRemoteActionAgeValue').textContent = data.remote_last_action ? ('Updated ' + data.remote_last_action_age + 's ago') : '';
        document.getElementById('resolutionValue').textContent = data.resolution + (data.resolution_key ? ' (' + data.resolution_key + ')' : '');
        document.getElementById('fpsValue').textContent = data.fps;
        document.getElementById('pendingScoresValue').textContent = data.pending_scores;
        document.getElementById('replayRecordingValue').textContent = onOff(data.replay_recording);
        document.getElementById('autoRecordValue').textContent = onOff(data.auto_record);
        document.getElementById('showZonesValue').textContent = onOff(data.show_scoring_zones);
        document.getElementById('modelPathValue').textContent = data.model_path || '-';
        document.getElementById('zonesFileValue').textContent = data.zones_file_path || '-';
        document.getElementById('modeSelect').value = data.mode_key || 'classic';
        document.getElementById('playfieldSelect').value = data.playfield_key || 'whiffle';
        const players = Array.isArray(data.players) ? data.players : [];
        if (!playerSelectDirty) {{
          playerSelect.innerHTML = '';
          players.forEach((name, index) => {{
            const opt = document.createElement('option');
            opt.value = index;
            opt.textContent = name || ('Player ' + (index + 1));
            playerSelect.appendChild(opt);
          }});
          if (playerSelect.options.length > 0) {{
            const selectedIndex = Math.min(
              Math.max(data.current_player_index ?? 0, 0),
              playerSelect.options.length - 1
            );
            playerSelect.value = String(selectedIndex);
          }}
        }}
        const trackCount = Math.max(1, data.music_track_count || 4);
        const trackSelect = document.getElementById('musicTrackSelect');
        if (trackSelect.options.length !== trackCount) {{
          trackSelect.innerHTML = '';
          for (let i = 0; i < trackCount; i++) {{
            const opt = document.createElement('option');
            opt.value = i;
            opt.textContent = 'Track ' + (i + 1);
            trackSelect.appendChild(opt);
          }}
        }}
        trackSelect.value = String(Math.min(data.selected_music_track_index ?? 0, trackCount - 1));
        document.getElementById('autoRecordButton').textContent = 'Auto-Record: ' + onOff(data.auto_record);
        document.getElementById('debugOverlayButton').textContent = 'Debug Overlay: ' + onOff(data.debug_overlay);
        document.getElementById('colorblindButton').textContent = 'Colorblind: ' + onOff(data.colorblind_mode);
        document.getElementById('showZonesButton').textContent = 'Scoring UI: ' + onOff(data.show_scoring_zones);
        document.getElementById('musicButton').textContent = 'Music: ' + onOff(data.background_music_on);
        document.getElementById('soundEffectsButton').textContent = 'Sound Effects: ' + onOff(data.game_sounds_on);
        document.getElementById('musicValue').textContent = onOff(data.background_music_on);
        document.getElementById('soundEffectsValue').textContent = onOff(data.game_sounds_on);
        document.getElementById('musicTrackValue').textContent = (data.music_track_count > 0) ? ('Track ' + ((data.selected_music_track_index ?? 0) + 1)) : '-';
        if (!playerInputDirty) {{
          playerNameInput.value = data.player_name;
        }}
        setConnectionBanner('online', 'Connected to the Whiffle host.');
      }} catch (error) {{
        setConnectionBanner('reconnecting', 'Trying to reconnect to the Whiffle host...');
      }}
    }}

    async function sendAction(actionName) {{
      const payload = {{
        player_name: playerNameInput.value,
        add_player_name: addPlayerNameInput.value,
        selected_player_index: parseInt(playerSelect.value, 10),
        mode: document.getElementById('modeSelect').value,
        playfield: document.getElementById('playfieldSelect').value,
        track_index: parseInt(document.getElementById('musicTrackSelect').value, 10)
      }};
      try {{
        const response = await fetch('/api/action', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          credentials: 'same-origin',
          body: JSON.stringify({{
            action: actionName,
            payload: payload
          }})
        }});

        if (response.status === 401) {{
          setConnectionBanner('expired', 'Session expired. Redirecting to login...');
          setTimeout(() => window.location.reload(), 900);
          return;
        }}

        const data = await response.json();
        document.getElementById('message').textContent = data.message || 'Action sent.';
        if (data.ok) {{
          playerInputDirty = false;
          playerSelectDirty = false;
          if (actionName === 'add_player') {{
            addPlayerNameInput.value = '';
          }}
        }}
        await fetchStatus();
      }} catch (error) {{
        document.getElementById('message').textContent = 'The remote could not reach the host.';
        setConnectionBanner('offline', 'Remote is offline. Reconnect to the Whiffle host to continue.');
      }}
    }}

    fetchStatus();
    setInterval(fetchStatus, 1500);
  </script>
</body>
</html>"""

            def _too_many_failed_logins(self) -> bool:
                ip = self._client_ip()
                count, blocked_until = service.failed_logins.get(ip, (0, 0.0))
                return blocked_until > time.time()

            def _register_failed_login(self) -> None:
                ip = self._client_ip()
                count, blocked_until = service.failed_logins.get(ip, (0, 0.0))
                now = time.time()
                if blocked_until > now:
                    return
                count += 1
                if count >= 5:
                    service.failed_logins[ip] = (0, now + 60.0)
                else:
                    service.failed_logins[ip] = (count, 0.0)

            def _clear_failed_logins(self) -> None:
                service.failed_logins.pop(self._client_ip(), None)

            def _set_session_cookie(self) -> None:
                session_id = secrets.token_urlsafe(24)
                with service.session_lock:
                    service.sessions[session_id] = time.time() + SESSION_TTL_SECONDS
                self.send_header(
                    "Set-Cookie",
                    f"{SESSION_COOKIE_NAME}={session_id}; HttpOnly; SameSite=Lax; Path=/; Max-Age={SESSION_TTL_SECONDS}",
                )

            def do_GET(self) -> None:
                if not self._is_local_request():
                    self._send_json({"ok": False, "message": "Remote access is limited to the local network."}, 403)
                    return

                parsed_url = urlparse(self.path)
                route_path = parsed_url.path

                if route_path == "/api/status":
                    if not self._authenticated():
                        self._send_json({"ok": False, "message": "Authentication required."}, 401)
                        return
                    status_payload = dict(
                        getattr(service.game_state, "remote_status_snapshot", {}) or {}
                    )
                    status_payload["session_seconds_remaining"] = service.get_session_seconds_remaining(
                        self._cookies().get(SESSION_COOKIE_NAME)
                    )
                    self._send_json(status_payload)
                    return

                if route_path == "/manifest.webmanifest":
                    self._send_bytes(
                        _manifest_json().encode("utf-8"),
                        "application/manifest+json; charset=utf-8",
                    )
                    return

                if route_path == "/service-worker.js":
                    self._send_bytes(
                        _service_worker_js().encode("utf-8"),
                        "application/javascript; charset=utf-8",
                    )
                    return

                if route_path == "/offline":
                    self._send_html(_offline_html())
                    return

                if route_path in ("/favicon.ico", "/icon.png"):
                    query_values = parse_qs(parsed_url.query or "")
                    requested_size = query_values.get("size", ["64"])[0]
                    try:
                        icon_size = max(32, min(512, int(requested_size)))
                    except ValueError:
                        icon_size = 64
                    self._send_bytes(_build_remote_icon_png(icon_size), "image/png")
                    return

                if self._authenticated():
                    self._send_html(self._render_dashboard())
                else:
                    self._send_html(self._render_login())

            def do_POST(self) -> None:
                if not self._is_local_request():
                    self._send_json({"ok": False, "message": "Remote access is limited to the local network."}, 403)
                    return

                if self.path == "/login":
                    content_length = int(self.headers.get("Content-Length", "0") or "0")
                    raw_body = self.rfile.read(content_length) if content_length else b""
                    try:
                        body_text = raw_body.decode("utf-8")
                    except UnicodeDecodeError:
                        body_text = ""
                    pin_value = parse_qs(body_text).get("pin", [""])[0]
                    configured_pin = str(
                        getattr(service.game_state, "operator_remote_pin", DEFAULT_REMOTE_PIN) or DEFAULT_REMOTE_PIN
                    )

                    if self._too_many_failed_logins():
                        self._send_html(self._render_login("Too many failed attempts. Try again in about a minute."))
                        return

                    if secrets.compare_digest(pin_value.strip(), configured_pin):
                        self.send_response(302)
                        self._set_session_cookie()
                        self.send_header("Location", "/")
                        self.end_headers()
                        self._clear_failed_logins()
                        return

                    self._register_failed_login()
                    self._send_html(self._render_login("Incorrect PIN."), 401)
                    return

                if self.path == "/logout":
                    session_id = self._cookies().get(SESSION_COOKIE_NAME)
                    if session_id:
                        with service.session_lock:
                            service.sessions.pop(session_id, None)
                    self.send_response(302)
                    self.send_header(
                        "Set-Cookie",
                        f"{SESSION_COOKIE_NAME}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0",
                    )
                    self.send_header("Location", "/")
                    self.end_headers()
                    return

                if self.path == "/api/action":
                    if not self._authenticated():
                        self._send_json({"ok": False, "message": "Authentication required."}, 401)
                        return

                    request_data = self._read_json()
                    action_name = str(request_data.get("action", "") or "").strip()
                    payload = request_data.get("payload", {})
                    response_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=1)
                    try:
                        service.game_state.remote_action_queue.put_nowait(
                            {
                                "action": action_name,
                                "payload": payload,
                                "response_queue": response_queue,
                            }
                        )
                    except queue.Full:
                        self._send_json({"ok": False, "message": "Operator action queue is full. Try again."}, 503)
                        return

                    try:
                        result = response_queue.get(timeout=ACTION_TIMEOUT_SECONDS)
                    except queue.Empty:
                        result = {"ok": True, "message": "Action queued. The game will apply it shortly."}
                    self._send_json(result)
                    return

                self._send_json({"ok": False, "message": "Not found."}, 404)

        return OperatorRemoteHandler

    def _cleanup_sessions(self) -> None:
        now = time.time()
        with self.session_lock:
            expired_sessions = [session_id for session_id, expiry in self.sessions.items() if expiry < now]
            for session_id in expired_sessions:
                self.sessions.pop(session_id, None)


def start_operator_remote(game_state: Any) -> None:
    """Start the operator remote if enabled in settings."""
    if not getattr(game_state, "operator_remote_enabled", True):
        logger.info("Operator remote disabled in settings.")
        return

    if getattr(game_state, "operator_remote_service", None) is not None:
        return

    service = OperatorRemoteService(game_state)
    service.start()
    game_state.operator_remote_service = service


def stop_operator_remote(game_state: Any) -> None:
    """Stop the operator remote during application cleanup."""
    service = getattr(game_state, "operator_remote_service", None)
    if service is None:
        return
    try:
        service.stop()
    finally:
        game_state.operator_remote_service = None
