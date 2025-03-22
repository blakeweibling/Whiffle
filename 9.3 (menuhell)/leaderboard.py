import requests
from datetime import datetime
import json
import os

class Leaderboard:
    """Manages the online and local leaderboard using Supabase REST API and a local JSON file."""
    def __init__(self):
        self.supabase_url = "https://jtkbujumrobglftzokcs.supabase.co"
        self.supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp0a2J1anVtcm9iZ2xmdHpva2NzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDIwMTM4NzcsImV4cCI6MjA1NzU4OTg3N30.OibLuqr3X922SUSBL8yGxDw8uwuTjivH97-2wNhJDqs"
        self.headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json"
        }
        self.table_name = "whifflescores"
        self.local_file = "local_leaderboard.json"
        self.local_scores = self.load_local_scores()
        self.logged_online_retrieval = False  # Flag to log online retrieval only once

    def load_local_scores(self):
        """Load scores from the local JSON file."""
        if os.path.exists(self.local_file):
            try:
                with open(self.local_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading local leaderboard: {e}")
                return {}
        return {"classic": [], "timed": []}  # Default structure: {mode: [scores]}

    def save_local_scores(self):
        """Save scores to the local JSON file."""
        try:
            with open(self.local_file, "w") as f:
                json.dump(self.local_scores, f, indent=4)
            print("Saved local leaderboard")
        except Exception as e:
            print(f"Error saving local leaderboard: {e}")

    def submit_score(self, initials: str, score: int, mode: str) -> bool:
        """Submit a score to the Supabase leaderboard and local leaderboard."""
        # Always save to local leaderboard
        if mode not in self.local_scores:
            self.local_scores[mode] = []
        self.local_scores[mode].append({
            "initials": initials[:3].upper(),
            "score": score,
            "mode": mode,
            "created_at": datetime.utcnow().isoformat()
        })
        # Sort local scores by score (descending) and keep top 5
        self.local_scores[mode] = sorted(self.local_scores[mode], key=lambda x: x["score"], reverse=True)[:5]
        self.save_local_scores()

        # Try to submit to online leaderboard using requests
        try:
            data = {
                "initials": initials[:3].upper(),
                "score": score,
                "mode": mode,
                "created_at": datetime.utcnow().isoformat()
            }
            response = requests.post(
                f"{self.supabase_url}/rest/v1/{self.table_name}",
                headers=self.headers,
                json=data
            )
            response.raise_for_status()  # Raises an exception for 4xx/5xx errors
            print(f"Successfully submitted score to online leaderboard: {initials} - {score} ({mode})")
            return True
        except Exception as e:
            print(f"Error submitting score to online leaderboard: {e}")
            return False

    def get_top_scores(self, mode: str, limit: int = 5) -> tuple[list, bool]:
        """Retrieve the top scores for a given mode, falling back to local if online fails."""
        # Try to fetch from online leaderboard using requests
        try:
            params = {
                "mode": f"eq.{mode}",
                "order": "score.desc",
                "limit": limit,
                "select": "initials,score,created_at"
            }
            response = requests.get(
                f"{self.supabase_url}/rest/v1/{self.table_name}",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            scores = response.json()
            if not self.logged_online_retrieval:
                print(f"Successfully retrieved scores from online leaderboard for mode: {mode}")
                self.logged_online_retrieval = True
            return scores, True  # True indicates online scores
        except Exception as e:
            self.logged_online_retrieval = False  # Reset flag on failure to allow logging on next success
            print(f"Error retrieving top scores from online leaderboard: {e}")

        # Fall back to local leaderboard
        if mode in self.local_scores:
            print(f"Using local leaderboard for mode: {mode}")
            return self.local_scores[mode][:limit], False  # False indicates local scores
        else:
            print(f"No scores found in local leaderboard for mode: {mode}")
            return [], False