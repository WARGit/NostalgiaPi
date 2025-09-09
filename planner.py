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

        while secs_left > 0:
            active = self.config.get_active_schedule_at(current_time)
            if not active:
                break

            # Gather all shows, ads & bumpers
            shows = sum((get_media_files(p) for p in active.shows), [])
            ads = sum((get_media_files(p) for p in active.ads), [])
            bumpers = sum((get_media_files(p) for p in active.bumpers), [])

            # Filter ads & shows against played.json to find what we are allowed to play
            shows = self.tracker.get_unplayed(shows, "shows")
            ads = self.tracker.get_unplayed(ads, "ads")

            candidate, category, dur = None, None, 0  # make some variables to use

            def pick(files: list[str], cat: str):
                nonlocal candidate, category, dur
                if not files:
                    return False
                shuffled = files[:]
                random.shuffle(shuffled)
                for choice in shuffled:
                    d = int(self.durations["by_path"].get(choice, 0))
                    if 0 < d <= secs_left:
                        candidate, category, dur = choice, cat, d
                        return True
                return False

            # Try to pick a show, then ad, then bumper
            if not pick(shows, "shows"):
                if not pick(ads, "ads"):
                    if not pick(bumpers, "bumpers"):
                        break  # nothing fits

            # Add chosen item
            playlist.append((candidate, category))
            secs_left -= dur
            current_time += timedelta(seconds=dur)

            # 🔑 If it was a show → add 2 ads immediately (if they fit)
            if category == "shows":
                for _ in range(2):
                    if pick(ads, "ads"):
                        playlist.append((candidate, category))
                        secs_left -= dur
                        current_time += timedelta(seconds=dur)
                    else:
                        break  # no ad fits, move on

        return playlist
