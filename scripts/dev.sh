#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Ambiente Python ausente. Rode: make install"
  exit 1
fi
if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  echo "Dependências do frontend ausentes. Rode: make install"
  exit 1
fi

export PYTHONPATH="$ROOT/backend"
trap 'kill 0' EXIT
"$ROOT/.venv/bin/uvicorn" app.main:app --app-dir "$ROOT/backend" --host 0.0.0.0 --port 8000 --reload &
(cd "$ROOT/frontend" && npm run dev) &
wait
