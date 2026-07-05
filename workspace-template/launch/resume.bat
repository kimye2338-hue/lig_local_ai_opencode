@echo off
rem OpenCodeLIG resume: recover interrupted runs and show the resume plan.
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
py -3.11 -c "import sys" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11 not found via 'py -3.11'. Install Python 3.11 first.
    exit /b 9
)
py -3.11 agent_ops\agentops.py resume
exit /b %errorlevel%
