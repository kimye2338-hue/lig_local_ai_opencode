@echo off
chcp 65001 >nul
setlocal EnableExtensions
set "HERE=%~dp0"
set "OUT=%HERE%OpenCodeLIG_OFFLINE_PACKAGE_20260708_112234.zip"
if exist "%OUT%" del /f /q "%OUT%"
copy /b "%HERE%OpenCodeLIG_OFFLINE_PACKAGE_20260708_112234.zip.part*" "%OUT%" >nul
if errorlevel 1 (
  echo [ERROR] Failed to merge parts.
  pause
  exit /b 1
)
echo [OK] Merged: %OUT%
echo Expected SHA256: e9b8d658f22e1257838077515929384d114d7f143fcc14a9ff8112df8a8616da
certutil -hashfile "%OUT%" SHA256
echo.
echo 위 SHA256 값이 Expected와 같으면 정상입니다.
pause
exit /b 0