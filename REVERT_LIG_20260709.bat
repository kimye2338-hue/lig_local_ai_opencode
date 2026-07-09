@echo off
chcp 65001 >nul
title OpenCodeLIG - revert previous patch

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
echo  이전 패치 되돌리기: hosts 차단 제거 + 런처 복원
echo ============================================================

echo [1/2] hosts 복원(models.dev 차단 제거)
if exist "%HOSTS%.opencodelig-bak" (
  copy /y "%HOSTS%.opencodelig-bak" "%HOSTS%" >nul 2>&1
  echo    [OK] hosts 를 백업으로 복원
) else (
  echo    [i] hosts 백업이 없어 OPENCODELIG 줄만 직접 제거
  powershell -NoProfile -Command "$p=$env:HOSTS; (Get-Content -LiteralPath $p) | Where-Object { $_ -notmatch 'OPENCODELIG-OFFLINE-FIX' -and $_ -notmatch '^\s*127\.0\.0\.1\s+(api\.)?models\.dev\s*$' } | Set-Content -LiteralPath $p -Encoding ascii"
  echo    [OK] models.dev 차단 줄 제거
)
ipconfig /flushdns >nul 2>&1

echo [2/2] 런처 복원
if exist "%LAUNCHER%.bak-20260709" (
  copy /y "%LAUNCHER%.bak-20260709" "%LAUNCHER%" >nul 2>&1
  echo    [OK] 런처를 백업으로 복원
) else (
  echo    [SKIP] 런처 백업 없음(런처는 숫자 하나만 바뀌어 무해)
)

echo ============================================================
echo  완료. RUN_OPENCODE_LIG.bat 다시 실행해
echo  OpenCode 가 (느리더라도) 다시 뜨는지 확인하세요.
echo  - 다시 뜨면: hosts 차단이 원인이었음 -> 다른 방법으로 3분지연을 잡겠습니다.
echo  - 그래도 안 뜨면: 알려주세요(원인이 다른 곳).
echo ============================================================
pause
exit /b 0
