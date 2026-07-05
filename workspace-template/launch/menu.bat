@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title AI(OpenCodeLIG)
set "HERE=%~dp0"
call "%HERE%_py.bat" || (pause & exit /b 9)
%PY% "%HERE%..\agent_ops\menu.py"
