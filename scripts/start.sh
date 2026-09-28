#!/usr/bin/env bash
# Inicia o monitor (polling + /status + painel em http://127.0.0.1:8000/).
#   ./start.sh               em primeiro plano
#   ./start.sh --background  em segundo plano (log em backend/logs/run.out)
set -euo pipefail
cd "$(dirname "$0")/../backend"
PY=.venv/bin/python
[ -x "$PY" ] || PY=python3
if [ "${1:-}" = "--background" ]; then
  mkdir -p logs
  nohup "$PY" -m repost_monitor run >> logs/run.out 2>&1 &
  echo "Monitor iniciado em segundo plano (PID $!)."
else
  exec "$PY" -m repost_monitor run
fi
