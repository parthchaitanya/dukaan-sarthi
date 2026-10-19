#!/usr/bin/env bash
# One command: install, seed demo data, compute metrics, start the app on http://localhost:8000
set -e
cd "$(dirname "$0")"
python3 -m pip install -q -r requirements.txt
[ -f data/dukaan.db ] || python3 -m backend.seed
[ -f data/metrics.json ] || python3 -m backend.metrics > /dev/null
echo "Dukaan Sarthi running at http://localhost:8000  (metrics: http://localhost:8000/metrics)"
exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
