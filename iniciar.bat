@echo off
rem Inicia o monitor e abre o painel no navegador. Feche esta janela para parar.
cd /d "%~dp0"
start "" /b powershell -NoProfile -Command "Start-Sleep 4; Start-Process 'http://127.0.0.1:8000/'"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
pause
