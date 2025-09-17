import os
import json
from typing import Dict, List

PLAYED_FILE = "played.json"

class PlayedTracker:
    def __init__(self):
        if os.path.exists(PLAYED_FILE):
            with open(PLAYED_FILE, "r") as f:
                self.data = json.load(f)
        else:
            self.data = {"shows": [], "ads": [], "bumpers": []}
            self.save()

    def save(self):
        with open(PLAYED_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def mark_played(self, file_path: str, category: str):
        if category not in self.data:
            self.data[category] = []
        if file_path not in self.data[category]:
            self.data[category].append(file_path)
            self.save()

    def get_unplayed(self, all_files: list[str], category: str) -> list[str]:
        played = set(self.data.get(category, []))
        all_set = set(all_files)
        if all_set and all_set.issubset(played):
            # reset this category when everything was played
            self.data[category] = []
            self.save()
            return all_files
        return [f for f in all_files if f not in played]

class QueuedTracker:
    """Track which media have been queued in the current playlist cycle."""

    def __init__(self, path: str = "queued.json"):
        """ when we initialize, always recreate queued json"""
        self.path = path
        self.data = {"shows": [], "ads": []}  # bumpers not tracked
        self.save()

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def mark_queued(self, filepath: str, category: str):
        """Mark a file as queued (except bumpers)."""
        if category not in ("shows", "ads"):
            return
        if filepath not in self.data[category]:
            self.data[category].append(filepath)
            self.save()

    def get_unqueued(self, files: List[str], category: str) -> List[str]:
        """Return files not yet queued in this cycle."""
        if category not in ("shows", "ads"):
            return files  # bumpers bypass queue tracking
        return [f for f in files if f not in self.data[category]]

    def reset(self, category: str | None = None):
        """Reset queue for all categories or just one."""
        if category:
            if category in self.data:
                self.data[category] = []
        else:
            self.data = {"shows": [], "ads": []}
        self.save()

