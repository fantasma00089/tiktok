# Instala o OpenClaw (agente local), registra a skill do monitor e agenda a supervisão.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path "$PSScriptRoot\..\..").Path
$SkillsDir = if ($env:OPENCLAW_SKILLS_DIR) { $env:OPENCLAW_SKILLS_DIR } else { Join-Path $HOME ".openclaw\workspace\skills" }
$Every = if ($env:SUPERVISE_EVERY) { $env:SUPERVISE_EVERY } else { "15m" }

if (-not (Get-Command openclaw -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "Instale o Node.js 22+ (https://nodejs.org) e rode de novo." }
    npm install -g openclaw@latest
    Write-Host ">> Rode 'openclaw onboard --install-daemon' e escolha o Ollama como provedor de modelo local."
}

New-Item -ItemType Directory -Force -Path $SkillsDir | Out-Null
$Target = Join-Path $SkillsDir "tiktok-repost-monitor"
if (Test-Path $Target) { Remove-Item -Recurse -Force $Target }
Copy-Item -Recurse "$Root\agent\openclaw\skills\tiktok-repost-monitor" $SkillsDir
Write-Host ">> Skill instalada em $Target"

$existing = (openclaw cron list 2>$null) -join "`n"
if ($existing -match "tiktok-repost-supervisor") {
    Write-Host ">> Job de supervisão já existe."
} else {
    openclaw cron add --name "tiktok-repost-supervisor" --every $Every --session isolated `
        --message "Use a skill tiktok-repost-monitor com REPOST_MONITOR_HOME=$Root: execute a ação 1 (garantir que o monitor está no ar) e depois a ação 2 (check). Responda só o resultado."
    if ($LASTEXITCODE -eq 0) { Write-Host ">> Supervisão agendada a cada $Every." }
    else { Write-Host ">> Não foi possível criar o job automaticamente; veja docs/AGENTE.md." }
}
