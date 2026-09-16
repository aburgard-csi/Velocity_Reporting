@echo off
rem WILL, the Workbook Intake and Layout Launcher: opens the ARS deck launcher in your browser. Lives in the CSM_Reporting folder;
rem see scripts\ars_launcher_web.py. Build ARS Deck.bat is the same thing without the browser.
setlocal
set "ROOT=%~dp0"
set "RPE_DATA_ROOT=%ROOT:~0,-1%"
set "APP=%ROOT%Tools\RPE\scripts\ars_launcher_web.py"
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
title WILL - Workbook Intake ^& Layout Launcher
rem Clears cmd's "UNC paths are not supported" notice; the script never uses the current directory.
cls
echo.
echo  WILL - Workbook Intake ^& Layout Launcher
echo  ------------------------------------------
call "%ROOT%Tools\RPE\scripts\launchers\runtime.cmd" || goto end
echo  Opening the builder in your browser...
"%PY%" "%APP%"
:end
echo.
pause
