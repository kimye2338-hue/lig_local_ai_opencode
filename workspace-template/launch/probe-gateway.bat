@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
where py >nul 2>nul || (echo [오류] py 런처가 없습니다. Python 3.11을 설치하세요. & exit /b 2)
py -3.11 --version >nul 2>nul || (echo [오류] Python 3.11이 없습니다. & exit /b 2)
set "PROBE_OUT_DIR=%~dp0probe_results"
echo 회사 gateway probe: 사전에 %%USERPROFILE%%\OpenCodeLIG_USERDATA\secrets\lig-api.env 를 채워야 합니다.
echo (로컬 Ollama로 테스트하려면: set LIG_PROVIDER_PROFILE=local_openai 후 재실행)
py -3.11 "%~dp0..\agent_ops\probe_gateway.py"
if errorlevel 3 (echo [중단] 마스킹 실패 — 파일이 생성되지 않았습니다. 결과를 올리지 마세요.)
if errorlevel 2 (echo 설정을 채운 뒤 다시 실행하세요.)
echo.
echo 생성된 JSON은 host/key가 마스킹되어 있으며, repo의 probe\results\ 에 올려주세요.
pause
