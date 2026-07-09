@echo off
chcp 65001 >nul
title OpenCodeLIG - make opencode start fast

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
echo  OpenCodeLIG 시작 복구: hosts 차단 제거 + 오프라인 빠른시작
echo ============================================================

echo [1/4] 이전에 내가 넣은 hosts 차단 제거
if exist "%HOSTS%.opencodelig-bak" copy /y "%HOSTS%.opencodelig-bak" "%HOSTS%" >nul 2>&1 & if exist "%HOSTS%.opencodelig-bak" goto :hosts_ok
powershell -NoProfile -Command "$p=$env:HOSTS; (Get-Content -LiteralPath $p) | Where-Object { $_ -notmatch 'OPENCODELIG-OFFLINE-FIX' -and $_ -notmatch '127\.0\.0\.1\s+(api\.)?models\.dev' } | Set-Content -LiteralPath $p -Encoding ascii"
:hosts_ok
echo    [OK] hosts 정리
ipconfig /flushdns >nul 2>&1

echo [2/4] 런처를 원본 백업으로 복원(내 편집 되돌림)
if exist "%LAUNCHER%.bak-20260709" copy /y "%LAUNCHER%.bak-20260709" "%LAUNCHER%" >nul 2>&1 & if exist "%LAUNCHER%.bak-20260709" echo    [OK] 런처 복원됨
if not exist "%LAUNCHER%.bak-20260709" echo    [SKIP] 런처 백업 없음 - 그대로 사용

echo [3/4] 오프라인 빠른시작 켜기: OPENCODE_PURE=1 (시스템 환경변수, 파일수정 아님)
setx OPENCODE_PURE 1 /M >nul
echo    [OK] OPENCODE_PURE=1 설정 - opencode 가 시작 시 외부 모델조회를 건너뜀(3분 대기 없음)

echo [4/4] 좀비 햄스터 정리(뮤텍스 해제)
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'hamster_overlay' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo    [OK] 정리 완료

echo ============================================================
echo  완료. 이 창 닫고 RUN_OPENCODE_LIG.bat 을 새로 더블클릭하세요.
echo   - OpenCode TUI 가 바로 떠야 합니다(3분 대기 없음).
echo   - 햄스터도 보여야 합니다.
echo  참고: 이 모드에선 opencode 내부 플러그인 일부(세션 자동저장 등)가 꺼집니다.
echo        대신 시작이 빠르고 안정적입니다. 자동저장까지 원하면 알려주세요.
echo  되돌리기: 관리자 CMD 에서  setx OPENCODE_PURE "" /M
echo ============================================================
pause
exit /b 0
