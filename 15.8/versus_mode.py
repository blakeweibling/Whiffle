# versus_mode.py
"""
Versus mode implementation for Whiffle Tracker.
Provides functionality for 2-4 players to compete by taking turns.
"""

import logging
from typing import Dict, Any, Optional

import cv2
import numpy as np

from constants import UIConstants
from game_state_helpers import show_notification
from game_types import CurrentGameState

logger = logging.getLogger(__name__)


def start_versus_mode(game_state):
    """
    Initialize versus mode using all available players (2-4).
    """
    from player import Player

    # Ensure at least two players exist
    if len(game_state.players) == 0:
        game_state.players.append(Player("Player 1"))
    if len(game_state.players) < 2:
        game_state.players.append(Player("Player 2"))

    player_count = len(game_state.players)

    game_state.versus_mode_active = True
    game_state.versus_players = list(game_state.players[:player_count])
    game_state.versus_player_count = player_count
    game_state.current_turn_player_index = 0
    game_state.versus_scores = [0] * player_count
    game_state.versus_stats = [{} for _ in range(player_count)]
    game_state.versus_results_frame = None

    # Start with first player
    game_state.reset_game(game_state.versus_players[0].name, "versus")

    show_notification(
        game_state, f"{game_state.versus_players[0].name}'s Turn (1/{player_count})", duration=3.0
    )

    names = " vs ".join(p.name for p in game_state.versus_players)
    logger.info(f"Started versus mode with {player_count} players: {names}")


def switch_versus_player_turn(game_state):
    """
    Switch to the next player's turn in versus mode.
    Save current player's score and stats.
    """
    current_idx = game_state.current_turn_player_index
    player_count = getattr(game_state, "versus_player_count", 2)

    if game_state.current_state != CurrentGameState.GAME_OVER:
        game_state.versus_scores[current_idx] = game_state.score

    if game_state.data_logger and hasattr(game_state, "current_session_stats"):
        if game_state.current_session_stats is not None:
            game_state.versus_stats[current_idx] = (
                game_state.current_session_stats.copy()
            )

    next_idx = current_idx + 1
    game_state.current_turn_player_index = next_idx
    next_player = game_state.versus_players[next_idx]

    game_state.reset_game(next_player.name, "versus")

    show_notification(
        game_state,
        f"{next_player.name}'s Turn ({next_idx + 1}/{player_count})",
        duration=3.0,
    )

    logger.info(f"Switched to {next_player.name}'s turn in versus mode")


def check_versus_mode_end(game_state) -> bool:
    """
    Check if the versus mode should end or switch to the next player.
    Returns True if action was taken (switching player or ending game).
    """
    if not game_state.versus_mode_active:
        return False

    if game_state.current_state == CurrentGameState.GAME_OVER:
        current_idx = game_state.current_turn_player_index
        player_count = getattr(game_state, "versus_player_count", 2)
        game_state.versus_scores[current_idx] = game_state.score

        if current_idx >= player_count - 1:
            if not getattr(game_state, "showing_versus_results", False):
                game_state.previous_state = game_state.current_state
                show_versus_results(game_state)
            return True
        else:
            switch_versus_player_turn(game_state)
            return True

    return False


def _render_results_frame(game_state) -> np.ndarray:
    """Render the versus results onto a frame and return it."""
    width = game_state.current_width
    height = game_state.current_height
    frame = np.zeros((height, width, 3), dtype=np.uint8)

    player_count = getattr(game_state, "versus_player_count", 2)
    scores = game_state.versus_scores[:player_count]

    # Determine winner(s)
    max_score = max(scores)
    winners = [i for i, s in enumerate(scores) if s == max_score]
    is_tie = len(winners) > 1

    # Header
    header = "VERSUS MODE RESULTS"
    (hw, _hh), _ = cv2.getTextSize(header, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 2)
    cv2.putText(
        frame, header,
        ((width - hw) // 2, 100),
        cv2.FONT_HERSHEY_SIMPLEX, 1.5, UIConstants.WHITE, 2, cv2.LINE_AA,
    )

    # Winner announcement
    if is_tie:
        winner_text = "IT'S A TIE!"
        winner_color = UIConstants.YELLOW
    else:
        winner_text = f"WINNER: {game_state.versus_players[winners[0]].name}"
        winner_color = UIConstants.ACCENT

    (ww, _wh), _ = cv2.getTextSize(winner_text, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 2)
    cv2.putText(
        frame, winner_text,
        ((width - ww) // 2, 180),
        cv2.FONT_HERSHEY_SIMPLEX, 1.2, winner_color, 2, cv2.LINE_AA,
    )

    # Player scores
    y_pos = 250
    for i in range(player_count):
        player = game_state.versus_players[i]
        score = scores[i]
        color = UIConstants.ACCENT if i in winners and not is_tie else UIConstants.WHITE
        if is_tie and i in winners:
            color = UIConstants.YELLOW

        line = f"{player.name}: {score} points"
        (lw, _lh), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
        cv2.putText(
            frame, line,
            ((width - lw) // 2, y_pos),
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2, cv2.LINE_AA,
        )
        y_pos += 50

    # Per-player stats (compact for 3-4 players)
    max_stats_per_player = 3 if player_count > 2 else 4
    y_pos += 10
    for i in range(player_count):
        player = game_state.versus_players[i]
        stats = game_state.versus_stats[i]
        if not stats:
            continue

        stat_header = f"{player.name}'s Stats:"
        cv2.putText(
            frame, stat_header,
            (width // 2 - 150, y_pos),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, UIConstants.WHITE, 1, cv2.LINE_AA,
        )
        y_pos += 30

        stat_count = 0
        for stat_name, stat_value in stats.items():
            if (
                isinstance(stat_value, (int, float))
                and stat_name not in ["score", "time_elapsed"]
                and stat_count < max_stats_per_player
            ):
                cv2.putText(
                    frame, f"  {stat_name}: {stat_value}",
                    (width // 2 - 130, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, UIConstants.WHITE, 1, cv2.LINE_AA,
                )
                y_pos += 25
                stat_count += 1
        y_pos += 10

    # Draw Rematch and Menu buttons
    btn_w, btn_h, btn_spacing = 200, 50, 30
    total_w = btn_w * 2 + btn_spacing
    btn_start_x = (width - total_w) // 2
    btn_y = height - 120

    from menu_utils import _draw_button

    rematch_rect = (btn_start_x, btn_y, btn_w, btn_h)
    _draw_button(frame, btn_start_x, btn_y, btn_w, btn_h, "Rematch (R)", UIConstants.PRIMARY, game_state=game_state)

    menu_btn_x = btn_start_x + btn_w + btn_spacing
    menu_rect = (menu_btn_x, btn_y, btn_w, btn_h)
    _draw_button(frame, menu_btn_x, btn_y, btn_w, btn_h, "Menu (M)", UIConstants.PRIMARY, game_state=game_state)

    game_state.versus_results_buttons = {
        "rematch": rematch_rect,
        "menu": menu_rect,
    }

    hint = "Press R for rematch | M or ESC for menu"
    (hint_w, _), _ = cv2.getTextSize(hint, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
    cv2.putText(
        frame, hint,
        ((width - hint_w) // 2, btn_y + btn_h + 30),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1, cv2.LINE_AA,
    )

    return frame


def show_versus_results(game_state):
    """
    Display the versus mode results screen showing the winner and stats.
    """
    if getattr(game_state, "showing_versus_results", False):
        logger.info("Results already being shown, skipping redundant display")
        return

    logger.info("Showing versus mode results")
    game_state.showing_versus_results = True

    frame = _render_results_frame(game_state)
    game_state.versus_results_frame = frame

    cv2.imshow(UIConstants.WINDOW_NAME, frame)
    cv2.waitKey(1)

    game_state.current_state = CurrentGameState.MENU


def redraw_versus_results(game_state):
    """Re-render and display the results frame (for click feedback refresh)."""
    frame = _render_results_frame(game_state)
    game_state.versus_results_frame = frame
    cv2.imshow(UIConstants.WINDOW_NAME, frame)
    cv2.waitKey(1)


def start_rematch(game_state):
    """Start a rematch with the same players."""
    game_state.showing_versus_results = False
    game_state.versus_results_frame = None
    game_state.versus_results_buttons = {}
    start_versus_mode(game_state)
    game_state.current_state = CurrentGameState.PLAYING
