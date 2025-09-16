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

            candidate, category, dur = None, None, 0  # make some variables to use

            # I don't like this here, remove in future, pass vars in and out properly
            def pick(files: list[str], cat: str, force=False):
                """ Pick an item to add to playlist, if force=true then it will be forced to pick an item even if it runs over the remaining secs """
                nonlocal candidate, category, dur
                if not files:
                    return False
                shuffled = files[:]
                random.shuffle(shuffled)
                for choice in shuffled:
                    d = int(self.durations["by_path"].get(choice, 0))
                    if force or (0 < d <= secs_left):
                        candidate, category, dur = choice, cat, d
                        return True
                return False

            if not pick(shows, "shows"):
                if not pick(ads, "ads"):
                    if not pick(bumpers, "bumpers", force=True):
                        break

            # Add chosen item
            playlist.append((candidate, category))  # add chosen item to playlist
            secs_left -= dur                        # Minus duration from seconds left
            current_time += timedelta(seconds=dur)  # Adjust current time by the duration of the item

            # If it was a show add 2 ads immediately (if they fit)
            if category == "shows":
                for _ in range(2):
                    if pick(ads, "ads"):
                        playlist.append((candidate, category))  # append the ad
                        secs_left -= dur                        # take duration from secs_left
                        current_time += timedelta(seconds=dur)  # adjust current time
                    else:
                        break  # no ad fits, move on

        return playlist
