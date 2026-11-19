@echo off
REM Convenience wrapper — the real launcher is the cross-platform run.py.
REM   run.bat                 - foreground (Ctrl+C to stop)
REM   run.bat start ^| stop ^| status
REM   run.bat --demo ^| --port 9000
setlocal
cd /d "%~dp0"
python run.py %*
endlocal
