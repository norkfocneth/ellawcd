@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
"%SCRIPT_DIR%.python\python.exe" "%SCRIPT_DIR%main.py" %*
