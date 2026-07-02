@echo off
rem OpenCodeLIG diagnostics: environment + provider readiness + agent runtime.
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
py -3.11 -c "import sys" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11 not found via 'py -3.11'. Install Python 3.11 first.
    exit /b 9
)
py -3.11 agent_ops\agentops.py doctor
set RC=%errorlevel%
echo.
echo Report : agent_ops\reports\DOCTOR_REPORT.md
echo Diag   : %USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics
exit /b %RC%
