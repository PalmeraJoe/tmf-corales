#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
cd "$root"
python3 -m pip install -r "$root/requirements.txt"
cd "$root/frontend"
if [[ ! -d node_modules ]]; then
  npm install
fi
npm run build
cd "$root"
export PYTHONPATH="$root/backend"
echo "Caleta en http://127.0.0.1:8010"
exec python3 -m uvicorn caleta.main:app --host 127.0.0.1 --port 8010
