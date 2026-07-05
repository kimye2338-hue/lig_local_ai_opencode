@echo off
rem OpenCodeLIG diagnostics: environment + provider readiness + agent runtime.
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
call "%~dp0_py.bat" || exit /b 9
%PY% agent_ops\agentops.py doctor
set RC=%errorlevel%
echo.
echo Report : agent_ops\reports\DOCTOR_REPORT.md
echo Diag   : %USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics
exit /b %RC%
