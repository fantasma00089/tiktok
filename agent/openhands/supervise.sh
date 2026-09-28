#!/usr/bin/env bash
# Loop de supervisão executado pelo agente dentro do sandbox do OpenHands.
# Consulta o monitor do host, força uma verificação e sinaliza reposts novos.
set -uo pipefail
API="${REPOST_API:-http://host.docker.internal:8000}"
TOKEN="${ADMIN_TOKEN:?defina ADMIN_TOKEN}"
EVERY="${SUPERVISE_EVERY_SECONDS:-300}"

while true; do
  if ! curl -fsS "$API/health" >/dev/null; then
    echo "ERRO monitor fora do ar em $API"
  else
    out="$(curl -fsS -X POST -H "Authorization: Bearer $TOKEN" "$API/api/check-now")" || out='{"ok":false,"erro":"falha na chamada"}'
    python3 - "$out" <<'PY'
import json, sys
d = json.loads(sys.argv[1])
if not d.get("ok"):
    print("ERRO", json.dumps({"erro": d.get("erro")}, ensure_ascii=False))
for r in d.get("novos_reposts") or []:
    print("REPOST_NOVO", r["url"])
PY
  fi
  sleep "$EVERY"
done
