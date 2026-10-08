<#
Release the ARS launcher to the CSM_Reporting share, so anyone can build an ARS deck without
Claude or a Python install (Aaron, 2026-09-15).

    powershell -ExecutionPolicy Bypass -File scripts\release_launcher.ps1 [-Root \\PADMIS105\Velocity_company\CSM_Reporting] [-Runtime]

What it writes under <Root>:
  Tools\RPE\        the code the launcher runs: build\, scripts\, validation\, templates\, fonts\,
                    clients.md, requirements.txt  (a copy of this checkout; re-run after any change,
                    including clients.md edits — the launcher reads the copy, not the repo)
  Tools\rpe-runtime.zip, Tools\rpe-runtime.txt
                    with -Runtime: this machine's Python plus the repo .venv's libraries, zipped,
                    and the stamp that tells each PC to unpack it again (scripts\launchers\runtime.cmd
                    unpacks to %LOCALAPPDATA%\RPE on first use). Needed only when the libraries change.
  Build ARS Deck.bat, ARS Deck User Guide.html   in <Root> itself
Each PC runs the code from a local copy, not from the share: scripts\launchers\runtime.cmd copies
Tools\RPE to %LOCALAPPDATA%\RPE\Code whenever RELEASE.txt changes, so a release reaches a PC the next
time its launcher starts. RELEASE.txt is the stamp, and is written last.
Copy-only: robocopy mirrors Tools\RPE (so a removed file does not linger and run), and never
touches Inputs, Outputs or Build Artifacts. Run the unit suite before releasing.

A release ships what is on origin/main and nothing else (Aaron, 2026-10-07). The script
refuses when the working tree has uncommitted changes or HEAD is not a commit on origin/main
(fetched first): on 2026-10-07 a release stamped "with uncommitted changes" shipped another
session's half-finished file, because robocopy mirrors the working tree. -Force releases
anyway and the stamp says so, for the day the rule has to bend; it should not be the habit.
#>
param(
    [string]$Root = $env:RPE_DATA_ROOT,
    [switch]$Runtime,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot

# ---------------------------------------------------------------- what is being released
$dirty = @(git -C $repo status --porcelain 2>$null | Where-Object { $_ })
$null = git -C $repo fetch origin main --quiet 2>$null
$fetched = $LASTEXITCODE -eq 0
$head = (git -C $repo rev-parse HEAD 2>$null)
$onMain = $false
if ($fetched) {
    $null = git -C $repo merge-base --is-ancestor $head origin/main 2>$null
    $onMain = $LASTEXITCODE -eq 0
}
$problems = @()
if ($dirty.Count) { $problems += "the working tree has $($dirty.Count) uncommitted change(s):`n    " + ($dirty -join "`n    ") }
if (-not $fetched) { $problems += "origin/main could not be fetched, so HEAD cannot be checked against it" }
elseif (-not $onMain) { $problems += "HEAD $((git -C $repo rev-parse --short HEAD)) is not on origin/main (commit and push first, or check out main)" }
if ($problems.Count) {
    $text = "Not released. A release ships origin/main and nothing else:`n  - " + ($problems -join "`n  - ")
    if (-not $Force) { throw "$text`nRe-run with -Force to release anyway; the stamp will say so." }
    Write-Warning "$text`n-Force given: releasing anyway."
}
if (-not $Root) {
    $envFile = Join-Path $repo '.env'
    if (Test-Path $envFile) {
        $line = Get-Content $envFile | Where-Object { $_ -match '^\s*RPE_DATA_ROOT\s*=' } | Select-Object -First 1
        if ($line) { $Root = ($line -split '=', 2)[1].Trim().Trim('"') }
    }
}
if (-not $Root -or -not (Test-Path $Root)) { throw "Share root not found: '$Root'. Pass -Root." }

$tools = Join-Path $Root 'Tools'
$code = Join-Path $tools 'RPE'
New-Item -ItemType Directory -Force $code | Out-Null

foreach ($d in 'build', 'scripts', 'validation', 'templates', 'fonts') {
    robocopy (Join-Path $repo $d) (Join-Path $code $d) /MIR /NFL /NDL /NJH /NJS /NP /R:2 /W:2 /XD __pycache__ .pytest_cache | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed for $d ($LASTEXITCODE)" }
}
foreach ($f in 'clients.md', 'requirements.txt', 'CHANGELOG.md') { Copy-Item (Join-Path $repo $f) (Join-Path $code $f) -Force }
$commit = (git -C $repo rev-parse --short HEAD) 2>$null
$stampNote = if ($problems.Count) { ' FORCED: ' + (($problems | ForEach-Object { ($_ -split "`n")[0] }) -join '; ') } else { ' (on origin/main, clean)' }
"released $(Get-Date -Format 'yyyy-MM-dd HH:mm') by $env:USERNAME from $repo at $commit$stampNote" |
    Set-Content -Encoding utf8 (Join-Path $code 'RELEASE.txt')

# The runtime ships as ONE zip that runtime.cmd unpacks to %LOCALAPPDATA%\RPE on each PC. A
# folder of ~20,000 small files crawled onto the share at a few MB a minute, and a Python run
# from the share would pay that same SMB cost on every import of every build.
$testPy = Join-Path $env:LOCALAPPDATA 'RPE\Python\python.exe'
if ($Runtime) {
    $venvCfg = Get-Content (Join-Path $repo '.venv\pyvenv.cfg')
    $base = (($venvCfg | Where-Object { $_ -match '^home\s*=' }) -split '=', 2)[1].Trim()
    $stage = Join-Path $env:TEMP "rpe-runtime-$PID"
    $py = Join-Path $stage 'Python'
    robocopy $base $py /E /NFL /NDL /NJH /NJS /NP /R:2 /W:2 /XD __pycache__ | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed for the Python runtime ($LASTEXITCODE)" }
    robocopy (Join-Path $repo '.venv\Lib\site-packages') (Join-Path $py 'Lib\site-packages') /E /NFL /NDL /NJH /NJS /NP /R:2 /W:2 /XD __pycache__ | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed for site-packages ($LASTEXITCODE)" }
    $zip = Join-Path $stage 'rpe-runtime.zip'
    Push-Location $stage
    try { tar -a -c -f $zip Python; if ($LASTEXITCODE) { throw "tar failed ($LASTEXITCODE)" } } finally { Pop-Location }
    Copy-Item $zip (Join-Path $tools 'rpe-runtime.part') -Force
    Move-Item (Join-Path $tools 'rpe-runtime.part') (Join-Path $tools 'rpe-runtime.zip') -Force
    # The stamp is what tells each PC to unpack again, so it changes with every runtime release.
    "python $((& (Join-Path $py 'python.exe') -c 'import sys; print(sys.version.split()[0])')) released $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') by $env:USERNAME, $((Get-Item $zip).Length) bytes" |
        Set-Content -Encoding ascii (Join-Path $tools 'rpe-runtime.txt')
    $testPy = Join-Path $py 'python.exe'
}
if (-not (Test-Path $testPy)) { $testPy = Join-Path $repo '.venv\Scripts\python.exe' }

if (-not (Test-Path $testPy)) { throw "No Python to test the release with: $testPy" }

foreach ($b in Get-ChildItem (Join-Path $repo 'scripts\launchers\*') -Include *.bat, *.html) {
    Copy-Item $b.FullName (Join-Path $Root $b.Name) -Force
}
& $testPy -c "import sys; sys.path.insert(0, r'$code\scripts'); sys.path.insert(0, r'$code\build'); import ars_launcher, build_month, pptx, matplotlib, pandas; print('launcher release OK:', sys.version.split()[0], sys.executable)"
$testOk = $LASTEXITCODE -eq 0
if ($Runtime) { Remove-Item $stage -Recurse -Force }   # this run's own temp staging copy, ~600 MB
if (-not $testOk) { throw 'The released code did not import. Fix and release again.' }
Get-Content (Join-Path $code 'RELEASE.txt')
if (Test-Path (Join-Path $tools 'rpe-runtime.txt')) { Get-Content (Join-Path $tools 'rpe-runtime.txt') } else { 'NO RUNTIME on the share yet: re-run with -Runtime' }
