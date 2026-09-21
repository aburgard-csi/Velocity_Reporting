<#
.SYNOPSIS
    Register (or remove) the "RPE Source Watch Watchdog" task -- outside
    detection and recovery for the daily source watch, since the failure it
    guards against cannot be caught from inside the watched process.

.DESCRIPTION
    Creates the task "RPE Source Watch Watchdog", which runs

        <repo>\.venv\Scripts\powershell.exe -ExecutionPolicy Bypass -File
            scripts\watch_task_watchdog.ps1

    once a day, a fixed offset after "RPE Source Watch" fires (default: the
    main task's time plus 15 minutes). See watch_task_watchdog.ps1's own header
    for the full diagnosis; in short: three mornings running the unattended
    08:00 trigger of the main task was created SUSPENDED by something outside
    our code (0 handles, 0 CPU, never executes an instruction) and Task
    Scheduler killed it 30 minutes later having done nothing. Every run started
    by hand, on an awake machine, finished normally in 1-3 minutes -- so the
    failure is specific to the unattended, cold-wake trigger, and nothing a
    timeout INSIDE watch_sources.py can detect, because the process never gets
    far enough to run any of our code, timeout included.

    The watchdog runs as its own scheduled task rather than as a background
    thread of the main one for the same reason: if whatever intercepts process
    creation can suspend the main task's process, a thread living inside that
    same process is exactly as stuck. A second, independently-triggered task is
    the only vantage point actually outside the failure.

    What it does, each time it fires (see watch_task_watchdog.ps1 for the
    detail): if today's report is already fresh, it exits silently -- most
    mornings this is a no-op. Otherwise it looks for a "RPE Source Watch"
    process matching the suspended signature (near-zero CPU, near-zero handle
    count, old enough that a healthy run would have finished), kills it, and
    retries the main task -- up to two kill-and-retry cycles before giving up
    and logging for a human. Every attempt, killed or not, is appended to
    Build Artifacts\source_watch_watchdog.log.

    Uses Windows PowerShell (powershell.exe), not pwsh, because that is what
    register_watch_task.ps1's own settings assume is on PATH for this user.

.PARAMETER Time
    Daily start time, HH:mm (24h). Default: 08:45 -- 45 minutes after the main
    task's own default of 08:00. If the main task runs at a different time,
    pass that time here plus your own margin; this script does not read the
    other task's trigger.

.PARAMETER Unregister
    Remove the task instead of creating it.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\register_watchdog_task.ps1
    powershell -ExecutionPolicy Bypass -File scripts\register_watchdog_task.ps1 -Time 07:45
    powershell -ExecutionPolicy Bypass -File scripts\register_watchdog_task.ps1 -Unregister
#>
[CmdletBinding()]
param(
    [string]$Time = "08:45",
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"
$TaskName = "RPE Source Watch Watchdog"
$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if ($Unregister) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed scheduled task '$TaskName'."
    } else {
        Write-Host "No scheduled task named '$TaskName'."
    }
    exit 0
}

$Script = Join-Path $Repo "scripts\watch_task_watchdog.ps1"
if (-not (Test-Path $Script)) { throw "Missing $Script" }

# Windows PowerShell, the same shell family register_watch_task.ps1 targets --
# not the venv's Python interpreter, since this task's job is to notice when
# a Python process has failed to start at all.
$PowerShellExe = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
if (-not (Test-Path $PowerShellExe)) { throw "Windows PowerShell not found at $PowerShellExe" }

$parsed = [datetime]::ParseExact($Time, "HH:mm", $null)

$action = New-ScheduledTaskAction -Execute $PowerShellExe `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`"" -WorkingDirectory $Repo
$trigger = New-ScheduledTaskTrigger -Daily -At $parsed
# 20 minutes is generous: the watchdog itself waits up to
# (MaxAttempts-1) * WaitBetweenAttemptsSeconds internally (default ~6-7 minutes
# for two retries) before giving up, and this ceiling is only a backstop against
# the watchdog itself somehow hanging.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$user = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force `
    -Description ("Detects a 'RPE Source Watch' run that Windows created suspended and never executed, " +
                  "kills it, and retries. Log: RPE_DATA_ROOT\Build Artifacts\source_watch_watchdog.log") | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
Write-Host ("Registered '{0}': daily at {1}, as {2}, state {3}" -f $TaskName, $Time, $user, $t.State)
Write-Host "  runs: $PowerShellExe -NoProfile -ExecutionPolicy Bypass -File `"$Script`""
Write-Host "  run now:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  remove:   powershell -ExecutionPolicy Bypass -File scripts\register_watchdog_task.ps1 -Unregister"
