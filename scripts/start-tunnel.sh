#!/usr/bin/env bash
# Expõe o endpoint /status local na internet.
#   ./start-tunnel.sh cloudflare   -> Cloudflare Quick Tunnel (URL *.trycloudflare.com, muda a cada execução)
#   ./start-tunnel.sh ngrok [dominio.ngrok-free.app]
set -euo pipefail
PORT="${PORT:-8000}"
case "${1:-cloudflare}" in
  cloudflare) exec cloudflared tunnel --url "http://localhost:$PORT" ;;
  ngrok) if [ -n "${2:-}" ]; then exec ngrok http --url="$2" "$PORT"; else exec ngrok http "$PORT"; fi ;;
  *) echo "uso: $0 [cloudflare|ngrok [dominio]]"; exit 1 ;;
esac
