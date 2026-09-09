@echo off
setlocal
set "ELLA_DIR=c:\Users\FOCNETH\OneDrive\Desktop\ellawcd"
pushd "%ELLA_DIR%"
if exist "%ELLA_DIR%\.venv\Scripts\python.exe" (
    "%ELLA_DIR%\.venv\Scripts\python.exe" "%ELLA_DIR%\main.py" %*
) else (
    python "%ELLA_DIR%\main.py" %*
)
popd
