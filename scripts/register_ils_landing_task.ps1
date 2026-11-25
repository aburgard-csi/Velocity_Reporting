<#
.SYNOPSIS
    Register (or remove) the daily ILS analysis landing as its own Windows scheduled task.

.DESCRIPTION
    Creates the task "RPE ILS Analysis Landing", which runs

        <repo>\.venv\Scripts\pythonw.exe scripts\land_ils_analysis.py --apply

    once a day at the given time (default 08:20, after the 08:00 source watch, whose
    --ils-analysis step lists what is new), as the current user, only while that user is
    logged on: the analysis share (\\ilsdbsrvr2) and \\PADMIS105 both need this user's
    network credentials.

    It copies the newest data pull of each client on the ILS analysts' review schedule into
    Inputs\ILS Analysis, zipped (Aaron, 2026-11-24). It is its own task, not a step of the
    source watch, because a pull runs to several GB and the watch has a 50-minute limit.
    land_ils_analysis.py stops itself between files at 45 minutes and the next day's run
    picks up where it stopped; the 50-minute limit here is the backstop.

    Off the VPN it reports the sources unreachable and exits 2, writing nothing. The run's
    report is in RPE_DATA_ROOT\Build Artifacts\ils_analysis\landing_latest.md (pythonw has no
    console), every landing in landings.json beside it.

    Registering the task is Aaron's decision; nothing runs this script for him.

.PARAMETER Time
    Daily start time, HH:mm (24h). Default 08:20.

.PARAMETER Repo
    Which checkout the task should run. Defaults to the one this script lives in, which is
    wrong in a worktree: a worktree has no .venv and no .env, and the task needs both.

.PARAMETER Unregister
    Remove the task instead of creating it.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\register_ils_landing_task.ps1
    powershell -ExecutionPolicy Bypass -File scripts\register_ils_landing_task.ps1 -Time 12:30
    powershell -ExecutionPolicy Bypass -File scripts\register_ils_landing_task.ps1 -Unregister
#>
[CmdletBinding()]
param(
    [string]$Time = "08:20",
    [string]$Repo = "",
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"
$TaskName = "RPE ILS Analysis Landing"
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

$Python = Join-Path $Repo ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $Python)) { $Python = Join-Path $Repo ".venv\Scripts\python.exe" }
if (-not (Test-Path $Python)) {
    throw "No .venv under $Repo. Create it (python -m venv .venv; pip install -r requirements.txt) first."
}
$Script = Join-Path $Repo "scripts\land_ils_analysis.py"
if (-not (Test-Path $Script)) { throw "Missing $Script (is this checkout up to date?)" }

$parsed = [datetime]::ParseExact($Time, "HH:mm", $null)
$TaskArgs = "`"$Script`" --apply"
$action = New-ScheduledTaskAction -Execute $Python -Argument $TaskArgs -WorkingDirectory $Repo
$trigger = New-ScheduledTaskTrigger -Daily -At $parsed
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 50) -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$user = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force `
    -Description ("Daily copy of the newest ILS analysis data pull of each client on the analysts' review schedule " +
                  "into Inputs\ILS Analysis, zipped. Report: RPE_DATA_ROOT\Build Artifacts\ils_analysis\landing_latest.md") | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
Write-Host ("Registered '{0}': daily at {1}, as {2}, state {3}" -f $TaskName, $Time, $user, $t.State)
Write-Host "  runs: $Python $TaskArgs"
$Console = Join-Path $Repo ".venv\Scripts\python.exe"
Write-Host "  plan only:  $Console `"$Script`""
Write-Host "  run now:    Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  remove:     powershell -ExecutionPolicy Bypass -File scripts\register_ils_landing_task.ps1 -Unregister"
