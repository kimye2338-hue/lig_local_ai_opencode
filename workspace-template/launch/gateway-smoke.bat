@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."

where py >nul 2>nul || (echo [ERROR] py launcher not found. Install Python 3.11. & exit /b 2)
py -3.11 --version >nul 2>nul || (echo [ERROR] Python 3.11 not found. & exit /b 2)

echo [1/2] Check lig-api.env
py -3.11 -c "from agent_ops.lig_providers import load_lig_env, validate_config; cfg=validate_config(load_lig_env()); print('ready:', cfg.get('ready')); [print('missing:', m) for m in cfg.get('missing', [])]; raise SystemExit(0 if cfg.get('ready') else 2)"
if errorlevel 2 (
    echo [STOP] Fill %%USERPROFILE%%\OpenCodeLIG_USERDATA\secrets\lig-api.env.
    exit /b 2
)

echo [2/2] Gateway 3-route smoke: lig-coding / lig-chat / lig-fallback
set "PROBE_OUT_DIR=%~dp0pilot_results\gateway"
py -3.11 agent_ops\probe_gateway.py
set RC=%errorlevel%
if not "%RC%"=="0" exit /b %RC%

echo [DONE] Result JSON: %PROBE_OUT_DIR%
exit /b 0
