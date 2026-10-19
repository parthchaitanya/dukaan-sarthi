@echo off
REM One command on Windows: install, seed demo data, compute metrics, start on http://localhost:8000
cd /d %~dp0
python -m pip install -q -r requirements.txt
if not exist data\dukaan.db python -m backend.seed
if not exist data\metrics.json python -m backend.metrics > NUL
echo Dukaan Sarthi running at http://localhost:8000  (metrics: http://localhost:8000/metrics)
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
