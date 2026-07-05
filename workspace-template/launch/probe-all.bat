@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
call "%~dp0_py.bat" || (pause & exit /b 9)
set "PROBE_OUT_DIR=%~dp0probe_results"

echo ============================================================
echo  [1/2] 환경 probe (앱/매크로 정책/OpenCode 기동 진단)
echo ============================================================
%PY% "%~dp0..\agent_ops\probe_env.py"

echo.
echo ============================================================
echo  [2/2] gateway probe (404면 discovery 모드가 올바른 경로 탐색)
echo ============================================================
echo (lig-api.env 미작성이면 이 단계는 안내 후 건너뜁니다)
%PY% "%~dp0..\agent_ops\probe_gateway.py"

echo.
echo ============================================================
echo  완료. 아래 폴더의 파일들을 반출해 repo의 probe\results\ 에
echo  올리거나, 내용을 그대로 복사해 전달해 주세요.
echo    %PROBE_OUT_DIR%
echo  (host/key는 자동 마스킹되어 있습니다)
echo ============================================================
pause
