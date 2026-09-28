@echo off
rem Teste (PROVIDER=mock): cria um repost falso e verifica na hora.
cd /d "%~dp0backend"
.venv\Scripts\python.exe -m repost_monitor simulate
.venv\Scripts\python.exe -m repost_monitor check
pause
