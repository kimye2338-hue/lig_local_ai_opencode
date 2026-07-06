@echo off
chcp 65001 >nul
setlocal EnableExtensions
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "HERE=%~dp0"
for %%I in ("%HERE%..") do set "APP=%%~fI"
for %%I in ("%APP%\..") do set "ROOT=%%~fI"
rem 위키 vault = USERDATA\memory\wiki (불가침)
if not defined LIG_MEMORY_DIR set "LIG_MEMORY_DIR=%ROOT%\userdata\memory"
set "VAULT=%LIG_MEMORY_DIR%\wiki"
if not exist "%VAULT%" mkdir "%VAULT%" >nul 2>&1

rem 1) Obsidian vault 설정 시드(없을 때만)
call "%HERE%_py.bat" || goto :openonly
cd /d "%APP%"
%PY% -m agent_ops.wiki_vault "%VAULT%"

rem 2) Obsidian 실행: tools\Obsidian(포터블) > 설치본 > 탐색기 폴백
:openonly
set "OBS_PORTABLE=%ROOT%\tools\Obsidian\Obsidian.exe"
set "OBS_INSTALLED=%LOCALAPPDATA%\Obsidian\Obsidian.exe"
if exist "%OBS_PORTABLE%" (
  start "" "%OBS_PORTABLE%" "%VAULT%"
  goto :done
)
if exist "%OBS_INSTALLED%" (
  start "" "%OBS_INSTALLED%" "%VAULT%"
  goto :done
)
echo [안내] Obsidian을 찾지 못했습니다. 탐색기로 위키 폴더만 엽니다.
echo         tools\Obsidian\Obsidian.exe 로 포터블을 넣거나 Obsidian을 설치하세요.
start "" explorer "%VAULT%"
:done
exit /b 0
