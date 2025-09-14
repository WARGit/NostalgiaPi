from models import Schedule, Config, System
from tracker import PlayedTracker
from planner import QueuePlanner
from player import PlaylistManager
from utils import *
import os
from datetime import datetime, timedelta

DURATIONS_JSON = "durations.json"
DURATIONS_SCRIPT = "durationanalyzer.py"

def main():

    # Pick the config file by OS
    CONFIG_FILE_NAME = "config_pi.json" if os.name != "nt" else "config_nt.json"

    # Load config
    if not os.path.exists(CONFIG_FILE_NAME):
        print(f"{CONFIG_FILE_NAME} does not exist!")
        return
    with open(CONFIG_FILE_NAME, "r") as f:
        raw  = json.load(f)

    # Build objects
    schedules = {name: Schedule.from_dict(data) for name, data in raw["schedules"].items()}
    system = System.from_dict(raw["system"])
    config = Config(schedules=schedules, system=system)
    # spin off background thread that restarts script at specified time
    start_restart_thread(system)

    # Loop through all schedules, get all paths and get all files from these paths to make "all_files"
    all_files = []
    for sched in schedules.values():
        for group in (sched.shows + sched.ads + sched.bumpers):
            files = get_media_files(group)  # expand the folder into its files
            all_files.extend(files)

    all_files = set(all_files)  # deduplicate files in the list by creating a new set object (schedules may have shared the same paths)

    # We can then compare all_files to the contents of the duration.json file

    # Load durations.json (if it exists) and get all items by path
    durationsjson = {}
    if os.path.exists(DURATIONS_JSON):
        with open(DURATIONS_JSON, "r", encoding="utf-8") as f:
            durationsjson = json.load(f).get("by_path", {})

    # Check if any files are missing from durations.json
    missing = [f for f in all_files if f not in durationsjson]

    # Evaluate and call duration analyzer script if json is missing any files on disk
    if missing:
        print(f"[INFO] {len(missing)} media files missing from {DURATIONS_JSON}, regenerating...")
        subprocess.run(["python", DURATIONS_SCRIPT], check=True)
    else:
        print("[INFO] durations.json is up to date")

    del all_files   # free up ram

    # Now onto the main work...
    # 1 show and 2 ads now play, timer to hook up, durations to be calculated and pool of shows / ads to be emptied as its used
    #  and reset accordingly, also update played.json to track items per schedule, so that a rest doesnt rest the items for all schedules

    # construct planner and played tracked, planner to plan what to play, tracker to track played items
    tracker = PlayedTracker()
    planner = QueuePlanner(config, tracker, durationsjson, system)

    # Plan from now until restart
    now = datetime.now()
    # WR - THIS PLAYLIST CURRENTLY CONSISTS ONLY OF SHOWS AND SEEMED TO REPEAT ONE PRETTY QUICKLY, SO EACH ITERATION
    # SHOULD BE REMOVING THE FILES THAT ARE QUEUED FROM THE SHOWS LIST AND WHEN ITS EMPTY IT NEEDS TO RESET
    plan = planner.build_playlist_until_restart(now)
    if not plan:
        print("[INFO] Nothing fits before restart. Exiting.")
        return

    # Create VLC manager, add planned items with categories
    manager = PlaylistManager(tracker)
    for file_path, category in plan:
        manager.add_to_playlist(file_path, category)

    # Start playback & go fullscreen
    manager.start_playback()
    time.sleep(1)
    manager.set_fullscreen(True)

    # Keep alive so VLC events fire
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        manager.stop_playback()
        manager.set_fullscreen(False)


if __name__ == "__main__":
    main()
