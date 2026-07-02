@echo off
rem OpenCodeLIG user-facing agent launcher.
rem Usage: run-agent.bat --mode mock --task "한글 작업 설명"
rem        run-agent.bat --mode real --task "..."   (requires lig-api.env)
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
py -3.11 -c "import sys" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11 not found via 'py -3.11'. Install Python 3.11 first.
    exit /b 9
)
py -3.11 agent_ops\agentops.py agent %*
set RC=%errorlevel%
if not "%RC%"=="0" echo [INFO] Diagnostics: %USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics
exit /b %RC%
