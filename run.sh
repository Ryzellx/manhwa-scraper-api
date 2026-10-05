#!/bin/bash
cd "$(dirname "$0")"
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate 2>/dev/null || true
pip install -q -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8078}
