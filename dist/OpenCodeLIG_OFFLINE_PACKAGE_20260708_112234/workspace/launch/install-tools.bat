@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
rem 반입된 wheel(tools\wheelhouse)을 오프라인 설치한다 — 선택 기능 활성화:
rem  진짜 Office 파일 생성(openpyxl/python-docx/python-pptx),
rem  문서 읽기(markitdown), 화면 OCR(rapidocr). 인터넷 불필요.
set "HERE=%~dp0"
cd /d "%HERE%.."
call "%HERE%_py.bat"
if errorlevel 1 (
  echo [ERROR] Python 3.11 을 찾지 못했습니다.
  pause
  exit /b 9
)

set "WH=%CD%\tools\wheelhouse"
if not exist "%WH%" (
  echo [ERROR] wheelhouse 가 없습니다: %WH%
  echo   반입 패키지의 tools\wheelhouse 폴더가 있는지 확인하세요.
  pause
  exit /b 1
)

echo === 반입 wheel 오프라인 설치 시작 (%WH%) ===
%PY% -m pip install --no-index --find-links "%WH%" openpyxl python-docx python-pptx "markitdown[pdf,docx,pptx,xlsx]" rapidocr-onnxruntime
set RC=%errorlevel%
echo.
if "%RC%"=="0" (
  echo [OK] 설치 완료. 상태 확인: %PY% agent_ops\agentops.py deps
) else (
  echo [WARN] 일부 설치 실패(코드 %RC%). 위 로그를 확인하세요.
)
pause
exit /b %RC%
