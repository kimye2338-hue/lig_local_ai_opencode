@echo off
rem OpenCodeLIG diagnostics: environment + provider readiness + agent runtime.
chcp 65001 >nul
set PYTHONUTF8=1
rem %~dp0 is re-resolved against the CURRENT dir when the bat was CALLed
rem with a relative path - capture it ONCE before any cd (learned the hard way).
set "HERE=%~dp0"
cd /d "%HERE%.."
call "%HERE%_py.bat" || exit /b 9
%PY% agent_ops\agentops.py doctor
set RC=%errorlevel%
echo.
echo Report : agent_ops\reports\DOCTOR_REPORT.md
echo Diag   : %USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics
exit /b %RC%
