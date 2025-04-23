# versus_mode.py
"""
Versus mode implementation for Whiffle Tracker.
Provides functionality for two players to compete by taking turns.
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
    Initialize versus mode with two players.
    """
    # Ensure we have two different players
    if len(game_state.players) < 2:
        # Add a second player if needed
        if len(game_state.players) == 0:
            from player import Player

            game_state.players.append(Player("Player 1"))
        if len(game_state.players) == 1:
            from player import Player

            game_state.players.append(Player("Player 2"))

    # Setup versus mode
    game_state.versus_mode_active = True
    game_state.versus_players = [game_state.players[0], game_state.players[1]]
    game_state.current_turn_player_index = 0
    game_state.versus_scores = [0, 0]
    game_state.versus_stats = [{}, {}]

    # Start with first player
    game_state.reset_game(game_state.versus_players[0].name, "versus")

    # Display turn notification
    show_notification(
        game_state, f"{game_state.versus_players[0].name}'s Turn", duration=3.0
    )

    logger.info(
        f"Started versus mode with {game_state.versus_players[0].name} vs {game_state.versus_players[1].name}"
    )


def switch_versus_player_turn(game_state):
    """
    Switch to the next player's turn in versus mode.
    Save current player's score and stats.
    """
    # Save current player's score
    current_player = game_state.current_turn_player_index
    game_state.versus_scores[current_player] = game_state.score

    # Store stats for current player
    if game_state.data_logger and hasattr(game_state, "current_session_stats"):
        if game_state.current_session_stats is not None:
            game_state.versus_stats[current_player] = (
                game_state.current_session_stats.copy()
            )

    # Switch player
    game_state.current_turn_player_index = 1 if current_player == 0 else 0
    next_player = game_state.versus_players[game_state.current_turn_player_index]

    # Reset for next player's turn
    game_state.reset_game(next_player.name, "versus")

    # Display turn notification
    show_notification(game_state, f"{next_player.name}'s Turn", duration=3.0)

    logger.info(f"Switched to {next_player.name}'s turn in versus mode")


def check_versus_mode_end(game_state) -> bool:
    """
    Check if the versus mode should end or switch to the next player.
    Returns True if action was taken (switching player or ending game).
    """
    if not game_state.versus_mode_active:
        return False

    if game_state.current_state == CurrentGameState.GAME_OVER:
        if game_state.current_turn_player_index == 1:
            # Both players finished, show versus results
            show_versus_results(game_state)
            return True
        elif game_state.current_turn_player_index == 0:
            # First player finished, switch to second player
            switch_versus_player_turn(game_state)
            return True

    return False


def show_versus_results(game_state):
    """
    Display the versus mode results screen showing the winner and stats.
    """
    frame = np.zeros(
        (game_state.current_height, game_state.current_width, 3), dtype=np.uint8
    )

    # Determine winner
    winner_idx = 0 if game_state.versus_scores[0] > game_state.versus_scores[1] else 1
    winner_name = game_state.versus_players[winner_idx].name

    # Draw header
    cv2.putText(
        frame,
        "VERSUS MODE RESULTS",
        (int(game_state.current_width / 2) - 200, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.5,
        UIConstants.WHITE,
        2,
        cv2.LINE_AA,
    )

    # Draw winner announcement
    if game_state.versus_scores[0] == game_state.versus_scores[1]:
        cv2.putText(
            frame,
            "IT'S A TIE!",
            (int(game_state.current_width / 2) - 100, 180),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            UIConstants.YELLOW,
            2,
            cv2.LINE_AA,
        )
    else:
        cv2.putText(
            frame,
            f"WINNER: {winner_name}",
            (int(game_state.current_width / 2) - 150, 180),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            UIConstants.GREEN,
            2,
            cv2.LINE_AA,
        )

    # Draw player scores
    y_pos = 250
    for i in range(2):
        player = game_state.versus_players[i]
        score = game_state.versus_scores[i]
        color = (
            UIConstants.GREEN
            if i == winner_idx
            and game_state.versus_scores[0] != game_state.versus_scores[1]
            else UIConstants.WHITE
        )

        cv2.putText(
            frame,
            f"{player.name}: {score} points",
            (int(game_state.current_width / 2) - 150, y_pos),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            color,
            2,
            cv2.LINE_AA,
        )
        y_pos += 50

    # Draw additional stats
    y_pos = 350
    for i in range(2):
        player = game_state.versus_players[i]
        stats = game_state.versus_stats[i]

        if stats:
            cv2.putText(
                frame,
                f"{player.name}'s Stats:",
                (int(game_state.current_width / 2) - 150, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                UIConstants.WHITE,
                1,
                cv2.LINE_AA,
            )
            y_pos += 40

            # Display at most 4 stats per player
            stat_count = 0
            for stat_name, stat_value in stats.items():
                if (
                    isinstance(stat_value, (int, float))
                    and stat_name not in ["score", "time_elapsed"]
                    and stat_count < 4
                ):
                    cv2.putText(
                        frame,
                        f"  {stat_name}: {stat_value}",
                        (int(game_state.current_width / 2) - 130, y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        UIConstants.WHITE,
                        1,
                        cv2.LINE_AA,
                    )
                    y_pos += 30
                    stat_count += 1
        y_pos += 20

    # Draw instructions
    cv2.putText(
        frame,
        "Press 'M' to return to menu",
        (int(game_state.current_width / 2) - 150, game_state.current_height - 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        UIConstants.WHITE,
        1,
        cv2.LINE_AA,
    )

    cv2.imshow(UIConstants.WINDOW_NAME, frame)
    cv2.waitKey(100)  # Small delay to ensure display

    # Wait for user input
    while True:
        key = cv2.waitKey(10) & 0xFF
        if key == ord("m") or key == ord("M"):
            game_state.current_state = CurrentGameState.MENU
            game_state.versus_mode_active = False
            break
