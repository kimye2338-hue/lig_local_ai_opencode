@echo off
chcp 65001 >nul
setlocal EnableExtensions

rem OpenCodeLIG unified launcher
rem - loads userdata\secrets\lig-api.env
rem - starts hamster pet hidden (no extra console windows)
rem - opens only OpenCode main window

for %%I in ("%~dp0.") do set "AGENTOPS_HOME=%%~fI"
for %%I in ("%AGENTOPS_HOME%\..") do set "OC_ROOT=%%~fI"

set "OCODE_EXE=%OC_ROOT%\bin\opencode.exe"
set "OPENCODE_USERDATA=%OC_ROOT%\userdata"
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
if not exist "%LIG_API_ENV_FILE%" (
  echo [ERROR] lig-api.env not found:
  echo %LIG_API_ENV_FILE%
  echo.
  echo Fill this file first, then run again.
  pause
  exit /b 1
)

rem Load lig-api.env into shell environment as well.
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%LIG_API_ENV_FILE%") do (
  if not "%%A"=="" set "%%A=%%B"
)

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
