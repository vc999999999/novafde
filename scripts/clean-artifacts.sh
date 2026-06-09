#!/usr/bin/env sh
(set -o pipefail) 2>/dev/null && set -euo pipefail || set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: sh scripts/clean-artifacts.sh [--yes]

Cleans generated artifact files and logs. This preserves drafts, history, and
Provider configuration.
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

if [ "${1:-}" != "--yes" ]; then
  echo "Pass --yes to remove generated artifacts and logs." >&2
  exit 1
fi

cd "$ROOT_DIR"
rm -rf backend/.data/artifacts logs
mkdir -p backend/.data/artifacts logs
echo "Generated artifacts and logs cleaned."
