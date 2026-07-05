@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
rem %~dp0 is re-resolved against the CURRENT dir when the bat was CALLed
rem with a relative path - capture it ONCE before any cd.
set "HERE=%~dp0"
call "%HERE%_py.bat" || exit /b 9

if not defined LIG_STATE_DIR set "LIG_STATE_DIR=%USERPROFILE%\OpenCodeLIG_USERDATA\state"
if not defined LIG_DIAG_DIR set "LIG_DIAG_DIR=%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics"

if not exist "%LIG_STATE_DIR%" mkdir "%LIG_STATE_DIR%" >nul 2>&1
if not exist "%LIG_DIAG_DIR%" mkdir "%LIG_DIAG_DIR%" >nul 2>&1

echo [OpenCodeLIG] Hamster overlay starting...
echo State: %LIG_STATE_DIR%
echo Diagnostics: %LIG_DIAG_DIR%
start "OpenCodeLIG Hamster" %PY% "%HERE%..\agent_ops\ui\hamster_overlay.py"
exit /b 0
