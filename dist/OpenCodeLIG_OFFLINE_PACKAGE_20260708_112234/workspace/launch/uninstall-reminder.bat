@echo off
rem Prints and optionally removes the daily Windows Task Scheduler reminder.
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set TASK_NAME=OpenCodeLIG Morning Briefing
set SCHTASKS_CMD=schtasks /Delete /TN "%TASK_NAME%" /F
echo %SCHTASKS_CMD%
echo.
set /p ANSWER=Run this command now? [y/N]
if /I not "%ANSWER%"=="y" (
    echo Cancelled. No scheduled task was removed.
    exit /b 0
)
%SCHTASKS_CMD%
exit /b %errorlevel%
