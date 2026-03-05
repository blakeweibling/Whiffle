# leaderboard.txt
"""
Leaderboard management for the Whiffle Tracker project.

This module provides a Leaderboard class to manage online and local leaderboards.
"""

import json
import logging
import os
from datetime import datetime
from logging import Logger
from time import sleep
from typing import Any, Dict, List, Tuple, Optional

import requests

# Suppress SSL warnings since we're disabling verification
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from constants import LeaderboardConstants

# Set up logging
logger: Logger = logging.getLogger(__name__)

# --- UPDATED: Add "retro" to the set of valid modes ---
VALID_MODES = {"classic", "timed", "fun", "practice", "survival", "retro"}
# --- END UPDATE ---

# Log SSL warning only once per process to avoid duplicate messages
_ssl_warning_logged = False


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

        # Warning about disabled SSL verification (log once per process)
        global _ssl_warning_logged
        if not _ssl_warning_logged:
            _ssl_warning_logged = True
            logger.warning(
                "SSL certificate verification is disabled for Supabase requests. This is not recommended for production environments."
            )

    def _load_local_scores(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load local scores from the JSON file.
        Returns:
            Dictionary of scores by mode, or an empty dict if the file doesn't exist or is invalid.
        """
        # --- UPDATED: Initialize structure with all valid modes ---
        default_scores = {mode: [] for mode in VALID_MODES}
        # --- END UPDATE ---

        if not os.path.exists(self.local_file):
            logger.info(
                f"Local leaderboard file {self.local_file} does not exist, initializing empty scores"
            )
            return default_scores  # Return initialized structure
        try:
            with open(self.local_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    logger.warning(
                        f"{self.local_file} contains invalid data, resetting to empty scores"
                    )
                    return default_scores  # Return initialized structure

                # --- UPDATED: Ensure all valid modes exist in loaded data ---
                for mode in VALID_MODES:
                    if mode not in data:
                        logger.warning(
                            f"Mode '{mode}' missing in {self.local_file}, initializing empty list."
                        )
                        data[mode] = []
                    elif not isinstance(data[mode], list):
                        logger.warning(
                            f"Data for mode '{mode}' in {self.local_file} is not a list, resetting."
                        )
                        data[mode] = []
                return data  # Return potentially corrected data
                # --- END UPDATE ---
        except json.JSONDecodeError as e:
            logger.error(
                f"Invalid JSON in {self.local_file}: {e}, resetting to empty scores"
            )
            return default_scores  # Return initialized structure
        except (IOError, PermissionError) as e:
            logger.error(
                f"Failed to read {self.local_file}: {e}, returning empty scores"
            )
            return default_scores  # Return initialized structure

    def _save_local_scores(self) -> None:
        """Save local scores to the JSON file."""
        try:
            # --- UPDATED: Ensure all valid modes are present before saving ---
            for mode in VALID_MODES:
                if mode not in self.local_scores:
                    self.local_scores[mode] = []
            # --- END UPDATE ---
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

        # Validate and sanitize data before sending
        validated_data = []
        for entry in data:
            # Ensure required fields are present and of proper type
            if (
                isinstance(entry.get("player_name"), str)
                and isinstance(entry.get("score"), int)
                and isinstance(entry.get("mode"), str)
                and entry.get("mode") in VALID_MODES
            ):
                # Create a clean entry with only the fields expected by the API
                # Always include screenshot_url field, set to None if not present
                clean_entry = {
                    "player_name": entry["player_name"],
                    "score": entry["score"],
                    "mode": entry["mode"],
                    "created_at": entry.get(
                        "created_at", datetime.utcnow().isoformat()
                    ),
                    "screenshot_url": entry.get("screenshot_url"),
                }
                if entry.get("playfield_type") in {"whiffle", "fivestar"}:
                    clean_entry["playfield_type"] = entry["playfield_type"]

                validated_data.append(clean_entry)
            else:
                logger.warning(f"Skipping invalid score entry: {entry}")

        if not validated_data:
            logger.warning("No valid data to send to Supabase after validation")
            return

        for attempt in range(retries):
            try:
                response = requests.post(
                    url,
                    headers=self.headers,
                    json=validated_data,
                    timeout=10,
                    verify=False,
                )  # Added verify=False to bypass SSL cert verification

                if response.status_code == 429:
                    logger.warning(
                        f"Rate limit hit on attempt {attempt + 1}, retrying in {delay}s"
                    )
                    sleep(delay)
                    continue

                # Try to get more detailed error information
                if response.status_code >= 400:
                    try:
                        error_detail = response.json()
                        logger.error(f"Supabase error details: {error_detail}")
                    except Exception:
                        logger.error(
                            f"Supabase error (no details available): {response.text[:500]}"
                        )

                response.raise_for_status()
                logger.info(f"Supabase POST successful (status {response.status_code})")
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

                # Try to get response content for more details
                try:
                    if hasattr(e, "response") and e.response is not None:
                        content = e.response.text
                        logger.error(f"Error response content: {content[:500]}")
                except Exception:
                    pass

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
                response = requests.get(
                    url, headers=self.headers, params=params, timeout=10, verify=False
                )  # Added verify=False to bypass SSL cert verification
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

    def submit_score(
        self,
        player_name: str,
        score: int,
        mode: str,
        screenshot_url: Optional[str] = None,
        playfield_type: Optional[str] = None,
    ) -> bool:
        """
        Queue a score for batch submission to the leaderboard, both online and locally.
        Args:
            player_name: Player's name.
            score: Player's score.
            mode: Game mode (must be in VALID_MODES).
            screenshot_url: Optional URL to a screenshot of the game.
            playfield_type: Optional playfield type ("whiffle" or "fivestar").

        Returns:
            bool: True (score is queued for submission).
        """
        # --- UPDATED: Validate against VALID_MODES set ---
        if not isinstance(mode, str) or mode not in VALID_MODES:
            logger.warning(
                f"Invalid mode '{mode}' for score submission, defaulting to 'classic'"
            )
            mode = "classic"
        # --- END UPDATE ---

        score_entry = {
            "player_name": player_name,  # Changed from "initials" to "player_name"
            "score": score,
            "mode": mode,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Add screenshot URL if provided
        if screenshot_url:
            score_entry["screenshot_url"] = screenshot_url
            logger.info(
                f"Including screenshot URL with score submission: {screenshot_url}"
            )
        if playfield_type:
            score_entry["playfield_type"] = playfield_type

        # --- UPDATED: Ensure mode key exists before appending ---
        if mode not in self.local_scores:
            self.local_scores[mode] = []  # Initialize if somehow missing
        # --- END UPDATE ---
        self.local_scores[mode].append(score_entry)
        self._save_local_scores()

        # Queue for batch submission (Change 4)
        self.pending_scores.append(score_entry)
        logger.info(
            f"Score queued for batch submission: {player_name} - {score} ({mode}, {playfield_type or 'unspecified'})"
        )
        return True  # Assume success for now

    def flush_pending_scores(self, retries: int = 3, delay: float = 1) -> int:
        """
        Submit all queued scores to Supabase in a batch.
        Args:
            retries: Number of retry attempts on failure.
            delay: Delay in seconds between retries.
        Returns:
            Number of scores successfully submitted (0 if none or on failure).
        """
        if not self.pending_scores:
            logger.debug("No pending scores to flush")
            return 0

        # Make a copy of the scores to avoid modifying during iteration
        scores_to_submit = self.pending_scores.copy()
        count = len(scores_to_submit)

        try:
            logger.info(
                f"Attempting to flush {count} pending score(s) to online leaderboard"
            )
            self._post_supabase(scores_to_submit, retries, delay)
            logger.info(
                f"Successfully submitted {count} scores to online leaderboard"
            )
            self.pending_scores.clear()
            return count
        except requests.RequestException as e:
            logger.warning(f"Failed to submit scores to online leaderboard: {e}")
            # We keep the scores in pending_scores for possible future submission
            logger.warning(
                f"Failed to submit {len(self.pending_scores)} scores to online leaderboard, keeping in queue"
            )
            return 0
        except Exception as e:
            # Catch any other exceptions to ensure game can still exit gracefully
            logger.error(f"Unexpected error when flushing scores: {e}")
            # Don't clear pending_scores, but don't let the exception propagate either
            return 0

    def get_top_scores(
        self, mode: str, limit: int = 5
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Retrieve the top scores for a given mode.
        Args:
            mode: Game mode (must be in VALID_MODES).
            limit: Maximum number of scores to return (default: 5).

        Returns:
            Tuple of (scores, online), where scores is a list of score entries sorted by score descending,
            and online is True if retrieved from Supabase, False if from local storage.
        """
        # --- UPDATED: Validate against VALID_MODES set ---
        if not isinstance(mode, str) or mode not in VALID_MODES:
            logger.warning(
                f"Invalid or unknown mode '{mode}' for get_top_scores, defaulting to 'classic'"
            )
            mode = "classic"
        # --- END UPDATE ---

        try:
            params = {
                "mode": f"eq.{mode}",
                "order": "score.desc",
                "limit": str(limit),
                "select": "player_name,score,created_at,screenshot_url",  # Added screenshot_url
            }
            scores = self._get_supabase(params)
            logger.debug(
                f"Successfully retrieved {len(scores)} scores from online leaderboard for mode: {mode}"
            )
            return scores, True
        except requests.RequestException:
            logger.warning(
                "Failed to retrieve top scores from online leaderboard, using local scores"
            )
            # --- UPDATED: Ensure mode key exists before accessing ---
            if mode in self.local_scores:
                sorted_scores = sorted(
                    self.local_scores[mode],
                    key=lambda x: x.get("score", 0),  # Use .get for safety
                    reverse=True,
                )[:limit]
                logger.debug(
                    f"Using local leaderboard with {len(sorted_scores)} scores for mode: {mode}"
                )
                return sorted_scores, False
            # --- END UPDATE ---
            logger.debug(f"No scores found in local leaderboard for mode: {mode}")
            return [], False
