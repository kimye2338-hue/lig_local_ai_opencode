@echo off
chcp 65001 >nul
title OpenCodeLIG - fast offline start (no PURE)

if "%~1"=="__elevated" goto :main
fltmc >nul 2>&1
if not errorlevel 1 goto :main
echo 관리자 권한으로 한 번만 다시 실행합니다... (UAC 창에서 예)
powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0' -ArgumentList '__elevated'"
exit /b

:main
setlocal EnableExtensions
set "ROOT=%USERPROFILE%\OpenCodeLIG"
set "WS=%ROOT%\workspace"
set "LAUNCHER=%WS%\RUN_OPENCODE_LIG.bat"
set "HOSTS=%SystemRoot%\System32\drivers\etc\hosts"

echo ============================================================
echo  OpenCodeLIG: PURE 없이 빠른 오프라인 시작(플러그인 유지)
echo ============================================================

echo [1/4] 이전에 내가 넣은 hosts 차단 제거(있으면)
if exist "%HOSTS%.opencodelig-bak" copy /y "%HOSTS%.opencodelig-bak" "%HOSTS%" >nul 2>&1 & if exist "%HOSTS%.opencodelig-bak" goto :hosts_ok
powershell -NoProfile -Command "$p=$env:HOSTS; if(Test-Path $p){ (Get-Content -LiteralPath $p) | Where-Object { $_ -notmatch 'OPENCODELIG-OFFLINE-FIX' -and $_ -notmatch '127\.0\.0\.1\s+(api\.)?models\.dev' } | Set-Content -LiteralPath $p -Encoding ascii }"
:hosts_ok
echo    [OK] hosts 정리
ipconfig /flushdns >nul 2>&1

echo [2/4] 런처를 원본 백업으로 복원(내 편집 되돌림)
if exist "%LAUNCHER%.bak-20260709" copy /y "%LAUNCHER%.bak-20260709" "%LAUNCHER%" >nul 2>&1 & if exist "%LAUNCHER%.bak-20260709" echo    [OK] 런처 복원됨
if not exist "%LAUNCHER%.bak-20260709" echo    [SKIP] 런처 백업 없음 - 그대로 사용

echo [3/4] 환경변수: PURE 해제 + models.dev/LSP/자동업뎃 조회만 끄기(플러그인은 유지)
setx OPENCODE_PURE "" /M >nul
setx OPENCODE_DISABLE_MODELS_FETCH 1 /M >nul
setx OPENCODE_DISABLE_LSP_DOWNLOAD 1 /M >nul
setx OPENCODE_DISABLE_AUTOUPDATE 1 /M >nul
echo    [OK] OPENCODE_PURE 해제, OPENCODE_DISABLE_MODELS_FETCH=1 설정(3분 대기 원인 제거)

echo [4/4] 좀비 햄스터 정리(뮤텍스 해제)
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'hamster_overlay' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo    [OK] 정리 완료

echo ============================================================
echo  완료. 이 창 닫고 RUN_OPENCODE_LIG.bat 을 새로 더블클릭하세요.
echo   - OpenCode TUI 가 3분 대기 없이 떠야 합니다.
echo   - PURE 는 껐으므로 플러그인(햄스터상태/세션 자동저장 등)은 그대로 동작합니다.
echo   - 햄스터도 보여야 합니다.
echo  근거: opencode.exe 안에 OPENCODE_DISABLE_MODELS_FETCH 가 있으면
echo        models.dev 조회를 건너뜁니다(바이너리 확인).
echo  되돌리기: 관리자 CMD 에서  setx OPENCODE_DISABLE_MODELS_FETCH "" /M
echo ============================================================
pause
exit /b 0
