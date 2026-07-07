@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
rem Shared Python 3.11 resolver. Sets %PY% for the calling BAT. Exit 9 if none.
rem Order: py -3.11 -> python -> python3.11 -> python3 (must report 3.11.x)
set "PY="
py -3.11 --version >nul 2>&1 && set "PY=py -3.11"
if defined PY goto :ok
for %%P in (python python3.11 python3) do (
    if not defined PY (
        for /f "tokens=2" %%V in ('%%P --version 2^>^&1') do (
            echo %%V | findstr /b /c:"3.11." >nul && set "PY=%%P"
        )
    )
)
if defined PY goto :ok
echo [ERROR] Python 3.11을 찾지 못했습니다.
echo         새 명령창에서 python --version 이 3.11.x 인지 확인하세요.
echo         (없으면 Python 3.11 오프라인 설치본을 반입해 설치하거나, 임베디드 zip을 풀어 PATH에 추가하세요)
exit /b 9
:ok
exit /b 0
