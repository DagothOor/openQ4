@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "%~dp0openQ4-client_x64.exe" (
  echo.
  echo  Не найден openQ4-client_x64.exe рядом с этим файлом.
  echo  openQ4-client_x64.exe was not found next to this file.
  echo  Скопируйте все файлы из папки 2_BAKE в папку игры, где лежит openQ4-client_x64.exe.
  echo  Copy every file from 2_BAKE into the game folder that contains openQ4-client_x64.exe.
  echo.
  pause
  exit /b 1
)
rem Back up the game config once: the bake launches the game windowed, and the game
rem would otherwise save that into your settings. Restored at the end.
powershell -NoProfile -Command "Get-ChildItem -Path $env:LOCALAPPDATA\openQ4, '%~dp0baseoq4' -Recurse -Filter openQ4Config.cfg -ErrorAction SilentlyContinue | ForEach-Object { $b = $_.FullName + '.before_bake'; if (-not (Test-Path -LiteralPath $b)) { Copy-Item -LiteralPath $_.FullName -Destination $b } }"
powershell -NoProfile -Command "Get-ChildItem -Path $env:LOCALAPPDATA\openQ4, '%~dp0baseoq4' -Recurse -Filter 'bake_*.log' -ErrorAction SilentlyContinue | Remove-Item -ErrorAction SilentlyContinue"
del /q "%~dp0bake_failed.txt" 2>nul
start "openQ4 bake log" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bake_log_viewer.ps1"
rem Full-quality bake of the whole campaign (3 bounces). Takes many hours: leave it overnight.
rem Maps that are already baked with these settings are skipped, so it can be restarted any time.
echo.
echo  Игра запустится на экране PRESS ANY KEY. Клавиша нажимается автоматически;
echo  если заставка висит дольше 15 секунд - щёлкните по окну игры и нажмите любую клавишу.
echo  The game starts on the PRESS ANY KEY screen. The key is pressed automatically;
echo  if it stays there longer than 15 seconds, click the game window and press any key.
echo.
copy /y "%~dp0zzz_bake_helper.pk4" "%~dp0baseoq4\" >nul
set MAPS=airdefense1 hangar1 hangar2 mcc_landing mcc_1 convoy1 building_b convoy2 convoy2b hub1 hub2 medlabs walker dispersal recomp putra waste mcc_2 storage1 storage2 tram1 tram1b process1 process2 network1 network2 core1 core2
for %%M in (%MAPS%) do (
  call echo  [%%time%%] Запекаю карту / Baking map game/%%M
  start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0bake_watch.ps1" -Map %%M
  start "openQ4 bake %%M" /low /wait "%~dp0openQ4-client_x64.exe" +set logFile 2 +set logFileName logs/bake_%%M.log +set r_fullscreen 0 +set r_lightGridIntensity 1 +set r_forceAmbient 0 +set r_lightGridAO 0 +set r_lightGridShadowFloor 0 +set r_hdrToneMap 0 +set r_lightGridBakeAsyncReadback 0 +set r_lightGridBakeReadbackSlots 1 +bakeLightGrids game/%%M size128 samples128 blends1 bounce3 -quit
)
del /q "%~dp0baseoq4\zzz_bake_helper.pk4" 2>nul

powershell -NoProfile -Command "Get-ChildItem -Path $env:LOCALAPPDATA\openQ4, '%~dp0baseoq4' -Recurse -Filter openQ4Config.cfg.before_bake -ErrorAction SilentlyContinue | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $_.FullName.Substring(0, $_.FullName.Length - 12) -Force; Remove-Item -LiteralPath $_.FullName }"
echo.
call echo  [%%time%%] Готово. Окно с логом можно закрыть.
echo  Done. You can close the log window.
if exist "%~dp0bake_failed.txt" (
  echo.
  echo  Эти карты не запеклись / These maps failed:
  type "%~dp0bake_failed.txt"
  echo.
  echo  Список сохранён в bake_failed.txt. Out of memory: увеличьте файл подкачки или запеките карту
  echo  через bake_one_map.bat позже. / The list is saved in bake_failed.txt. Out of memory: enlarge
  echo  the page file, or bake the map later with bake_one_map.bat.
)
echo.
pause
