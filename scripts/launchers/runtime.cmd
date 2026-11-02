@echo off
rem Put the launcher's Python AND its code on this PC. Running either straight off the share is
rem slow: Python imports thousands of small files over SMB, and every lookup of a file that is
rem not there (most of them) costs about 50 ms - a build that takes minutes locally ran for an
rem hour on 2026-10-06 and never finished.
rem   Python: unpacked from the share on first use, and again whenever a new runtime is released.
rem   Code:   Tools\RPE copied to %LOCALAPPDATA%\RPE\Code whenever a new release is stamped.
rem Called by the launcher .bat files, and by the CSM Sheila Claude extension (sheila_mcp\extension),
rem with ROOT set; sets PY and CODE, exits 1 if it cannot. It never touches Claude.
set "RT=%LOCALAPPDATA%\RPE"
set "PY=%RT%\Python\python.exe"
set "CODE=%RT%\Code"
set "SRC=%ROOT%Tools\RPE"
call :python || exit /b 1
call :code || exit /b 1
exit /b 0

:python
set "ZIP=%ROOT%Tools\rpe-runtime.zip"
set "STAMP=%ROOT%Tools\rpe-runtime.txt"
if not exist "%ZIP%" (
  echo  The launcher runtime is missing: %ZIP%
  echo  Ask Aaron to run the launcher release.
  exit /b 1
)
if exist "%PY%" if exist "%RT%\rpe-runtime.txt" fc "%STAMP%" "%RT%\rpe-runtime.txt" >nul 2>&1 && exit /b 0
echo  Setting up Python on this PC - first run or a new release, a minute or two...
if not exist "%RT%" mkdir "%RT%"
tar -xf "%ZIP%" -C "%RT%"
if errorlevel 1 (
  echo  Could not unpack %ZIP%
  exit /b 1
)
if not exist "%PY%" (
  echo  Unpacked, but %PY% is not there. Ask Aaron.
  exit /b 1
)
copy /y "%STAMP%" "%RT%\rpe-runtime.txt" >nul
exit /b 0

:code
if not exist "%SRC%\scripts\ars_launcher.py" (
  echo  The launcher code is missing: %SRC%
  echo  Ask Aaron to run the launcher release.
  exit /b 1
)
if exist "%CODE%\scripts\ars_launcher.py" if exist "%SRC%\RELEASE.txt" if exist "%CODE%\RELEASE.txt" fc "%SRC%\RELEASE.txt" "%CODE%\RELEASE.txt" >nul 2>&1 && exit /b 0
echo  Copying the launcher code to this PC - first run or a new release, under a minute...
rem The local stamp is removed first and written last, so a copy that stops half way is redone.
if exist "%CODE%\RELEASE.txt" del "%CODE%\RELEASE.txt"
robocopy "%SRC%" "%CODE%" /MIR /NFL /NDL /NJH /NJS /NP /R:2 /W:2 /XD __pycache__ /XF RELEASE.txt >nul
if errorlevel 8 (
  echo  Could not copy the launcher code from %SRC%
  exit /b 1
)
if exist "%SRC%\RELEASE.txt" copy /y "%SRC%\RELEASE.txt" "%CODE%\RELEASE.txt" >nul
exit /b 0
