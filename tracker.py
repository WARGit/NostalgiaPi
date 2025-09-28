import os
import json
import logging
from datetime import datetime

class PlayedTracker:
    """Track which media have been played, per schedule"""

    def __init__(self, path: str = "played.json"):
        logging.debug(f"Init PlayedTracker with path {path}")
        self.path = path
        if os.path.exists(self.path):
            logging.debug(f"path exists, loading from {self.path}")
            with open(self.path, "r") as f:
                self.data = json.load(f)
        else:
            logging.debug(f"path does not exist, creating path")
            self.data = {}  # per-schedule: {schedule_name: {"shows": [], "ads": [], "bumpers": []}}
            self.save()

    def save(self):
        logging.debug(f"Saving data to {self.path}")
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def ensure_schedule(self, schedule: str):
        logging.debug(f"Checking if schedule {schedule} is in PlayedTracker data")
        if schedule not in self.data:
            logging.debug(f"Schedule {schedule} is not in data, adding")
            self.data[schedule] = {"shows": [], "ads": [], "bumpers": []}
        else:
            logging.debug(f"Schedule {schedule} is already in data")

    def mark_played(self, schedule: str, filepath: str, category: str):
        """Mark a file as played under a schedule"""
        logging.debug("Begin marking file as played")
        self.ensure_schedule(schedule)
        logging.debug(f"checking if filepath {filepath} is in data")
        if filepath not in self.data[schedule][category]:
            logging.debug(f"filepath {filepath} is not in data, appending and saving")
            self.data[schedule][category].append(filepath)
            self.save()
        else:
            logging.debug(f"filepath {filepath} is in data")

    def reset_if_exhausted(self, schedule: str, category: str):
        """Reset JSON for this schedule/category if all items have been played"""
        logging.debug("Begin reset_if_exhausted")
        self.ensure_schedule(schedule)
        logging.debug(f"Get all played from data")
        all_played = self.data[schedule].get(category, [])
        if all_played:
            print(f"Resetting played {category} for schedule '{schedule}'")
            self.data[schedule][category] = []
            self.save()
        else:
            print(f"{category} for schedule '{schedule}' are not exhausted")

QUEUED_JSON_PATH = "queued.json"

class QueuedTracker:
    """Track which media has been queued in the current playlist cycle"""

    def __init__(self):
        self.filepath = QUEUED_JSON_PATH
        self.data: list[dict] = [] #= self.load()
        # always delete json before we start
        if os.path.exists(QUEUED_JSON_PATH):
            os.remove(QUEUED_JSON_PATH)

    def load(self) -> list[dict]:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    data = json.load(f)
                    return data
            except Exception as e:
                logging.error(f"Failed to load queued.json: {e}")
        return []

    def save(self):
        logging.debug(f"Saving data to {self.filepath}")
        try:
            with open(self.filepath, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save queued.json: {e}")

    def mark_queued(self, filepath: str, category: str, scheduled_time: datetime):
        """Add an item to queued.json (shows/ads only) for display via web ui"""
        if category not in ("shows", "ads"):
            logging.debug(f"{category} are not tracked as part of queue")
            return

        entry = {
            "category": category,
            "filepath": filepath,
            "time": scheduled_time.isoformat()
        }

        logging.debug(f"Queueing {filepath} at {entry['time']} in category {category}")
        self.data.append(entry)
        self.save()
