"""The watchdog finds a LONE suspended process (2026-10-07).

Windows PowerShell 5.1 unrolls a function's one-element result to a scalar, and a [pscustomobject] has no
.Count there, so `if ($stuck.Count -gt 0)` was false for exactly one suspended process and the watchdog
logged "no suspended process found ... needs a human look" while the 08:00 fire sat stuck for two hours.
It only ever worked when two turned up together (a stuck fire plus the next one stacked on it) - every
"found" line in source_watch_watchdog.log is a pair. The function now returns an array on purpose.
"""
import os
import re
import shutil
import subprocess

import pytest

POWERSHELL = shutil.which("powershell") or shutil.which("powershell.exe")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "watch_task_watchdog.ps1")

pytestmark = pytest.mark.skipif(not POWERSHELL, reason="Windows PowerShell is not available")


def _function_text():
    src = open(SCRIPT, encoding="utf-8").read()
    m = re.search(r"function Find-StuckWatchProcesses \{.*?\n\}\n", src, re.S)
    assert m, "Find-StuckWatchProcesses not found in the watchdog"
    return m.group(0)


def _run(count_of_fake_processes, age_hours=2, cpu="$null", handles=0, reasons=False):
    """Run the real function with Get-CimInstance / Get-Process stubbed to `n` processes of
    the given age and counters (the defaults are the suspended signature)."""
    prog = f"""
$MinAgeSecondsToJudge = 240
$MaxAgeSecondsAlive = 10800
function Get-CimInstance {{
    @(1..{count_of_fake_processes} | Where-Object {{ {count_of_fake_processes} -gt 0 }}) | ForEach-Object {{
        [pscustomobject]@{{ ProcessId = 1000 + $_; ParentProcessId = 1; CreationDate = (Get-Date).AddHours(-{age_hours})
                            CommandLine = 'pythonw.exe C:\\x\\watch_sources.py --copy' }} }}
}}
function Get-Process {{ [pscustomobject]@{{ CPU = {cpu}; HandleCount = {handles} }} }}
{_function_text()}
$stuck = Find-StuckWatchProcesses
"count=" + $stuck.Count + " gt0=" + ($stuck.Count -gt 0)
{'"reason=" + (@($stuck | ForEach-Object { $_.Reason }) -join "|")' if reasons else ''}
"""
    out = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", prog],
                         capture_output=True, text=True, timeout=60)
    return out.stdout.strip()


def test_a_single_suspended_process_is_found():
    assert _run(1) == "count=1 gt0=True"


def test_two_suspended_processes_are_still_found():
    assert _run(2) == "count=2 gt0=True"


def test_no_suspended_process_is_still_none():
    assert _run(0) == "count=0 gt0=False"


def test_the_call_site_wraps_the_result_in_an_array_too():
    src = open(SCRIPT, encoding="utf-8").read()
    assert "$stuck = @(Find-StuckWatchProcesses)" in src


# ------------------------------------------------------------------ alive too long
# 2026-10-05: the run reached the shares, copied for two hours, then hung in its mail step
# with 73 s of CPU and 161 handles - nothing like the suspended signature - and the
# scheduler's own limit did not end it. The task is MultipleInstances IgnoreNew, so the
# next 08:00 fire was dropped. A watch process older than $MaxAgeSecondsAlive is stuck
# whatever its counters say (Aaron, 2026-10-07).
def test_a_live_process_older_than_the_limit_is_stuck():
    assert _run(1, age_hours=4, cpu=73.2, handles=161, reasons=True) == \
        "count=1 gt0=True\nreason=older than 10800 s"


def test_a_live_process_within_the_limit_is_not():
    assert _run(1, age_hours=1, cpu=73.2, handles=161, reasons=True) == "count=0 gt0=False\nreason="


def test_a_suspended_process_is_still_named_as_such():
    assert _run(1, reasons=True) == "count=1 gt0=True\nreason=created suspended"


def test_an_overage_process_is_cleared_even_when_todays_run_happened():
    """Watch-RanToday is true for a run that reached the shares and then hung, so the
    silent exit must look for the over-age process first - or it is still there at 08:00."""
    src = open(SCRIPT, encoding="utf-8").read()
    head = src[src.index("if (Watch-RanToday) {"):]
    assert head.index('Where-Object { $_.Reason -like "older than*" }') < head.index("exit 0")