#!/usr/bin/env bash
set -euo pipefail

if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

exec uvicorn customer_portal.main:app --host 0.0.0.0 --port 8080 --reload
