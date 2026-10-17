# ClaudeOS Startup Script - Windows PowerShell
# Usage: .\scripts\start.ps1

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "  ClaudeOS v1.0.0 - Starting..." -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""

# Prefer the project virtualenv when present
$PY = if (Test-Path (Join-Path $ROOT ".venv\Scripts\python.exe")) { Join-Path $ROOT ".venv\Scripts\python.exe" } else { "python" }

# Load .env to read ports
$FLASK_PORT = 5000
$STREAMLIT_PORT = 8501
$envFile = Join-Path $ROOT ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^FLASK_PORT=(.+)$") { $FLASK_PORT = [int]$Matches[1] }
        if ($_ -match "^STREAMLIT_PORT=(.+)$") { $STREAMLIT_PORT = [int]$Matches[1] }
    }
}

# Kill existing processes on ports
foreach ($port in @($FLASK_PORT, $STREAMLIT_PORT)) {
    $lines = netstat -ano 2>$null | Select-String ":$port\s"
    foreach ($line in $lines) {
        $parts = $line.ToString().Trim() -split "\s+"
        $procId = $parts[-1]
        if ($procId -match "^\d+$" -and $procId -ne "0") {
            try { taskkill /F /PID $procId 2>$null | Out-Null } catch {}
        }
    }
}

Start-Sleep 1

# Migrations run automatically inside Flask create_app() — no separate step needed.

# Start Flask API via waitress in background
# Use Start-Process (not Start-Job) — inherits PATH and env vars correctly.
Write-Host "Starting API on :$FLASK_PORT ..." -ForegroundColor Cyan
$apiProc = Start-Process -FilePath $PY `
    -ArgumentList "scripts\serve_api.py", $FLASK_PORT `
    -WorkingDirectory $ROOT `
    -PassThru `
    -WindowStyle Hidden

# Wait for API with retries (60s window — Python imports + migrations take ~15-35s)
$apiReady = $false
Start-Sleep 1
for ($i = 1; $i -le 60; $i++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$FLASK_PORT/api/v1/health" -TimeoutSec 3
        if ($health.status -eq "ok") {
            Write-Host "  API: RUNNING on :$FLASK_PORT  (v$($health.version))" -ForegroundColor Green
            $apiReady = $true
            break
        }
    } catch {}
    Start-Sleep 1
}
if (-not $apiReady) {
    Write-Host "  API: FAILED to start - check logs/api.log" -ForegroundColor Red
    if ($apiProc -and -not $apiProc.HasExited) { $apiProc.Kill() }
    exit 1
}

Write-Host ""
Write-Host "Starting Dashboard on :$STREAMLIT_PORT ..." -ForegroundColor Cyan
Write-Host "(Press Ctrl+C to stop)" -ForegroundColor DarkGray
Write-Host ""

# Start Streamlit (foreground)
Set-Location $ROOT
$env:CLAUDEOS_DEV_API_KEY = if (Test-Path $envFile) { (Get-Content $envFile | Select-String "CLAUDEOS_DEV_API_KEY=(.+)").Matches.Groups[1].Value } else { "" }
& $PY -m streamlit run dashboard\app.py --server.port $STREAMLIT_PORT --server.headless true
