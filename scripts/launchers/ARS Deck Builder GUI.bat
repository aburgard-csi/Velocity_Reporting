@echo off
rem CSM Sheila (Smart Helper for Executive Insights, Layouts and Analytics): opens the ARS deck launcher in your browser. Lives in the CSM_Reporting folder;
rem see scripts\ars_launcher_web.py. Build ARS Deck.bat is the same thing without the browser.
setlocal
set "ROOT=%~dp0"
set "RPE_DATA_ROOT=%ROOT:~0,-1%"
set "APP=%ROOT%Tools\RPE\scripts\ars_launcher_web.py"
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
title CSM Sheila - Smart Helper for Executive Insights, Layouts ^& Analytics
rem Clears cmd's "UNC paths are not supported" notice; the script never uses the current directory.
cls
echo.
echo  CSM Sheila
echo  Smart Helper for Executive Insights, Layouts ^& Analytics
echo  --------------------------------------------------------
call "%ROOT%Tools\RPE\scripts\launchers\runtime.cmd" || goto end
echo  Opening the builder in your browser...
"%PY%" "%APP%"
:end
echo.
pause
