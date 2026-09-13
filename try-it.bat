@echo off
rem ---------------------------------------------------------------
rem  Practice on a throwaway copy.  Double-click this file.
rem
rem  Opens the pilot kindergarten in a temporary data folder,
rem  waits while you click around, and deletes everything on exit.
rem  Neither your working data nor the NAS is touched.
rem
rem  Pass /auto to walk the whole scenario by itself instead.
rem
rem  IMPORTANT: this file must stay ASCII-only.  After "chcp 65001"
rem  cmd re-reads the rest of the file at a byte offset, so any
rem  multi-byte text - even in a rem comment - breaks parsing.
rem ---------------------------------------------------------------

cd /d "%~dp0"
chcp 65001 > nul
set PYTHONUTF8=1

if /i "%~1"=="/auto" (
    python tools\scenario.py
) else (
    python tools\scenario.py --hand
)

echo.
pause
