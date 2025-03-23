"""
Leaderboard management for the Whiffle Tracker project.

This module provides a Leaderboard class to manage online and local leaderboards.
"""

import json
import os
import logging
import requests
from datetime import datetime
from typing import List, Tuple, Dict, Any
from logging import Logger

from constants import DEFAULT_MUSIC_VOLUME

# Leaderboard configuration constants
LEADERBOARD_FILE: str = "whiffle_leaderboard.json"
TABLE_NAME: str = "whifflescores"

# Set up logging
logger: Logger = logging.getLogger(__name__)

class Leaderboard:
    """Manages the online and local leaderboard using Supabase REST API and a local JSON file.

    Attributes:
        requests: The requests module for HTTP calls.
        supabase_url: URL of the Supabase instance.
        supabase_key: API key for Supabase authentication.
        headers: HTTP headers for Supabase requests.
        table_name: Name of the Supabase table for scores.
        local_file: Path to the local leaderboard JSON file.
        local_scores: Dictionary of local scores by mode.
    """
    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        self.requests = requests
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.headers: Dict[str, str] = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json"
        }
        self.table_name: str = TABLE_NAME
        self.local_file: str = LEADERBOARD_FILE
        self.local_scores: Dict[str, List[Dict[str, Any]]] = self._load_local_scores()

    def _load_local_scores(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load local scores from the JSON file.

        Returns:
            Dictionary of scores by mode, or an empty dict if the file doesn't exist or is invalid.
        """
        if os.path.exists(self.local_file):
            try:
                with open(self.local_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading local leaderboard from {self.local_file}: {e}")
                return {"classic": [], "timed": []}
        return {"classic": [], "timed": []}

    def _save_local_scores(self) -> None:
        """Save local scores to the JSON file."""
        try:
            with open(self.local_file, "w") as f:
                json.dump(self.local_scores, f, indent=4)
            logger.info(f"Saved local leaderboard to {self.local_file}")
        except Exception as e:
            logger.error(f"Error saving local leaderboard to {self.local_file}: {e}")

    def _make_supabase_request(self, method: str, endpoint: str, data: Dict[str, Any] = None, params: Dict[str, str] = None) -> Any:
        """
        Make a request to the Supabase API.

        Args:
            method: HTTP method ("post" or "get").
            endpoint: API endpoint.
            data: Data to send for POST requests.
            params: Query parameters for GET requests.

        Returns:
            Response data from the API.

        Raises:
            requests.RequestException: If the request fails.
        """
        url = f"{self.supabase_url}/rest/v1/{self.table_name}"
        try:
            if method == "post":
                response = self.requests.post(url, headers=self.headers, json=data)
            else:
                response = self.requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json() if method == "get" else None
        except requests.RequestException as e:
            logger.error(f"Supabase request failed: {e}, status_code={getattr(e.response, 'status_code', 'N/A')}")
            raise

    def submit_score(self, initials: str, score: int, mode: str) -> bool:
        """
        Submit a score to the leaderboard, both online and locally.

        Args:
            initials: Player initials (max 3 characters).
            score: Player's score.
            mode: Game mode ("classic" or "timed").

        Returns:
            bool: True if the online submission was successful, False otherwise.
        """
        if mode not in self.local_scores:
            self.local_scores[mode] = []

        # Add to local scores
        score_entry = {
            "initials": initials[:3].upper(),
            "score": score,
            "mode": mode,
            "created_at": datetime.utcnow().isoformat()
        }
        self.local_scores[mode].append(score_entry)
        self.local_scores[mode] = sorted(self.local_scores[mode], key=lambda x: x["score"], reverse=True)[:5]
        self._save_local_scores()

        # Submit to online leaderboard
        try:
            self._make_supabase_request("post", self.table_name, data=score_entry)
            logger.info(f"Successfully submitted score to online leaderboard: {initials} - {score} ({mode})")
            return True
        except requests.RequestException:
            logger.warning(f"Failed to submit score to online leaderboard, saved locally")
            return False

    def get_top_scores(self, mode: str, limit: int = 5) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Retrieve the top scores for a given mode.

        Args:
            mode: Game mode ("classic" or "timed").
            limit: Maximum number of scores to return (default: 5).

        Returns:
            Tuple of (scores, online), where scores is a list of score entries,
            and online is True if retrieved from Supabase, False if from local storage.
        """
        try:
            params = {
                "mode": f"eq.{mode}",
                "order": "score.desc",
                "limit": str(limit),
                "select": "initials,score,created_at"
            }
            scores = self._make_supabase_request("get", self.table_name, params=params)
            logger.info(f"Successfully retrieved scores from online leaderboard for mode: {mode}")
            return scores, True
        except requests.RequestException:
            logger.warning(f"Failed to retrieve top scores from online leaderboard, using local scores")

        if mode in self.local_scores:
            logger.info(f"Using local leaderboard for mode: {mode}")
            return self.local_scores[mode][:limit], False
        logger.info(f"No scores found in local leaderboard for mode: {mode}")
        return [], False