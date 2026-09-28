#!/usr/bin/env bash
# Cria o ambiente virtual do backend, instala dependências e gera o .env.
set -euo pipefail
cd "$(dirname "$0")/../backend"
PY="${PYTHON:-python3}"
"$PY" -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ é necessário"'
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -r requirements.txt
# Navegador usado pelo modo PROVIDER=browser (no Windows usamos o Edge instalado)
.venv/bin/python -m playwright install chromium
[ -f .env ] || { cp .env.example .env; echo ">> backend/.env criado — edite TIKTOK_USERNAME e PROVIDER."; }
.venv/bin/python -m repost_monitor doctor || true
