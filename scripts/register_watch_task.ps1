<#
.SYNOPSIS
    Register (or remove) the daily CSI-share check as a Windows scheduled task.

.DESCRIPTION
    Creates the task "RPE Source Watch", which runs

        <repo>\.venv\Scripts\pythonw.exe scripts\watch_sources.py `
            --notify --copy --prune --mail --once-daily

    once a day at the given time, as the current user, only while that user is
    logged on. Logged-on matters twice over: the task needs this user's network
    credentials to read \\PADMIS105, and the Windows toast it raises has to land
    on a desktop someone can see.

    --copy copies roster clients' new files from the shares into Inputs/
    (the ODD extract only from the newest month), so the builds and the performance
    dashboard see them without a manual step. --prune then deletes inputs that a
    newer period (or weekly) of the same client and kind supersedes; the newest of
    each is always kept, and a file with no newer version is never touched.

    --mail also takes the MRPC / CashPlease reports and the ICS workbooks from
    Outlook, which never land on a share.

    A missed run (laptop asleep, docked late) is started as soon as the machine
    is back, and the task waits for a network connection rather than failing on
    a machine that has not finished connecting.

    THE FIRE IS RETRIED, and that is not belt-and-braces. On 2026-09-09, -10 and
    -11 the 08:00 process was created by the scheduler and left SUSPENDED - zero
    CPU, no modules loaded, the interpreter never initialized - then killed at
    the execution limit. Three mornings produced no check and no trace. Only the
    unattended time-triggered fires did this; every run started by hand on an
    awake machine finished in two to three minutes. So the trigger repeats
    hourly through the morning, on the reasoning that a later fire meets a
    machine that is properly awake, and -WakeToRun asks for one at the start.
    The repeats are cheap: --once-daily makes a fire that follows a successful
    run exit immediately. "Successful" there means it reached the shares, so a
    fire that found the VPN down does not stop the later ones going to look.

    The execution limit is 20 minutes, not 30: a stuck fire has to be cleared
    before the next one is due, or MultipleInstances IgnoreNew would drop it. A
    healthy run takes two to three minutes, and the mail step inside it has a
    ten-minute timeout of its own.

    Whether any of this actually happened is a separate question, and the task
    cannot answer it - a fire that never runs writes nothing. Ask the watch
    itself, from anywhere:

        <repo>\.venv\Scripts\python.exe scripts\watch_sources.py --check-stale

    The venv interpreter is used, not the Windows Store python, for the same
    reason validation/qa_all.py insists on it: the Store python lacks the repo's
    dependencies and fails quietly.

.PARAMETER Time
    Daily start time, HH:mm (24h). Default 08:00.

.PARAMETER Repo
    Which checkout the task should run. Defaults to the one this script lives
    in, which is wrong in a worktree: a worktree has no .venv and no .env, and
    the task needs both. Point it at the checkout that does.

.PARAMETER RetryHours
    How long to keep re-firing hourly after Time. Default 4 (08:00 to 12:00).
    0 registers a single daily fire with no retries.

.PARAMETER Unregister
    Remove the task instead of creating it.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\register_watch_task.ps1
    powershell -ExecutionPolicy Bypass -File scripts\register_watch_task.ps1 -Time 07:30
    powershell -ExecutionPolicy Bypass -File scripts\register_watch_task.ps1 -Unregister
#>
[CmdletBinding()]
param(
    [string]$Time = "08:00",
    [string]$Repo = "",
    [int]$RetryHours = 4,
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"
$TaskName = "RPE Source Watch"
if (-not $Repo) { $Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path) }
if (-not (Test-Path $Repo)) { throw "No such checkout: $Repo" }

if ($Unregister) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed scheduled task '$TaskName'."
    } else {
        Write-Host "No scheduled task named '$TaskName'."
    }
    exit 0
}

# pythonw: no console window flashes up on the desktop each morning. Output goes
# to Build Artifacts\source_watch.log either way, so nothing is lost by it.
$Python = Join-Path $Repo ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $Python)) { $Python = Join-Path $Repo ".venv\Scripts\python.exe" }
if (-not (Test-Path $Python)) {
    throw "No .venv under $Repo. Create it (python -m venv .venv; pip install -r requirements.txt) first."
}
$Script = Join-Path $Repo "scripts\watch_sources.py"
if (-not (Test-Path $Script)) { throw "Missing $Script" }

$parsed = [datetime]::ParseExact($Time, "HH:mm", $null)

$TaskArgs = "`"$Script`" --notify --copy --prune --mail"
# Only pass --once-daily if the code being registered actually knows it. This
# script is routinely newer than the checkout it points at - an unmerged branch,
# a worktree, a -Repo somewhere else - and an argument argparse does not
# recognise would make every fire exit 2 without checking anything. The retries
# still work without it; they just do the full scan each time.
if (Select-String -Path $Script -Pattern '--once-daily' -Quiet -SimpleMatch) {
    $TaskArgs += " --once-daily"
} else {
    Write-Warning ("{0} has no --once-daily; registering without it. Each retry " -f $Script)
    Write-Warning "         will do a full scan instead of exiting early."
}
$action = New-ScheduledTaskAction -Execute $Python `
    -Argument $TaskArgs -WorkingDirectory $Repo

$trigger = New-ScheduledTaskTrigger -Daily -At $parsed
if ($RetryHours -gt 0) {
    # A daily trigger carries no repetition of its own; borrow one from a
    # throwaway -Once trigger. Why it repeats at all is in .DESCRIPTION.
    $trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $parsed `
        -RepetitionInterval (New-TimeSpan -Hours 1) `
        -RepetitionDuration (New-TimeSpan -Hours $RetryHours)).Repetition
}

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun
$user = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force `
    -Description ("Daily check of \\PADMIS105 for new ODDD extracts, DCOs and workbooks, copied into Inputs. " +
                  "Report: RPE_DATA_ROOT\Build Artifacts\source_watch_latest.md") | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
Write-Host ("Registered '{0}': daily at {1}, as {2}, state {3}" -f $TaskName, $Time, $user, $t.State)
if ($RetryHours -gt 0) {
    Write-Host ("  retries: hourly for {0} h after {1}; --once-daily makes a fire" -f $RetryHours, $Time)
    Write-Host "           that follows a successful run exit immediately"
} else {
    Write-Host "  retries: none (-RetryHours 0)"
}
Write-Host "  runs: $Python $TaskArgs"
# python.exe, not pythonw: --check-stale exists to print, and pythonw has no
# stdout to print to.
$Console = Join-Path $Repo ".venv\Scripts\python.exe"
Write-Host "  did it run?  $Console `"$Script`" --check-stale"
Write-Host "  run now:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  remove:   powershell -ExecutionPolicy Bypass -File scripts\register_watch_task.ps1 -Unregister"
