#!/usr/bin/env bash
# Instala o OpenClaw (agente local), registra a skill do monitor e agenda a supervisão.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILLS_DIR="${OPENCLAW_SKILLS_DIR:-$HOME/.openclaw/workspace/skills}"
EVERY="${SUPERVISE_EVERY:-15m}"

if ! command -v openclaw >/dev/null 2>&1; then
  command -v npm >/dev/null || { echo "Instale o Node.js 22+ (https://nodejs.org) e rode de novo."; exit 1; }
  npm install -g openclaw@latest
  echo ">> Rode 'openclaw onboard --install-daemon' e escolha o Ollama como provedor de modelo local."
fi

mkdir -p "$SKILLS_DIR"
rm -rf "$SKILLS_DIR/tiktok-repost-monitor"
cp -R "$ROOT/agent/openclaw/skills/tiktok-repost-monitor" "$SKILLS_DIR/"
echo ">> Skill instalada em $SKILLS_DIR/tiktok-repost-monitor"

if openclaw cron list 2>/dev/null | grep -q "tiktok-repost-supervisor"; then
  echo ">> Job de supervisão já existe."
else
  openclaw cron add \
    --name "tiktok-repost-supervisor" \
    --every "$EVERY" \
    --session isolated \
    --message "Use a skill tiktok-repost-monitor com REPOST_MONITOR_HOME=$ROOT: execute a ação 1 (garantir que o monitor está no ar) e depois a ação 2 (check). Responda só o resultado." \
    && echo ">> Supervisão agendada a cada $EVERY." \
    || echo ">> Não foi possível criar o job automaticamente; veja docs/AGENTE.md."
fi
