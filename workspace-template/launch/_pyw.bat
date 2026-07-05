@echo off
chcp 65001 >nul
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
echo [ERROR] Pythonw 3.11 not found.
echo Check: py -3.11 --version
exit /b 9
:ok
exit /b 0
