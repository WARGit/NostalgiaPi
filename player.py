import os
import vlc
from tracker import PlayedTracker
from models import Config   # ✅ import Config so we can type hint it

class PlaylistManager:
    """
    Wraps VLC MediaListPlayer, tracks (file and category) so we can mark
    played items via VLCs MediaPlayerEndReached event.
    """
    def __init__(self, config: Config, tracker: PlayedTracker):
        self.config = config            # store config so we can use it later
        self.tracker = tracker          # store tracker
        self.instance = vlc.Instance()  # create vlc instance

        self.media_list = self.instance.media_list_new()
        self.list_player = self.instance.media_list_player_new()
        self.list_player.set_media_list(self.media_list)

        # map MRL to category
        self.category_by_mrl: dict[str, str] = {}

        # attach end event
        mp = self.list_player.get_media_player()
        em = mp.event_manager()
        em.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_media_end)

    def _on_media_end(self, event):
        import urllib.parse
        from datetime import datetime

        mp = self.list_player.get_media_player()
        media = mp.get_media()
        if not media:
            return

        mrl = media.get_mrl()  # e.g., file:///path/to/video.mp4
        category = self.category_by_mrl.get(mrl)  # e.g., "shows", "ads", "bumpers"

        # Convert MRL to OS path
        path = mrl
        if mrl.startswith("file://"):
            raw = mrl.replace("file:///", "", 1)
            raw = urllib.parse.unquote(raw)  # decode %20 → space

            if os.name == "nt":
                raw = raw.replace("/", "\\")
            path = os.path.normpath(raw)
        else:
            path = mrl

        # Determine active schedule at the current time
        now = datetime.now()
        active_schedule = self.config.get_active_schedule_at(now)
        if active_schedule:
            schedule_name = next(
                (n for n, s in self.config.schedules.items() if s is active_schedule),
                "global"
            )
        else:
            schedule_name = "global"

        if category:
            print(f"[EVENT] Finished: {path} ({category}),  marking played under schedule '{schedule_name}'")
            self.tracker.mark_played(schedule_name, path, category)
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
            print("[INFO] Playlist empty")
            return
        self.list_player.play()
        print("[INFO] Playback started")

    def stop_playback(self):
        self.list_player.stop()
        print("[INFO] Playback stopped")

    def set_fullscreen(self, enable: bool):
        mp = self.list_player.get_media_player()
        mp.set_fullscreen(enable)
