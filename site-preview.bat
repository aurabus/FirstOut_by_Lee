@echo off
rem ---------------------------------------------------------------
rem  Homepage local preview - just double-click this file.
rem  A browser opens at http://127.0.0.1:8080/
rem  Close this window (or press Ctrl+C) to stop.
rem
rem  IMPORTANT: this file must stay ASCII-only.  After "chcp 65001"
rem  cmd re-reads the rest of the file at a byte offset, so any
rem  multi-byte text - even in a rem comment - breaks parsing.
rem  All Korean wording lives in tools/site_serve.py.
rem ---------------------------------------------------------------

cd /d "%~dp0"
chcp 65001 > nul
set PYTHONUTF8=1

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" tools\site_serve.py
) else (
    python tools\site_serve.py
)

if errorlevel 9009 (
    echo.
    echo   [!] Python not found. Install it from python.org and retry.
    echo.
    pause
)
