@echo off
rem CSM Sheila: opens the ARS deck launcher in your browser. Lives in the CSM_Reporting folder;
rem see scripts\ars_launcher_web.py. Build ARS Deck CLI.bat is the same thing without the browser.
setlocal
set "ROOT=%~dp0"
set "RPE_DATA_ROOT=%ROOT:~0,-1%"
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
title CSM Sheila
rem Clears cmd's "UNC paths are not supported" notice; the script never uses the current directory.
cls
echo.
echo  CSM Sheila
echo  ----------
call "%ROOT%Tools\RPE\scripts\launchers\runtime.cmd" || goto end
set "APP=%CODE%\scripts\ars_launcher_web.py"
echo  Opening the builder in your browser...
"%PY%" "%APP%"
:end
echo.
pause
