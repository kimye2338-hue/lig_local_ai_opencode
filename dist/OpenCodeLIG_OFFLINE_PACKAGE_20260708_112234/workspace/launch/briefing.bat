@echo off
rem OpenCodeLIG morning briefing launcher.
chcp 65001 >nul
set PYTHONUTF8=1
rem %~dp0 is re-resolved against the CURRENT dir when the bat was CALLed
rem with a relative path - capture it ONCE before any cd (learned the hard way).
set "HERE=%~dp0"
cd /d "%HERE%.."
call "%HERE%_py.bat" || exit /b 9
%PY% agent_ops\agentops.py briefing
set RC=%errorlevel%
echo.
echo Report: agent_ops\results\reports
exit /b %RC%
