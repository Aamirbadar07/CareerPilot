# CareerPilot PowerShell Launcher
Write-Host "Starting CareerPilot Full-Stack Platform..." -ForegroundColor Cyan

$root = $PSScriptRoot
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

Write-Host "[1/3] Starting Backend API on http://127.0.0.1:8000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$backendDir'; uv run uvicorn app.main:app --host 127.0.0.1 --port 8000"

Start-Sleep -Seconds 2

Write-Host "[2/3] Starting Frontend UI on http://localhost:3000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$frontendDir'; npm run dev"

Start-Sleep -Seconds 3

Write-Host "[3/3] Opening CareerPilot in your default browser..." -ForegroundColor Yellow
Start-Process "http://localhost:3000"

Write-Host "`nCareerPilot is live!" -ForegroundColor Green
Write-Host "  - Frontend: http://localhost:3000"
Write-Host "  - Backend:  http://127.0.0.1:8000"
Write-Host "  - Health:   http://127.0.0.1:8000/health`n"
