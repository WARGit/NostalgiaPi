import logging

from models import Schedule, Config, System
from tracker import PlayedTracker, QueuedTracker
from planner import QueuePlanner
from player import PlaylistManager
from utils import *
import os
import json
from datetime import datetime
from utils import setup_logging

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

    # Build objects and setup logging
    schedules = {name: Schedule.from_dict(data) for name, data in raw["schedules"].items()}
    system = System.from_dict(raw["system"])
    config = Config(schedules=schedules, system=system)
    setup_logging(config.system)  # enable logging as per flag in system part of config
    logging.debug("Initialization complete")

    # spin off background thread that restarts script at specified time
    start_restart_thread(system)

    # Call method to ensure durations for all files have been calculated, if not they will be re-calculated
    ensure_durations_have_been_calculated(schedules)

    # Now onto the main work - read durations json but this time not just by_path, json will always exist, we made sure in above method
    with open(DURATIONS_JSON, "r", encoding="utf-8") as f:
        durations_json = json.load(f)

    # construct objects
    tracker         = PlayedTracker() # Track played items
    queued_tracker  = QueuedTracker() # Track queued items
    planner         = QueuePlanner(config, tracker, queued_tracker, durations_json, system) # plans the queue of shows/ads/bumpers

    # build the playlist
    plan = planner.build_playlist_until_restart(datetime.now())
    if not plan:
        print("[INFO] Nothing fits before restart. Exiting.")
        return

    # Create VLC manager, add planned items with categories
    manager = PlaylistManager(config, tracker)
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
