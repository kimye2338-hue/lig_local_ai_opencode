@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
rem ocd - 현재 폴더에서 OpenCodeLIG 를 연다(폴더-로컬 프로필 + 전역 기억).
rem 설치기가 이 파일을 %USERPROFILE%\OpenCodeLIG\bin\ocd.bat 로 복사하고
rem %BIN% 을 사용자 PATH 에 등록하므로, 아무 폴더의 새 CMD 창에서 그냥 `ocd`.
set "OCDPY=%USERPROFILE%\OpenCodeLIG\workspace\agent_ops\ocd.py"
if not exist "%OCDPY%" (
  echo [ERROR] OpenCodeLIG 가 설치되어 있지 않습니다: %OCDPY%
  exit /b 9
)
rem py 런처가 있으면 3.11 로, 없으면 python 으로 (이중 실행 방지: 한 쪽만).
where py >nul 2>nul
if %errorlevel%==0 (
  set "PY_CMD=py -3.11 -X utf8"
  %PY_CMD% "%OCDPY%" %*
) else (
  python -X utf8 "%OCDPY%" %*
)
