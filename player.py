import os
import vlc
import logging
import urllib.parse
from tracker import PlayedTracker
from models import Config
from datetime import datetime

class PlaylistManager:
    """
    Wraps VLC MediaListPlayer, tracks (file and category) so we can mark
    played items via VLCs MediaPlayerEndReached event.
    """
    def __init__(self, config: Config, tracker: PlayedTracker):
        logging.debug("Init PlaylistManager")
        self.config = config            # store config so we can use it later
        self.tracker = tracker          # store tracker
        logging.debug("Create VLC instance")
        self.instance = vlc.Instance()  # create vlc instance

        self.media_list = self.instance.media_list_new()
        self.list_player = self.instance.media_list_player_new()
        self.list_player.set_media_list(self.media_list)

        # map MRL to category
        self.category_by_mrl: dict[str, str] = {}

        # attach end event
        logging.debug("Setup VLC Event for MediaPlayerEndReached")
        mp = self.list_player.get_media_player()
        em = mp.event_manager()
        em.event_attach(vlc.EventType.MediaPlayerEndReached, self.on_media_end)

    def on_media_end(self, event):

        logging.debug("Begin on_media_end")
        mp = self.list_player.get_media_player()
        media = mp.get_media()
        if not media:
            return

        mrl = media.get_mrl()  # e.g., file:///path/to/video.mp4
        logging.debug(f"mrl is: {mrl}")
        category = self.category_by_mrl.get(mrl)  # e.g., "shows", "ads", "bumpers"
        logging.debug(f"category is: {category}")

        # Convert MRL to OS path
        path = mrl
        logging.debug(f"path is: {path}")
        if mrl.startswith("file://"):
            logging.debug(f"mrl starts with file://")
            raw = mrl.replace("file:///", "", 1)
            logging.debug(f"raw is: {raw}")
            raw = urllib.parse.unquote(raw)  # decode %20 → space
            logging.debug(f"raw is: {raw}")

            if os.name == "nt":
                raw = raw.replace("/", "\\")
                logging.debug(f"OS is {os.name}, raw is: {raw}")
            path = os.path.normpath(raw)
            logging.debug(f"path is {path}")
        else:
            logging.debug(f"mrl doesnt start with file://")
            path = mrl

        # Determine active schedule at the current time
        now = datetime.now()
        logging.debug(f"datetime now is: {now}")
        active_schedule = self.config.get_active_schedule_at(now)
        logging.debug(f"active schedule retrieved")
        if active_schedule:
            logging.debug(f"Get schedule name")
            schedule_name = next((n for n, s in self.config.schedules.items() if s is active_schedule),"global")
            logging.debug(f"schedule name is {schedule_name}")
        else:
            logging.debug(f"no active schedule! set to 'global'")
            schedule_name = "global"

        if category:
            logging.debug(f"Finished: {path} ({category}),  marking played under schedule '{schedule_name}'")
            self.tracker.mark_played(schedule_name, path, category)
        else:
            logging.debug(f"Finished: {path} (unknown category)")

    def add_to_playlist(self, file_path: str, category: str):
        logging.debug(f"Begin add_to_playlist")
        media = self.instance.media_new_path(file_path)
        mrl = media.get_mrl()
        self.media_list.add_media(media)
        self.category_by_mrl[mrl] = category
        logging.debug(f"{file_path} ({category}) added to playlist, total items: {self.media_list.count()}")

    def start_playback(self):
        logging.debug(f"Begin start_playback")
        if self.media_list.count() == 0:
            logging.debug("Playlist empty! returning")
            return
        self.list_player.play()
        logging.debug("Playback started")

    def stop_playback(self):
        logging.debug(f"Begin stop_playback")
        self.list_player.stop()
        logging.debug("Playback stopped")

    def set_fullscreen(self, enable: bool):
        logging.debug(f"Begin set_fullscreen")
        mp = self.list_player.get_media_player()
        mp.set_fullscreen(enable)
        logging.debug(f"Fullscreen set to {enable}")
