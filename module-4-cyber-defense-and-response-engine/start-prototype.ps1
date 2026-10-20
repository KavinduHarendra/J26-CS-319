# Autonomous Cyber Defense Prototype - Startup Script
Write-Host "Starting UAV Cyber Defense Research Prototype..." -ForegroundColor Cyan
Write-Host "RESEARCH PROTOTYPE - Simulated Data Only" -ForegroundColor Yellow

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Start backend
Write-Host "`nStarting FastAPI backend on http://127.0.0.1:8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; py -m uvicorn main:app --reload --port 8000"

Start-Sleep -Seconds 3

# Start frontend
Write-Host "Starting React frontend on http://localhost:5173 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev"

Start-Sleep -Seconds 5

Write-Host "`nOpening browser..." -ForegroundColor Green
Start-Process "http://localhost:5173"

Write-Host "`nWorkflow: Defense Evaluation, upload JSON files, review risk and recommendation, inspect audit log" -ForegroundColor Cyan
