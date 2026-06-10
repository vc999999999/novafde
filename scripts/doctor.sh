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

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

PYTHONPATH=backend "$PYTHON_BIN" - <<'PY'
from app.main import create_app
app = create_app()
print(f"Backend import ok: {app.title}")
PY

# Check that key Python packages can be imported
PYTHONPATH=backend "$PYTHON_BIN" - <<'PY'
import importlib
required = ["fastapi", "uvicorn", "pydantic", "yaml", "httpx", "cryptography", "keyring"]
missing = []
for pkg in required:
    try:
        importlib.import_module(pkg)
    except ImportError:
        missing.append(pkg)
if missing:
    print(f"WARNING: Missing Python packages: {', '.join(missing)}")
else:
    print("All required Python packages importable.")
PY

test -f skill-forge/package.json || { echo "ERROR: skill-forge/package.json missing." >&2; exit 1; }

# Check that node_modules exists
if [ -d skill-forge/node_modules ]; then
  echo "node_modules directory found."
else
  echo "WARNING: skill-forge/node_modules missing. Run 'cd skill-forge && npm install'."
fi

mkdir -p backend/.data/artifacts logs config

if [ -f config/providers.local.json ]; then
  "$PYTHON_BIN" -m json.tool config/providers.local.json >/dev/null
  echo "Provider config JSON ok."
else
  echo "Provider config not found; run sh scripts/setup-llm.sh."
fi

echo "Doctor checks finished."