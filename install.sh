#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 é obrigatório."
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "Node.js/npm é obrigatório."
  exit 1
fi

python3 -m venv .venv 2>/dev/null || python3 -m virtualenv .venv
.venv/bin/pip install -r backend/requirements.txt
(cd frontend && npm install)
echo "Instalação concluída. Rode: ./dev.sh"
