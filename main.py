# import Modules
import cv2  # install package opencv-python
import os  # For file and folder management
import random  # For random number generation
import time
import json
import threading
import queue
import vlc  # import vlc module (on windows this is installed with pip3 install python-vlc)

from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime, timedelta

PLAYED_FILE = "played.json"

# Class representing a schedule from the config file
@dataclass
class Schedule:
    priority: int
    daysofweek: List[int]  # 1–6 for Mon–Sun, 0 = Any
    dates: List[int]  # 1–31, 0 = Any
    months: List[int]  # 1–12, 0 = Any
    starthour: int  # 0–23
    startminute: int  # 0-59
    endhour: int  # 0–23
    endminute: int  # 0-59
    shows: List[str]
    ads: List[str]
    bumpers: List[str]  # bumpers are usually only 10 seconds, typical "coming up next type video, used to fill out schedule to get as accurate alignment as possible"

    @classmethod
    def from_dict(cls, data: Dict) -> "Schedule":
        """Factory to build a Schedule from JSON dict with proper type conversion."""
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
            bumpers = list(data["bumpers"])
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

# Class representing the system part of the config file
@dataclass
class System:
    restarthour: int
    restartminute: int

    @classmethod
    def from_dict(cls, data: Dict) -> "System":
        """Factory to build a System from JSON dict with proper type conversion."""
        return cls(
            restarthour=int(data["restarthour"]),
            restartminute=int(data["restartminute"])
        )

# Class representing the config file
@dataclass
class Config:
    # attribute that holds a KVP of schedule objects with the schedule name being the str and schedule being a schedule object
    schedules: Dict[str, Schedule]

    def get_active_schedule_at(self, when: datetime) -> Schedule | None:
        """Return the highest-priority active schedule at a given datetime."""
        active = [s for s in self.schedules.values() if s.is_active(
            hour=when.hour,
            weekday=(when.weekday() + 1),  # shift to 1–7
            day=when.day,
            month=when.month
        )]
        if not active:
            return None
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

# OLD PLAYBACK TIMER THREAD, LOOKS USEFUL AS IT ACTUALLY STARTS A THREAD
class PlaybackTimer:
    def __init__(self, tracker, durations):
        self.tracker = tracker
        self.durations = durations
        self.queue = queue.Queue()  # FIFO
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.running = True
        self.thread.start()

    def add_media(self, file_path, category):
        """Add a media file to the timer queue (starts tracking it)."""
        duration = self.durations["by_path"].get(file_path, 0)
        if duration <= 0:
            print(f"[Timer] Warning: no duration for {file_path}, marking instantly.")
            self.tracker.mark_played(file_path, category)
            return
        self.queue.put((file_path, category, duration))

    def _worker(self):
        """Background worker that processes the queue sequentially."""
        while self.running:
            try:
                file_path, category, duration = self.queue.get(timeout=1)
            except queue.Empty:
                continue

            print(f"[Timer] Waiting {duration}s for {file_path}...")
            time.sleep(duration)  # block for the duration
            print(f"[Timer] Duration finished, marking {file_path} as played.")
            self.tracker.mark_played(file_path, category)
            self.queue.task_done()

    def stop(self):
        """Stop the timer thread cleanly."""
        self.running = False
        self.thread.join()

# NEW PLAYED TRACKER THREAD, DOESNT START A THREAD, DOES IT NEED TO? NOT SURE BUT THIS + ABOVE PROBABLY MERGE
class PlayedTracker:
    def __init__(self):
        if os.path.exists(PLAYED_FILE):
            with open(PLAYED_FILE, "r") as f:
                self.data = json.load(f)
        else:
            self.data = {"shows": [], "ads": []}
            self._save()

    def _save(self):
        with open(PLAYED_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def mark_played(self, file_path, media_type):
        """Mark a file as played (after successful playback)."""
        if file_path not in self.data[media_type]:
            self.data[media_type].append(file_path)
            self._save()

    def has_been_played(self, file_path, media_type):
        return file_path in self.data[media_type]

    def reset(self, media_type=None):
        """Reset played list (all or just one type)."""
        if media_type:
            self.data[media_type] = []
        else:
            self.data = {"shows": [], "ads": []}
        self._save()

    def get_unplayed(self, all_files, media_type):
        """Return unplayed files. Reset automatically if all were played."""
        played = set(self.data[media_type])
        all_files_set = set(all_files)

        # If all files have been played → reset and return everything again
        if all_files_set.issubset(played):
            self.reset(media_type)
            return all_files  # start fresh

        # Otherwise, return only unplayed
        return [f for f in all_files if f not in played]

# NOT USED, RANDOMLY PICKS NEXT SHOW / AD
class MediaScheduler:

    # Constructor that takes in a list of shows and ads
    def __init__(self, shows: list[str], ads: list[str]):
        self.original_shows = list(shows)
        self.original_ads = list(ads)
        self.shows_pool = list(shows)
        self.ads_pool = list(ads)
        random.shuffle(self.shows_pool)
        random.shuffle(self.ads_pool)

    def get_next_show(self) -> str:
        if not self.shows_pool:
            self.shows_pool = list(self.original_shows)
            random.shuffle(self.shows_pool)
        return self.shows_pool.pop()

    def get_next_ads(self, count: int = 2) -> list[str]:
        ads_to_play = []
        for _ in range(count):
            if not self.ads_pool:
                self.ads_pool = list(self.original_ads)
                random.shuffle(self.ads_pool)
            ads_to_play.append(self.ads_pool.pop())
        return ads_to_play

# HOOKS INTO VLC EVENT AND UPDATES PLAYED.JSON ONCE MEDIA ENDS, ALSO STARTS/STOPS/FULLSCREENS VLC
class PlaylistManager:
    def __init__(self, tracker: PlayedTracker, timer: PlaybackTimer):
        self.tracker = tracker
        self.instance = vlc.Instance()
        self.playback_timer = timer
        self.list_player = self.instance.media_list_player_new()
        self.media_list = self.instance.media_list_new()
        self.list_player.set_media_list(self.media_list)

        # Attach VLC end event
        event_manager = self.list_player.get_media_player().event_manager()
        event_manager.event_attach(
            vlc.EventType.MediaPlayerEndReached, self._on_media_end
        )

    def _on_media_end(self, event):
        media = event.u.media
        if not media:
            return
        mrl = media.get_mrl()
        path = mrl[7:] if mrl.startswith("file://") else mrl
        print(f"[EVENT] Finished playing: {path}")

        # Mark file as played in played.json
        self.tracker.mark_played(path)

    def start_playback(self):
        print("[INFO] Starting playback…")
        self.list_player.play()

    def stop_playback(self):
        print("[INFO] Stopping playback…")
        self.list_player.stop()

    def set_fullscreen(self, enable: bool):
        mp = self.list_player.get_media_player()
        mp.set_fullscreen(enable)

    def add_to_playlist(self, file_path: str):
        media = self.instance.media_new_path(file_path)
        self.media_list.add_media(media)
        print(f"[INFO] Added: {file_path} | Playlist count: {self.media_list.count()}")

    def add_to_playlist(self, file_path, category):
        """Add a new media file to the playlist and timer dynamically."""
        media = self.instance.media_new(file_path)
        self.media_list.add_media(media)            # Add media to VLC
        self.playback_timer.add_media(file_path, category)   # Add to timer queue immediately

        print(f"Added to playlist: {file_path} ({category})")
        print(f"Current playlist count: {self.media_list.count()}")

class QueuePlanner:
    def __init__(self, config: Config, tracker: PlayedTracker, durations: dict, system: System):
        self.config = config
        self.tracker = tracker
        self.durations = durations
        self.system = system

    def build_playlist_until_restart(self, start_time: datetime) -> list[tuple[str, str]]:
        """
        Build a list of (file_path, category) from `start_time` until restart.
        Categories: "shows", "ads", "bumpers".
        """
        playlist = []
        current_time = start_time  # we pass in the start time initially as datetime.now but at the bottom of this method we take the duration from the time so it moves along the timeline
        secs_left = seconds_until_restart(self.system)

        while secs_left > 0:
            # 1. Which schedule will be active at the current_time?
            active_schedule = self.config.get_active_schedule_at(current_time)
            if not active_schedule:
                ## LOG ERROR HERE
                break

            show_paths = active_schedule.shows
            ad_paths = active_schedule.ads
            bumper_paths = active_schedule.bumpers

            # 2. Collect candidates
            shows, ads, bumpers = [], [], []
            for p in show_paths:
                shows.extend(get_media_files(p))
            for p in ad_paths:
                ads.extend(get_media_files(p))
            for p in bumper_paths:
                bumpers.extend(get_media_files(p))

            # 3. Filter unplayed
            shows = self.tracker.get_unplayed(shows, "shows")
            ads = self.tracker.get_unplayed(ads, "ads")
            # bumpers usually repeat often → no tracking
            # (optional: track them if you like)

            # 4. Try to pick something that fits
            candidate, category, dur = None, None, 0

            # Prefer a show if it fits
            if shows:
                choice = random.choice(shows)
                dur = self.durations["by_path"].get(choice, 0)
                if 0 < dur <= secs_left:
                    candidate, category = choice, "shows"

            # Otherwise try an ad
            if candidate is None and ads:
                choice = random.choice(ads)
                dur = self.durations["by_path"].get(choice, 0)
                if 0 < dur <= secs_left:
                    candidate, category = choice, "ads"

            # Otherwise try bumpers (small files to fill gaps)
            if candidate is None and bumpers:
                choice = random.choice(bumpers)
                dur = self.durations["by_path"].get(choice, 0)
                if 0 < dur <= secs_left:
                    candidate, category = choice, "bumpers"

            # 5. If nothing fits → stop
            if candidate is None:
                break

            # 6. Accept candidate
            playlist.append((candidate, category))
            secs_left -= dur
            current_time += timedelta(seconds=dur)

        return playlist


# NOT USED
def get_active_media_at(self, when: datetime) -> tuple[list[str], list[str]]:
    """
    Return (shows, ads) for the highest-priority active schedule(s)
    at the given datetime.
    If multiple schedules share the top priority, merge their shows/ads.
    """
    active = [s for s in self.schedules.values() if s.is_active(
        hour=when.hour,
        weekday=when.weekday(),  # 0=Mon .. 6=Sun
        day=when.day,
        month=when.month
    )]

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

    return list(shows), list(ads)

# Function to get all media files from the current folder
def get_media_files(folder):
    return [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(('.mkv', '.mp4', '.avi'))
    ]
# END DEF

# NOT USED
def seconds_until(hour: int, minute: int = 0):
    now = datetime.now()
    end_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if end_time < now:
        # target has passed today → add 1 day
        end_time += timedelta(days=1)

    return int((end_time - now).total_seconds())

def seconds_until_restart(system: System) -> int:
    now = datetime.now()

    # Build today's restart datetime
    restart_today = now.replace(hour=system.restarthour,
                                minute=system.restartminute,
                                second=0, microsecond=0)

    if now >= restart_today:
        # Restart time has passed for today → schedule for tomorrow
        restart_today += timedelta(days=1)

    delta = restart_today - now
    return int(delta.total_seconds())


# ==========================================================
# ===================== MAIN ===============================
# ==========================================================
def main():

    # === Set the config file name according to OS ====
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

    # === Load durations.json if exist ===
    if os.path.exists("durations.json"):
        print("durations.json exists, proceed")
        with open("durations.json", "r") as f:
            durjson = json.load(f)
    else:
        print("durations.json does not exist!")
        print("please run durationanalyzer.py first!")
        exit(1)

    # === Read schedules from rawjson ===
    schedules = {name: Schedule.from_dict(details) for name, details in cfgjson["schedules"].items()}
    config = Config(schedules=schedules)
    del schedules  # Free up RAM










    # read the system part of config json
    system2 = System.from_dict(cfgjson["system"])
    # Create the tracker thread that waits for an event to be raised from VLC to say the current item has been played which then is marked as such in played.json
    tracker = PlayedTracker()
    timer = PlaybackTimer(tracker, durjson)
    # build a planner object
    planner2 = QueuePlanner(config, tracker, durjson, system2)
    ## call the playlist builder to build the playlist from now until the restart is scheduled
    # This also adds the queued items to the timers queue so they are marked as played as VLC raises the event
    playlist = planner2.build_playlist_until_restart(datetime.now())
    manager = PlaylistManager(tracker, timer)
    manager.start_playback()

    time.sleep(300)



    # now we have our schedules lets find out which media is to be used/is active considering as well which media has already been played:
    # Get list of all media based on the schedule that is currently active
    show_paths, ad_paths = config.get_active_media()  # returns tuple (i.e 2 lists)

    # From these folders then we need to know which shows and ads we are allowed to play:
    # so get all media from the active folders first
    all_shows = []  # create empty array
    for show_path in show_paths:  # loop through current active show paths
        all_shows.extend(get_media_files(show_path))  # extend the array with results of the get

    all_ads = []  # create empty array
    for ad_path in ad_paths:  # loop through current active ads paths
        all_ads.extend(get_media_files(ad_path))  # extend the array with results of the get

    # now we have all shows+ads that we could *possibly* play, we need to know which we *can* play
    tracker = PlayedTracker()  # so make a playedTracker object
    unplayed_shows = tracker.get_unplayed(all_shows, "shows")
    unplayed_ads = tracker.get_unplayed(all_ads, "ads")

    # now we know which ones are unplayed we can select a random one to start playing
    files = [
        random.choice(unplayed_shows)
    ]

    # Add files array to manager object
    manager = PlaylistManager(files)

    # Get duration of file from array (only 1 in the array to start)
    # duration = durjson["by_path"].get(files[0])

    # === Read restart time from rawjson first so we can start playing the first file and do the rest of the calculations as it plays ===
    system = System.from_dict(cfgjson["system"])
    del cfgjson  # Free up RAM

    # == work out how long we have left before a restart should occur and immediately begin playing ====
    secs_left = seconds_until_restart(system)
    manager.start_playback()

    # sleep and then make it fullscreen
    time.sleep(1)  # wait a little for player to initialize
    manager.set_fullscreen(True)

    # setup timer thread to wait for the duration of the current show and then mark it as played
    timer = PlaybackTimer(tracker, durjson)
    timer.add_media(files[0], "shows")  # only 1 item in files at this point so fine.

    # Now Keep script alive so playback continues and begin adding more files
    try:
        while True:
            time.sleep(1)
            # here then we can begin adding more files and deducting from the time we have left in the current schedule up until the daily reboot

            # === 1. Check remaining time before restart ===
            secs_left = seconds_until_restart(system)
            if secs_left <= 0:
                print("Restart time reached, stopping playback.")
                manager.stop_playback()
                break


    except KeyboardInterrupt:
        manager.stop_playback()
        manager.set_fullscreen(False)

# END DEF

if __name__ == "__main__":
    main()
