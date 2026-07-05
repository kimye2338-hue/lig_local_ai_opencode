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
echo    4. 상태 진단        (doctor)
echo    5. 게이트웨이 점검  (LLM 연결 확인)
echo    0. 종료
echo  --------------------------------------------
set "SEL="
set /p SEL=번호 선택:
if "%SEL%"=="1" goto :task
if "%SEL%"=="2" goto :briefing
if "%SEL%"=="3" goto :weekly
if "%SEL%"=="4" goto :doctor
if "%SEL%"=="5" goto :smoke
if "%SEL%"=="0" exit /b 0
echo  잘못된 선택입니다.
goto :menu

:task
echo.
set "TASK="
set /p TASK=무슨 작업을 할까요? (한 줄로):
if "%TASK%"=="" (echo  작업 내용이 비어 있습니다.& goto :menu)
%PY% agent_ops\agentops.py work --task "%TASK%" --mode real
echo.
echo  산출물 폴더: agent_ops\results\artifacts  (탐색기로 열려면 아무 키)
pause >nul
start "" explorer "agent_ops\results\artifacts"
goto :menu

:briefing
%PY% agent_ops\agentops.py briefing
echo.
echo  보고서: agent_ops\results\reports
pause
goto :menu

:weekly
%PY% agent_ops\agentops.py weekly
echo.
echo  보고서: agent_ops\results\reports
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
