@echo off
rem CSM Sheila as a desktop app: the same Sheila as ARS Deck Builder GUI.bat, in a window of her own (Microsoft Edge
rem in app mode) instead of a browser tab. Close the window and she stops, once any build in progress finishes.
rem Lives in the CSM_Reporting folder; see scripts\sheila_app.py.
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
call "%ROOT%Tools\RPE\scripts\launchers\runtime.cmd" || goto fail
set "APP=%CODE%\scripts\ars_launcher_web.py"
rem pythonw has no console window: Sheila's own window is the only one. What she prints goes to
rem %LOCALAPPDATA%\RPE\sheila_app.log.
set "PYW=%PY:python.exe=pythonw.exe%"
if not exist "%PYW%" set "PYW=%PY%"
echo  Opening Sheila's window. This one closes by itself.
start "" "%PYW%" "%APP%" --app
exit /b 0
:fail
echo.
pause
