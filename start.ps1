# AI Legal Aid System - Startup Script (Production)
Write-Host ""
Write-Host " ==========================================" -ForegroundColor Cyan
Write-Host "  AI Legal Aid System - IBM WatsonX" -ForegroundColor Cyan
Write-Host "  Production Build" -ForegroundColor Cyan
Write-Host " ==========================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path ".env")) {
    Write-Host " ERROR: .env not found!" -ForegroundColor Red
    Write-Host " Copy .env.example to .env and set WATSONX_API_KEY" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"; exit 1
}

Write-Host " Installing/verifying dependencies..." -ForegroundColor Yellow
& py -m pip install -r requirements.txt -q

Write-Host ""
Write-Host " Starting server..." -ForegroundColor Green
Write-Host " URL: http://127.0.0.1:5000" -ForegroundColor Cyan
Write-Host " Admin: admin@legalaid.ai / Admin@1234" -ForegroundColor Yellow
Write-Host " Press Ctrl+C to stop." -ForegroundColor Gray
Write-Host ""

# Auto-open browser after 2s
Start-Job { Start-Sleep 2; Start-Process "http://127.0.0.1:5000" } | Out-Null

& py app.py
