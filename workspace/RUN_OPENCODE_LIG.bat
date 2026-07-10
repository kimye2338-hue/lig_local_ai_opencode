@echo off
chcp 65001 >nul
setlocal EnableExtensions
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "LITELLM_LOCAL_MODEL_COST_MAP=True"
set "LITELLM_LOCAL_POLICY_TEMPLATES=True"
set "LITELLM_LOCAL_BLOG_POSTS=True"

rem OpenCodeLIG unified launcher
rem - keeps OpenCode plugins enabled
rem - uses a clean OpenCode runtime cache to avoid company-network startup waits
rem - starts the hamster overlay from the real installed workspace

for %%I in ("%~dp0.") do set "AGENTOPS_HOME=%%~fI"
for %%I in ("%AGENTOPS_HOME%\..") do set "OC_ROOT=%%~fI"

if not defined LIG_PROJECT_DIR (
  set "LIG_PROJECT_DIR=%CD%"
)
if /I "%LIG_PROJECT_DIR%"=="%USERPROFILE%" set "LIG_PROJECT_DIR=%AGENTOPS_HOME%"
if /I "%LIG_PROJECT_DIR%"=="%WINDIR%\System32" set "LIG_PROJECT_DIR=%AGENTOPS_HOME%"
if /I "%LIG_PROJECT_DIR%"=="%WINDIR%\SysWOW64" set "LIG_PROJECT_DIR=%AGENTOPS_HOME%"
echo(%LIG_PROJECT_DIR%| findstr /I /B /C:"%WINDIR%\\" >nul && set "LIG_PROJECT_DIR=%AGENTOPS_HOME%"
for %%I in ("%LIG_PROJECT_DIR%") do if /I "%%~fI"=="%%~dI\" set "LIG_PROJECT_DIR=%AGENTOPS_HOME%"

set "LIG_AGENTOPS_HOME=%AGENTOPS_HOME%"
set "OCODE_EXE=%OC_ROOT%\bin\opencode.exe"
set "OPENCODE_USERDATA=%USERPROFILE%\OpenCodeLIG_USERDATA"
if not defined AGENTOPS_MEMORY_DIR set "AGENTOPS_MEMORY_DIR=%OPENCODE_USERDATA%\memory"
set "AGENTOPS_ROOT=%LIG_PROJECT_DIR%"
set "PYTHONPATH=%AGENTOPS_HOME%;%PYTHONPATH%"
set "LIG_API_ENV_FILE=%OPENCODE_USERDATA%\secrets\lig-api.env"
set "LIG_STATE_DIR=%OPENCODE_USERDATA%\state"
set "LIG_DIAG_DIR=%OPENCODE_USERDATA%\diagnostics"
set "LIG_LAUNCH_LOG=%LIG_DIAG_DIR%\run_opencode_lig.log"
set "OPENCODE_DISABLE_DEFAULT_PLUGINS=1"
set "NO_UPDATE_NOTIFIER=1"
set "LIG_HAMSTER_WATCH_PROCESS=opencode.exe"
set "LIG_HAMSTER_START_GRACE_SECONDS=300"

if not exist "%OPENCODE_USERDATA%" mkdir "%OPENCODE_USERDATA%"
if not exist "%OPENCODE_USERDATA%\secrets" mkdir "%OPENCODE_USERDATA%\secrets"
if not exist "%OPENCODE_USERDATA%\config" mkdir "%OPENCODE_USERDATA%\config"
if not exist "%LIG_STATE_DIR%" mkdir "%LIG_STATE_DIR%"
if not exist "%LIG_DIAG_DIR%" mkdir "%LIG_DIAG_DIR%"

if not exist "%OCODE_EXE%" (
  echo [ERROR] opencode.exe not found:
  echo %OCODE_EXE%
  pause
  exit /b 1
)

rem 처음이면 secret 파일을 템플릿에서 자동 생성한다.
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

rem 햄스터 시작 전 상태 리셋.
>"%LIG_STATE_DIR%\current_status.json" echo {"status":"idle","task":"idle"}
del /q "%LIG_DIAG_DIR%\agent-loop-last.json" >nul 2>&1
del /q "%LIG_DIAG_DIR%\tool-dispatch-last.json" >nul 2>&1

rem ============================================================
rem Start hamster overlay.
rem Use fixed workspace path first so it also works when launched by ocd.
rem Correct actual path:
rem   %USERPROFILE%\OpenCodeLIG\workspace\agent_ops\ui\hamster_overlay.py
rem ============================================================

set "LIG_WORKSPACE_HOME=%USERPROFILE%\OpenCodeLIG\workspace"
set "HAMSTER_PY="
set "HAMSTER_HOME="
set "HAMSTER_LOG=%LIG_DIAG_DIR%\hamster_overlay_start.log"

if exist "%LIG_WORKSPACE_HOME%\agent_ops\ui\hamster_overlay.py" set "HAMSTER_PY=%LIG_WORKSPACE_HOME%\agent_ops\ui\hamster_overlay.py"
if exist "%LIG_WORKSPACE_HOME%\agent_ops\ui\hamster_overlay.py" set "HAMSTER_HOME=%LIG_WORKSPACE_HOME%"
if not defined HAMSTER_PY if exist "%AGENTOPS_HOME%\agent_ops\ui\hamster_overlay.py" set "HAMSTER_PY=%AGENTOPS_HOME%\agent_ops\ui\hamster_overlay.py"
if not defined HAMSTER_HOME if exist "%AGENTOPS_HOME%\agent_ops\ui\hamster_overlay.py" set "HAMSTER_HOME=%AGENTOPS_HOME%"
if not defined HAMSTER_PY goto :hamster_not_found

>>"%LIG_LAUNCH_LOG%" echo [%time%] Starting hamster_overlay.py
>>"%LIG_LAUNCH_LOG%" echo HAMSTER_PY=%HAMSTER_PY%
>"%HAMSTER_LOG%" echo [%date% %time%] starting hamster
>>"%HAMSTER_LOG%" echo HAMSTER_PY=%HAMSTER_PY%
>>"%HAMSTER_LOG%" echo HAMSTER_HOME=%HAMSTER_HOME%
>>"%HAMSTER_LOG%" echo LIG_WORKSPACE_HOME=%LIG_WORKSPACE_HOME%
>>"%HAMSTER_LOG%" echo AGENTOPS_HOME=%AGENTOPS_HOME%
>>"%HAMSTER_LOG%" echo OPENCODE_USERDATA=%OPENCODE_USERDATA%

rem Make sure hamster can import agent_ops from the selected home.
set "LIG_AGENTOPS_HOME=%HAMSTER_HOME%"
set "PYTHONPATH=%HAMSTER_HOME%;%PYTHONPATH%"
if exist "%AGENTOPS_HOME%\launch\_pyw.bat" call "%AGENTOPS_HOME%\launch\_pyw.bat"
if defined PYW start "OpenCodeLIG Hamster" /B /MIN /D "%HAMSTER_HOME%" %PYW% "%HAMSTER_PY%"
if not defined PYW start "OpenCodeLIG Hamster" /B /MIN /D "%HAMSTER_HOME%" pythonw "%HAMSTER_PY%"
goto :hamster_done

:hamster_not_found
>>"%LIG_LAUNCH_LOG%" echo [%time%] hamster_overlay.py not found
>"%HAMSTER_LOG%" echo [%date% %time%] hamster_overlay.py not found
:hamster_done

cd /d "%AGENTOPS_HOME%"

rem 구 모드/primary 정리 (best-effort).
py -3.11 -m agent_ops.clean_stale >nul 2>&1 || python -m agent_ops.clean_stale >nul 2>&1

rem 위키 자동화: vault 자동 시드 + Obsidian 자동 실행.
rem BEGIN LIG EXISTING-INSTALL HOTFIX 20260709
if not exist "%OPENCODE_USERDATA%\memory\wiki" mkdir "%OPENCODE_USERDATA%\memory\wiki" >nul 2>&1
py -3.11 -m agent_ops.wiki_vault "%OPENCODE_USERDATA%\memory\wiki" >nul 2>&1 || python -m agent_ops.wiki_vault "%OPENCODE_USERDATA%\memory\wiki" >nul 2>&1
if "%LIG_AUTO_WIKI%"=="0" goto :wiki_done
set "OBSEXE="
for %%P in ("%AGENTOPS_HOME%\tools\Obsidian\Obsidian.exe" "%OC_ROOT%\tools\Obsidian\Obsidian.exe" "%LOCALAPPDATA%\Obsidian\Obsidian.exe" "%LOCALAPPDATA%\Programs\Obsidian\Obsidian.exe" "%PROGRAMFILES%\Obsidian\Obsidian.exe") do if not defined OBSEXE if exist "%%~P" set "OBSEXE=%%~P"
if not defined OBSEXE for /f "delims=" %%F in ('dir /b /s "%OC_ROOT%\Obsidian.exe" 2^>nul') do if not defined OBSEXE set "OBSEXE=%%F"
if defined OBSEXE if exist "%AGENTOPS_HOME%\launch\obsidian_detached.vbs" wscript "%AGENTOPS_HOME%\launch\obsidian_detached.vbs" "%OBSEXE%" "%OPENCODE_USERDATA%\memory\wiki"
:wiki_done
rem END LIG EXISTING-INSTALL HOTFIX 20260709

rem BEGIN LIG PROJECT WORKDIR HOTFIX 20260709
rem 프로그램 본체는 설치 폴더에서 읽고, 사용자가 cd로 들어온 폴더를 작업 기준으로 사용한다.
if not exist "%LIG_PROJECT_DIR%" mkdir "%LIG_PROJECT_DIR%" >nul 2>&1
if /I "%LIG_PROJECT_DIR%"=="%AGENTOPS_HOME%" goto :project_ready
if not exist "%LIG_PROJECT_DIR%\.opencode" (
  xcopy /E /I /Y "%AGENTOPS_HOME%\.opencode" "%LIG_PROJECT_DIR%\.opencode" >nul
)
if not exist "%LIG_PROJECT_DIR%\.opencode\plugins" mkdir "%LIG_PROJECT_DIR%\.opencode\plugins" >nul 2>&1
rem 필수 플러그인: session-autosave.ts memory-inject.ts command-guard.ts hamster-status.ts compaction-handoff.ts
for %%F in ("%AGENTOPS_HOME%\.opencode\plugins\*.ts") do copy /Y "%%~fF" "%LIG_PROJECT_DIR%\.opencode\plugins\%%~nxF" >nul
if not exist "%LIG_PROJECT_DIR%\agent_ops" mkdir "%LIG_PROJECT_DIR%\agent_ops" >nul 2>&1
if exist "%AGENTOPS_HOME%\launch\project_agentops_wrapper.py" (
  copy /Y "%AGENTOPS_HOME%\launch\project_agentops_wrapper.py" "%LIG_PROJECT_DIR%\agent_ops\agentops.py" >nul
  copy /Y "%AGENTOPS_HOME%\launch\project_agentops_wrapper.py" "%LIG_PROJECT_DIR%\agent_ops\command_guard.py" >nul
  copy /Y "%AGENTOPS_HOME%\launch\project_agentops_wrapper.py" "%LIG_PROJECT_DIR%\agent_ops\safe_file_writer.py" >nul
)
if not exist "%LIG_PROJECT_DIR%\agent_ops\results" mkdir "%LIG_PROJECT_DIR%\agent_ops\results" >nul 2>&1
:project_ready
cd /d "%LIG_PROJECT_DIR%"
rem END LIG PROJECT WORKDIR HOTFIX 20260709

set "OPENCODE_FAST_BASE=%OPENCODE_USERDATA%\opencode_fast_runtime"
set "OPENCODE_FAST_CONFIG=%OPENCODE_FAST_BASE%\config"
set "OPENCODE_FAST_DATA=%OPENCODE_FAST_BASE%\data"
set "OPENCODE_FAST_CACHE=%OPENCODE_FAST_BASE%\cache"
set "OPENCODE_LEGACY_CONFIG=%OPENCODE_USERDATA%\config"
set "OPENCODE_LEGACY_DATA=%OPENCODE_USERDATA%\data"
set "OPENCODE_LEGACY_CACHE=%OPENCODE_USERDATA%\cache"

if not exist "%OPENCODE_FAST_CONFIG%" mkdir "%OPENCODE_FAST_CONFIG%" >nul 2>&1
if not exist "%OPENCODE_FAST_DATA%" mkdir "%OPENCODE_FAST_DATA%" >nul 2>&1
if not exist "%OPENCODE_FAST_CACHE%" mkdir "%OPENCODE_FAST_CACHE%" >nul 2>&1
if not exist "%OPENCODE_FAST_BASE%\.migrated" (
  if not exist "%OPENCODE_FAST_CONFIG%\*" if exist "%OPENCODE_LEGACY_CONFIG%" robocopy "%OPENCODE_LEGACY_CONFIG%" "%OPENCODE_FAST_CONFIG%" /E /XO >nul
  if not exist "%OPENCODE_FAST_DATA%\*" if exist "%OPENCODE_LEGACY_DATA%" robocopy "%OPENCODE_LEGACY_DATA%" "%OPENCODE_FAST_DATA%" /E /XO >nul
  if not exist "%OPENCODE_FAST_CACHE%\*" if exist "%OPENCODE_LEGACY_CACHE%" robocopy "%OPENCODE_LEGACY_CACHE%" "%OPENCODE_FAST_CACHE%" /E /XO >nul
  >"%OPENCODE_FAST_BASE%\.migrated" echo migrated
)

set "OPENCODE_CONFIG_DIR=%OPENCODE_FAST_CONFIG%"
set "XDG_CONFIG_HOME=%OPENCODE_FAST_CONFIG%"
set "XDG_DATA_HOME=%OPENCODE_FAST_DATA%"
set "XDG_CACHE_HOME=%OPENCODE_FAST_CACHE%"

set "OPENCODE_CONFIG=%AGENTOPS_HOME%\opencode.json"
set "OPENCODE_PURE="

set "OPENCODE_DISABLE_MODELS_FETCH=1"
set "OPENCODE_DISABLE_AUTOUPDATE=1"
set "OPENCODE_DISABLE_LSP_DOWNLOAD=1"
set "OPENCODE_MODELS_URL=http://127.0.0.1:9/api.json"

set "NPM_CONFIG_REGISTRY=http://127.0.0.1:9/"
set "npm_config_registry=http://127.0.0.1:9/"
set "NPM_CONFIG_FETCH_TIMEOUT=1000"
set "NPM_CONFIG_FETCH_RETRIES=0"
set "npm_config_fetch_timeout=1000"
set "npm_config_fetch_retries=0"
set "BUN_CONFIG_REGISTRY=http://127.0.0.1:9/"
set "BUN_INSTALL_CACHE_DIR=%OPENCODE_FAST_CACHE%\bun"

set "NO_PROXY=*"
set "no_proxy=*"
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "ALL_PROXY="
set "http_proxy="
set "https_proxy="
set "all_proxy="
set "npm_config_proxy="
set "npm_config_https_proxy="

"%OCODE_EXE%" %*

exit /b %errorlevel%
