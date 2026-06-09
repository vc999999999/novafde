#!/usr/bin/env sh
(set -o pipefail) 2>/dev/null && set -euo pipefail || set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: sh scripts/install.sh

Checks local Python and Node runtimes, creates a Python virtual environment,
installs backend/frontend dependencies, initializes local directories, and
creates an .env template without storing credentials.
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

cd "$ROOT_DIR"

command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 is required." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "ERROR: npm is required." >&2; exit 1; }

python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r backend/requirements.txt

(cd skill-forge && npm install)

mkdir -p backend/.data/artifacts logs config
if [ ! -f .env ]; then
  cat > .env <<'EOF'
# SkillForge local configuration.
# Store provider credentials in your shell environment or fill these locally.
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
EOF
  echo "Created .env template."
else
  echo ".env already exists; leaving it unchanged."
fi

echo "Install finished."
