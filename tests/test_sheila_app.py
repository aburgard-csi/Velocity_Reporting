"""CSM Sheila as a desktop app (scripts/sheila_app.py; Aaron, 2026-11-28: "Create a version of Sheila that will run as a
desktop app. Maintain both the web version and the app version."). The app is the same server and page in an Edge app
window; it stops when the window closes, never in the middle of a build."""
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "build"))

import sheila_app as A  # noqa: E402

URL = "http://127.0.0.1:5555/"


def fake_edge(tmp_path, where="ProgramFiles(x86)"):
    base = tmp_path / where.replace("(", "_").replace(")", "_")
    exe = base / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    return {where: str(base)}, str(exe)


def test_edge_is_found_where_windows_installs_it(tmp_path, monkeypatch):
    monkeypatch.setattr(A.shutil, "which", lambda name: None)
    env, exe = fake_edge(tmp_path)
    assert A.find_edge(env) == exe
    env, exe = fake_edge(tmp_path, "LOCALAPPDATA")                      # a per-user install
    assert A.find_edge(env) == exe
    assert A.find_edge({}) is None


def test_the_window_is_an_app_window_on_sheilas_own_profile(tmp_path):
    cmd = A.command("msedge.exe", URL, tmp_path / "prof")
    assert cmd[0] == "msedge.exe" and f"--app={URL}" in cmd                # no address bar, no tabs
    assert f"--user-data-dir={tmp_path / 'prof'}" in cmd                  # never the CSM's own browser profile
    assert "--no-first-run" in cmd
    assert A.profile_dir({"LOCALAPPDATA": str(tmp_path)}) == tmp_path / "RPE" / "sheila_app"


def test_window_open_reads_edges_lock_and_never_creates_it(tmp_path, monkeypatch):
    assert A.window_open(tmp_path) is False
    assert not (tmp_path / "lockfile").exists()                           # the check leaves nothing behind
    (tmp_path / "lockfile").write_bytes(b"")
    assert A.window_open(tmp_path) is False                               # a stale lock after a crash: not in use
    real = os.open

    def held(path, flags, *a):
        if str(path).endswith("lockfile"):
            raise PermissionError("in use")
        return real(path, flags, *a)
    monkeypatch.setattr(A.os, "open", held)
    assert A.window_open(tmp_path) is True                                # Edge holds it while a window is open


class Proc:
    def __init__(self, alive_polls):
        self.n = alive_polls

    def poll(self):
        if self.n > 0:
            self.n -= 1
            return None
        return 0


def harness(monkeypatch, tmp_path, open_states, busy_states=(), proc=None):
    """run() with a fake Edge: `open_states` is what window_open answers, in order (then False); `busy_states` what
    busy() answers (then False)."""
    states, busies = list(open_states), list(busy_states)
    monkeypatch.setattr(A, "window_open", lambda p: states.pop(0) if states else False)
    calls = {"shutdown": 0, "browser": [], "said": [], "cmd": None}

    def popen(cmd):
        calls["cmd"] = cmd
        return proc or Proc(0)
    out = A.run(URL, lambda: calls.__setitem__("shutdown", calls["shutdown"] + 1),
                busy=lambda: busies.pop(0) if busies else False, say=calls["said"].append,
                edge="msedge.exe", profile=tmp_path / "prof", popen=popen, sleep=lambda s: None,
                open_browser=calls["browser"].append)
    return out, calls


def test_closing_the_window_stops_sheila_once(monkeypatch, tmp_path):
    out, calls = harness(monkeypatch, tmp_path, [False, True, True, True, False, False], proc=Proc(10))
    assert out == "app" and calls["shutdown"] == 1 and calls["browser"] == []
    assert calls["cmd"][1] == f"--app={URL}"


def test_a_build_in_progress_finishes_before_she_stops(monkeypatch, tmp_path):
    order = []
    states = [True, True, False]
    busy = [True, True, True, False]
    monkeypatch.setattr(A, "window_open", lambda p: states.pop(0) if states else False)
    out = A.run(URL, lambda: order.append("shutdown"),
                busy=lambda: (order.append("busy"), busy.pop(0) if busy else False)[1],
                say=lambda m: order.append(m), edge="msedge.exe", profile=tmp_path / "p",
                popen=lambda cmd: Proc(0), sleep=lambda s: None, open_browser=lambda u: None)
    assert out == "app"
    assert order[-1] == "shutdown" and order.count("busy") == 4               # waited until nothing was running
    assert any("Finishing the build" in str(m) for m in order)


def test_a_second_launch_handed_to_a_running_edge_still_waits_for_the_window(monkeypatch, tmp_path):
    # Edge hands the window to the Edge already running on the profile and its own process exits at once:
    # the lock, not the process, says the window is open.
    out, calls = harness(monkeypatch, tmp_path, [True, True, True, True, False], proc=Proc(0))
    assert out == "app" and calls["shutdown"] == 1


def test_no_edge_opens_the_browser_and_keeps_serving(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "find_edge", lambda env=None: None)
    calls = {"shutdown": 0, "browser": []}
    out = A.run(URL, lambda: calls.__setitem__("shutdown", 1), say=lambda m: None,
                open_browser=calls["browser"].append, popen=lambda c: pytest.fail("no Edge to start"))
    assert out == "browser" and calls["browser"] == [URL] and calls["shutdown"] == 0


def test_an_edge_that_never_shows_a_window_falls_back_to_the_browser(monkeypatch, tmp_path):
    out, calls = harness(monkeypatch, tmp_path, [False, False, False], proc=Proc(1))
    assert out == "failed" and calls["browser"] == [URL] and calls["shutdown"] == 0


def test_busy_counts_deck_builds_and_ils_runs(monkeypatch):
    import ars_launcher_web as W
    import ils_runs

    class J:
        def __init__(self, done):
            self.done = done
    monkeypatch.setattr(W, "_jobs", {})
    monkeypatch.setattr(ils_runs, "_jobs", {})
    assert W.busy() is False
    W._jobs["1539"] = J(False)
    assert W.busy() is True
    W._jobs["1539"] = J(True)
    ils_runs._jobs[("review", "1125")] = J(False)
    assert W.busy() is True
    ils_runs._jobs[("review", "1125")] = J(True)
    assert W.busy() is False


def test_the_app_launcher_starts_the_same_sheila_without_a_console():
    raw = (REPO / "scripts" / "launchers" / "CSM Sheila App.bat").read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")      # cmd needs CRLF
    bat = raw.decode("ascii")
    assert 'call "%ROOT%Tools\\RPE\\scripts\\launchers\\runtime.cmd"' in bat
    assert "ars_launcher_web.py" in bat and '"%APP%" --app' in bat        # the same server, the app window
    assert "pythonw.exe" in bat
    web = (REPO / "scripts" / "launchers" / "ARS Deck Builder GUI.bat").read_text(encoding="ascii")
    assert "--app" not in web                                             # the web version is unchanged


def test_without_a_console_what_she_prints_goes_to_a_log(monkeypatch, tmp_path):
    monkeypatch.setattr(A.sys, "stdout", None)
    monkeypatch.setattr(A.sys, "stderr", None)
    path = A.log_to_file({"LOCALAPPDATA": str(tmp_path)})
    try:
        print("hello from pythonw")
        A.sys.stdout.flush()
        assert path == tmp_path / "RPE" / "sheila_app.log"
        assert "hello from pythonw" in path.read_text(encoding="utf-8")
    finally:
        A.sys.stdout.close()
