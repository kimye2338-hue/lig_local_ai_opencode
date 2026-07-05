@echo off
rem Prints and optionally installs a daily Windows Task Scheduler reminder.
chcp 65001 >nul
set PYTHONUTF8=1
set TASK_NAME=OpenCodeLIG Morning Briefing
set TASK_CMD=%~dp0briefing.bat
set SCHTASKS_CMD=schtasks /Create /SC DAILY /ST 08:30 /TN "%TASK_NAME%" /TR "\"%TASK_CMD%\"" /F
echo %SCHTASKS_CMD%
echo.
set /p ANSWER=Run this command now? [y/N] 
if /I not "%ANSWER%"=="y" (
    echo Cancelled. No scheduled task was created.
    exit /b 0
)
%SCHTASKS_CMD%
exit /b %errorlevel%
