@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "HERE=%~dp0"
set "WS="
if exist "%HERE%agent_ops\pending_check.py" set "WS=%HERE%"
if not defined WS if exist "%HERE%workspace\agent_ops\pending_check.py" set "WS=%HERE%workspace"
if not defined WS if exist "%USERPROFILE%\OpenCodeLIG\workspace\agent_ops\pending_check.py" set "WS=%USERPROFILE%\OpenCodeLIG\workspace"

if not defined WS (
  echo [ERROR] OpenCodeLIG workspace not found.
  echo Run this file from the package root or installed workspace.
  pause
  exit /b 1
)

set "OUT=%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\pending_checks"
if not exist "%OUT%" mkdir "%OUT%"

echo.
echo ============================================================
echo OpenCodeLIG one-shot pending validation
echo ============================================================
echo Workspace: %WS%
echo Report dir: %OUT%
echo.

pushd "%WS%"
py -3.11 agent_ops\pending_check.py --out-dir "%OUT%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo [WARN] One or more required checks failed. Review:
  echo   %OUT%\pending-check-last.md
) else (
  echo.
  echo [OK] Required checks passed. Review pending items:
  echo   %OUT%\pending-check-last.md
)
popd

echo.
echo Send this file when requesting final completion:
echo   %OUT%\pending-check-last.md
echo.
pause
exit /b %RC%
