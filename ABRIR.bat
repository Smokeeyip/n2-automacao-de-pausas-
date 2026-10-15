@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0dist\N2.exe" (
    start "" "%~dp0dist\N2.exe"
    exit /b
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INICIAR.ps1"
if errorlevel 1 pause
