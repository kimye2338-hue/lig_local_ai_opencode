@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
where py >nul 2>nul || (echo [오류] py 런처가 없습니다. Python 3.11을 설치하세요. & exit /b 2)
py -3.11 --version >nul 2>nul || (echo [오류] Python 3.11이 없습니다. & exit /b 2)

set "CHROME_EXE="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_EXE if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_EXE if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_EXE (
    echo [오류] Chrome 실행 파일을 찾지 못했습니다.
    exit /b 2
)

set "OPEN_CODE_LIG_CHROME_PROFILE=%TEMP%\opencodelig_chrome"
echo Chrome CDP profile: %OPEN_CODE_LIG_CHROME_PROFILE%
echo Chrome CDP endpoint: http://127.0.0.1:9222/json
start "" "%CHROME_EXE%" --remote-debugging-port=9222 --user-data-dir="%OPEN_CODE_LIG_CHROME_PROFILE%" about:blank
exit /b 0
