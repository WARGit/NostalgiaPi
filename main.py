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
from numpy.matlib import empty

PLAYED_FILE = "played.json"


# 3.0 - including adverts
# 10 - Backport config file and Add OS detection - Tested on pi, works.
# 11 - experimented with cv2, added a new class to handle calculating durations - incomplete and TESTED ON PI, CAN WORK IF PACKAGES ARE INSTALLED FIRST
# 12-
# vnext is add the media scheduler which schedules for the next 24 hours

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


# Class to handle calculating durations of files and writing to a json on disk.
# As per chat=gpt, 1000 shows would take ~400KB in RAM, so very efficient
class DurationCache:
    def __init__(self, cache_file="durations.json"):
        self.cache_file = cache_file
        self._durations = {}
        self._lock = threading.Lock()

        # Ensure file exists
        if not os.path.exists(self.cache_file):
            with open(self.cache_file, "w") as f:
                json.dump({}, f)

        self._load()

    def _load(self):
        with open(self.cache_file, "r") as f:
            try:
                self._durations = json.load(f)
            except json.JSONDecodeError:
                self._durations = {}

    def _save(self):
        with self._lock:
            with open(self.cache_file, "w") as f:
                json.dump(self._durations, f, indent=2)

    def get_duration(self, filepath):
        """Return duration in seconds, calculating and caching if needed."""
        filepath = os.path.abspath(filepath)
        if filepath in self._durations:
            return self._durations[filepath]

        duration = self._calculate_duration(filepath)
        if duration is not None:
            self._durations[filepath] = duration
            self._save()
        return duration

    def _calculate_duration(self, filepath):
        """Uses OpenCV to get duration of video in seconds."""
        try:
            cap = cv2.VideoCapture(filepath)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            if fps > 0 and frames > 0:
                return round(frames / fps, 2)
        except Exception:
            pass
        return None

    def preload_folder(self, folder):
        """Start a background thread to scan all media in a folder."""
        thread = threading.Thread(target=self._preload_worker, args=(folder,))
        thread.daemon = True  # doesn’t block program exit
        thread.start()

    def _preload_worker(self, folder):
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith((".mp4", ".avi", ".mkv", ".mov")):
                    filepath = os.path.join(root, f)
                    # trigger calculation if not cached
                    if os.path.abspath(filepath) not in self._durations:
                        self.get_duration(filepath)


# Class representing the media scheduler
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
            ads=list(data["ads"])
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


# Lock to synchronize media changes between threads
media_lock = threading.Lock()


# Function to get all media files from the current folder
def get_media_files(folder):
    return [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(('.mkv', '.mp4', '.avi'))
    ]


# END DEF

# Function to shuffle files and keep track of played ones
def shuffle_files(media_files):
    random.shuffle(media_files)  # Shuffle the media files list
    return media_files


# END DEF

# function to play media for the channel
def play_media():
    # Setup folders
    tv_folder = "/home/war/Videos/8am"
    ad_folder = "/home/war/Videos/ads"

    # Declare global list of played files
    global played_tv
    global played_ads
    global ad_due

    ## new
    # Create a media list
    media_list = media_player.media_list_new()

    # Create a media list player
    list_player = media_player.media_list_player_new()

    # Link the list player to the media list
    list_player.set_media_list(media_list)

    #
    ## new

    while True:

        if ad_due == 0:
            print("AD DUE 0")
            # get file from tv folder
            tv_files = get_media_files(tv_folder)
            print(f"ad_files count {len(tv_files)}")
            # Choose random file
            selected_file = select_rnd_file(tv_files, played_tv, tv_folder)
            print(f"selected_file {selected_file}")
            # call player
            print(f"Add to played list")
            # play_file(selected_file)
            # Add file to the playlist
            media_list.add_media(media_player.media_new(selected_file))
            # Play the playlist
            list_player.play()

            print(f"file played called, now sleep")
            # Wait for the media to start playing
            time.sleep(1)
            # Mark the current file as played
            played_tv.append(selected_file)
            # Ensure the player keeps playing, otherwise reset it
            print(f"wait for player to stop")
            # while media_player.is_playing():
            #    time.sleep(0.1)
            ad_due = 2

        else:
            print(f"AD DUE {ad_due}")
            # get file from tv folder
            ad_files = get_media_files(ad_folder)
            print(f"ad_files count {len(ad_files)}")
            # Choose random file
            selected_file = select_rnd_file(ad_files, played_ads, ad_folder)
            print(f"selected_file {selected_file}")
            # call player
            # play_file(selected_file)
            # Add file to the playlist
            media_list.add_media(media_player.media_new(selected_file))
            # Play the playlist
            list_player.play()
            print(f"file played called, now sleep")
            # Wait for the media to start playing
            time.sleep(1)
            # Mark the current file as played
            print(f"Add to played list")
            played_ads.append(selected_file)
            # Ensure the player keeps playing, otherwise reset it
            print(f"wait for player to stop")
            # while media_player.is_playing():
            #    time.sleep(0.1)
            # decrement, i.e play 2 ads until done
            ad_due -= 1


# END DEF

def play_file(file_path):
    with media_lock:
        media = vlc.Media(file_path)
        media_player.set_media(media)
        media_player.play()


# END DEF

def seconds_until(hour: int, minute: int = 0):
    now = datetime.now()
    end_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if end_time < now:
        # target has passed today → add 1 day
        end_time += timedelta(days=1)

    return int((end_time - now).total_seconds())


# Example: seconds until 17:59
remaining_seconds = seconds_until(17, 59)
print(remaining_seconds)


# ==========================================================
# ===================== MAIN ===============================
# ==========================================================
def main():

    # === 03-09-25 -- this little block here is how we setup a playlist and start it.
    # should we calculate what we require for all of our schedules up to the restart time and play like that? e.g. 24 hours at a time

    instance = vlc.Instance()
    media_list = instance.media_list_new()

    media_list.add_media(
        instance.media_new("C:\\Videos\\shows\\test.avi"))
    media_list.add_media(instance.media_new("C:\\Videos\\ads\\test.mp4"))  # add before playing

    list_player = instance.media_list_player_new()
    list_player.set_media_list(media_list)

    player = list_player.get_media_player()

    #list_player.play()
    #time.sleep(0.5)
    #player.set_fullscreen(True)
    # ======================

    # global keeps track of which files have been played, files are added to this list as they are played
    global played_tv
    played_tv = []  # List to keep track of played files

    global played_ads
    played_ads = []  # List to keep track of played files

    global ad_due
    ad_due = 0

    # test

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

    # === Load durations.json if exist ===
    if os.path.exists("durations.json"):
        print("durations.json exists, proceed")
        with open("durations.json", "r") as f:
            durjson = json.load(f)
    else:
        print("durations.json does not exist!")
        print("please run durationanalyzer.py first!")
        exit(1)

    # === Read restart time from rawjson ===
    # restarttime = {name: System.from_dict(details) for name, details in cfgjson["system"].items()}

    system = System.from_dict(cfgjson["system"])

    # === Read schedules from rawjson ===
    schedules = {name: Schedule.from_dict(details) for name, details in cfgjson["schedules"].items()}
    del cfgjson  # Free up RAM
    config = Config(schedules=schedules)
    del schedules  # Free up RAM

    # now we have our schedule lets find out which media is to be used/is active considering as well which media has already been played:

    # Usually we do this:
    # Get list of all media based on the schedule that is currently active
    show_paths, ad_paths = config.get_active_media()  # returns tuple (i.e 2 lists)

    # From these folders then we need to know which items we are allowed to play:
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
    selected_file = random.choice(unplayed_shows)

    # Get duration of selected_file
    duration = durjson["by_path"].get(selected_file)

    # play selected file here

    # setup timer thread to wait for this duration and then mark as played
    timer = PlaybackTimer(tracker, durjson)
    timer.add_media(selected_file, "shows")

    # ================== whilst timer thread waits we can start to queue other files in a main loop here =============

    # now almost the old logic with ad_due etc here in a loop to build a playlist of files

    ad_due = 2  # declare at 2 so ads start to play next

    # ========================

    # create vlc media player object
    # global media_player
    # media_player = vlc.Instance()

    # --- Create a VLC media list ---
    # media_list = media_player.media_list_new()

    # Add each file to the media list
    # for media_file in playlist_files:
    #    media = media_player.media_new(media_file)
    #    media_list.add_media(media)

    # --- Create a media list player ---
    # list_player = media_player.media_list_player_new()

    # Link the list player to the media list
    # list_player.set_media_list(media_list)

    # Optionally: start playback
    # list_player.play()

    # ========================

    while True:

        if ad_due == 0:
            print("AD DUE 0")
            # get file from tv folder
            tv_files = get_media_files(tv_folder)
            print(f"ad_files count {len(tv_files)}")
            # Choose random file
            selected_file = select_rnd_file(tv_files, played_tv, tv_folder)
            print(f"selected_file {selected_file}")
            # call player
            print(f"Add to played list")
            # play_file(selected_file)
            # Add file to the playlist
            media_list.add_media(media_player.media_new(selected_file))
            # Play the playlist
            list_player.play()

            print(f"file played called, now sleep")
            # Wait for the media to start playing
            time.sleep(1)
            # Mark the current file as played
            played_tv.append(selected_file)
            # Ensure the player keeps playing, otherwise reset it
            print(f"wait for player to stop")
            # while media_player.is_playing():
            #    time.sleep(0.1)
            # ad_due = 2

        else:
            print(f"AD DUE {ad_due}")
            # get file from tv folder
            ad_files = get_media_files(ad_folder)
            print(f"ad_files count {len(ad_files)}")
            # Choose random file
            selected_file = select_rnd_file(ad_files, played_ads, ad_folder)
            print(f"selected_file {selected_file}")
            # call player
            # play_file(selected_file)
            # Add file to the playlist
            media_list.add_media(media_player.media_new(selected_file))
            # Play the playlist
            list_player.play()
            print(f"file played called, now sleep")
            # Wait for the media to start playing
            time.sleep(1)
            # Mark the current file as played
            print(f"Add to played list")
            played_ads.append(selected_file)
            # Ensure the player keeps playing, otherwise reset it
            print(f"wait for player to stop")
            # while media_player.is_playing():
            #    time.sleep(0.1)
            # decrement, i.e play 2 ads until done
        # ad_due -= 1

    # select_rnd_file()
    endhour = 17
    endhour = 18
    endhour = 19

    # now randomly pick a show
    # get the shows duration
    # setup a timer thread that sits and waits for the duration of the show
    # start playing the show
    # queue up ads and more shows up but as we do add the durations to a stack that the timer thread works through
    # timer fires, writes that the show has been played to played.json

    # SEE CHAT GPT FOR THE TIMER THREAD BITS

    # activeschedule = config.get_active_schedule()

    endhour = 17
    endminute = 59

    seconds_remaining = seconds_until(endhour, endminute)

    # ==============EXAMPLE USAGE ======================================
    tracker = PlayedTracker()

    # Example schedule
    shows = ["show1.mp4", "show2.mp4", "show3.mp4"]

    # Play a file...
    tracker.mark_played("show1.mp4", "shows")

    # Check if complete rotation
    if tracker.all_played(shows, "shows"):
        print("All shows played! Resetting...")
        tracker.reset("shows")
    # =================================================================

    # ====== Since you already have durations.json, the logic will be: =====

    # duration = durations.get(file_path)
    # play_file(file_path, duration)

    # if playback_reached(duration):
    #        played_tracker.mark_played(file_path, media_type)

    # That ensures files only get added if actually played to the end.

    ## ===== can do this to fire something after X seconds =====
    # def my_task():
    #   print("Task fired at", time.strftime("%H:%M:%S"))

    # Fire after 10 seconds
    # t = threading.Timer(10, my_task)
    # t.start()

    # now we have a list of the ads and shows we should be playing at this time we need to:
    # 1 - find out how long left before this schedule ends

    # 2- Read durations.json and see what we can fit into the schedule, what if none fit? just ads?

    # ms = MediaScheduler()

    # Create the play media thread if we are not on win/nt
    if os.name != "nt":
        print(f"we are not on win we re on '{os.name}'")
        # global media_player
        # media_player = vlc.Instance()
        # play_thread = threading.Thread(target=play_media, daemon=True)
        # play_thread.start()

    # Main thread just sleeps to allow other threads to work
    while True:
        time.sleep(1)


# END DEF

if __name__ == "__main__":
    main()
