@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
where py >nul 2>nul || (echo [오류] py 런처가 없습니다. Python 3.11을 설치하세요. & exit /b 2)
py -3.11 --version >nul 2>nul || (echo [오류] Python 3.11이 없습니다. & exit /b 2)
cd /d "%~dp0.."
for /f "usebackq delims=" %%I in (`git rev-parse --show-toplevel 2^>nul`) do set "GIT_ROOT=%%I"
if not defined GIT_ROOT (
    echo [오류] git checkout 안에서 실행하세요.
    exit /b 2
)
set "SCRIPT_REL=scripts/precommit_scan.py"
if exist "%GIT_ROOT%\workspace-template\scripts\precommit_scan.py" set "SCRIPT_REL=workspace-template/scripts/precommit_scan.py"
if not exist "%GIT_ROOT%\.git\hooks" mkdir "%GIT_ROOT%\.git\hooks"
> "%GIT_ROOT%\.git\hooks\pre-commit" echo #!/bin/sh
>> "%GIT_ROOT%\.git\hooks\pre-commit" echo py -3.11 "%SCRIPT_REL%"
echo 설치 완료: %GIT_ROOT%\.git\hooks\pre-commit
exit /b 0
