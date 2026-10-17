# ClaudeOS MCP Tool Server — Phase 12.2
# Starts the MCP server on port 5100 (configurable via MCP_PORT in .env)
# Allows Claude Desktop, Cursor, and any MCP client to call ClaudeOS agents as tools.

$ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $ROOT

# Load MCP_PORT from .env if present
$MCP_PORT = 5100
if (Test-Path ".env") {
    $envLine = Get-Content ".env" | Where-Object { $_ -match "^MCP_PORT=" }
    if ($envLine) { $MCP_PORT = ($envLine -split "=", 2)[1].Trim() }
}

Write-Host "Starting ClaudeOS MCP server on port $MCP_PORT..." -ForegroundColor Green

# Kill existing process on that port
$existing = netstat -ano | findstr ":$MCP_PORT " | ForEach-Object { ($_ -split "\s+")[-1] } | Select-Object -First 1
if ($existing -and $existing -match "^\d+$") {
    Write-Host "Killing existing process on port $MCP_PORT (PID $existing)..." -ForegroundColor Yellow
    taskkill /F /PID $existing 2>$null
    Start-Sleep -Seconds 1
}

Write-Host "MCP server URL: http://localhost:$MCP_PORT/mcp" -ForegroundColor Cyan
Write-Host "Add to Claude Desktop config:" -ForegroundColor Cyan
Write-Host '  "mcpServers": { "claudeos": { "url": "http://localhost:' + $MCP_PORT + '/mcp" } }' -ForegroundColor White
Write-Host ""

python -m mcp.server
