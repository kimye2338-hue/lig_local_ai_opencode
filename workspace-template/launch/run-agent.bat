@echo off
rem OpenCodeLIG user-facing agent launcher.
rem Usage: run-agent.bat --mode mock --task "한글 작업 설명"
rem        run-agent.bat --mode real --task "..."   (requires lig-api.env)
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
call "%~dp0_py.bat" || exit /b 9
%PY% agent_ops\agentops.py agent %*
set RC=%errorlevel%
if not "%RC%"=="0" echo [INFO] Diagnostics: %USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics
exit /b %RC%
