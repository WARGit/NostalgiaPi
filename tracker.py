import os
import json
from typing import List

class PlayedTracker:
    """Track which media have been played, per schedule."""

    def __init__(self, path: str = "played.json"):
        self.path = path
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                self.data = json.load(f)
        else:
            self.data = {}  # per-schedule: {schedule_name: {"shows": [], "ads": [], "bumpers": []}}
            self.save()

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def _ensure_schedule(self, schedule: str):
        if schedule not in self.data:
            self.data[schedule] = {"shows": [], "ads": [], "bumpers": []}

    def mark_played(self, schedule: str, filepath: str, category: str):
        """Mark a file as played under a schedule."""
        self._ensure_schedule(schedule)
        if filepath not in self.data[schedule][category]:
            self.data[schedule][category].append(filepath)
            self.save()

    def get_unplayed(self, schedule: str, all_files: List[str], category: str) -> List[str]:
        self._ensure_schedule(schedule)
        played = set(self.data[schedule].get(category, []))
        all_set = set(all_files)
        if all_set and all_set.issubset(played):
            # Everything played → reset only this schedule + category
            self.data[schedule][category] = []
            self.save()
            return all_files
        return [f for f in all_files if f not in played]

    def reset_if_exhausted(self, schedule: str, category: str):
        """Reset JSON for this schedule/category if all items have been played."""
        self._ensure_schedule(schedule)
        all_played = self.data[schedule].get(category, [])
        if all_played:
            print(f"[RESET] Resetting played {category} for schedule '{schedule}'")
            self.data[schedule][category] = []
            self.save()


class QueuedTracker:
    """Track which media have been queued in the current playlist cycle, per schedule."""

    def __init__(self, path: str = "queued.json"):
        self.path = path
        self.data = {}  # per-schedule: {schedule_name: {"shows": [], "ads": []}}
        self.save()  # always clear queued.json on init

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def _ensure_schedule(self, schedule: str):
        if schedule not in self.data:
            self.data[schedule] = {"shows": [], "ads": []}  # bumpers not tracked

    def mark_queued(self, schedule: str, filepath: str, category: str):
        """Mark a file as queued (except bumpers)."""
        if category not in ("shows", "ads"):
            return
        self._ensure_schedule(schedule)
        if filepath not in self.data[schedule][category]:
            self.data[schedule][category].append(filepath)
            self.save()

    def get_unqueued(self, schedule: str, files: List[str], category: str) -> List[str]:
        if category not in ("shows", "ads"):
            return files  # bumpers bypass queue tracking
        self._ensure_schedule(schedule)
        return [f for f in files if f not in self.data[schedule][category]]

    def reset(self, schedule: str | None = None, category: str | None = None):
        """Reset queue for all schedules/categories or a specific one."""
        if schedule:
            self._ensure_schedule(schedule)
            if category:
                if category in self.data[schedule]:
                    self.data[schedule][category] = []
            else:
                self.data[schedule] = {"shows": [], "ads": []}
        else:
            self.data = {}
        self.save()

    def reset_if_exhausted(self, schedule: str, category: str):
        """Reset JSON for this schedule/category if all items have been queued."""
        self._ensure_schedule(schedule)
        all_queued = self.data[schedule].get(category, [])
        if all_queued:
            print(f"[RESET] Resetting queued {category} for schedule '{schedule}'")
            self.data[schedule][category] = []
            self.save()
