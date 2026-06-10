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

# Load environment variables (e.g. provider API keys) from the project .env.
if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  . "$ROOT_DIR/.env"
  set +a
fi

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

echo "Backend:  http://127.0.0.1:${BACKEND_PORT}"
echo "Frontend: http://127.0.0.1:${FRONTEND_PORT}"
echo "Logs:     logs/backend.log and logs/frontend.log"
echo "Stop:     press Ctrl+C"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "$BACKEND_PORT" > logs/backend.log 2>&1 &
BACKEND_PID="$!"

(cd skill-forge && npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT") > logs/frontend.log 2>&1 &
FRONTEND_PID="$!"

# --- Health checks -----------------------------------------------------------
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-30}"
HEALTH_INTERVAL=2

echo "Waiting for backend to become healthy (timeout ${HEALTH_TIMEOUT}s)..."
elapsed=0
while [ "$elapsed" -lt "$HEALTH_TIMEOUT" ]; do
  if curl -sf "http://127.0.0.1:${BACKEND_PORT}/api/health" >/dev/null 2>&1; then
    echo "Backend is up (PID ${BACKEND_PID})."
    break
  fi
  sleep "$HEALTH_INTERVAL"
  elapsed=$((elapsed + HEALTH_INTERVAL))
done
if [ "$elapsed" -ge "$HEALTH_TIMEOUT" ]; then
  echo "WARNING: Backend did not respond within ${HEALTH_TIMEOUT}s. Check logs/backend.log."
fi

echo "Waiting for frontend to become reachable (timeout ${HEALTH_TIMEOUT}s)..."
elapsed=0
while [ "$elapsed" -lt "$HEALTH_TIMEOUT" ]; do
  if curl -sf "http://127.0.0.1:${FRONTEND_PORT}" >/dev/null 2>&1; then
    echo "Frontend is up (PID ${FRONTEND_PID})."
    break
  fi
  sleep "$HEALTH_INTERVAL"
  elapsed=$((elapsed + HEALTH_INTERVAL))
done
if [ "$elapsed" -ge "$HEALTH_TIMEOUT" ]; then
  echo "WARNING: Frontend did not respond within ${HEALTH_TIMEOUT}s. Check logs/frontend.log."
fi

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

wait