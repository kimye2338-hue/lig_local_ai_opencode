@echo off
rem OpenCodeLIG morning briefing launcher.
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
call "%~dp0_py.bat" || exit /b 9
%PY% agent_ops\agentops.py briefing
set RC=%errorlevel%
echo.
echo Report: agent_ops\results\reports
exit /b %RC%
