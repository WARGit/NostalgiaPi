import os
import json
import logging
from datetime import datetime
import random

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

    def __init__(self, config):
        self.filepath = QUEUED_JSON_PATH
        self.channel_name = config.system.channel_name

         #config.get("system", {}).get("channel_name", "NostalgiaPi")
        # always delete json before we start and start fresh
        if os.path.exists(QUEUED_JSON_PATH):
            os.remove(QUEUED_JSON_PATH)
        self.data = {"channel_name": self.channel_name, "entries": []}

    def save(self):
        logging.debug(f"Saving data to {self.filepath}")
        try:
            with open(self.filepath, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save queued.json: {e}")

    def mark_queued(self, filepath: str, category: str, scheduled_time: datetime):
        """Add an item to queued.json (shows only) for display via web ui"""
        if category != "shows":
            logging.debug(f"{category} are not tracked as part of queue")
            return

        time_formatted = scheduled_time.strftime("%I:%M %p").lstrip("0")
        day_name = scheduled_time.strftime("%a")

        # Pick a random icon from static/img/icons
        icon_dir = os.path.join("static", "img", "icons")
        icon = None
        if os.path.exists(icon_dir):
            icons = [f"img/icons/{f}" for f in os.listdir(icon_dir) if
                     f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]
            if icons:
                icon = random.choice(icons)

        entry = {
            "filepath": filepath,
            "day": day_name,
            "time": time_formatted,
            "icon": icon
        }

        logging.debug(f"Queueing {filepath} at {entry['time']} on {entry['day']} for channel {self.channel_name}")
        self.data["channel_name"] = self.channel_name
        self.data["entries"].append(entry)

        # Recalculate banner + floating images each time we save
        self._update_visuals()

        self.save()

    def _update_visuals(self):
        """Update banner (month-specific) and random floating images"""
        # Banner (month-tied)
        month_name = datetime.now().strftime("%B").lower()
        banner_dir = os.path.join("static", "img", "banners")

        banner = None
        if os.path.exists(banner_dir):
            for ext in ("png", "jpg", "jpeg", "gif"):
                candidate = f"{month_name}.{ext}"
                if candidate in os.listdir(banner_dir):
                    banner = f"img/banners/{candidate}"
                    break
        if banner is None and os.path.exists(banner_dir):
            banners = [f"img/banners/{f}" for f in os.listdir(banner_dir)]
            if banners:
                banner = random.choice(banners)

        # Floating images
        img_dir = os.path.join("static", "img", "tvguide")
        random_images = []
        if os.path.exists(img_dir):
            img_files = [f"img/tvguide/{f}" for f in os.listdir(img_dir)]
            random_images = random.sample(img_files, min(3, len(img_files)))

        self.data["banner"] = banner
        self.data["random_images"] = random_images

