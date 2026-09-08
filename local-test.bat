@echo off
rem ---------------------------------------------------------------
rem  Build and run the app locally, then check it is really alive.
rem  Just double-click this file. Needs Docker Desktop running.
rem
rem  IMPORTANT: this file must stay ASCII-only.  After "chcp 65001"
rem  cmd re-reads the rest of the file at a byte offset, so any
rem  multi-byte text - even in a rem comment - breaks parsing.
rem  All Korean wording lives in tools/local_up.ps1.
rem ---------------------------------------------------------------

cd /d "%~dp0"
chcp 65001 > nul

powershell -NoProfile -ExecutionPolicy Bypass -File "tools\local_up.ps1"

echo.
pause
