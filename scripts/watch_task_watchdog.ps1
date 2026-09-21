<#
.SYNOPSIS
    Detect and recover a "RPE Source Watch" run stuck in Windows' own process
    creation, not in our code.

.DESCRIPTION
    Three mornings running (2026-09-09, -10, -11) the 08:00 unattended trigger
    of "RPE Source Watch" produced NOTHING -- no log entry, no report, killed by
    Task Scheduler at the 30-minute ExecutionTimeLimit. Every run started BY HAND
    on an awake machine, including immediately after diagnosing this, finished
    normally in 1-3 minutes. The failure is specific to the unattended, cold
    (Modern Standby wake) trigger.

    The processes are not hung in our code -- they are CREATED SUSPENDED and never
    execute a single instruction: zero TotalProcessorTime, 0 handles, ~2.5MB
    working set, one thread parked in Wait/Suspended. A process actually blocked
    in SMB I/O or Outlook COM has loaded modules and nonzero CPU; these have
    neither. A manual retry on 2026-09-11 also surfaced a second, unrelated
    oddity worth recording here rather than mistaking for the same bug: every
    python launch in this pipeline (watch_sources.py, and the mail_sources.py
    subprocess it spawns) appears TWICE in the process list, the second a direct
    child of the first with an identical command line and creation timestamp --
    consistent with an endpoint-protection agent (Symantec Endpoint Protection is
    installed on this machine) intercepting process creation and relaunching it
    under its own supervision. That relaunch is presumably where a run can get
    stuck: if the agent's own hook can't complete (e.g. a cloud reputation lookup
    with no network yet available right after a Modern Standby wake), the
    relaunched child sits suspended forever and nothing in Python ever runs to
    time itself out.

    Because the stall is outside the process that would need to detect it, the
    fix cannot be a code-level timeout (see mail_sources.py / watch_sources.py
    for the one that already exists for a DIFFERENT failure mode -- an Outlook COM
    call that blocks with live CPU and loaded modules -- which this is not). The
    fix has to watch from OUTSIDE: a second scheduled task, running a few minutes
    after the main trigger, that recognises the suspended signature, kills it,
    and retries.

.PARAMETER MainTaskName
    The task to watch. Default "RPE Source Watch".

.PARAMETER FreshWithinMinutes
    How old the report can be and still count as "today's run happened".
    Default 180 (3 hours) -- generous, because the point is only to tell "did
    SOMETHING run recently" from "nothing happened since before this trigger".

.PARAMETER MinAgeSecondsToJudge
    A process younger than this is not yet judged stuck -- a healthy run is
    still allowed its normal 1-3 minutes. Default 240 (4 minutes).

.PARAMETER MaxAttempts
    Total tries (the original firing counts as attempt 1). Default 3, so at
    most 2 kill-and-retry cycles before giving up and logging for a human.

.PARAMETER WaitBetweenAttemptsSeconds
    How long to wait, after retrying, before checking whether the retry itself
    is healthy or also stuck. Default 200 (a healthy run takes 1-3 minutes; this
    gives room without holding the watchdog task open for the full 30 minutes
    the main task is allowed).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\watch_task_watchdog.ps1
    (scheduled by register_watch_task.ps1 -Watchdog; also safe to run by hand --
    a healthy morning is a silent no-op)
#>
[CmdletBinding()]
param(
    [string]$MainTaskName = "RPE Source Watch",
    [int]$FreshWithinMinutes = 120,
    [int]$MinAgeSecondsToJudge = 240,
    [int]$MaxAttempts = 3,
    [int]$WaitBetweenAttemptsSeconds = 200
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

# ---------------------------------------------------------------- data root
# Same resolution rule as rpe_env.py: RPE_DATA_ROOT env var, else .env, so the
# watchdog logs alongside the same source_watch_latest.md the task itself
# writes rather than guessing a path. PowerShell reads .env directly because
# invoking Python just to find a path is one more process that this problem
# could theoretically befall.
function Get-DataRoot {
    if ($env:RPE_DATA_ROOT) { return $env:RPE_DATA_ROOT }
    $envFile = Join-Path $Repo ".env"
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^\s*RPE_DATA_ROOT\s*=\s*(.+?)\s*$') { return $Matches[1] }
        }
    }
    throw "RPE_DATA_ROOT not found in the environment or $envFile"
}

$DataRoot = Get-DataRoot
$BuildArtifacts = Join-Path $DataRoot "Build Artifacts"
if (-not (Test-Path $BuildArtifacts)) { New-Item -ItemType Directory -Path $BuildArtifacts -Force | Out-Null }
$ReportPath = Join-Path $BuildArtifacts "source_watch_latest.md"
$WatchdogLog = Join-Path $BuildArtifacts "source_watch_watchdog.log"

function Write-Log([string]$msg) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Host $line
    Add-Content -Path $WatchdogLog -Value $line
}

function Report-IsFresh {
    if (-not (Test-Path $ReportPath)) { return $false }
    $age = (Get-Date) - (Get-Item $ReportPath).LastWriteTime
    return $age.TotalMinutes -le $FreshWithinMinutes
}

# What the watchdog actually wants to know (Aaron, 2026-09-21): has a run reached the shares
# TODAY? The report's own freshness cannot say - on 2026-09-21 the 08:00 run wrote its report at
# 08:14 and the 09:01 fire was then created suspended, so at 09:06 the report was 52 minutes old
# and perfectly fresh while that morning's later copy was never going to happen. watch_sources
# --check-today reads the run record the runs themselves stamp. A checkout that does not carry
# the flag (argparse exits 2) falls back to the report.
function Watch-RanToday {
    $py = Join-Path $Repo ".venv\Scripts\python.exe"
    $script = Join-Path $Repo "scripts\watch_sources.py"
    if (-not (Test-Path $py) -or -not (Test-Path $script)) { return (Report-IsFresh) }
    $null = & $py $script --check-today 2>&1
    switch ($LASTEXITCODE) {
        0 { return $true }
        1 { return $false }
        default { return (Report-IsFresh) }      # flag not supported in this checkout
    }
}

# ---------------------------------------------------------------- signature
# The one fact that distinguishes "created suspended, will NEVER run" from
# "running slowly" or "genuinely blocked in I/O with modules loaded": zero
# handles and effectively zero CPU time, on a process old enough that a
# healthy run would already be well underway or finished. A process still
# under $MinAgeSecondsToJudge old is given the benefit of the doubt even if
# its counters look thin, because every process starts at 0/0 for an instant.
function Find-StuckWatchProcesses {
    $procs = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*watch_sources.py*" }
    $stuck = @()
    foreach ($p in $procs) {
        $ageSec = ((Get-Date) - $p.CreationDate).TotalSeconds
        if ($ageSec -lt $MinAgeSecondsToJudge) { continue }
        try {
            $live = Get-Process -Id $p.ProcessId -ErrorAction Stop
            $cpu = if ($live.CPU) { $live.CPU } else { 0 }
            $handles = $live.HandleCount
        } catch {
            continue   # already gone between the CIM query and now
        }
        if ($cpu -lt 0.05 -and $handles -lt 10) {
            $stuck += [pscustomobject]@{
                ProcessId = $p.ProcessId; ParentProcessId = $p.ParentProcessId
                AgeSeconds = [int]$ageSec; CPU = $cpu; Handles = $handles
                CommandLine = $p.CommandLine
            }
        }
    }
    return $stuck
}

function Kill-ProcessTree([int]$rootPid) {
    # Children first: killing a parent whose child is itself suspended can
    # leave the child orphaned and still consuming the slot this run needs.
    $all = Get-CimInstance Win32_Process
    $children = $all | Where-Object { $_.ParentProcessId -eq $rootPid }
    foreach ($c in $children) { Kill-ProcessTree -rootPid $c.ProcessId }
    try { Stop-Process -Id $rootPid -Force -ErrorAction Stop; Write-Log "  killed PID $rootPid" }
    catch { Write-Log "  PID $rootPid already gone" }
}

# ---------------------------------------------------------------- main
if (Watch-RanToday) {
    # The common case, every healthy morning: say nothing, touch nothing.
    exit 0
}

Write-Log "=== watchdog: no run has reached the shares today ==="
$attempt = 1
while ($attempt -le $MaxAttempts) {
    $stuck = Find-StuckWatchProcesses
    if ($stuck.Count -gt 0) {
        Write-Log ("attempt {0}: found {1} suspended process(es) for '{2}':" -f $attempt, $stuck.Count, $MainTaskName)
        foreach ($s in $stuck) {
            Write-Log ("  PID {0} (parent {1}): age {2}s, CPU {3}, handles {4}" -f `
                $s.ProcessId, $s.ParentProcessId, $s.AgeSeconds, $s.CPU, $s.Handles)
        }
        # Kill from the roots -- a process in this list with no parent ALSO in
        # this list is a root; killing it recursively takes its children too.
        $pidSet = $stuck.ProcessId
        $roots = $stuck | Where-Object { $pidSet -notcontains $_.ParentProcessId }
        foreach ($r in $roots) { Kill-ProcessTree -rootPid $r.ProcessId }
        Write-Log "attempt ${attempt}: retrying '$MainTaskName' now"
        Start-ScheduledTask -TaskName $MainTaskName
    } elseif ($attempt -eq 1) {
        # Stale report, no stuck process, and the task's own history says it
        # never fired at all today -- genuinely unusual; log it and get out
        # rather than guessing at a fix for a failure mode nobody has seen yet.
        $info = Get-ScheduledTaskInfo -TaskName $MainTaskName
        $resultHex = "0x{0:x}" -f $info.LastTaskResult
        $msg = "no suspended process found. Task last ran " + $info.LastRunTime + `
            ", result " + $info.LastTaskResult + " (" + $resultHex + "). " + `
            "Nothing to kill and retry -- needs a human look."
        Write-Log $msg
        exit 1
    } else {
        # A retry we started ourselves neither finished nor is visibly stuck --
        # give it a little longer before calling this attempt a loss.
        Write-Log "attempt ${attempt}: no stuck process found; the retry may still be finishing"
    }

    Start-Sleep -Seconds $WaitBetweenAttemptsSeconds
    if (Watch-RanToday) {
        Write-Log "attempt ${attempt}: recovered -- a run reached the shares"
        exit 0
    }
    $attempt++
}

Write-Log ("gave up after {0} attempts -- no run has reached the shares today. Manual intervention needed." -f $MaxAttempts)
exit 1
