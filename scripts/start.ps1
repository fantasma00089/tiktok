# Inicia o monitor (polling + /status + painel em http://127.0.0.1:8000/).
#   .\start.ps1              em primeiro plano
#   .\start.ps1 -Background  em segundo plano, sem janela
param([switch]$Background)
Set-Location "$PSScriptRoot\..\backend"
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
if ($Background) {
    $pyw = ".\.venv\Scripts\pythonw.exe"
    if (-not (Test-Path $pyw)) { $pyw = $py }
    Start-Process -FilePath $pyw -ArgumentList "-m", "repost_monitor", "run" -WindowStyle Hidden -WorkingDirectory (Get-Location)
    Write-Host "Monitor iniciado em segundo plano. Painel: http://127.0.0.1:8000/"
} else {
    & $py -m repost_monitor run
}
