import os
import vlc
import urllib.parse
from tracker import PlayedTracker

class PlaylistManager:
    """
    Wraps VLC MediaListPlayer, tracks (file->category) so we can mark
    played items via VLC's MediaPlayerEndReached event.
    """
    def __init__(self, tracker: PlayedTracker):
        self.tracker = tracker
        self.instance = vlc.Instance()

        self.media_list = self.instance.media_list_new()
        self.list_player = self.instance.media_list_player_new()
        self.list_player.set_media_list(self.media_list)

        # map MRL -> category
        self.category_by_mrl: dict[str, str] = {}

        # attach end event
        mp = self.list_player.get_media_player()
        em = mp.event_manager()
        em.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_media_end)

    def _on_media_end(self, event):
        # Ask the media player what just finished
        mp = self.list_player.get_media_player()
        media = mp.get_media()
        if not media:
            return
        mrl = media.get_mrl()  # e.g., file:///path/to/video.mp4
        category = self.category_by_mrl.get(mrl)  # 'file:///c:/Videos/bumpers/test.mp4'
        # Convert MRL to a plain path if you prefer to store paths:
        path = mrl
        if mrl.startswith("file://"):
            # strip the file:// prefix
            raw = mrl.replace("file:///", "", 1)

            # decode URL escapes like %20 → space
            raw = urllib.parse.unquote(raw)

            if os.name == "nt":
                # On Windows, VLC gives forward slashes; fix them
                raw = raw.replace("/", "\\")
            path = os.path.normpath(raw)
        else:
            path = mrl

        if category:
            print(f"[EVENT] Finished: {path} ({category}) → marking played")
            self.tracker.mark_played(path, category)
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
            print("[INFO] Playlist empty.")
            return
        self.list_player.play()
        print("[INFO] Playback started.")

    def stop_playback(self):
        self.list_player.stop()
        print("[INFO] Playback stopped.")

    def set_fullscreen(self, enable: bool):
        mp = self.list_player.get_media_player()
        mp.set_fullscreen(enable)
