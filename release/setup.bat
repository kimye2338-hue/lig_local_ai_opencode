@echo off
rem OpenCodeLIG installer shim - finds Python 3.11 then delegates ALL logic to
rem release\setup_impl.py (batch keeps zero logic; cmd pitfalls broke 3 installs).
chcp 65001 >nul
set PYTHONUTF8=1
setlocal
set "HERE=%~dp0"

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
    echo [STOP] Python 3.11 not found.
    echo        Check: open a new cmd and run  python --version  ^(need 3.11.x^),
    echo        or unzip release\prefetch\python-3.11.9-embed-amd64.zip and add to PATH.
    goto :the_end
)
echo [1/6] Python 3.11: %PYEXE%

%PYEXE% "%HERE%setup_impl.py"

:the_end
echo.
pause
