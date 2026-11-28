"""sheila_app.py — CSM Sheila as a Windows desktop app (Aaron, 2026-11-28: "Create a version of Sheila that will run as a
desktop app. Maintain both the web version and the app version. This needs to run on Windows.").

THE APP IS THE SAME SHEILA. `ars_launcher_web.py --app` starts the same 127.0.0.1 server, with the same token, page and
build queue, and shows the page in a window of its own instead of a browser tab: Microsoft Edge in app mode (no address
bar, no tabs, Sheila's own title and icon in the taskbar). Nothing about the page is forked, so every change to Sheila
reaches both versions; the web version (`ARS Deck Builder GUI.bat`, a browser tab) is unchanged.

Why Edge's app mode and not a Python window library: Edge (and its WebView2 runtime) is on every Windows 11 PC, so the
app needs nothing added to the Python runtime the CSMs share (a native-window library on Windows needs pythonnet, which
the runtime's Python 3.14 does not reliably support), and it renders exactly what the web version renders.

THE WINDOW OWNS THE APP. Edge runs on a profile of Sheila's own (`%LOCALAPPDATA%\\RPE\\sheila_app`), which remembers the
window's size and place, keeps Sheila out of the CSM's own browser, and gives a reliable signal: Edge holds `lockfile`
in that folder locked while any window on it is open and removes it when the last one closes (`window_open`). When the
window closes, the server stops, after any deck build or ILS run in progress finishes (`busy`), so closing the window
never cuts a build short. A second launch while one is open opens a second window on the same profile; each server stays
until every Sheila window is closed.

No Edge (it can be removed by policy): Sheila says so and opens in the default browser, which is the web version, and keeps
serving until the process is stopped, as the web version does.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

WINDOW = (1440, 900)              # the first window's size; Edge remembers the CSM's own after that
OPEN_TIMEOUT = 45                 # seconds to wait for the window to appear before treating the launch as failed
POLL = 2.0                        # seconds between checks that the window is still open


def find_edge(env=None):
    """The path of msedge.exe, or None. The usual install places first, then PATH."""
    env = os.environ if env is None else env
    for base in (env.get("ProgramFiles(x86)"), env.get("ProgramFiles"), env.get("LOCALAPPDATA")):
        if base:
            p = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if p.is_file():
                return str(p)
    return shutil.which("msedge")


def profile_dir(env=None):
    """Sheila's own Edge profile, beside the local runtime (`%LOCALAPPDATA%\\RPE`)."""
    env = os.environ if env is None else env
    base = env.get("LOCALAPPDATA") or env.get("TMPDIR") or "/tmp"
    return Path(base) / "RPE" / "sheila_app"


def command(edge, url, profile, size=WINDOW):
    """The Edge command line for Sheila's window."""
    return [edge, f"--app={url}", f"--user-data-dir={profile}", f"--window-size={size[0]},{size[1]}",
            "--no-first-run", "--no-default-browser-check", "--disable-background-mode",
            "--disable-features=msEdgeStartupBoost"]


def window_open(profile):
    """True while an Edge window is open on Sheila's profile: Edge keeps `lockfile` there locked while it runs and removes
    it on exit. Opened WITHOUT creating it, so a check never leaves a lock file behind."""
    lock = os.path.join(str(profile), "lockfile")
    try:
        fd = os.open(lock, os.O_RDWR)
    except FileNotFoundError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    os.close(fd)
    return False                                          # a stale file Edge left after a crash: not in use


def run(url, shutdown, busy=lambda: False, say=print, edge=None, profile=None, popen=subprocess.Popen,
        sleep=time.sleep, clock=time.monotonic, open_browser=webbrowser.open):
    """Open Sheila's window on `url` and call `shutdown()` when it closes and nothing is running. Returns "app" when the
    window was shown and closed, "browser" when there is no Edge (the page opened in the browser and the server keeps
    serving), "failed" when Edge started but no window appeared (the page opened in the browser instead)."""
    edge = edge or find_edge()
    if not edge:
        say(" Microsoft Edge was not found, so Sheila opens in your browser instead.")
        open_browser(url)
        return "browser"
    profile = Path(profile or profile_dir())
    profile.mkdir(parents=True, exist_ok=True)
    proc = popen(command(edge, url, profile))
    say(" Sheila's window is open. Close it when you're done.")
    start = clock()
    while not window_open(profile) and proc.poll() is None:
        if clock() - start > OPEN_TIMEOUT:
            break
        sleep(0.5)
    if not window_open(profile) and proc.poll() is not None:
        # Edge exited without leaving a window open on the profile (blocked by policy, or it crashed): the browser.
        say(" Sheila's window did not open, so she opens in your browser instead.")
        open_browser(url)
        return "failed"
    while window_open(profile) or proc.poll() is None:
        sleep(POLL)
    if busy():
        say(" Sheila's window is closed. Finishing the build in progress before she stops.")
        while busy():
            sleep(POLL)
    say(" Sheila's window is closed. Stopping.")
    shutdown()
    return "app"


def log_to_file(env=None):
    """Under pythonw there is no console: send what Sheila prints to `%LOCALAPPDATA%\\RPE\\sheila_app.log` (the last run
    only), so a failure can still be read. Does nothing when there is a console."""
    if sys.stdout is not None and sys.stderr is not None:
        return None
    path = profile_dir(env).parent / "sheila_app.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "w", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or fh
    sys.stderr = sys.stderr or fh
    return path
