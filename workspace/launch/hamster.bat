@echo off
chcp 65001 >nul
setlocal EnableExtensions
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "HERE=%~dp0"
for %%I in ("%HERE%..") do set "WS=%%~fI"
for %%I in ("%WS%\..") do set "ROOT=%%~fI"
if not defined LIG_STATE_DIR set "LIG_STATE_DIR=%ROOT%\userdata\state"
if not defined LIG_DIAG_DIR set "LIG_DIAG_DIR=%ROOT%\userdata\diagnostics"
if not exist "%LIG_STATE_DIR%" mkdir "%LIG_STATE_DIR%" >nul 2>&1
if not exist "%LIG_DIAG_DIR%" mkdir "%LIG_DIAG_DIR%" >nul 2>&1
if /I "%~1"=="--hidden" goto :hidden
call "%HERE%_py.bat" || exit /b 9
echo [OpenCodeLIG] Hamster overlay starting...
echo State: %LIG_STATE_DIR%
echo Diagnostics: %LIG_DIAG_DIR%
%PY% "%HERE%..\agent_ops\ui\hamster_overlay.py"
exit /b %errorlevel%
:hidden
call "%HERE%_pyw.bat" || exit /b 9
%PYW% "%HERE%..\agent_ops\ui\hamster_overlay.py"
exit /b 0
