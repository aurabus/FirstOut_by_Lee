@echo off
rem ---------------------------------------------------------------
rem  Build a .tar image file to upload into Container Manager.
rem  Just double-click this file. Needs Docker Desktop running.
rem
rem  IMPORTANT: this file must stay ASCII-only.  After "chcp 65001"
rem  cmd re-reads the rest of the file at a byte offset, so any
rem  multi-byte text - even in a rem comment - breaks parsing.
rem  All Korean wording lives in tools/make_image.ps1.
rem ---------------------------------------------------------------

cd /d "%~dp0"
chcp 65001 > nul

powershell -NoProfile -ExecutionPolicy Bypass -File "tools\make_image.ps1"

echo.
pause
