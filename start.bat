@echo off
title AI Legal Aid System (Production)
echo.
echo  ==========================================
echo   AI Legal Aid System - IBM WatsonX
echo   Production Build
echo  ==========================================
echo.

if not exist ".env" (
    echo  ERROR: .env not found. Copy .env.example to .env and set WATSONX_API_KEY
    pause
    exit /b 1
)

echo  Installing/verifying dependencies...
py -m pip install -r requirements.txt -q

echo.
echo  Starting server...
echo  Open your browser at: http://127.0.0.1:5000
echo  Default admin: admin@legalaid.ai / Admin@1234
echo  Press Ctrl+C to stop.
echo.

py app.py
pause
