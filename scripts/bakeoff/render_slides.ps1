<#
Export every slide of a .pptx to PNG, one file per slide, using the PowerPoint that is already
on this PC (COM). Nothing to install. Review tool only: never part of a build or a delivery
(CLAUDE.md: no render step in the pipeline).

    powershell -ExecutionPolicy Bypass -File scripts\bakeoff\render_slides.ps1 -Deck <file.pptx> -Out <folder> [-Width 1600]

Writes <folder>\slide-01.png, slide-02.png, ... at the deck's own aspect ratio.
#>
param(
    [Parameter(Mandatory = $true)][string]$Deck,
    [Parameter(Mandatory = $true)][string]$Out,
    [int]$Width = 1600
)

$ErrorActionPreference = "Stop"
$Deck = (Resolve-Path $Deck).Path
New-Item -ItemType Directory -Force $Out | Out-Null
$Out = (Resolve-Path $Out).Path

# MsoTriState without the interop assembly: msoTrue = -1, msoFalse = 0.
$msoTrue = -1
$msoFalse = 0

$app = New-Object -ComObject PowerPoint.Application
try {
    # Open(FileName, ReadOnly, Untitled, WithWindow)
    $pres = $app.Presentations.Open($Deck, $msoTrue, $msoFalse, $msoFalse)
    try {
        $ratio = $pres.PageSetup.SlideHeight / $pres.PageSetup.SlideWidth
        $height = [int][math]::Round($Width * $ratio)
        $n = $pres.Slides.Count
        for ($i = 1; $i -le $n; $i++) {
            $png = Join-Path $Out ("slide-{0:D2}.png" -f $i)
            $pres.Slides.Item($i).Export($png, "PNG", $Width, $height)
        }
        Write-Host ("{0} slides -> {1}" -f $n, $Out)
    }
    finally {
        $pres.Close()
    }
}
finally {
    $app.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)
}
