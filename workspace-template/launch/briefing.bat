@echo off
rem OpenCodeLIG morning briefing launcher.
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
py -3.11 -c "import sys" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11 not found via 'py -3.11'. Install Python 3.11 first.
    exit /b 9
)
py -3.11 agent_ops\agentops.py briefing
set RC=%errorlevel%
echo.
echo Report: agent_ops\results\reports
exit /b %RC%
