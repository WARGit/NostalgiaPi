# =========================
# ======= imports =========
# =========================
import os
import json
import time
import random
from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime, timedelta

import vlc   # pip install python-vlc

PLAYED_FILE = "played.json"


# =========================
# ===== Data classes ======
# =========================

@dataclass
class Schedule:
    priority: int
    daysofweek: List[int]   # 1–7 for Mon–Sun, 0 = Any   (note: we pass weekday+1)
    dates: List[int]        # 1–31, 0 = Any
    months: List[int]       # 1–12, 0 = Any
    starthour: int          # 0–23
    startminute: int        # 0–59
    endhour: int            # 0–23
    endminute: int          # 0–59
    shows: List[str]
    ads: List[str]
    bumpers: List[str]

    @classmethod
    def from_dict(cls, data: Dict) -> "Schedule":
        return cls(
            priority=int(data["priority"]),
            daysofweek=[int(x) for x in data["daysofweek"]],
            dates=[int(x) for x in data["dates"]],
            months=[int(x) for x in data["months"]],
            starthour=int(data["starthour"]),
            startminute=int(data["startminute"]),
            endhour=int(data["endhour"]),
            endminute=int(data["endminute"]),
            shows=list(data["shows"]),
            ads=list(data["ads"]),
            bumpers=list(data["bumpers"]),
        )

    def is_active(self, hour: int, weekday: int, day: int, month: int) -> bool:
        # hour window (supports wrap past midnight)
        start = self.starthour
        end = self.endhour
        if start == end:
            in_hour = True  # 24h window
        elif start < end:
            in_hour = start <= hour < end
        else:
            in_hour = (hour >= start) or (hour < end)

        in_dow = (0 in self.daysofweek) or (weekday in self.daysofweek)
        in_month = (0 in self.months) or (month in self.months)
        in_date = (0 in self.dates) or (day in self.dates)
        return in_hour and in_dow and in_month and in_date

@dataclass
class System:
    restarthour: int
    restartminute: int

    @classmethod
    def from_dict(cls, data: Dict) -> "System":
        return cls(
            restarthour=int(data["restarthour"]),
            restartminute=int(data["restartminute"]),
        )


@dataclass
class Config:
    schedules: Dict[str, Schedule]

    def get_active_schedule_at(self, when: datetime) -> Schedule | None:
        active = [
            s for s in self.schedules.values()
            if s.is_active(
                hour=when.hour,
                weekday=(when.weekday() + 1),  # datetime: 0=Mon..6=Sun → we use 1..7
                day=when.day,
                month=when.month
            )
        ]
        if not active:
            return None
        # priority 1 is highest
        return sorted(active, key=lambda s: s.priority)[0]


# =========================
# ===== Helpers/IO ========
# =========================

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


def seconds_until_restart(system: System) -> int:
    now = datetime.now()
    restart = now.replace(hour=system.restarthour,
                          minute=system.restartminute,
                          second=0, microsecond=0)
    if now >= restart:
        restart += timedelta(days=1)
    return int((restart - now).total_seconds())


# =========================
# ==== PlayedTracker ======
# =========================

class PlayedTracker:
    def __init__(self):
        if os.path.exists(PLAYED_FILE):
            with open(PLAYED_FILE, "r") as f:
                self.data = json.load(f)
        else:
            self.data = {"shows": [], "ads": [], "bumpers": []}
            self._save()

    def _save(self):
        with open(PLAYED_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def mark_played(self, file_path: str, category: str):
        if category not in self.data:
            self.data[category] = []
        if file_path not in self.data[category]:
            self.data[category].append(file_path)
            self._save()

    def get_unplayed(self, all_files: list[str], category: str) -> list[str]:
        played = set(self.data.get(category, []))
        all_set = set(all_files)
        if all_set and all_set.issubset(played):
            # reset this category when everything was played
            self.data[category] = []
            self._save()
            return all_files
        return [f for f in all_files if f not in played]


# =========================
# ===== QueuePlanner ======
# =========================

class QueuePlanner:
    """
    Builds a play queue from 'now' until the configured restart time,
    honoring active schedule at each point in time and using durations
    from durations["by_path"].
    """
    def __init__(self, config: Config, tracker: PlayedTracker, durations: dict, system: System):
        self.config = config
        self.tracker = tracker
        self.durations = durations
        self.system = system

    def build_playlist_until_restart(self, start_time: datetime) -> list[tuple[str, str]]:
        playlist: list[tuple[str, str]] = []
        current_time = start_time
        secs_left = seconds_until_restart(self.system)

        while secs_left > 0:
            active = self.config.get_active_schedule_at(current_time)
            if not active:
                break

            # Gather candidates
            shows = sum((get_media_files(p) for p in active.shows), [])
            ads = sum((get_media_files(p) for p in active.ads), [])
            bumpers = sum((get_media_files(p) for p in active.bumpers), [])

            # Filter with played.json (shows/ads); bumpers can repeat
            shows = self.tracker.get_unplayed(shows, "shows")
            ads = self.tracker.get_unplayed(ads, "ads")

            candidate, category, dur = None, None, 0

            def pick(files: list[str], cat: str):
                nonlocal candidate, category, dur
                if not files:
                    return
                choice = random.choice(files)
                d = int(self.durations["by_path"].get(choice, 0))
                if 0 < d <= secs_left:
                    candidate, category, dur = choice, cat, d

            # try show → ad → bumper
            pick(shows, "shows")
            if candidate is None:
                pick(ads, "ads")
            if candidate is None:
                pick(bumpers, "bumpers")

            if candidate is None:
                # nothing fits the remaining window
                break

            playlist.append((candidate, category))
            secs_left -= dur
            current_time += timedelta(seconds=dur)

        return playlist


# =========================
# ==== PlaylistManager ====
# =========================

class PlaylistManager:
    """
    Wraps VLC MediaListPlayer, tracks (file->category) so we can mark
    played items via VLC's MediaPlayerEndReached event.
    """
    def __init__(self, tracker: PlayedTracker):
        self.tracker = tracker
        self.instance = vlc.Instance()

        self.media_list = self.instance.media_list_new()
        self.list_player = self.instance.media_list_player_new()
        self.list_player.set_media_list(self.media_list)

        # map MRL -> category
        self.category_by_mrl: dict[str, str] = {}

        # attach end event
        mp = self.list_player.get_media_player()
        em = mp.event_manager()
        em.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_media_end)

    def _on_media_end(self, event):
        # Ask the media player what just finished
        mp = self.list_player.get_media_player()
        media = mp.get_media()
        if not media:
            return
        mrl = media.get_mrl()  # e.g., file:///path/to/video.mp4
        category = self.category_by_mrl.get(mrl)
        # Convert MRL to a plain path if you prefer to store paths:
        path = mrl
        if mrl.startswith("file://"):
            # Linux/Mac: file:///home/pi/file.mp4
            # Windows: file:///C:/Videos/file.mp4
            path = mrl.replace("file://", "", 1)
            if os.name != "nt":
                # libvlc URL-encodes spaces etc; best-effort decode
                import urllib.parse
                path = urllib.parse.unquote(path)

        if category:
            print(f"[EVENT] Finished: {path} ({category}) → marking played")
            self.tracker.mark_played(path, category)
        else:
            print(f"[EVENT] Finished: {path} (category unknown)")

    def add_to_playlist(self, file_path: str, category: str):
        media = self.instance.media_new_path(file_path)
        mrl = media.get_mrl()
        self.media_list.add_media(media)
        self.category_by_mrl[mrl] = category
        print(f"[QUEUE] + {file_path} [{category}]  | total: {self.media_list.count()}")

    def start_playback(self):
        if self.media_list.count() == 0:
            print("[INFO] Playlist empty.")
            return
        self.list_player.play()
        print("[INFO] Playback started.")

    def stop_playback(self):
        self.list_player.stop()
        print("[INFO] Playback stopped.")

    def set_fullscreen(self, enable: bool):
        mp = self.list_player.get_media_player()
        mp.set_fullscreen(enable)


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
