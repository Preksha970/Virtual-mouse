@echo off
title AeroLock - AI Virtual Mouse & Gesture Security System
cd /d "%~dp0"

echo ==========================================================
echo    AEROLOCK // AI VIRTUAL MOUSE ^& GESTURE SECURITY SYSTEM
echo ==========================================================
echo.
echo Starting AeroLock application...
echo Web Dashboard will be available at: http://127.0.0.1:5000
echo.

python app.py %*

if %errorlevel% neq 0 (
    echo.
    echo [!] Application exited with an error.
    pause
)
