# ClaudeOS Stop Script
$FLASK_PORT = 5000
$STREAMLIT_PORT = 8501
$envFile = Join-Path (Split-Path -Parent $PSScriptRoot) ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^FLASK_PORT=(.+)$") { $FLASK_PORT = [int]$Matches[1] }
        if ($_ -match "^STREAMLIT_PORT=(.+)$") { $STREAMLIT_PORT = [int]$Matches[1] }
    }
}

foreach ($port in @($FLASK_PORT, $STREAMLIT_PORT)) {
    $lines = netstat -ano 2>$null | Select-String ":$port\s" | Select-String "LISTENING"
    foreach ($line in $lines) {
        $parts = $line.ToString().Trim() -split "\s+"
        $procId = $parts[-1]
        if ($procId -match "^\d+$" -and $procId -ne "0") {
            taskkill /F /PID $procId 2>$null | Out-Null
            Write-Host "Killed PID $procId on :$port" -ForegroundColor Yellow
        }
    }
}
Write-Host "ClaudeOS stopped." -ForegroundColor Green
