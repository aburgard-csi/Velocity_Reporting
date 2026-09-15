@echo off
rem Build one client's ARS deck into Outputs. Lives in the CSM_Reporting folder; see scripts\ars_launcher.py.
setlocal
set "ROOT=%~dp0"
set "RPE_DATA_ROOT=%ROOT:~0,-1%"
set "APP=%ROOT%Tools\RPE\scripts\ars_launcher.py"
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
title Build ARS Deck
rem Clears cmd's "UNC paths are not supported" notice; the script never uses the current directory.
cls
echo.
echo  Build an ARS deck
echo  -----------------
call "%ROOT%Tools\RPE\scripts\launchers\runtime.cmd" || goto end
set "CID="
set /p "CID= Client number: "
if "%CID%"=="" goto end
"%PY%" "%APP%" status %CID%
rem 3 = ready, but this period's deck was already sent: ask instead of stopping.
if errorlevel 3 goto sent
if errorlevel 1 goto end
echo.
rem choice is case-insensitive (no /CS): y and Y both work.
choice /C YN /M " Build the ARS deck and put it in Outputs"
if errorlevel 2 goto end
"%PY%" "%APP%" build %CID%
goto end
:sent
echo.
choice /C YN /M " This deck was already sent. Rebuild it and replace the one in Outputs"
if errorlevel 2 goto end
"%PY%" "%APP%" build %CID% --rebuild
:end
echo.
pause
