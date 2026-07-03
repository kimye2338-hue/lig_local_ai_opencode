@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
where py >nul 2>nul || (echo [오류] py 런처가 없습니다. Python 3.11을 설치하세요. & exit /b 2)
py -3.11 --version >nul 2>nul || (echo [오류] Python 3.11이 없습니다. & exit /b 2)
set "PROBE_OUT_DIR=%~dp0probe_results"
py -3.11 "%~dp0..\agent_ops\probe_env.py"
echo.
echo 위 결과 파일을 깃허브 repo의 probe\results\ 폴더에 올려주세요.
echo (회사 PC라면 파일을 반출해 집 PC에서 커밋)
pause
