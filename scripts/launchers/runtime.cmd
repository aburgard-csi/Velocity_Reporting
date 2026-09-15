@echo off
rem Put the launcher's Python on this PC: unpacked from the share on first use, and again
rem whenever a new runtime is released. Running Python straight off the share imports
rem thousands of small files over SMB and takes minutes per build.
rem Called by the launcher .bat files with ROOT set; sets PY, exits 1 if it cannot.
set "RT=%LOCALAPPDATA%\RPE"
set "PY=%RT%\Python\python.exe"
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
