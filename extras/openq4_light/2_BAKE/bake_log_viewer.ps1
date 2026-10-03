# Shows the bake progress from the openQ4 log files (the game window freezes while baking).
$host.UI.RawUI.WindowTitle = "openQ4 bake log"
Write-Host "Waiting for the bake log..."
$cur = $null; $pos = 0
while ($true) {
    $f = Get-ChildItem -Path "$env:LOCALAPPDATA\openQ4", (Join-Path $PSScriptRoot "baseoq4") -Recurse -Filter 'bake_*.log' -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($f) {
        if ($f.FullName -ne $cur) { $cur = $f.FullName; $pos = 0; Write-Host ""; Write-Host ("==== " + $f.FullName) }
        $lines = @(Get-Content -LiteralPath $cur -ErrorAction SilentlyContinue)
        if ($lines.Count -gt $pos) {
            $lines[$pos..($lines.Count - 1)] |
                Where-Object { $_ -match 'bakeLightGrids|FATAL|Out of memory|skipping' } |
                ForEach-Object { Write-Host $_ }
            $pos = $lines.Count
        }
    }
    Start-Sleep -Seconds 3
}
