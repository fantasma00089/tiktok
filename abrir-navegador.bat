@echo off
rem Abre o navegador do monitor (visivel) no perfil configurado.
rem Use se o TikTok pedir login ou captcha: resolva na janela e FECHE-A ao terminar.
cd /d "%~dp0backend"
.venv\Scripts\python.exe -m repost_monitor abrir-navegador
pause
