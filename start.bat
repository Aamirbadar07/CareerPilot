@echo off
title CareerPilot Launcher
echo Starting CareerPilot Full-Stack Platform...

cd /d "%~dp0backend"
echo [1/3] Ensuring database migrations are up to date...
start "CareerPilot Backend" cmd /k "title CareerPilot Backend API && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000"

timeout /t 2 /nobreak > nul

cd /d "%~dp0frontend"
echo [2/3] Starting Next.js frontend...
start "CareerPilot Frontend" cmd /k "title CareerPilot Frontend && npm run dev"

timeout /t 3 /nobreak > nul

echo [3/3] Opening CareerPilot in your browser...
start http://localhost:3000

echo.
echo ========================================================
echo   CareerPilot is running!
echo   - Frontend: http://localhost:3000
echo   - Backend:  http://127.0.0.1:8000
echo   - Health:   http://127.0.0.1:8000/health
echo ========================================================
echo.
