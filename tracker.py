import os
import json
import logging

class PlayedTracker:
    """Track which media have been played, per schedule."""

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
        """Mark a file as played under a schedule."""
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
        """Reset JSON for this schedule/category if all items have been played."""
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

class QueuedTracker:
    """Track which media have been queued in the current playlist cycle, per schedule."""

    def __init__(self, path: str = "queued.json"):
        logging.debug(f"Init QueuedTracker with path {path}")
        self.path = path
        self.data = {}  # per-schedule: {schedule_name: {"shows": [], "ads": []}}
        self.save()  # always clear queued.json on init

    def save(self):
        logging.debug(f"Saving data to {self.path}")
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def ensure_schedule(self, schedule: str):
        if schedule not in self.data:
            logging.debug(f"Schedule {schedule} is not in data, adding")
            self.data[schedule] = {"shows": [], "ads": []}  # bumpers not tracked
        else:
            logging.debug(f"Schedule {schedule} is already in data")

    def mark_queued(self, schedule: str, filepath: str, category: str):
        """Mark a file as queued (except bumpers)."""
        if category not in ("shows", "ads"):
            logging.debug(f"Category {category} is not in array, returning")
            return

        self.ensure_schedule(schedule)
        if filepath not in self.data[schedule][category]:
            logging.debug(f"filepath {filepath} is not in QueuedTracker data, appending and saving")
            self.data[schedule][category].append(filepath)
            self.save()
        else:
            logging.debug(f"filepath {filepath} is already in QueuedTracker data")

    # might just be here from duplicating played tracker - think about if we need to reset queued items? dont think we do
    def reset_if_exhausted(self, schedule: str, category: str):
        """Reset JSON for this schedule/category if all items have been queued."""
        logging.debug("Begin reset_if_exhausted")
        self.ensure_schedule(schedule)
        logging.debug(f"Get all queued from QueuedTracker data")
        all_queued = self.data[schedule].get(category, [])
        if all_queued:
            logging.debug(f"Resetting queued {category} for schedule '{schedule}'")
            self.data[schedule][category] = []
            self.save()
        else:
            logging.debug(f"Queue {category} is empty")
