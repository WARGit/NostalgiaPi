import subprocess
import time
import os
import sys
import threading
import json

from models import System
from datetime import datetime, timedelta

DURATIONS_JSON = "durations.json"
DURATIONS_SCRIPT = "durationanalyzer.py"

def seconds_until_restart(system) -> int:
    """Return number of seconds until the next scheduled action (restart/shutdown)."""
    now = datetime.now()
    target_time = now.replace(hour=system.hour, minute=system.minute, second=0, microsecond=0)

    # If today's time has already passed, roll to tomorrow
    if target_time <= now:
        target_time += timedelta(days=1)

    return int((target_time - now).total_seconds())

def restart_program():
    """Restart the current Python script in-place."""
    print("[SYSTEM] Restarting program...")
    python = sys.executable
    os.execl(python, python, *sys.argv)  # replaces the current process

def get_media_files(folder: str) -> list[str]:
    """Return full paths of video files in a folder (no recursion)."""
    try:
        return [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith(('.mkv', '.mp4', '.avi'))
        ]
    except FileNotFoundError:
        return []

def wait_for_restart(system: System):
    """Background loop to wait until the scheduled time, then perform the action (restart/shutdown)."""
    while True:
        secs = seconds_until_restart(system)
        print(f"[SYSTEM] {system.action.capitalize()} scheduled in {secs // 60} minutes ({secs} seconds).")
        time.sleep(secs)

        if system.action == "restart":
            # Soft restart of the script
            print("[SYSTEM] Time reached. Restarting script now...")
            python = sys.executable
            os.execv(python, [python] + sys.argv)

        elif system.action == "shutdown":
            # Shutdown the Raspberry Pi
            print("[SYSTEM] Time reached. Shutting down system now...")
            subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)

        else:
            print(f"[ERROR] Unknown system action '{system.action}'. Doing nothing.")
            time.sleep(60)  # wait a minute before re-checking

def start_restart_thread(system: System):
    """Start the restart timer thread."""
    print("[RESTART] STARTING RESTART THREAD...")
    t = threading.Thread(target=wait_for_restart, args=(system,), daemon=True)

    t.start()
    print("[RESTART] RESTART THREAD STARTED.")
    return t

def ensure_durations(config):
    """
    Ensure durations.json is up to date with all media in schedules.
    If any media files are missing from durations.json, re-run durationanalyzer.py.
    """
    # Gather all media files from schedules
    all_files = []
    for sched in config.schedules:
        for group in (sched.shows + sched.ads + sched.bumpers):
            all_files.extend(get_media_files(group))

    all_files = set(all_files)  # deduplicate

    # Load durations.json (if it exists)
    durations = {}
    if os.path.exists(DURATIONS_JSON):
        with open(DURATIONS_JSON, "r", encoding="utf-8") as f:
            durations = json.load(f).get("by_path", {})

    # Check if any files are missing
    missing = [f for f in all_files if f not in durations]

    if missing:
        print(f"[INFO] {len(missing)} media files missing from {DURATIONS_JSON}, regenerating...")
        subprocess.run(["python", DURATIONS_SCRIPT], check=True)
    else:
        print("[INFO] durations.json is up to date")
