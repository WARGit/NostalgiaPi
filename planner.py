import logging
import random
from datetime import datetime, timedelta
from models import Config, System
from tracker import PlayedTracker, QueuedTracker
from utils import get_media_files, seconds_until_restart
import pathlib

class QueuePlanner:
    """
    Builds a play queue from 'now' until the configured restart time,
    honoring active schedule at each point in time and using durations
    from durations["by_path"].
    """

    def __init__(self, config: Config, tracker: PlayedTracker, queue_tracker: QueuedTracker, durations: dict, system: System):
        logging.debug(f"Init QueuePlanner")
        self.config = config
        self.tracker = tracker
        self.queue_tracker = queue_tracker
        self.durations = durations
        self.system = system

    def build_playlist_until_restart(self, start_time: datetime) -> list[tuple[str, str]]:
        """Builds a playlist that runs from now until the reboot time specified.
           Takes into account the active schedule at each point in time."""
        logging.debug(f"Begin build_playlist_until_restart")
        playlist: list[tuple[str, str]] = []
        current_time = start_time
        logging.debug(f"Current time: {current_time}")
        secs_left = seconds_until_restart(self.system)
        logging.debug(f"Secs left: {secs_left}")

        # Maintain per-schedule in-memory lists of available shows/ads
        schedule_pools: dict[str, dict[str, list[str]]] = {}

        # Track last played per schedule/category
        last_played: dict[tuple[str, str], str] = {}

        while secs_left > 0:
            logging.debug(f"Contine Loop - Secs left: {secs_left}")
            active = self.config.get_active_schedule_at(current_time)   # get the active schedule object for the time (time is shifted as we build the playlist)
            if not active:
                logging.debug(f"No active schedule at {current_time}, please define one!")
                break
            else:
                logging.debug(f"Active schedule determined from {active.starthour}:{active.startminute}-{active.endhour}:{active.endminute}")

            # find the schedule name (dict key) for this schedule object
            schedule_name = next((n for n, s in self.config.schedules.items() if s is active), None)    # get the name of the schedule
            if schedule_name is None:
                logging.debug(f"Schedule name could not be determined!")
                schedule_name = "unknown"
            else:
                logging.debug(f"Schedule name: {schedule_name}")

            # Initialize pools for this schedule if not already
            if schedule_name not in schedule_pools:
                logging.debug(f"Schedule name {schedule_name} not in pool, add shows/ads/bumpers")
                shows = sum((get_media_files(p) for p in active.shows), [])
                ads = sum((get_media_files(p) for p in active.ads), [])
                bumpers = sum((get_media_files(p) for p in active.bumpers), [])
                schedule_pools[schedule_name] = {
                    "shows": shows,
                    "ads": ads,
                    "bumpers": bumpers
                }
            else:
                logging.debug(f"Schedule name: {schedule_name} already in pool")

            pool = schedule_pools[schedule_name]

            # Reset per-schedule played if pools exhausted
            for category in ("shows", "ads"):
                if not pool[category]:      # if the list of "shows" or "ads" is empty
                    logging.debug(f"Pool {pool[category]} is exhausted")
                    self.tracker.reset_if_exhausted(schedule_name, category)    # reset the json
                    files = sum((get_media_files(p) for p in getattr(active, category)), []) # re-gather files from disk
                    logging.debug(f"Refill pool from files on disk")
                    pool[category] = files  # refill the pool

                else:
                    logging.debug(f"Pool {pool[category]} is not empty")

            candidate, category, dur = None, None, 0    # set up an object to be filled by pick method

            def pick(files: list[str], cat: str, force=False):
                logging.debug(f"Begin pick")
                nonlocal candidate, category, dur
                if not files:
                    logging.debug(f"No files! returning false")
                    return False
                logging.debug(f"Shuffling files")
                shuffled = files[:]
                random.shuffle(shuffled)

                # avoid repeating the last played if possible
                last = last_played.get((schedule_name, cat))
                logging.debug(f"Last played: {last}")
                for choice in shuffled:
                    if choice == last and len(shuffled) > 1:
                        logging.debug(f"Last played: {last} matches choice {choice}, skipping")
                        continue  # skip immediate repeat after reset

                    logging.debug(f"Get duration of choice {choice}")
                    d = int(self.durations["by_path"].get(choice, 0))
                    logging.debug(f"Duration is: {d}")
                    if d <= 0:
                        logging.debug(f"Duration {d}, less than zero!, skipping")
                        continue
                    logging.debug(f"Force: {force}")
                    if force or d <= secs_left:
                        candidate, category, dur = choice, cat, d
                        if cat in ("shows", "ads"):
                            # remove picked file from in-memory pool
                            logging.debug(f"Removing choice {choice} from files pool and returning true")
                            files.remove(choice)
                            # update last played
                            last_played[(schedule_name, cat)] = choice
                            return True
                logging.debug("returning false")
                return False

            # Try picking in order: shows → ads → bumpers
            if not pick(pool["shows"], "shows"):
                logging.debug(f"Unable to pick a show!")
                if not pick(pool["ads"], "ads"):
                    logging.debug(f"Unable to pick an ad!")
                    if not pick(pool["bumpers"], "bumpers", force=True):
                        logging.debug(f"Unable to pick a bumper! Something very wrong!")
                        break  # very unlikely with bumpers

            if candidate is None:
                logging.debug(f"No candidate!")
                break

            # If we are about to play a show, randomly add a bumper before it based on config file value
            if category == "shows" and pool["bumpers"]:
                logging.debug(f"Randomly add bumper before show")
                if random.random() < getattr(active, "bumper_chance", 0.5): # get from config file, default to 50%
                    logging.debug("Adding bumper")
                    bumper_candidate, bumper_dur = None, 0

                    def pick_bumper(files: list[str]):
                        nonlocal bumper_candidate, bumper_dur
                        if not files:
                            return False
                        shuffled = files[:]
                        random.shuffle(shuffled)
                        for choice in shuffled:
                            d = int(self.durations["by_path"].get(choice, 0))
                            if d <= 0:
                                continue
                            bumper_candidate, bumper_dur = choice, d
                            return True
                        return False

                    if pick_bumper(pool["bumpers"]):
                        # Append bumper first
                        playlist.append((bumper_candidate, "bumpers"))
                        secs_left -= bumper_dur
                        current_time += timedelta(seconds=bumper_dur)
                        logging.debug(f"Inserted {bumper_candidate} ({bumper_dur}s) before show")
                else:
                    logging.debug(f"No bumper will be added")

            logging.debug(f"Added {candidate} candidate to playlist")

            self.queue_tracker.mark_queued(pathlib.Path(candidate).stem, category, current_time)
            playlist.append((candidate, category))
            secs_left -= dur
            logging.debug(f"secs_left: {secs_left}")
            current_time += timedelta(seconds=dur)
            logging.debug(f"current_time: {current_time}")

            # If we just added a show then add 2 ads immediately (if they fit)
            if category == "shows":
                for _ in range(2):
                    logging.debug(f"Adding 2 ads before next show")
                    if pick(pool["ads"], "ads"):
                        logging.debug(f"Appending ad to playlist {candidate}")
                        playlist.append(((candidate), category))
                        logging.debug(f"secs_left: {secs_left}")
                        secs_left -= dur
                        logging.debug(f"current_time: {current_time}")
                        current_time += timedelta(seconds=dur)
                    else:
                        logging.debug(f"Could not pick Ads! something wrong!")
                        break
        logging.debug(f"Playlist creation complete, returning")
        return playlist


