#!/usr/bin/env bash
# Start everything for local dev. Requires Docker, Python 3.12, Node 20+.
set -e
cd "$(dirname "$0")"
echo "▶ Redis (redis-stack)…";   docker compose up -d
echo "▶ Backend deps…";          (cd services/agent && python3.12 -m venv .venv 2>/dev/null || true; . .venv/bin/activate && pip install -q -r requirements.txt)
echo "▶ Frontend deps…";         (cd apps/web && npm install --silent)
echo ""
echo "Now run these in two terminals:"
echo "  1) cd services/agent && . .venv/bin/activate && uvicorn main:app --port 8000"
echo "  2) cd apps/web && npm run dev      # http://localhost:3000"
