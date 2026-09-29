<#
Stage one client's files from CSM_Reporting\Inputs into a v5 checkout's 01-Data layout, so the
v5 deck can be built from the SAME source files Aaron's build reads, without v5's fetch step
(the watcher lands everything in Inputs now; v5's fetch is going away, James 2026-09-29).

    powershell -ExecutionPolicy Bypass -File scripts\bakeoff\stage_v5_inputs.ps1 -V5Root C:\Projects\v5 -Client 1441 -Period 2026-09 [-Root M:\CSM_Reporting]

Copies  <Root>\Inputs\ODDD\<Client>_ODDD.zip      -> <V5Root>\01-Data\ARS\<Period>\<Client>\
Expands <Root>\Inputs\Txn Files\<Client>\*.zip    -> <V5Root>\01-Data\Txn Files\<Client>\   (v5 reads loose .txt/.csv only)
Read-only on the share. Review tool only, never part of a build.
#>
param(
    [Parameter(Mandatory = $true)][string]$V5Root,
    [Parameter(Mandatory = $true)][string]$Client,
    [Parameter(Mandatory = $true)][string]$Period,
    [string]$Root = $env:RPE_DATA_ROOT
)

$ErrorActionPreference = "Stop"
if (-not $Root) { throw "Set -Root or `$env:RPE_DATA_ROOT (M:\CSM_Reporting)." }
if ($Period -notmatch '^\d{4}-\d{2}$') { throw "Period must be YYYY-MM for v5, e.g. 2026-09 (got '$Period')." }

$odd = Join-Path $Root ("Inputs\ODDD\{0}_ODDD.zip" -f $Client)
if (-not (Test-Path $odd)) { throw "No ODDD zip for $Client at $odd" }
$oddDest = Join-Path $V5Root ("01-Data\ARS\{0}\{1}" -f $Period, $Client)
New-Item -ItemType Directory -Force $oddDest | Out-Null
Copy-Item $odd $oddDest -Force
Write-Host ("ODD   {0} -> {1}" -f (Split-Path $odd -Leaf), $oddDest)

$txnSrc = Join-Path $Root ("Inputs\Txn Files\{0}" -f $Client)
$txnDest = Join-Path $V5Root ("01-Data\Txn Files\{0}" -f $Client)
if (Test-Path $txnSrc) {
    New-Item -ItemType Directory -Force $txnDest | Out-Null
    $n = 0
    Get-ChildItem $txnSrc -File | ForEach-Object {
        if ($_.Extension -ieq ".zip") { Expand-Archive $_.FullName -DestinationPath $txnDest -Force }
        else { Copy-Item $_.FullName $txnDest -Force }
        $n++
    }
    Write-Host ("TXN   {0} file(s) -> {1}" -f $n, $txnDest)
} else {
    Write-Host ("TXN   none for {0} (no folder at {1}); v5 will skip the transaction chapter" -f $Client, $txnSrc)
}
