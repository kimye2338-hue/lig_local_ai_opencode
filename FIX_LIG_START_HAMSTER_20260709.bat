@echo off
chcp 65001 >nul
title OpenCodeLIG - TUI delay and hamster fix

rem 승격 재실행이면(__elevated 인자) 재확인 없이 바로 본작업 - 무한 루프 방지.
if "%~1"=="__elevated" goto :main
rem 관리자면 바로 진행, 아니면 딱 한 번만 승격(fltmc=신뢰성 있는 관리자 판정).
fltmc >nul 2>&1
if not errorlevel 1 goto :main
echo 관리자 권한으로 한 번만 다시 실행합니다... (UAC 창에서 예 를 누르세요)
powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0' -ArgumentList '__elevated'"
exit /b

:main
setlocal EnableExtensions
set "ROOT=%USERPROFILE%\OpenCodeLIG"
set "WS=%ROOT%\workspace"
set "LAUNCHER=%WS%\RUN_OPENCODE_LIG.bat"
set "HOSTS=%SystemRoot%\System32\drivers\etc\hosts"

echo ============================================================
echo  OpenCodeLIG 패치: (1) TUI 3분 지연  (2) 햄스터 미표시
echo ============================================================
if not exist "%WS%" (
  echo [ERROR] 설치본을 찾지 못했습니다: %WS%
  echo   경로가 다르면 이 bat 의 ROOT 줄을 실제 설치폴더로 고쳐 실행하세요.
  pause & exit /b 1
)

rem ===== 문제1: opencode.exe 시작 시 models.dev 조회가 폐쇄망에서 3분 매달림 =====
rem 관리자일 때만 hosts 로 외부 조회를 즉시 실패시켜 지연 제거. (PURE 는 계속 꺼둬 플러그인 유지)
echo.
echo [1/3] 외부 모델조회 호스트 차단(hosts)
fltmc >nul 2>&1
if errorlevel 1 (
  echo    [WARN] 관리자 권한이 아니라 hosts 단계를 건너뜁니다.
  echo           이 bat 을 마우스 우클릭 - 관리자 권한으로 실행 하면 3분 지연도 고쳐집니다.
  goto :hamster
)
findstr /C:"OPENCODELIG-OFFLINE-FIX" "%HOSTS%" >nul 2>&1
if not errorlevel 1 (
  echo    [SKIP] 이미 적용됨
  goto :hamster
)
copy /y "%HOSTS%" "%HOSTS%.opencodelig-bak" >nul 2>&1
>>"%HOSTS%" echo.
>>"%HOSTS%" echo # OPENCODELIG-OFFLINE-FIX 20260709 - remove next 2 lines to revert
>>"%HOSTS%" echo 127.0.0.1 models.dev
>>"%HOSTS%" echo 127.0.0.1 api.models.dev
ipconfig /flushdns >nul 2>&1
echo    [OK] models.dev / api.models.dev 차단. 백업: %HOSTS%.opencodelig-bak

:hamster
rem ===== 문제2a: 지금 떠있는 좀비 햄스터 정리(뮤텍스 해제) =====
echo.
echo [2/3] 좀비 햄스터 프로세스 정리(뮤텍스 해제)
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'hamster_overlay' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo    [OK] 정리 완료(있었다면 종료)

rem ===== 문제2b: 런처 grace 300->60 (종료후 뮤텍스 빨리 해제, 좀비 재발 방지) =====
echo.
echo [3/3] 런처 시작유예 300초 -> 60초
if not exist "%LAUNCHER%" (
  echo    [SKIP] 런처를 찾지 못함
  goto :done
)
copy /y "%LAUNCHER%" "%LAUNCHER%.bak-20260709" >nul 2>&1
powershell -NoProfile -Command "$p=$env:LAUNCHER; $t=[IO.File]::ReadAllText($p,[Text.Encoding]::UTF8); if($t -match 'LIG_HAMSTER_START_GRACE_SECONDS=300'){ [IO.File]::WriteAllText($p, ($t -replace 'LIG_HAMSTER_START_GRACE_SECONDS=300','LIG_HAMSTER_START_GRACE_SECONDS=60'), (New-Object Text.UTF8Encoding($false))); Write-Host '   [OK] grace 300 -> 60' } else { Write-Host '   [SKIP] grace 줄 없음 또는 이미 변경됨' }"
:done
echo.
echo ============================================================
echo  완료. Obsidian, OpenCode 를 모두 끄고 RUN_OPENCODE_LIG.bat 로 다시 실행해
echo  (1) TUI 가 빨리 뜨는지 (2) 햄스터가 보이는지 확인하세요.
echo.
echo  되돌리기:
echo   - hosts: %HOSTS%.opencodelig-bak 로 복원(또는 hosts 의 OPENCODELIG 블록 삭제)
echo   - 런처 : %LAUNCHER%.bak-20260709 로 복원
echo ============================================================
pause
exit /b 0
