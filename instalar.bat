@echo off
rem Instala o monitor (ambiente Python + dependencias + backend\.env).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
echo.
echo Pronto. Edite backend\.env (TIKTOK_USERNAME e PROVIDER) e depois rode iniciar.bat
pause
