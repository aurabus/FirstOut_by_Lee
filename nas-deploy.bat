@echo off
rem ---------------------------------------------------------------
rem  Push the current code to the NAS and (re)start the services.
rem  Just double-click this file.
rem
rem  IMPORTANT: this file must stay ASCII-only.  After "chcp 65001"
rem  cmd re-reads the rest of the file at a byte offset, so any
rem  multi-byte text - even in a rem comment - breaks parsing.
rem  All Korean wording lives in tools/nas_deploy.ps1.
rem ---------------------------------------------------------------

cd /d "%~dp0"
chcp 65001 > nul

powershell -NoProfile -ExecutionPolicy Bypass -File "tools\nas_deploy.ps1"

echo.
pause
