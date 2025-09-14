from models import System
import time
import os
import sys
import threading
from datetime import datetime, timedelta

def seconds_until_restart(system) -> int:
    """Return number of seconds until the next restart time."""
    now = datetime.now()
    restart_time = now.replace(hour=system.restarthour, minute=system.restartminute, second=0, microsecond=0)

    # If restart time today has already passed, schedule it for tomorrow
    if restart_time <= now:
        restart_time += timedelta(days=1)

    return int((restart_time - now).total_seconds())

def restart_program():
    """Restart the current Python script in-place."""
    print("[SYSTEM] Restarting program...")
    python = sys.executable
    os.execl(python, python, *sys.argv)  # replaces the current process

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

def wait_for_restart(system: System):
    """Background loop to wait until restart time, then restart the script."""
    while True:
        secs = seconds_until_restart(system)
        print(f"[RESTART] Restart scheduled in {secs // 60} minutes ({secs} seconds).")
        time.sleep(secs)

        # Perform soft restart
        print("[RESTART] Time reached. Restarting script now...")
        python = sys.executable
        os.execv(python, [python] + sys.argv)

def start_restart_thread(system: System):
    """Start the restart timer thread."""
    print("[RESTART] STARTING RESTART THREAD...")
    t = threading.Thread(target=wait_for_restart, args=(system,), daemon=True)

    t.start()
    print("[RESTART] RESTART THREAD STARTED.")
    return t
