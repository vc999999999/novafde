#!/usr/bin/env sh
(set -o pipefail) 2>/dev/null && set -euo pipefail || set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: sh scripts/run.sh

Starts the FastAPI backend and Vite frontend, writes logs under logs/, and
prints local access URLs. Stop both processes with Ctrl+C.
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

cd "$ROOT_DIR"
mkdir -p logs

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

echo "Backend:  http://127.0.0.1:${BACKEND_PORT}"
echo "Frontend: http://127.0.0.1:${FRONTEND_PORT}"
echo "Logs:     logs/backend.log and logs/frontend.log"
echo "Stop:     press Ctrl+C"

python3 -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "$BACKEND_PORT" > logs/backend.log 2>&1 &
BACKEND_PID="$!"

(cd skill-forge && npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT") > logs/frontend.log 2>&1 &
FRONTEND_PID="$!"

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

wait
