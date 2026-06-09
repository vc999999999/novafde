#!/usr/bin/env sh
(set -o pipefail) 2>/dev/null && set -euo pipefail || set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: sh scripts/doctor.sh

Checks Python, Node, backend imports, frontend package metadata, local data
directories, and Provider config presence. Does not print credential values.
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

cd "$ROOT_DIR"

command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 missing." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "ERROR: npm missing." >&2; exit 1; }

PYTHONPATH=backend python3 - <<'PY'
from app.main import create_app
app = create_app()
print(f"Backend import ok: {app.title}")
PY

test -f skill-forge/package.json || { echo "ERROR: skill-forge/package.json missing." >&2; exit 1; }
mkdir -p backend/.data/artifacts logs config

if [ -f config/providers.local.json ]; then
  python3 -m json.tool config/providers.local.json >/dev/null
  echo "Provider config JSON ok."
else
  echo "Provider config not found; run sh scripts/setup-llm.sh."
fi

echo "Doctor checks finished."
