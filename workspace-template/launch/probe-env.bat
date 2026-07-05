@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
call "%~dp0_py.bat" || (pause & exit /b 9)
set "PROBE_OUT_DIR=%~dp0probe_results"
%PY% "%~dp0..\agent_ops\probe_env.py"
echo.
echo 위 결과 파일을 깃허브 repo의 probe\results\ 폴더에 올려주세요.
echo (회사 PC라면 파일을 반출해 집 PC에서 커밋)
pause
