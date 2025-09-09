import random
from datetime import datetime, timedelta
from models import Config, System
from tracker import PlayedTracker
from utils import get_media_files, seconds_until_restart

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

        # Keep working copies of the pools
        all_shows = sum((get_media_files(p) for p in self.config.get_active_schedule_at(start_time).shows), [])
        all_ads = sum((get_media_files(p) for p in self.config.get_active_schedule_at(start_time).ads), [])

        shows_pool = self.tracker.get_unplayed(all_shows, "shows")
        ads_pool = self.tracker.get_unplayed(all_ads, "ads")

        while secs_left > 0:
            active = self.config.get_active_schedule_at(current_time)
            if not active:
                break

            bumpers = sum((get_media_files(p) for p in active.bumpers), [])

            candidate, category, dur = None, None, 0

            def pick(files: list[str], cat: str):
                nonlocal candidate, category, dur
                if not files:
                    return False
                random.shuffle(files)
                for choice in files:
                    d = int(self.durations["by_path"].get(choice, 0))
                    if 0 < d <= secs_left:
                        candidate, category, dur = choice, cat, d
                        # Remove from pool so it won’t repeat in this cycle
                        files.remove(choice)
                        # If pool now empty, reset tracker and refill
                        if not files:
                            self.tracker.reset(cat)
                            if cat == "shows":
                                files.extend(all_shows)
                            elif cat == "ads":
                                files.extend(all_ads)
                            random.shuffle(files)
                        return True
                return False

            # Try to pick a show → ad → bumper
            if not pick(shows_pool, "shows"):
                if not pick(ads_pool, "ads"):
                    if not pick(bumpers, "bumpers"):
                        break

            playlist.append((candidate, category))
            secs_left -= dur
            current_time += timedelta(seconds=dur)

            # If show, immediately try to add 2 ads
            if category == "shows":
                for _ in range(2):
                    if pick(ads_pool, "ads"):
                        playlist.append((candidate, category))
                        secs_left -= dur
                        current_time += timedelta(seconds=dur)
                    else:
                        break

        return playlist
