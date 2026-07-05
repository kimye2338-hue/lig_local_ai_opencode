@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
rem %~dp0 is re-resolved against the CURRENT dir when the bat was CALLed
rem with a relative path - capture it ONCE before any cd (learned the hard way).
set "HERE=%~dp0"
call "%HERE%_py.bat" || (pause & exit /b 9)
set "PROBE_OUT_DIR=%HERE%probe_results"
%PY% "%HERE%..\agent_ops\probe_env.py"
echo.
echo 위 결과 파일을 깃허브 repo의 probe\results\ 폴더에 올려주세요.
echo (회사 PC라면 파일을 반출해 집 PC에서 커밋)
pause
