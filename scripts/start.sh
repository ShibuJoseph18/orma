#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -d "$HOME/.nvm" ]; then
  export NVM_DIR="$HOME/.nvm"
  source "$NVM_DIR/nvm.sh"
fi
if [ ! -x .venv/bin/python ]; then
  uv venv --python 3.13 .venv
  uv pip install --python .venv/bin/python -r backend/requirements.txt
fi
if [ ! -d node_modules ]; then npm install; fi
if [ ! -f backend/.env ]; then cp backend/.env.example backend/.env; fi
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
orma_api_pid=$!
trap 'kill "$orma_api_pid" 2>/dev/null || true' EXIT INT TERM
npm run dev
