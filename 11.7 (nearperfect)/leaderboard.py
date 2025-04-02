"""
Leaderboard management for the Whiffle Tracker project.

This module provides a Leaderboard class to manage online and local leaderboards.
"""

import json
import os
import logging
import requests
from datetime import datetime
from time import sleep
from typing import List, Tuple, Dict, Any
from logging import Logger

from game_constants import LeaderboardConstants

# Set up logging
logger: Logger = logging.getLogger(__name__)


class Leaderboard:
    """Manages the online and local leaderboard using Supabase REST API and a local JSON file.

    Attributes:
        supabase_url: URL of the Supabase instance.
        supabase_key: API key for Supabase authentication.
        headers: HTTP headers for Supabase requests.
        table_name: Name of the Supabase table for scores.
        local_file: Path to the local leaderboard JSON file.
        local_scores: Dictionary of local scores by mode.
        pending_scores: List of scores queued for batch submission to Supabase.
    """

    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        if not supabase_url or not supabase_key:
            logger.error("Supabase URL and key must be provided")
            raise ValueError("Supabase URL and key must be provided")
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.headers: Dict[str, str] = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
        }
        self.table_name: str = LeaderboardConstants.TABLE_NAME
        self.local_file: str = LeaderboardConstants.LEADERBOARD_FILE
        self.local_scores: Dict[str, List[Dict[str, Any]]] = self._load_local_scores()
        self.pending_scores: List[Dict[str, Any]] = (
            []
        )  # Queue for batch updates (Change 4)

    def _load_local_scores(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load local scores from the JSON file.

        Returns:
            Dictionary of scores by mode, or an empty dict if the file doesn't exist or is invalid.

        Examples:
            >>> lb = Leaderboard("url", "key")
            >>> lb._load_local_scores()
            {"classic": [{"player_name": "Player 1", "score": 100, "mode": "classic", "created_at": "2023-..."}]}
        """
        if not os.path.exists(self.local_file):
            logger.info(
                f"Local leaderboard file {self.local_file} does not exist, initializing empty scores"
            )
            return {"classic": [], "timed": []}
        try:
            with open(self.local_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    logger.warning(
                        f"{self.local_file} contains invalid data, resetting to empty scores"
                    )
                    return {"classic": [], "timed": []}
                return data
        except json.JSONDecodeError as e:
            logger.error(
                f"Invalid JSON in {self.local_file}: {e}, resetting to empty scores"
            )
            return {"classic": [], "timed": []}
        except (IOError, PermissionError) as e:
            logger.error(
                f"Failed to read {self.local_file}: {e}, returning empty scores"
            )
            return {"classic": [], "timed": []}

    def _save_local_scores(self) -> None:
        """Save local scores to the JSON file."""
        try:
            with open(self.local_file, "w", encoding="utf-8") as f:
                json.dump(self.local_scores, f, indent=4)
            logger.info(f"Saved local leaderboard to {self.local_file}")
        except (IOError, PermissionError) as e:
            logger.error(f"Error saving local leaderboard to {self.local_file}: {e}")

    def _post_supabase(
        self, data: List[Dict[str, Any]], retries: int = 3, delay: float = 1
    ) -> None:
        """
        Make a POST request to the Supabase API with retry logic.

        Args:
            data: List of score entries to send in the POST request.
            retries: Number of retry attempts on failure.
            delay: Delay in seconds between retries.

        Raises:
            requests.RequestException: If all retries fail.
        """
        url = f"{self.supabase_url}/rest/v1/{self.table_name}"
        for attempt in range(retries):
            try:
                response = requests.post(url, headers=self.headers, json=data)
                if response.status_code == 429:
                    logger.warning(
                        f"Rate limit hit on attempt {attempt + 1}, retrying in {delay}s"
                    )
                    sleep(delay)
                    continue
                response.raise_for_status()
                return
            except requests.Timeout:
                logger.error(f"Request timed out on attempt {attempt + 1}")
                if attempt == retries - 1:
                    raise
                sleep(delay)
            except requests.RequestException as e:
                logger.error(
                    f"Supabase POST failed on attempt {attempt + 1}: {e}, "
                    f"status: {getattr(e.response, 'status_code', 'N/A')}"
                )
                if attempt == retries - 1:
                    raise
                sleep(delay)

    def _get_supabase(
        self, params: Dict[str, str], retries: int = 3, delay: float = 1
    ) -> List[Dict[str, Any]]:
        """
        Make a GET request to the Supabase API with retry logic.

        Args:
            params: Query parameters for the GET request.
            retries: Number of retry attempts on failure.
            delay: Delay in seconds between retries.

        Returns:
            Response data from the API.

        Raises:
            requests.RequestException: If all retries fail.
        """
        url = f"{self.supabase_url}/rest/v1/{self.table_name}"
        for attempt in range(retries):
            try:
                response = requests.get(url, headers=self.headers, params=params)
                if response.status_code == 429:
                    logger.warning(
                        f"Rate limit hit on attempt {attempt + 1}, retrying in {delay}s"
                    )
                    sleep(delay)
                    continue
                response.raise_for_status()
                return response.json()
            except requests.Timeout:
                logger.error(f"Request timed out on attempt {attempt + 1}")
                if attempt == retries - 1:
                    raise
                sleep(delay)
            except requests.RequestException as e:
                logger.error(
                    f"Supabase GET failed on attempt {attempt + 1}: {e}, "
                    f"status: {getattr(e.response, 'status_code', 'N/A')}"
                )
                if attempt == retries - 1:
                    raise
                sleep(delay)

    def submit_score(self, player_name: str, score: int, mode: str) -> bool:
        """
        Queue a score for batch submission to the leaderboard, both online and locally.

        Args:
            player_name: Player's name.
            score: Player's score.
            mode: Game mode ("classic" or "timed").

        Returns:
            bool: True (score is queued for submission).
        """
        if not isinstance(mode, str) or mode not in {"classic", "timed"}:
            logger.warning(f"Invalid mode '{mode}', defaulting to 'classic'")
            mode = "classic"

        score_entry = {
            "player_name": player_name,  # Changed from "initials" to "player_name"
            "score": score,
            "mode": mode,
            "created_at": datetime.utcnow().isoformat(),
        }

        if mode not in self.local_scores:
            self.local_scores[mode] = []
        self.local_scores[mode].append(score_entry)
        self._save_local_scores()

        # Queue for batch submission (Change 4)
        self.pending_scores.append(score_entry)
        logger.info(
            f"Score queued for batch submission: {player_name} - {score} ({mode})"
        )
        return True  # Assume success for now

    def flush_pending_scores(self, retries: int = 3, delay: float = 1) -> None:
        """
        Submit all queued scores to Supabase in a batch.

        Args:
            retries: Number of retry attempts on failure.
            delay: Delay in seconds between retries.
        """
        if not self.pending_scores:
            logger.debug("No pending scores to flush")
            return
        try:
            self._post_supabase(self.pending_scores, retries, delay)
            logger.info(
                f"Successfully submitted {len(self.pending_scores)} scores to online leaderboard"
            )
            self.pending_scores.clear()
        except requests.RequestException:
            logger.warning(
                f"Failed to submit {len(self.pending_scores)} scores to online leaderboard, keeping in queue"
            )

    def get_top_scores(
        self, mode: str, limit: int = 5
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Retrieve the top scores for a given mode.

        Args:
            mode: Game mode ("classic" or "timed").
            limit: Maximum number of scores to return (default: 5).

        Returns:
            Tuple of (scores, online), where scores is a list of score entries sorted by score descending,
            and online is True if retrieved from Supabase, False if from local storage.
        """
        if not isinstance(mode, str) or mode not in self.local_scores:
            logger.warning(f"Invalid or unknown mode '{mode}', defaulting to 'classic'")
            mode = "classic"

        try:
            params = {
                "mode": f"eq.{mode}",
                "order": "score.desc",
                "limit": str(limit),
                "select": "player_name,score,created_at",  # Updated to select player_name
            }
            scores = self._get_supabase(params)
            logger.info(
                f"Successfully retrieved {len(scores)} scores from online leaderboard for mode: {mode}"
            )
            return scores, True
        except requests.RequestException:
            logger.warning(
                f"Failed to retrieve top scores from online leaderboard, using local scores"
            )
            if mode in self.local_scores:
                sorted_scores = sorted(
                    self.local_scores[mode], key=lambda x: x["score"], reverse=True
                )[:limit]
                logger.info(
                    f"Using local leaderboard with {len(sorted_scores)} scores for mode: {mode}"
                )
                return sorted_scores, False
            logger.info(f"No scores found in local leaderboard for mode: {mode}")
            return [], False
