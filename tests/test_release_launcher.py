"""release_launcher.ps1 ships origin/main and nothing else (Aaron, 2026-10-07; the default since
2026-10-08, "make -FromOrigin the default").

robocopy mirrors whatever is on disk onto the share, so on 2026-10-07 a release from the working
tree stamped "with uncommitted changes" and carried another session's half-finished file to
every CSM. By default the script now fetches origin/main, checks it out detached into a release
worktree of its own and releases THAT; -FromWorkingTree releases the checkout and then refuses a
dirty tree or a HEAD not on origin/main unless -Force is also given, and a forced release says so
in RELEASE.txt. These tests read the script: the worktree step and the guard have to come before
anything is copied, and the .venv has to be read from the real checkout, never the worktree.
"""
import os
import re
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "release_launcher.ps1")
POWERSHELL = shutil.which("powershell") or shutil.which("powershell.exe")


def _src():
    return open(SCRIPT, encoding="utf-8").read()


# ------------------------------------------------------------------ the default: origin/main
def test_the_default_releases_a_detached_checkout_of_origin_main():
    src = _src()
    assert "if (-not $FromWorkingTree) {" in src
    assert "git -C $repo fetch origin main" in src
    assert "worktree add --detach $wt origin/main" in src
    assert "checkout --detach origin/main" in src            # the kept worktree is moved, not re-made
    assert "'-FromWorkingTree', '-VenvRepo', $repo" in src    # the inner run releases the worktree


def test_the_worktree_step_comes_before_the_guard_and_the_copy():
    src = _src()
    worktree = src.index("if (-not $FromWorkingTree) {")
    guard = src.index("git -C $repo status --porcelain")
    first_copy = src.index("robocopy (Join-Path $repo $d)")
    assert worktree < guard < first_copy


def test_the_release_worktree_is_kept_between_runs_so_robocopy_copies_only_changes():
    """A fresh worktree every time gives every file a new mtime and robocopy re-copies the
    templates and fonts (ten minutes on the share, 2026-10-08); a kept one moves only what changed."""
    src = _src()
    assert "Join-Path $env:LOCALAPPDATA 'RPE\\release-worktree'" in src
    assert "worktree prune" in src and "$registered -contains $wt" in src


def test_the_runtime_reads_the_venv_from_the_real_checkout():
    src = _src()
    assert "Join-Path $VenvRepo '.venv\\pyvenv.cfg'" in src
    assert "Join-Path $VenvRepo '.venv\\Lib\\site-packages'" in src
    assert "Join-Path $repo '.venv" not in src                # the worktree has no .venv


def test_a_failed_fetch_releases_nothing():
    src = _src()
    assert "origin/main could not be fetched; nothing released" in src


# ------------------------------------------------------------------ -FromWorkingTree
def test_the_guard_checks_both_a_clean_tree_and_origin_main():
    src = _src()
    assert "merge-base --is-ancestor $head origin/main" in src
    assert "uncommitted change(s)" in src and "is not on origin/main" in src


def test_force_is_the_only_way_past_and_the_stamp_says_so():
    src = _src()
    assert re.search(r"\[switch\]\$Force", src) and re.search(r"\[switch\]\$FromWorkingTree", src)
    assert "if (-not $Force) { throw" in src
    assert "FORCED: " in src                      # written into RELEASE.txt
    assert "(with uncommitted changes)" not in src  # the old, quiet wording is gone


def test_the_stamp_names_its_source():
    src = _src()
    assert "'origin/main (release worktree)'" in src and '"working tree $repo"' in src


@pytest.mark.skipif(not POWERSHELL, reason="Windows PowerShell is not available")
def test_the_script_parses():
    prog = ("$t=$null;$e=$null;[System.Management.Automation.Language.Parser]::ParseFile("
            f"'{SCRIPT}',[ref]$t,[ref]$e)|Out-Null;$e.Count")
    out = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", prog],
                         capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "0", out.stdout + out.stderr


# ------------------------------------------------------------------ the scheduled tasks' checkout
def test_a_release_from_origin_main_moves_the_tasks_checkout_to_the_released_commit():
    """Aaron, 2026-11-24: "have the release update the tasks checkout too". The 08:00 watch, its watchdog and the
    ILS landing run from their own checkout (RPE_TASKS_CHECKOUT); each release from origin/main moves it to the
    commit just released, AFTER the release succeeded, and -FromWorkingTree (which exits before) never does."""
    src = _src()
    inner = src.index("& powershell @args")
    failed = src.index('throw "release from origin/main failed')
    update = src.index("Update-TasksCheckout -Released (git -C $wt rev-parse HEAD)")
    assert inner < failed < update < src.index("exit 0", update)
    assert "git -C $full checkout --detach $Released --quiet" in src
    assert "RPE_TASKS_CHECKOUT" in src and "'^\\s*RPE_TASKS_CHECKOUT\\s*='" in src   # environment, else .env


def test_the_tasks_checkout_step_never_fails_a_release_and_never_touches_changes():
    src = _src()
    body = src[src.index("function Update-TasksCheckout"):src.index("# ---------------------------------------------------------------- origin/main")]
    assert "throw" not in body                                    # the release has already happened
    assert "RPE_TASKS_CHECKOUT not set; skipped." in body
    assert "is not a worktree of $repo; left alone." in body
    assert "local change(s); left alone" in body and "status --porcelain" in body
    assert "catch {" in body