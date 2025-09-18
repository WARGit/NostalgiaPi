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
        """Builds a playlist that runs from now until the reboot time specified.
           Takes into account the active schedule at each point in time."""
        playlist: list[tuple[str, str]] = []
        current_time = start_time
        secs_left = seconds_until_restart(self.system)

        # Maintain per-schedule in-memory lists of available shows/ads
        schedule_pools: dict[str, dict[str, list[str]]] = {}

        while secs_left > 0:
            active = self.config.get_active_schedule_at(current_time)
            if not active:
                print(f"[WARN] No schedule active at {current_time}")
                break

            # find the schedule name (dict key) for this schedule object
            schedule_name = next((n for n, s in self.config.schedules.items() if s is active), None)
            if schedule_name is None:
                schedule_name = "unknown"

            # Initialize pools for this schedule if not already
            if schedule_name not in schedule_pools:
                shows = sum((get_media_files(p) for p in active.shows), [])
                ads = sum((get_media_files(p) for p in active.ads), [])
                bumpers = sum((get_media_files(p) for p in active.bumpers), [])
                schedule_pools[schedule_name] = {
                    "shows": shows,
                    "ads": ads,
                    "bumpers": bumpers
                }

            pool = schedule_pools[schedule_name]

            # Reset per-schedule played/queued if pools exhausted
            for category in ("shows", "ads"):
                if not pool[category]:
                    self.tracker.reset_if_exhausted(schedule_name, category)
                    self.queue_tracker.reset_if_exhausted(schedule_name, category)
                    # re-gather files from disk
                    files = sum((get_media_files(p) for p in getattr(active, category)), [])
                    pool[category] = files

            candidate, category, dur = None, None, 0

            def pick(files: list[str], cat: str, force=False):
                nonlocal candidate, category, dur
                if not files:
                    return False
                shuffled = files[:]
                random.shuffle(shuffled)
                for choice in shuffled:
                    d = int(self.durations["by_path"].get(choice, 0))
                    if d <= 0:
                        continue
                    if force or d <= secs_left:
                        candidate, category, dur = choice, cat, d
                        if cat in ("shows", "ads"):
                            self.queue_tracker.mark_queued(schedule_name, choice, cat)
                        # remove picked file from in-memory pool
                        files.remove(choice)
                        return True
                return False

            # Try picking in order: shows → ads → bumpers
            if not pick(pool["shows"], "shows"):
                if not pick(pool["ads"], "ads"):
                    if not pick(pool["bumpers"], "bumpers", force=True):
                        break  # very unlikely with bumpers

            if candidate is None:
                break

            playlist.append((candidate, category))
            secs_left -= dur
            current_time += timedelta(seconds=dur)

            # If we just added a show then add 2 ads immediately (if they fit)
            if category == "shows":
                for _ in range(2):
                    if pick(pool["ads"], "ads"):
                        playlist.append((candidate, category))
                        secs_left -= dur
                        current_time += timedelta(seconds=dur)
                    else:
                        break

        return playlist


