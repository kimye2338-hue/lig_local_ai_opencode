@echo off
rem OpenCodeLIG offline setup — installs from bundled wheels only (no internet).
rem Usage: setup.bat        (run from the unzipped bundle root)
rem AGENTS.md constraints: no -ExecutionPolicy Bypass, no internet (pip --no-index).
chcp 65001 >nul
set PYTHONUTF8=1
setlocal enabledelayedexpansion
set ROOT=%~dp0
set TARGET=%USERPROFILE%\OpenCodeLIG
set USERDATA=%USERPROFILE%\OpenCodeLIG_USERDATA
set FAIL=0

echo === OpenCodeLIG offline setup ===

rem --- 1. Python 3.11 present? ---
py -3.11 --version >nul 2>&1
if errorlevel 1 (
    echo [STOP] Python 3.11 not found via 'py -3.11'.
    echo        Install the bundled python-embed ^(release\vendor\python-embed\^) or
    echo        company Python 3.11, then re-run setup.bat.
    exit /b 9
)
echo [OK] Python 3.11 present.

rem --- 2. Offline wheel install (no index, bundled wheels only) ---
if exist "%ROOT%release\prefetch\" (
    echo [..] Installing bundled wheels ^(--no-index^) ...
    py -3.11 -m pip install --no-index --find-links "%ROOT%release\prefetch" pywin32 openpyxl python-pptx >"%TEMP%\opencodelig_pip.log" 2>&1
    if errorlevel 1 (
        echo [WARN] wheel install reported an error. See %TEMP%\opencodelig_pip.log
        echo        Core agent_ops is stdlib-only and still works; COM/office features
        echo        need these wheels. Continuing.
        set FAIL=1
    ) else (
        echo [OK] Wheels installed ^(pywin32/openpyxl/python-pptx^).
    )
) else (
    echo [WARN] No release\prefetch\ in bundle — skipping wheel install.
    echo        Core stdlib runtime works; office/COM adapters stay unavailable.
)

rem --- 3. Place the workspace ---
echo [..] Placing workspace at %TARGET% ...
if not exist "%TARGET%" mkdir "%TARGET%"
xcopy "%ROOT%workspace-template" "%TARGET%\workspace\" /E /I /Y /Q >nul
if errorlevel 1 (
    echo [STOP] Failed to copy workspace-template to %TARGET%\workspace.
    echo        Check disk space and write permission on %USERPROFILE%.
    exit /b 3
)
echo [OK] Workspace at %TARGET%\workspace.

rem --- 4. USERDATA folders ---
if not exist "%USERDATA%" mkdir "%USERDATA%"
if not exist "%USERDATA%\diagnostics" mkdir "%USERDATA%\diagnostics"
if not exist "%USERDATA%\audit" mkdir "%USERDATA%\audit"
if not exist "%USERDATA%\secrets" mkdir "%USERDATA%\secrets"
echo [OK] USERDATA at %USERDATA%.

rem --- 5. doctor ---
echo [..] Running doctor ...
pushd "%TARGET%\workspace"
py -3.11 agent_ops\agentops.py doctor >"%USERDATA%\diagnostics\setup_doctor.txt" 2>&1
set DOCTOR_RC=%errorlevel%
popd
if not "%DOCTOR_RC%"=="0" (
    echo [WARN] doctor exit %DOCTOR_RC% — see %USERDATA%\diagnostics\setup_doctor.txt
    set FAIL=1
) else (
    echo [OK] doctor completed ^(report: %USERDATA%\diagnostics\setup_doctor.txt^).
)

rem --- 6. summary ---
echo.
echo === Setup summary ===
if "%FAIL%"=="0" (
    echo [DONE] All steps OK.
) else (
    echo [DONE with warnings] Review the messages above.
)
echo Next: fill %USERDATA%\secrets\lig-api.env ^(NEVER commit it^), then
echo       run  %TARGET%\workspace\launch\gateway-smoke.bat  and follow docs\PILOT_DAY1.md.
exit /b 0
