<#
.SYNOPSIS
    Register (or remove) the daily CSI-share check as a Windows scheduled task.

.DESCRIPTION
    Creates the task "RPE Source Watch", which runs

        <repo>\.venv\Scripts\pythonw.exe scripts\watch_sources.py --notify --copy --prune

    once a day at the given time, as the current user, only while that user is
    logged on. Logged-on matters twice over: the task needs this user's network
    credentials to read \\PADMIS105, and the Windows toast it raises has to land
    on a desktop someone can see.

    --copy copies roster clients' new files from the shares into Inputs/ on Drive
    (the ODD extract only from the newest month), so the builds and the performance
    dashboard see them without a manual step. --prune then deletes Drive inputs that a
    newer period (or weekly) of the same client and kind supersedes; the newest of
    each is always kept, and a file with no newer version is never touched.

    A missed run (laptop asleep, docked late) is started as soon as the machine
    is back, and the task waits for a network connection rather than failing on
    a machine that has not finished connecting.

    The venv interpreter is used, not the Windows Store python, for the same
    reason validation/qa_all.py insists on it: the Store python lacks the repo's
    dependencies and fails quietly.

.PARAMETER Time
    Daily start time, HH:mm (24h). Default 08:00.

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
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"
$TaskName = "RPE Source Watch"
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

$action = New-ScheduledTaskAction -Execute $Python `
    -Argument "`"$Script`" --notify --copy --prune" -WorkingDirectory $Repo
$trigger = New-ScheduledTaskTrigger -Daily -At $parsed
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$user = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force `
    -Description ("Daily check of \\PADMIS105 for new ODDD extracts, DCOs and workbooks, copied to Drive Inputs. " +
                  "Report: RPE_DATA_ROOT\Build Artifacts\source_watch_latest.md") | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
Write-Host ("Registered '{0}': daily at {1}, as {2}, state {3}" -f $TaskName, $Time, $user, $t.State)
Write-Host "  runs: $Python `"$Script`" --notify --copy --prune"
Write-Host "  run now:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  remove:   powershell -ExecutionPolicy Bypass -File scripts\register_watch_task.ps1 -Unregister"
