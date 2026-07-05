@echo off
rem OpenCodeLIG resume: recover interrupted runs and show the resume plan.
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
call "%~dp0_py.bat" || exit /b 9
%PY% agent_ops\agentops.py resume
exit /b %errorlevel%
