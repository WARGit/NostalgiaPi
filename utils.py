import subprocess
import time
import os
import sys
import threading
import json
import logging

from models import System
from datetime import datetime, timedelta

DURATIONS_JSON = "durations.json"
DURATIONS_SCRIPT = "durationanalyzer.py"
DURATIONS_ERRORS = "duration_errors.json"

def seconds_until_restart(system) -> int:
    """Return number of seconds until the next scheduled action (restart/shutdown)."""
    now = datetime.now()
    logging.debug(f"time now: {now}")
    target_time = now.replace(hour=system.hour, minute=system.minute, second=0, microsecond=0)
    logging.debug(f"target_time: {target_time}")

    # If today's time has already passed, roll to tomorrow
    if target_time <= now:
        logging.debug(f"target_time: {target_time} < now: {now}")
        target_time += timedelta(days=1)

    logging.debug(f"returning: {int((target_time - now).total_seconds())}")
    return int((target_time - now).total_seconds())

def get_media_files(folder: str) -> list[str]:
    """Return full paths of video files in a folder (with recursion)."""
    files: list[str] = []
    try:
        logging.debug(f"Begin getting files from: {folder}")
        for root, _, filenames in os.walk(folder):
            logging.debug(f"root: {root}, filenames: {filenames}")
            for f in filenames:
                logging.debug(f"f: {f}")
                if f.lower().endswith(('.mkv', '.mp4', '.avi')):
                    logging.debug(f"appending: {os.path.join(root, f)}")
                    files.append(os.path.join(root, f))
    except FileNotFoundError:
        logging.error(f"File not found!: {os.path.join(folder, folder)}")
        return []
    logging.debug(f"returning filecount: {len(files)}")
    return files

def wait_for_restart(system: System):
    """Background loop to wait until the scheduled time, then perform the action (restart/shutdown)."""
    while True:
        secs = seconds_until_restart(system)
        logging.debug(f"{system.action.capitalize()} scheduled in {secs // 60} minutes ({secs} seconds).")
        time.sleep(secs)

        if system.action == "restart":
            # Soft restart of the script
            logging.debug("Time reached. Restarting script now...")
            python = sys.executable
            os.execv(python, [python] + sys.argv)

        elif system.action == "shutdown":
            # Shutdown the Pi
            logging.debug("Time reached. Shutting down system now...")
            subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)

        else:
            logging.error(f"Unknown system action! '{system.action}'. sleep before re-checking")
            time.sleep(60)  # wait a minute before re-checking
            # Infinite loop here if nothing defined in json, maybe just default to restart?

def start_restart_thread(system: System):
    """Start the restart timer thread."""
    logging.debug("setup restart thread")
    t = threading.Thread(target=wait_for_restart, args=(system,), daemon=True)
    logging.debug("start restart thread")
    t.start()
    logging.debug("restart thread started")
    return t

def ensure_durations_have_been_calculated(schedules):
    """
    Ensure durations.json is up to date with all media in schedules.
    If any media files are missing from durations.json, re-run durationanalyzer.py
    NOTE: we only check the media against "by_path" in json, if we have the path we should have the duration too, this should be enough
    """

    # Gather all media files from schedules
    all_files = []
    logging.debug("Begin looping through schedules")
    for sched in schedules.values():
        logging.debug(f"schedule: {sched}")
        for group in (sched.shows + sched.ads + sched.bumpers):
            logging.debug(f"group: {group}")
            all_files.extend(get_media_files(group))  # end up with a list of file names here
            logging.debug(f"all_files count: {len(all_files)}")

    logging.debug("deduplicate all_files list")
    all_files = set(all_files)  # deduplicate
    logging.debug(f"all_files count: {len(all_files)}")

    # Load durations.json (if it exists)
    durations = {}
    missing = []    # make empty list to store missing items
    if os.path.exists(DURATIONS_JSON):
        logging.debug(f"loading durations from: {DURATIONS_JSON} and checking for missing files")
        with open(DURATIONS_JSON, "r", encoding="utf-8") as f:
            durations = json.load(f).get("by_path", {})
            # Check if any files are missing
            missing = [f for f in all_files if f not in durations]
    else:
       missing.extend("missing") # add an item since json was missing to trigger re-calc

    logging.debug(f"missing files length: {len(missing)}")

    # if there are any missing items then re-calc all, first remove durations and duration_errors. json files
    if len(missing) > 0:
        logging.debug(f"Some files are missing durations, we will recalculate them")

        logging.debug(f"removing {DURATIONS_JSON} if exists")
        if os.path.exists(DURATIONS_JSON):
           os.remove(DURATIONS_JSON)

        logging.debug(f"removing {DURATIONS_ERRORS} if exists")
        if os.path.exists(DURATIONS_ERRORS):
           os.remove(DURATIONS_ERRORS)

        logging.debug(f"calling {DURATIONS_SCRIPT}")
        subprocess.run(["python", DURATIONS_SCRIPT], check=True)
    else:
        logging.debug("Durations.json is up to date, nothing to do")

def setup_logging(system):

    # if we are not to log then return
    if not system.create_debug_file:
        return

    # always delete debug log before we start
    if os.path.exists("debug.log"):
        os.remove("debug.log")

    log_level = logging.DEBUG
    handlers = [logging.StreamHandler()]  # allows us to always log to console
    handlers.append(logging.FileHandler("debug.log", mode="a"))

    logging.basicConfig(
        level = logging.DEBUG,
        format = "%(asctime)s [%(levelname)s] %(funcName)s: %(message)s",
        handlers = handlers
    )
