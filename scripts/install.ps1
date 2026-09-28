# Cria o ambiente virtual do backend, instala dependências e gera o .env (Windows).
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\backend"
$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
& $py -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10+ e necessario'"
if (-not (Test-Path .venv)) { & $py -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip | Out-Null
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
# O modo navegador usa o Microsoft Edge que ja vem no Windows (nada para baixar).
$edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ }
if (-not $edge) {
    Write-Host ">> Edge nao encontrado; baixando o Chromium do Playwright..."
    & .\.venv\Scripts\python.exe -m playwright install chromium
    Write-Host ">> Coloque BROWSER_CHANNEL= (vazio) no backend\.env para usar esse Chromium."
}
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host ">> backend\.env criado - edite TIKTOK_USERNAME e PROVIDER."
}
& .\.venv\Scripts\python.exe -m repost_monitor doctor
