@echo off
rem Verifica os reposts agora (abre o navegador invisivel e le a aba Reposts).
cd /d "%~dp0backend"
.venv\Scripts\python.exe -m repost_monitor check
echo.
if %ERRORLEVEL%==10 (echo REPOST NOVO DETECTADO!) else if %ERRORLEVEL%==0 (echo Nenhum repost novo.) else (echo Deu erro - veja a mensagem acima.)
pause
