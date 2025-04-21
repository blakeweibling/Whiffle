# leaderboard.py
import json
import os
from datetime import datetime

class Leaderboard:
    def __init__(self):
        self.local_file = "local_leaderboard.json"
        self.local_scores = self.load_local_scores()

    def load_local_scores(self):
        if os.path.exists(self.local_file):
            try:
                with open(self.local_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading local leaderboard: {e}")
                return {}
        return {"classic": [], "timed": []}

    def save_local_scores(self):
        try:
            with open(self.local_file, "w") as f:
                json.dump(self.local_scores, f, indent=4)
            print("Saved local leaderboard")
        except Exception as e:
            print(f"Error saving local leaderboard: {e}")

    def submit_score(self, initials: str, score: int, mode: str) -> bool:
        if mode not in self.local_scores:
            self.local_scores[mode] = []
        self.local_scores[mode].append({
            "initials": initials[:3].upper(),
            "score": score,
            "mode": mode,
            "created_at": datetime.utcnow().isoformat()
        })
        self.local_scores[mode] = sorted(self.local_scores[mode], key=lambda x: x["score"], reverse=True)[:5]  # Keep top 5
        self.save_local_scores()
        print(f"Submitted score to local leaderboard: {initials} - {score} ({mode})")
        return True

    def get_top_scores(self, mode: str, limit: int = 5) -> tuple[list, bool]:
        if mode in self.local_scores:
            print(f"Using local leaderboard for mode: {mode}")
            return self.local_scores[mode][:limit], False
        else:
            print(f"No scores found in local leaderboard for mode: {mode}")
            return [], False