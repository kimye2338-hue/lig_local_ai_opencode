@echo off
rem OpenCodeLIG 일일 사용 메뉴 - 이 파일 하나만 실행하면 됩니다.
chcp 65001 >nul
set PYTHONUTF8=1
title AI비서 (OpenCodeLIG)
cd /d "%~dp0.."
call "%~dp0_py.bat" || (pause & exit /b 9)

:menu
echo.
echo  ============================================
echo    AI비서 - 무엇을 도와드릴까요?
echo  ============================================
echo    1. 업무 시키기      (예: 회의록 초안 만들어줘)
echo    2. 아침 브리핑      (오늘 일정/할일/어제 요약)
echo    3. 주간보고 초안
echo    4. 일정 추가        (예: 금요일 14시 보고서 마감)
echo    5. 오늘/이번주 일정 보기
echo    6. Outlook 일정 가져오기
echo    7. 상태 진단        (doctor)
echo    8. 게이트웨이 점검  (LLM 연결 확인)
echo    0. 종료
echo  --------------------------------------------
set "SEL="
set /p SEL=번호 선택:
if "%SEL%"=="1" goto :task
if "%SEL%"=="2" goto :briefing
if "%SEL%"=="3" goto :weekly
if "%SEL%"=="4" goto :schedadd
if "%SEL%"=="5" goto :schedlist
if "%SEL%"=="6" goto :outlook
if "%SEL%"=="7" goto :doctor
if "%SEL%"=="8" goto :smoke
if "%SEL%"=="0" exit /b 0
echo  잘못된 선택입니다.
goto :menu

:task
echo.
set "TASK="
set /p TASK=무슨 작업을 할까요? (한 줄로):
if not defined TASK (echo  작업 내용이 비어 있습니다.& goto :menu)
set "TASK=%TASK:"=%"
set "REF="
set /p REF=참고할 파일/폴더 경로 (없으면 Enter):
set "REF=%REF:"=%"
if defined REF (
    %PY% agent_ops\agentops.py work --task "%TASK%" --mode real --input "%REF%"
) else (
    %PY% agent_ops\agentops.py work --task "%TASK%" --mode real
)
if errorlevel 1 (
    echo.
    echo  [안내] 작업이 완료되지 못했습니다. 7번(상태 진단)을 실행하거나
    echo         %%USERPROFILE%%\OpenCodeLIG_USERDATA\diagnostics 를 확인하세요.
    pause
    goto :menu
)
echo.
echo  완료. 산출물 폴더를 엽니다... (아무 키)
pause >nul
set "LASTRUN="
for /f "delims=" %%D in ('dir /b /ad /o-d "agent_ops\results\artifacts" 2^>nul') do (
    if not defined LASTRUN set "LASTRUN=%%D"
)
if defined LASTRUN (
    start "" explorer "agent_ops\results\artifacts\%LASTRUN%"
) else (
    start "" explorer "agent_ops\results\artifacts"
)
goto :menu

:briefing
%PY% agent_ops\agentops.py briefing
echo.
echo  보고서: agent_ops\results\reports  (.md는 메모장으로 열어도 됩니다)
pause
goto :menu

:weekly
%PY% agent_ops\agentops.py weekly
echo.
echo  보고서: agent_ops\results\reports
pause
goto :menu

:schedadd
echo.
set "SCHED="
set /p SCHED=일정 내용 (예: 금요일 14시 진동시험 보고서 마감):
if not defined SCHED (echo  일정 내용이 비어 있습니다.& goto :menu)
set "SCHED=%SCHED:"=%"
%PY% agent_ops\agentops.py schedule add "%SCHED%"
pause
goto :menu

:schedlist
%PY% agent_ops\agentops.py schedule list --when week
pause
goto :menu

:outlook
%PY% agent_ops\agentops.py schedule sync-outlook
pause
goto :menu

:doctor
%PY% agent_ops\agentops.py doctor
pause
goto :menu

:smoke
call "%~dp0gateway-smoke.bat"
pause
goto :menu
