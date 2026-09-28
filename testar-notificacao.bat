@echo off
rem Mostra uma notificacao de teste do Windows.
cd /d "%~dp0backend"
.venv\Scripts\python.exe -m repost_monitor test-notification
pause
