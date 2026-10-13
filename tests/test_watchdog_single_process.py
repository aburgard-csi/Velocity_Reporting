"""The watchdog counts its stuck processes right for none, one and several.

Windows PowerShell 5.1 unrolls a function's one-element result to a scalar, and a [pscustomobject] has no
.Count there, so `if ($stuck.Count -gt 0)` was false for exactly one suspended process and the watchdog
logged "no suspended process found ... needs a human look" while the 08:00 fire sat stuck for two hours
(2026-10-07). The first fix returned the collected array as `,$stuck`, and that met the @() at the call
site, which wrapped it AGAIN: no process at all came back as ONE element (an empty array), so an attempt
whose retry was running fine logged "found 1 stuck process(es)", a line with every field blank -- "PID
(parent ): age s, CPU , handles  --" -- and fired the task a second time (2026-10-08, 2026-10-12).

The function now writes each stuck process to the pipeline as its own object and every caller wraps the
call in @(), the one shape that counts right for 0, 1 and n. These tests call it the way the script does.
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


def _source():
    return open(SCRIPT, encoding="utf-8").read()


def _function_text(name):
    m = re.search(r"function %s[ (].*?\n\}\n" % re.escape(name), _source(), re.S)
    assert m, "%s not found in the watchdog" % name
    return m.group(0)


def _stubs(count_of_fake_processes, age_hours, cpu, handles):
    """Get-CimInstance / Get-Process stubbed to `n` processes of the given age and counters
    (the defaults in the callers are the suspended signature)."""
    return f"""
$MinAgeSecondsToJudge = 240
$MaxAgeSecondsAlive = 10800
function Get-CimInstance {{
    @(1..{count_of_fake_processes} | Where-Object {{ {count_of_fake_processes} -gt 0 }}) | ForEach-Object {{
        [pscustomobject]@{{ ProcessId = 1000 + $_; ParentProcessId = 1; CreationDate = (Get-Date).AddHours(-{age_hours})
                            CommandLine = 'pythonw.exe C:\\x\\watch_sources.py --copy' }} }}
}}
function Get-Process {{ [pscustomobject]@{{ CPU = {cpu}; HandleCount = {handles} }} }}
{_function_text("Find-StuckWatchProcesses")}
"""


def _powershell(prog):
    out = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", prog],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def _run(count_of_fake_processes, age_hours=2, cpu="$null", handles=0, reasons=False):
    """Run the real function AS THE SCRIPT CALLS IT -- wrapped in @() -- against the stubs."""
    prog = _stubs(count_of_fake_processes, age_hours, cpu, handles) + f"""
$stuck = @(Find-StuckWatchProcesses)
"count=" + $stuck.Count + " gt0=" + ($stuck.Count -gt 0)
{'"reason=" + (@($stuck | ForEach-Object { $_.Reason }) -join "|")' if reasons else ''}
"""
    return _powershell(prog)


def test_a_single_suspended_process_is_found():
    assert _run(1) == "count=1 gt0=True"


def test_two_suspended_processes_are_still_found():
    assert _run(2) == "count=2 gt0=True"


def test_no_suspended_process_is_still_none():
    """The 2026-10-08 / 2026-10-12 case: an empty result must not count as one blank process."""
    assert _run(0) == "count=0 gt0=False"


def test_each_element_is_one_process_with_its_own_fields():
    """Not an array of processes inside a one-element array -- the shape behind the blank log line."""
    prog = _stubs(2, 2, "$null", 0) + """
$stuck = @(Find-StuckWatchProcesses)
"types=" + (@($stuck | ForEach-Object { $_.GetType().Name }) -join "|")
"pids=" + (@($stuck | ForEach-Object { $_.ProcessId }) -join "|")
"""
    assert _powershell(prog) == "types=PSCustomObject|PSCustomObject\npids=1001|1002"


def test_the_function_emits_objects_and_never_returns_a_collection():
    fn = _function_text("Find-StuckWatchProcesses")
    assert "return" not in fn, "returning a collection is what both counting bugs were made of"
    assert "+=" not in fn


def test_the_call_sites_wrap_the_result_in_an_array():
    src = _source()
    assert "$stuck = @(Find-StuckWatchProcesses)" in src
    assert "$old = @(Find-StuckWatchProcesses | Where-Object" in src


# ------------------------------------------------------------------ the log line
def test_the_stuck_process_log_line_carries_every_field():
    """2026-10-08 09:53:29  PID  (parent ): age s, CPU , handles  --  : six blanks. Run the real
    Kill-StuckRoots with Write-Log and Kill-ProcessTree stubbed and read the line it logs."""
    prog = _stubs(1, 2, "$null", 0) + f"""
$script:lines = @()
function Write-Log([string]$msg) {{ $script:lines += $msg }}
function Kill-ProcessTree([int]$rootPid) {{ $script:lines += "kill " + $rootPid }}
{_function_text("Kill-StuckRoots")}
$stuck = @(Find-StuckWatchProcesses)
Kill-StuckRoots $stuck
$script:lines -join "`n"
"""
    out = _powershell(prog)
    assert re.search(r"^\s*PID 1001 \(parent 1\): age \d+s, CPU 0, handles 0 -- created suspended$", out, re.M), out
    assert "kill 1001" in out


def test_a_stuck_parent_and_child_are_killed_from_the_root_only():
    prog = _stubs(2, 2, "$null", 0).replace("ParentProcessId = 1;", "ParentProcessId = $(if ($_ -eq 2) { 1001 } else { 1 });") + f"""
$script:lines = @()
function Write-Log([string]$msg) {{ $script:lines += $msg }}
function Kill-ProcessTree([int]$rootPid) {{ $script:lines += "kill " + $rootPid }}
{_function_text("Kill-StuckRoots")}
Kill-StuckRoots @(Find-StuckWatchProcesses)
(@($script:lines | Where-Object {{ $_ -like "kill *" }})) -join "|"
"""
    assert _powershell(prog) == "kill 1001"


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
    src = _source()
    head = src[src.index("if (Watch-RanToday) {"):]
    assert head.index('Where-Object { $_.Reason -like "older than*" }') < head.index("exit 0")


def test_the_overage_filter_sees_one_process_at_a_time():
    """`$_.Reason -like` on a whole array of processes passed the array as one object; each
    process must reach Where-Object on its own so the filter and the count are per process."""
    prog = _stubs(2, 2, "$null", 0).replace(
        "CreationDate = (Get-Date).AddHours(-2)",
        "CreationDate = (Get-Date).AddHours(-$(if ($_ -eq 2) { 4 } else { 2 }))").replace(
        "CPU = $null; HandleCount = 0", "CPU = 73.2; HandleCount = 161") + """
$old = @(Find-StuckWatchProcesses | Where-Object { $_.Reason -like "older than*" })
"count=" + $old.Count + " pid=" + $old[0].ProcessId
"""
    assert _powershell(prog) == "count=1 pid=1002"
