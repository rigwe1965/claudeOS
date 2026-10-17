@echo off
REM Stops ClaudeOS (Flask + Streamlit).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\stop.ps1"
pause
