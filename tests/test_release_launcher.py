"""release_launcher.ps1 ships origin/main and nothing else (Aaron, 2026-10-07).

robocopy mirrors the WORKING TREE onto the share, so on 2026-10-07 a release stamped "with
uncommitted changes" carried another session's half-finished file to every CSM. The script
now refuses a dirty tree or a HEAD that is not on origin/main unless -Force is given, and a
forced release says so in RELEASE.txt. These tests read the script: the guard has to be the
first thing after the parameters, before anything is copied.
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


def test_the_guard_runs_before_anything_is_copied():
    src = _src()
    guard = src.index("git -C $repo status --porcelain")
    first_copy = src.index("robocopy (Join-Path $repo $d)")
    assert guard < first_copy


def test_the_guard_checks_both_a_clean_tree_and_origin_main():
    src = _src()
    assert "git -C $repo fetch origin main" in src
    assert "merge-base --is-ancestor $head origin/main" in src
    assert "uncommitted change(s)" in src and "is not on origin/main" in src


def test_force_is_the_only_way_past_and_the_stamp_says_so():
    src = _src()
    assert re.search(r"\[switch\]\$Force", src)
    assert "if (-not $Force) { throw" in src
    assert "FORCED: " in src                      # written into RELEASE.txt
    assert "(with uncommitted changes)" not in src  # the old, quiet wording is gone


@pytest.mark.skipif(not POWERSHELL, reason="Windows PowerShell is not available")
def test_the_script_parses():
    prog = ("$t=$null;$e=$null;[System.Management.Automation.Language.Parser]::ParseFile("
            f"'{SCRIPT}',[ref]$t,[ref]$e)|Out-Null;$e.Count")
    out = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", prog],
                         capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "0", out.stdout + out.stderr
