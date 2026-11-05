@echo off
rem CSM Sheila in Claude: started by Claude Desktop through the "CSM Sheila" extension (sheila_mcp\extension).
rem stdout is the MCP protocol, so everything this script and runtime.cmd print goes to stderr (Claude's
rem log), and runtime.cmd reads nothing from stdin (<nul), which carries Claude's first messages.
rem   1. The same refresh Sheila's page does when it opens: Python and the code from the share to this PC.
rem   2. Serve from this PC's copy (python -m sheila_mcp).
rem A share that does not answer leaves the PC's copy as it is; a PC that never had Sheila stops here.
setlocal
if "%SHEILA_ROOT%"=="" set "SHEILA_ROOT=M:\CSM_Reporting"
set "ROOT=%SHEILA_ROOT%"
if not "%ROOT:~-1%"=="\" set "ROOT=%ROOT%\"
set "RPE_DATA_ROOT=%ROOT:~0,-1%"
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
set "PY=%LOCALAPPDATA%\RPE\Python\python.exe"
set "CODE=%LOCALAPPDATA%\RPE\Code"
if exist "%ROOT%Tools\RPE\scripts\launchers\runtime.cmd" (
  call "%ROOT%Tools\RPE\scripts\launchers\runtime.cmd" <nul 1>&2
) else (
  echo sheila: %ROOT% does not answer; using this PC's copy 1>&2
)
if not exist "%PY%" goto missing
if not exist "%CODE%\sheila_mcp\__main__.py" goto missing
"%PY%" -X utf8 "%CODE%\sheila_mcp\legacy.py" <nul 1>&2
cd /d "%CODE%"
"%PY%" -X utf8 -m sheila_mcp
exit /b %errorlevel%

:missing
echo sheila: Sheila is not set up on this PC and %ROOT% did not answer. Check the CSM Reporting folder in the extension's settings. 1>&2
exit /b 1
