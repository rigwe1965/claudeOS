@echo off
REM Starts ClaudeOS (Flask API + Streamlit dashboard). Double-click to run.
cd /d "%~dp0"
start "" /b cmd /c "timeout /t 25 /nobreak >nul & start http://localhost:8501"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\start.ps1"
echo.
echo ClaudeOS stopped.
pause
