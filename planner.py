import random
import os
import json
from datetime import datetime, timedelta
from models import Config, System
from tracker import PlayedTracker, QueuedTracker
from utils import get_media_files, seconds_until_restart

class QueuePlanner:
    """
    Builds a play queue from 'now' until the configured restart time,
    honoring active schedule at each point in time and using durations
    from durations["by_path"].
    """

    def __init__(self, config: Config, tracker: PlayedTracker, queue_tracker: QueuedTracker, durations: dict, system: System):
        self.config = config
        self.tracker = tracker
        self.queue_tracker = queue_tracker
        self.durations = durations
        self.system = system

    def build_playlist_until_restart(self, start_time: datetime) -> list[tuple[str, str]]:
        """ Builds a playlist that runs from now until the reboot time specified.
            Takes into account the active schedule at each point in time. """
        playlist: list[tuple[str, str]] = [] # Create a playlist to hold items
        current_time = start_time           # assign current time as start time
        secs_left = seconds_until_restart(self.system) # Call method to find out how many secs until restart

        while secs_left > 0:            # as long as there are seconds left:
            active = self.config.get_active_schedule_at(current_time)   # get schedule that will be active (current_time is updated as we go round this loop)
            if not active:
                print(f"[WARN] No schedule active at {current_time}")
                break

            # Gather all shows, ads & bumpers for the active schedule
            shows = sum((get_media_files(p) for p in active.shows), [])
            ads = sum((get_media_files(p) for p in active.ads), [])
            bumpers = sum((get_media_files(p) for p in active.bumpers), [])

            # Filter ads & shows against played.json to find what we are allowed to play during this schedule
            shows = self.tracker.get_unplayed(shows, "shows")
            ads = self.tracker.get_unplayed(ads, "ads")

            # Filter ads and shows against queued.json to find out what hasn't already been queued up
            shows = self.queue_tracker.get_unqueued(shows, "shows")
            ads = self.queue_tracker.get_unqueued(ads, "ads")

            candidate, category, dur = None, None, 0

            def pick(files: list[str], cat: str, force= False):
                """ Pick an item to add to playlist, if force=true then it will be forced to pick an item even if it runs over the remaining secs """
                nonlocal candidate, category, dur
                if not files:
                    return False
                shuffled = files[:]
                random.shuffle(shuffled)
                for choice in shuffled:
                    print(f"[INFO] choice: {choice}")
                    d = int(self.durations["by_path"].get(choice, 0))
                    print(f"[INFO] d: {d}")
                    if d <= 0:  # if the choice doesn't fit move onto the next iteration
                        print(f"[WARN] choice did not fit!")
                        continue
                    if force or d <= secs_left:         # otherwise if it fits or force is true then
                        print(f"[INFO] force: {force}, d: {d}, secs_left: {secs_left}")
                        print(f"[INFO] assign candidate: {choice}")
                        print(f"[INFO] assign category: {cat}")
                        print(f"[INFO] assign dur: {d}")
                        candidate, category, dur = choice, cat, d
                        # mark immediately as queued if show/ad
                        if cat in ("shows", "ads"):
                            print(f"[INFO] cat is in shows / ads")
                            self.queue_tracker.mark_queued(choice, cat)
                            print(f"[INFO] Returning true")
                        return True
                print(f"[INFO] Returning false")
                return False

            # Try to pick something
            if not pick(shows, "shows"):
                if not pick(ads, "ads"):
                    if not pick(bumpers, "bumpers", force=True):
                        break  # nothing fits (very unlikely with bumpers)

            if candidate is None:
                break

            if secs_left <= 240:
                print(f"[INFO] secs_left: {secs_left}")

            playlist.append((candidate, category))
            secs_left -= dur
            current_time += timedelta(seconds=dur)

            # If we just added a show then add 2 ads immediately (if they fit)
            if category == "shows":
                for _ in range(2):
                    if pick(ads, "ads"):
                        playlist.append((candidate, category))  # append the ad
                        secs_left -= dur  # take duration from secs_left
                        current_time += timedelta(seconds=dur)  # adjust current time
                    else:
                        break  # no ad fits, move on # TODO change to continue instead?


        return playlist

