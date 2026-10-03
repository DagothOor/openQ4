# Watches one openQ4 bake run (started by the bake_*.bat files).
# 1) The game waits on "PRESS ANY KEY TO CONTINUE": press Space in the game window until
#    the bake log shows the bake has started. Keys go only to the game window.
# 2) If the log shows a FATAL error (for example "Out of memory"), the game hangs on an
#    error message: write the map name to bake_failed.txt and close the game, so the
#    .bat moves on to the next map.
param([string]$Map)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Fg {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
}
"@
$exe = 'openQ4-client_x64'
$failedList = Join-Path $PSScriptRoot 'bake_failed.txt'
$ws = New-Object -ComObject WScript.Shell

function Get-BakeLog {
    Get-ChildItem -Path "$env:LOCALAPPDATA\openQ4", (Join-Path $PSScriptRoot 'baseoq4') -Recurse -Filter "bake_$Map.log" -ErrorAction SilentlyContinue | Select-Object -First 1
}

# Wait for the game process to appear (up to 2 minutes).
$deadline = (Get-Date).AddMinutes(2)
while (-not (Get-Process -Name $exe -ErrorAction SilentlyContinue)) {
    if ((Get-Date) -gt $deadline) { exit }
    Start-Sleep -Seconds 1
}

$started = $false
$keyDeadline = (Get-Date).AddMinutes(5)
while (Get-Process -Name $exe -ErrorAction SilentlyContinue) {
    $log = Get-BakeLog
    if ($log) {
        $fatal = Select-String -LiteralPath $log.FullName -Pattern 'FATAL:|Out of memory' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($fatal) {
            Add-Content -LiteralPath $failedList -Value ("game/{0}   {1}" -f $Map, $fatal.Line.Trim()) -Encoding ASCII
            Start-Sleep -Seconds 2
            Stop-Process -Name $exe -Force -ErrorAction SilentlyContinue
            exit
        }
        if (-not $started -and (Select-String -LiteralPath $log.FullName -Pattern 'bakeLightGrids' -Quiet -ErrorAction SilentlyContinue)) {
            $started = $true
        }
    }
    if (-not $started -and (Get-Date) -lt $keyDeadline) {
        $p = Get-Process -Name $exe -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
        if ($p) {
            [void]$ws.AppActivate($p.Id)
            Start-Sleep -Milliseconds 400
            $fgPid = 0; [void][Fg]::GetWindowThreadProcessId([Fg]::GetForegroundWindow(), [ref]$fgPid)
            if ($fgPid -eq $p.Id) { $ws.SendKeys(' ') }
        }
    }
    Start-Sleep -Seconds 3
}
