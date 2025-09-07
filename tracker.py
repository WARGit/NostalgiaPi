import os
import json

PLAYED_FILE = "played.json"

class PlayedTracker:
    def __init__(self):
        if os.path.exists(PLAYED_FILE):
            with open(PLAYED_FILE, "r") as f:
                self.data = json.load(f)
        else:
            self.data = {"shows": [], "ads": [], "bumpers": []}
            self._save()

    def _save(self):
        with open(PLAYED_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def mark_played(self, file_path: str, category: str):
        if category not in self.data:
            self.data[category] = []
        if file_path not in self.data[category]:
            self.data[category].append(file_path)
            self._save()

    def get_unplayed(self, all_files: list[str], category: str) -> list[str]:
        played = set(self.data.get(category, []))
        all_set = set(all_files)
        if all_set and all_set.issubset(played):
            # reset this category when everything was played
            self.data[category] = []
            self._save()
            return all_files
        return [f for f in all_files if f not in played]
