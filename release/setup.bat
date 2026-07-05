@echo off
rem OpenCodeLIG one-shot offline installer. Double-click and follow 1-2 prompts.
rem No internet used (pip --no-index). No -ExecutionPolicy Bypass.
chcp 65001 >nul
set PYTHONUTF8=1
setlocal
rem 이 파일은 번들의 release\ 안에 있다 — 번들 루트는 한 단계 위.
for %%I in ("%~dp0..") do set "ROOT=%%~fI\"
rem 안전망: 혹시 다른 위치에서 실행되면 workspace-template가 보이는 쪽을 루트로.
if not exist "%ROOT%workspace-template\" if exist "%~dp0workspace-template\" set "ROOT=%~dp0"
if not exist "%ROOT%workspace-template\" if exist "%CD%\workspace-template\" set "ROOT=%CD%\"
set "TARGET=%USERPROFILE%\OpenCodeLIG"
set "USERDATA=%USERPROFILE%\OpenCodeLIG_USERDATA"
set "ENVFILE=%USERDATA%\secrets\lig-api.env"
set "FAIL=0"

echo.
echo  ==============================================
echo    OpenCodeLIG 설치를 시작합니다 (오프라인)
echo  ==============================================
echo.
if not exist "%ROOT%workspace-template\" (
    echo [중단] 번들 구조를 찾지 못했습니다 ^(workspace-template 폴더 없음^).
    echo        zip을 통째로 푼 폴더에서  설치.bat  을 실행했는지 확인하세요.
    echo        탐색 위치: %ROOT%
    goto :the_end
)

rem --- 1. Python 3.11 찾기 (py -3.11 / python / python3.11 / python3) ---
set "PYEXE="
py -3.11 --version >nul 2>&1 && set "PYEXE=py -3.11"
if not defined PYEXE (
    for %%P in (python python3.11 python3) do (
        if not defined PYEXE (
            for /f "tokens=2" %%V in ('%%P --version 2^>^&1') do (
                echo %%V | findstr /b /c:"3.11." >nul && set "PYEXE=%%P"
            )
        )
    )
)
if not defined PYEXE (
    echo [중단] Python 3.11 을 찾지 못했습니다.
    echo        새 명령창에서 python --version 이 3.11.x 로 나오는지 확인하세요.
    echo        없다면 release\prefetch\python-3.11.9-embed-amd64.zip 을 풀어 PATH에 추가한 뒤
    echo        이 파일을 다시 실행하세요.
    goto :the_end
)
echo [1/6] Python 3.11 확인: %PYEXE%

rem --- 2. 오프라인 wheel 설치 ---
if exist "%ROOT%release\prefetch\" (
    echo [2/6] 부속 라이브러리 설치 중 ^(인터넷 사용 안 함^) ...
    %PYEXE% -m pip install --no-index --find-links "%ROOT%release\prefetch" pywin32 openpyxl python-pptx >"%TEMP%\opencodelig_pip.log" 2>&1
    if errorlevel 1 (
        echo [주의] 일부 라이브러리 설치 실패 — 로그: %TEMP%\opencodelig_pip.log
        echo        핵심 기능은 그대로 동작합니다. 엑셀/오피스 자동화만 제한될 수 있습니다.
        set "FAIL=1"
    ) else (
        echo        완료.
    )
) else (
    echo [2/6] 번들에 라이브러리가 없어 건너뜁니다 ^(핵심 기능은 동작^).
)

rem --- 3. 프로그램 배치 ---
echo [3/6] 프로그램 설치 중: %TARGET%\workspace ...
if not exist "%TARGET%" mkdir "%TARGET%"
xcopy "%ROOT%workspace-template" "%TARGET%\workspace\" /E /I /Y /Q >nul
if errorlevel 1 (
    echo [중단] 파일 복사 실패. 디스크 공간/쓰기 권한을 확인하세요.
    goto :the_end
)
echo        완료.

rem --- 4. 데이터 폴더 ---
if not exist "%USERDATA%" mkdir "%USERDATA%"
if not exist "%USERDATA%\diagnostics" mkdir "%USERDATA%\diagnostics"
if not exist "%USERDATA%\audit" mkdir "%USERDATA%\audit"
if not exist "%USERDATA%\secrets" mkdir "%USERDATA%\secrets"
echo [4/6] 데이터 폴더 준비: %USERDATA%

rem --- 5. 게이트웨이(사내 LLM) 설정 ---
if exist "%ENVFILE%" (
    echo [5/6] 게이트웨이 설정: 기존 설정 발견 — 그대로 사용합니다.
    goto :after_env
)
echo [5/6] 게이트웨이^(사내 LLM^) 설정 — 모르면 그냥 Enter 두 번 ^(나중에 설정 가능^).
set "GWURL="
set /p GWURL=  게이트웨이 주소 붙여넣기 (예: http://호스트):
set "GWKEY="
set /p GWKEY=  API 키 붙여넣기:
> "%ENVFILE%" echo # LIG 사내 게이트웨이 설정 - 이 파일은 절대 커밋/반출 금지
if defined GWURL (
    >> "%ENVFILE%" echo LIG_GATEWAY_BASE_URL=%GWURL%
) else (
    >> "%ENVFILE%" echo LIG_GATEWAY_BASE_URL=REPLACE_WITH_GATEWAY_URL
)
if defined GWKEY (
    >> "%ENVFILE%" echo LIG_API_KEY=%GWKEY%
) else (
    >> "%ENVFILE%" echo LIG_API_KEY=REPLACE_WITH_KEY
)
if defined GWURL (
    echo        저장됨: %ENVFILE%
) else (
    echo        건너뜀 — 나중에 %ENVFILE% 파일을 열어 두 값을 채우면 됩니다.
)
:after_env

rem --- 6. 자가 진단 + 바탕화면 바로가기 ---
echo [6/6] 자가 진단 중 ...
pushd "%TARGET%\workspace"
%PYEXE% agent_ops\agentops.py doctor >"%USERDATA%\diagnostics\setup_doctor.txt" 2>&1
set "DOCTOR_RC=%errorlevel%"
popd
if not "%DOCTOR_RC%"=="0" (
    echo [주의] 진단에서 경고 — %USERDATA%\diagnostics\setup_doctor.txt 참고.
    set "FAIL=1"
) else (
    echo        정상.
)
if exist "%USERPROFILE%\Desktop\" (
    > "%USERPROFILE%\Desktop\AI비서.bat" echo @echo off
    >> "%USERPROFILE%\Desktop\AI비서.bat" echo cd /d "%%USERPROFILE%%\OpenCodeLIG\workspace\launch"
    >> "%USERPROFILE%\Desktop\AI비서.bat" echo call "AI비서.bat"
    echo        바탕화면에 [AI비서] 바로가기를 만들었습니다.
) else (
    echo        바탕화면 폴더를 찾지 못해 바로가기는 건너뜁니다.
    echo        직접 실행 경로: %TARGET%\workspace\launch\AI비서.bat
)

echo.
echo  ==============================================
if "%FAIL%"=="0" (
    echo    설치 완료. 바탕화면의 [AI비서] 를 실행하세요.
) else (
    echo    설치 완료 ^(일부 경고 있음 - 위 메시지 참고^).
    echo    바탕화면의 [AI비서] 를 실행하세요.
)
echo  ==============================================

:the_end
echo.
pause
