import os
import json
import time
from datetime import datetime

from models import Schedule, Config, System
from tracker import PlayedTracker
from planner import QueuePlanner
from player import PlaylistManager

# =========================
# ========= MAIN ==========
# =========================

def main():
    # Pick the config file by OS
    CONFIG_FILE_NAME = "config_pi.json" if os.name != "nt" else "config_nt.json"

    # Load config
    if not os.path.exists(CONFIG_FILE_NAME):
        print(f"{CONFIG_FILE_NAME} does not exist!")
        return
    with open(CONFIG_FILE_NAME, "r") as f:
        cfgjson = json.load(f)

    # Load durations
    if not os.path.exists("durations.json"):
        print("durations.json does not exist! Please run durationanalyzer.py first.")
        return
    with open("durations.json", "r") as f:
        durjson = json.load(f)

    # Build objects
    schedules = {name: Schedule.from_dict(d) for name, d in cfgjson["schedules"].items()}
    config = Config(schedules=schedules)
    system = System.from_dict(cfgjson["system"])
    tracker = PlayedTracker()
    planner = QueuePlanner(config, tracker, durjson, system)

    # Plan from now until restart
    now = datetime.now()
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
