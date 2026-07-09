@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo.
echo ============================================================
echo OpenCodeLIG existing-install hotfix 20260709
echo ============================================================
echo.

set "ROOT=%USERPROFILE%\OpenCodeLIG"
set "WS=%ROOT%\workspace"
set "PATCHPY="

if exist "%~dp0workspace\patches\existing_install_hotfix_20260709.py" set "PATCHPY=%~dp0workspace\patches\existing_install_hotfix_20260709.py"
if not defined PATCHPY if exist "%WS%\patches\existing_install_hotfix_20260709.py" set "PATCHPY=%WS%\patches\existing_install_hotfix_20260709.py"

if not exist "%WS%\agent_ops\pending_check.py" (
  echo [ERROR] Existing OpenCodeLIG workspace not found:
  echo   %WS%
  echo Install OpenCodeLIG first, then run this patch.
  pause
  exit /b 1
)

if not defined PATCHPY (
  echo [ERROR] Patch script not found.
  echo Expected one of:
  echo   %~dp0workspace\patches\existing_install_hotfix_20260709.py
  echo   %WS%\patches\existing_install_hotfix_20260709.py
  echo.
  echo Keep this BAT inside the patch/package folder and run again.
  pause
  exit /b 1
)

echo Target install:
echo   %ROOT%
echo Patch script:
echo   %PATCHPY%
echo.
echo Optional wheels:
echo   If you have mss-*.whl, put it under .\patch_wheels\ next to this BAT
echo   or under workspace\tools\wheelhouse before running.
echo.

py -3.11 "%PATCHPY%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo [ERROR] Patch failed. Review:
  echo   %USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\patches
  pause
  exit /b %RC%
)

echo.
echo [OK] Patch finished.
echo Latest check report:
echo   %USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\pending_checks\pending-check-last.md
echo Patch log:
echo   %USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\patches
echo.
pause
exit /b 0
