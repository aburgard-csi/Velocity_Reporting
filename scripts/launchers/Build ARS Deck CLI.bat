@echo off
rem Build one client's ARS deck into Outputs. Lives in the CSM_Reporting folder; see scripts\ars_launcher.py.
setlocal
set "ROOT=%~dp0"
set "RPE_DATA_ROOT=%ROOT:~0,-1%"
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
title Build ARS Deck CLI
rem Clears cmd's "UNC paths are not supported" notice; the script never uses the current directory.
cls
echo.
echo  Build an ARS deck
echo  -----------------
call "%ROOT%Tools\RPE\scripts\launchers\runtime.cmd" || goto end
set "APP=%CODE%\scripts\ars_launcher.py"
set "CID="
set /p "CID= Client number: "
if "%CID%"=="" goto end
"%PY%" "%APP%" status %CID%
rem 3 = ready, but this period's deck is already in Outputs: ask instead of stopping.
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
choice /C YN /M " This month's deck is already in Outputs. Rebuild it and replace it"
if errorlevel 2 goto end
"%PY%" "%APP%" build %CID% --rebuild
:end
echo.
pause
