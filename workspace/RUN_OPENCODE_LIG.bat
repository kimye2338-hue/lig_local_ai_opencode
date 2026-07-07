@echo off
chcp 65001 >nul
setlocal EnableExtensions
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

rem OpenCodeLIG unified launcher
rem - loads %USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env
rem - starts hamster pet hidden (no extra console windows)
rem - opens only OpenCode main window

for %%I in ("%~dp0.") do set "AGENTOPS_HOME=%%~fI"
for %%I in ("%AGENTOPS_HOME%\..") do set "OC_ROOT=%%~fI"

set "OCODE_EXE=%OC_ROOT%\bin\opencode.exe"
rem USERDATA는 파이썬 런타임 기본값(core.py: %USERPROFILE%\OpenCodeLIG_USERDATA)과
rem 개별 bat(gateway-smoke/probe-gateway 등)·문서와 반드시 일치시킨다.
set "OPENCODE_USERDATA=%USERPROFILE%\OpenCodeLIG_USERDATA"
set "LIG_API_ENV_FILE=%OPENCODE_USERDATA%\secrets\lig-api.env"
set "LIG_STATE_DIR=%OPENCODE_USERDATA%\state"
set "LIG_DIAG_DIR=%OPENCODE_USERDATA%\diagnostics"
set "XDG_CONFIG_HOME=%OPENCODE_USERDATA%\config"
set "XDG_DATA_HOME=%OPENCODE_USERDATA%\data"
set "XDG_CACHE_HOME=%OPENCODE_USERDATA%\cache"
set "OPENCODE_CONFIG=%AGENTOPS_HOME%\opencode.json"
set "OPENCODE_DISABLE_DEFAULT_PLUGINS=1"
set "OPENCODE_PURE=1"
set "NO_UPDATE_NOTIFIER=1"
set "LIG_HAMSTER_WATCH_PROCESS=opencode.exe"

if not exist "%OPENCODE_USERDATA%" mkdir "%OPENCODE_USERDATA%"
if not exist "%OPENCODE_USERDATA%\secrets" mkdir "%OPENCODE_USERDATA%\secrets"
if not exist "%LIG_STATE_DIR%" mkdir "%LIG_STATE_DIR%"
if not exist "%LIG_DIAG_DIR%" mkdir "%LIG_DIAG_DIR%"
if not exist "%XDG_CONFIG_HOME%" mkdir "%XDG_CONFIG_HOME%"
if not exist "%XDG_DATA_HOME%" mkdir "%XDG_DATA_HOME%"
if not exist "%XDG_CACHE_HOME%" mkdir "%XDG_CACHE_HOME%"

if not exist "%OCODE_EXE%" (
  echo [ERROR] opencode.exe not found:
  echo %OCODE_EXE%
  pause
  exit /b 1
)
rem 처음이면 secret 파일을 템플릿에서 자동 생성. 템플릿에 게이트웨이 주소/키/
rem 라우트/모델이 이미 채워져 있으므로 별도 설정 없이 바로 연결된다.
if not exist "%LIG_API_ENV_FILE%" (
  if exist "%AGENTOPS_HOME%\config\lig-api.env.example" (
    copy /y "%AGENTOPS_HOME%\config\lig-api.env.example" "%LIG_API_ENV_FILE%" >nul
    echo [설정] 게이트웨이 설정 파일을 만들었습니다: %LIG_API_ENV_FILE%
  ) else (
    echo [ERROR] lig-api.env 및 템플릿을 찾지 못했습니다: %LIG_API_ENV_FILE%
    pause
    exit /b 1
  )
)

rem 게이트웨이 주소/키가 비어 있거나 아직 플레이스홀더면 그때만 안내(자동 감지).
rem 값이 채워져 있으면(기본 배포 상태) 아무 것도 묻지 않고 그대로 진행한다.
set "NEED_FILL="
findstr /R /C:"^LIG_GATEWAY_BASE_URL=$" "%LIG_API_ENV_FILE%" >nul 2>&1 && set "NEED_FILL=1"
findstr /C:"REPLACE_WITH" "%LIG_API_ENV_FILE%" >nul 2>&1 && set "NEED_FILL=1"
findstr /C:"PUT_INTERNAL" "%LIG_API_ENV_FILE%" >nul 2>&1 && set "NEED_FILL=1"
if defined NEED_FILL (
  echo [안내] 게이트웨이 주소/키가 아직 비어 있습니다. 아래 파일의
  echo   LIG_GATEWAY_BASE_URL 과 LIG_API_KEY 를 채우세요: %LIG_API_ENV_FILE%
  start "" notepad "%LIG_API_ENV_FILE%"
  echo   채운 뒤 저장하고 아무 키나 누르세요.
  pause
)

rem Load lig-api.env into shell environment as well.
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%LIG_API_ENV_FILE%") do (
  if not "%%A"=="" set "%%A=%%B"
)

rem OpenCode TUI 가 기본모델이 아니라 사내 EXAONE/Qwen 으로 열리게 — opencode.json 의
rem provider baseURL({env:...})을 게이트웨이 호스트+라우트로 조합해 넘긴다.
set "LIG_OPENCODE_BASEURL_CODING=%LIG_GATEWAY_BASE_URL%%LIG_ROUTE_CODING%"
set "LIG_OPENCODE_BASEURL_FALLBACK=%LIG_GATEWAY_BASE_URL%%LIG_ROUTE_FALLBACK%"

rem First-run convenience: keep a copy of workspace config under userdata config.
if exist "%AGENTOPS_HOME%\config" xcopy /D /E /I /Y "%AGENTOPS_HOME%\config\*" "%XDG_CONFIG_HOME%\" >nul

rem Start hamster hidden (single-instance overlay; duplicates auto-exit)
if exist "%AGENTOPS_HOME%\launch\hamster_hidden.vbs" (
  wscript "%AGENTOPS_HOME%\launch\hamster_hidden.vbs"
)

cd /d "%AGENTOPS_HOME%"

rem 구 모드/primary 정리 (best-effort) — 패치 후에도 primary=agent 하나 강제.
py -3.11 -m agent_ops.clean_stale >nul 2>&1 || python -m agent_ops.clean_stale >nul 2>&1

"%OCODE_EXE%" %*

exit /b %errorlevel%
