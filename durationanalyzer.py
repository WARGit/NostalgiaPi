# import Modules
import cv2      # install package opencv-python
import os       # For file and folder management
import json
import random   # For random number generation
import math
from models import *

ERROR_FILE = "duration_errors.json"

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
            raw = json.load(f)
    else:
        print(f"{CONFIG_FILE_NAME} does not exist!")
        exit(1)

    # === Read schedules from rawjson so we know the media paths ===
    schedules = {name: Schedule.from_dict(data) for name, data in raw["schedules"].items()}
    system = System.from_dict(raw["system"])
    config = Config(schedules=schedules, system=system)

    # Setup empty array to hold all media
    all_media = []

    # loop through schedules and add all shows and ads to array above
    for s in config.schedules.values():
        all_media.extend(s.shows)
        all_media.extend(s.ads)
        all_media.extend(s.bumpers)

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
