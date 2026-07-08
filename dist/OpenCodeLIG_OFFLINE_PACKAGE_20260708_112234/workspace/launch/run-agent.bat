@echo off
rem OpenCodeLIG user-facing agent launcher.
rem Usage: run-agent.bat --mode mock --task "한글 작업 설명"
rem        run-agent.bat --mode real --task "..."   (requires lig-api.env)
chcp 65001 >nul
set PYTHONUTF8=1
rem %~dp0 is re-resolved against the CURRENT dir when the bat was CALLed
rem with a relative path - capture it ONCE before any cd (learned the hard way).
set "HERE=%~dp0"
cd /d "%HERE%.."
call "%HERE%_py.bat" || exit /b 9
%PY% agent_ops\agentops.py agent %*
set RC=%errorlevel%
if not "%RC%"=="0" echo [INFO] Diagnostics: %USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics
exit /b %RC%
