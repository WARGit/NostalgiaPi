# import Modules
import cv2 # install package opencv-python
import os  # For file and folder management
import json
import random  # For random number generation
import time
import threading
import math

from numpy.matlib import empty
ERROR_FILE = "duration_errors.json"

if os.name != "nt":
    import vlc  # import vlc module if not on win/nt
from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime

# Class to handle calculating durations of files and writing to a json on disk.
# As per chat=gpt, 1000 shows would take ~400KB in RAM, so very efficient
class DurationCache:
    def __init__(self, cache_file="durations.json"):
        self.cache_file = cache_file
        self.by_path = {}
        self.by_duration = {}
        self.load()

    def load(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "r") as f:
                data = json.load(f)
                self.by_path = data.get("by_path", {})
                self.by_duration = data.get("by_duration", {})
        else:
            # Create an empty cache file on first run
            self.by_path = {}
            self.by_duration = {}
            self.save()

    def save(self):
        data = {
            "by_path": self.by_path,
            "by_duration": self.by_duration
        }
        with open(self.cache_file, "w") as f:
            json.dump(data, f, indent=2)

    def add(self, path, duration):
        """Add or update a file duration."""
        path = os.path.abspath(path)
        duration_str = str(round(duration, 2))

        # If the file already exists, remove old duration entry
        if path in self.by_path:
            old_duration_str = str(round(self.by_path[path], 2))
            if old_duration_str in self.by_duration:
                if path in self.by_duration[old_duration_str]:
                    self.by_duration[old_duration_str].remove(path)
                    if not self.by_duration[old_duration_str]:
                        del self.by_duration[old_duration_str]

        # Add to by_path
        self.by_path[path] = duration

        # Add to by_duration
        if duration_str not in self.by_duration:
            self.by_duration[duration_str] = []
        if path not in self.by_duration[duration_str]:
            self.by_duration[duration_str].append(path)

        # Save immediately so file always exists & stays up to date
        self.save()

    def get_duration(self, path):
        """Return duration (seconds) or None."""
        return self.by_path.get(os.path.abspath(path))

    def get_files_with_duration(self, duration):
        """Return all files with an exact duration (as list of paths)."""
        return self.by_duration.get(str(round(duration, 2)), [])

    def get_under(self, seconds):
        """Return all files with duration <= seconds."""
        return [path for path, dur in self.by_path.items() if dur <= seconds]

    def get_between(self, min_sec, max_sec):
        """Return all files with min_sec <= duration <= max_sec."""
        return [path for path, dur in self.by_path.items() if min_sec <= dur <= max_sec]

# Class representing a schedule from the config file
@dataclass
class Schedule:
    priority: int
    daysofweek: List[int]   # 1–6 for Mon–Sun, 0 = Any
    dates: List[int]        # 1–31, 0 = Any
    months: List[int]       # 1–12, 0 = Any
    starthour: int          # 0–23
    endhour: int            # 0–23
    shows: List[str]
    ads: List[str]

    @classmethod
    def from_dict(cls, data: Dict) -> "Schedule":
        """Factory to build a Schedule from JSON dict with proper type conversion."""
        return cls(
            priority    =int(data["priority"]),
            daysofweek  =[int(x) for x in data["daysofweek"]],
            dates       =[int(x) for x in data["dates"]],
            months      =[int(x) for x in data["months"]],
            starthour   =int(data["starthour"]),
            endhour     =int(data["endhour"]),
            shows       =list(data["shows"]),
            ads         =list(data["ads"])
        )

    def is_active(self, hour: int, weekday: int, day: int, month: int) -> bool:
        # --- Check hour range (supports wrap past midnight) ---
        if self.starthour <= self.endhour:
            in_hour = self.starthour <= hour < self.endhour
        else:
            in_hour = hour >= self.starthour or hour < self.endhour

        # --- Check weekday ---
        in_dayofweek = (0 in self.daysofweek) or (weekday in self.daysofweek)

        # --- Check month ---
        in_month = (0 in self.months) or (month in self.months)

        # --- Check date ---
        in_date = (0 in self.dates) or (day in self.dates)

        return in_hour and in_dayofweek and in_month and in_date

    def is_active_now(self) -> bool:
        """Check if this schedule is active right now (system time)."""
        now = datetime.now()
        return self.is_active(
            hour=now.hour,
            weekday=(now.weekday() + 1),  # shift datetime 0–6 to human readable 1–7
            day=now.day,
            month=now.month
        )

# Class representing the config file
@dataclass
class Config:
    # attribute that holds a KVP of schedule objects with the schedule name being the str and schedule being a schedule object
    schedules: Dict[str, Schedule]

    def get_active_schedule(self) -> Schedule | None:
        """Return the highest-priority active schedule, or None if none match."""
        active = [s for s in self.schedules.values() if s.is_active_now()]
        if not active:
            return None
        # priority 1 is highest, so sort ascending
        return sorted(active, key=lambda s: s.priority)[0]

    def get_active_media(self) -> tuple[list[str], list[str]]:
        # Return (shows, ads) for the highest-priority active schedule(s).
        # If multiple schedules share the top priority, merge their shows and ads
        # without duplicates.

        active = [s for s in self.schedules.values() if s.is_active_now()]
        if not active:
            return [], []

        # Find the minimum (highest) priority among active
        top_priority = min(s.priority for s in active)

        # Collect unique shows/ads from all active schedules with that priority
        shows: set[str] = set()
        ads: set[str] = set()
        for s in active:
            if s.priority == top_priority:
                shows.update(s.shows)
                ads.update(s.ads)

        # Return as lists (deterministic ordering optional, e.g. sorted)
        return list(shows), list(ads)

# Function to get all media files from the current folder
def get_media_files(folder):
    video_exts = ('.mkv', '.mp4', '.avi')
    media_files = []
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(video_exts):
                media_files.append(os.path.join(root, f))
    return media_files
# END DEF

# Function to shuffle files and keep track of played ones
def shuffle_files(media_files):
    random.shuffle(media_files)  # Shuffle the media files list
    return media_files
# END DEF

def log_duration_error(file_path, reason="unknown error"):
    errors = {}
    if os.path.exists(ERROR_FILE):
        with open(ERROR_FILE, "r") as f:
            try:
                errors = json.load(f)
            except json.JSONDecodeError:
                errors = {}

    errors[file_path] = reason

    with open(ERROR_FILE, "w") as f:
        json.dump(errors, f, indent=2)

def clear_duration_error(file_path):
    """Remove file from error log if it exists."""
    if not os.path.exists(ERROR_FILE):
        return
    with open(ERROR_FILE, "r") as f:
        try:
            errors = json.load(f)
        except json.JSONDecodeError:
            errors = {}
    if file_path in errors:
        del errors[file_path]
        with open(ERROR_FILE, "w") as f:
            json.dump(errors, f, indent=2)

def get_duration_rounded(file_path):
    try:
        print(f"begin duration calculation for {file_path}")
        cap = cv2.VideoCapture(file_path)

        if not cap.isOpened():
            print(f"file could not be opened!")
            log_duration_error(file_path, "could not open file")
            return 0

        print(f"file opened, get fps")
        fps = cap.get(cv2.CAP_PROP_FPS)

        print(f"get frame_count")
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)

        print(f"get duration")
        duration = frame_count / fps if fps else 0

        print(f"release file handle")
        cap.release()

        rounded = math.ceil(duration)
        print(f"returning duration '{rounded}'")
        return rounded

    except Exception as e:
        log_duration_error(file_path, str(e))
        return 0

# ==========================================================
# ===================== MAIN ===============================
# ==========================================================
def main():

    # === Set the config file name accoring to OS ====
    if os.name != "nt":
        CONFIG_FILE_NAME = "config_pi.json"
    else:
        CONFIG_FILE_NAME = "config_nt.json"

    # === Load config.json if exist ===
    if os.path.exists(CONFIG_FILE_NAME):
        print(f"{CONFIG_FILE_NAME} exists, proceed")
        with open(CONFIG_FILE_NAME, "r") as f:
            cfgjson = json.load(f)
    else:
        print(f"{CONFIG_FILE_NAME} does not exist!")
        exit(1)

    # === Read schedules from rawjson so we know the media paths ===
    schedules = {name: Schedule.from_dict(details) for name, details in cfgjson["schedules"].items()}
    del cfgjson  # Free up RAM
    config = Config(schedules=schedules)
    del schedules # Free up RAM

    # Setup empty array to hold all media
    all_media = []

    # loop through schedules and add all shows and ads to array above
    for s in config.schedules.values():
        all_media.extend(s.shows)
        all_media.extend(s.ads)

    # now remove any duplicate paths from the array
    all_media = list(set(all_media))

    # object to write to duration cache json
    cache = DurationCache()

    # now loop through all paths and begin calculating duration
    for dir in all_media:
        # get files in path
        filesinpath = get_media_files(dir)
        for f in filesinpath:
            duration = ""  # empty variable
            # get duration of file
            duration = get_duration_rounded(os.path.join(dir, f))  # dir/file
            print(f"file: {os.path.join(dir, f)} is {duration}")
            cache.add(os.path.join(dir, f), duration)
            cache.save()

    print("file durations calculated successfully")
# END DEF

if __name__ == "__main__":
    main()
