# Expõe o endpoint /status local na internet.
#   .\start-tunnel.ps1 cloudflare
#   .\start-tunnel.ps1 ngrok [dominio.ngrok-free.app]
param([string]$Kind = "cloudflare", [string]$Domain = "")
$port = if ($env:PORT) { $env:PORT } else { "8000" }
switch ($Kind) {
    "cloudflare" { cloudflared tunnel --url "http://localhost:$port" }
    "ngrok" { if ($Domain) { ngrok http --url=$Domain $port } else { ngrok http $port } }
    default { Write-Host "uso: .\start-tunnel.ps1 [cloudflare|ngrok [dominio]]" }
}
