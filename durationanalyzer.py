import cv2      # install package opencv-python
import os       # For file and folder management
import json
import logging
import math
from models import *
from utils import setup_logging

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


# Function to get all media files from the current folder
def get_media_files(folder):
    logging.debug(f"Begin get media files for folder {folder}")
    video_exts = ('.mkv', '.mp4', '.avi')
    media_files = []
    for root, _, files in os.walk(folder):  # os.walk gets a tuple - "root, dirs, files" '_' discards dirs
        logging.debug(f"root {root}")
        for f in files:
            logging.debug(f"file {f}")
            if f.lower().endswith(video_exts):
                logging.debug(f"file {f}, matches {video_exts}, appending")
                media_files.append(os.path.join(root, f))
    logging.debug(f"Returning media files coun t{len(media_files)}")
    return media_files

def log_duration_error(file_path, reason="unknown error"):

    logging.debug("Begin log_duration_error")
    # Create empty JSON if not exist or load exsiting from disk
    if not os.path.exists(ERROR_FILE):
        logging.debug(f"{ERROR_FILE} does not exist, we will create")
        with open(ERROR_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)
    else:
        logging.debug(f"{ERROR_FILE} does exists, we will load")
        with open(ERROR_FILE, "r") as f:
            try:
                errors = json.load(f)
            except json.JSONDecodeError:
                errors = {}

    logging.debug(f"Create errors object with file_path {file_path} and reason: {reason}")
    errors[file_path] = reason  # Create object to write to JSON

    # Write error Json
    logging.debug("writing object to file")
    with open(ERROR_FILE, "w") as f:
        json.dump(errors, f, indent=2)

def get_duration_rounded(file_path):
    try:
        logging.debug(f"begin duration calculation for {file_path}")
        cap = cv2.VideoCapture(file_path)

        if not cap.isOpened():
            logging.debug(f"file could not be opened!")
            log_duration_error(file_path, "could not open file")
            return 0

        logging.debug(f"file opened, get fps")
        fps = cap.get(cv2.CAP_PROP_FPS)

        logging.debug(f"get frame_count")
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)

        logging.debug(f"get duration")
        duration = frame_count / fps if fps else 0

        logging.debug(f"release file handle")
        cap.release()

        rounded = math.ceil(duration)
        logging.debug(f"returning duration '{rounded}'")
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
    setup_logging(config.system)  # enable logging as per flag in system part of config
    logging.debug("Initialization of DurationAnalyzer complete")

    # Setup empty array to hold all media
    all_media = []

    # loop through schedules and add all shows and ads to array above
    for s in config.schedules.values():
        logging.debug("Adding shows, ads, bumpers for analysis")
        all_media.extend(s.shows)
        all_media.extend(s.ads)
        all_media.extend(s.bumpers)

    logging.debug(f"remove dupes from '{len(all_media)}' paths")
    # now remove any duplicate paths from the array
    all_media = list(set(all_media))
    logging.debug(f"Dupes removed, '{len(all_media)}' paths remain")
    cache = DurationCache()     # object to write to duration cache json

    # now loop through all paths and begin calculating duration
    for dir in all_media:
        logging.debug(f"Analyzing '{dir}'")
        # get files in path
        files_in_path = get_media_files(dir)
        logging.debug(f"files_in_path count '{len(files_in_path)}'")
        for f in files_in_path:
            # get duration of file
            duration = get_duration_rounded(os.path.join(dir, f))  # dir/file
            logging.debug(f"file: {os.path.join(dir, f)} is {duration}")
            cache.add(os.path.join(dir, f), duration)
            cache.save()

    logging.debug("file durations calculated successfully")
# END DEF

if __name__ == "__main__":
    main()
