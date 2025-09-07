import os
from datetime import datetime, timedelta
from models import System

def get_media_files(folder: str) -> list[str]:
    """Return full paths of video files in a folder (no recursion)."""
    try:
        return [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith(('.mkv', '.mp4', '.avi'))
        ]
    except FileNotFoundError:
        return []


def seconds_until_restart(system: System) -> int:
    now = datetime.now()
    restart = now.replace(hour=system.restarthour,
                          minute=system.restartminute,
                          second=0, microsecond=0)
    if now >= restart:
        restart += timedelta(days=1)
    return int((restart - now).total_seconds())

