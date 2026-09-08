@echo off
rem ---------------------------------------------------------------
rem  Homepage file checker - just double-click this file.
rem
rem  IMPORTANT: this file must stay ASCII-only.
rem  Once "chcp 65001" switches the code page, cmd re-reads the rest
rem  of the file at a byte offset; any multi-byte text - even inside
rem  a rem comment - shifts everything and cmd runs the garbage as
rem  commands. All Korean wording lives in tools/site_check.py.
rem ---------------------------------------------------------------

cd /d "%~dp0"
chcp 65001 > nul
set PYTHONUTF8=1

echo.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" tools\site_check.py
) else (
    python tools\site_check.py
)

if errorlevel 9009 (
    echo.
    echo   [!] Python not found. Install it from python.org and retry.
)

echo.
pause
