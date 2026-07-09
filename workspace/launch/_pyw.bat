@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "LITELLM_LOCAL_MODEL_COST_MAP=True"
set "LITELLM_LOCAL_POLICY_TEMPLATES=True"
set "LITELLM_LOCAL_BLOG_POSTS=True"
rem Shared Pythonw 3.11 resolver. Sets %PYW% for the calling BAT. Exit 9 if none.
set "PYW="
pyw -3.11 -c "pass" >nul 2>&1 && set "PYW=pyw -3.11"
if defined PYW goto :ok
if exist "%LocalAppData%\Programs\Python\Python311\pythonw.exe" set "PYW=%LocalAppData%\Programs\Python\Python311\pythonw.exe"
if defined PYW goto :ok
if exist "%ProgramFiles%\Python311\pythonw.exe" set "PYW=%ProgramFiles%\Python311\pythonw.exe"
if defined PYW goto :ok
where pythonw >nul 2>&1 && set "PYW=pythonw"
if defined PYW goto :ok
echo [ERROR] Pythonw 3.11을 찾지 못했습니다.
echo         새 명령창에서 py -3.11 --version 또는 python --version 이 3.11.x 인지 확인하세요.
exit /b 9
:ok
exit /b 0
