#!/usr/bin/env sh
(set -o pipefail) 2>/dev/null && set -euo pipefail || set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: sh scripts/setup-llm.sh

Configures a local Claude or OpenAI-compatible Provider. Values can be supplied
with environment variables:
  SKILLFORGE_PROVIDER_PROTOCOL
  SKILLFORGE_PROVIDER_NAME
  SKILLFORGE_PROVIDER_BASE_URL
  SKILLFORGE_PROVIDER_MODEL
  SKILLFORGE_PROVIDER_KEY_ENV

The script writes config/providers.local.json. Add the key from the local
Provider settings screen so it is stored in the system keychain or encrypted
local secret store.
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

cd "$ROOT_DIR"
mkdir -p config
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

PROTOCOL="${SKILLFORGE_PROVIDER_PROTOCOL:-claude}"
NAME="${SKILLFORGE_PROVIDER_NAME:-${PROTOCOL}-primary}"
BASE_URL="${SKILLFORGE_PROVIDER_BASE_URL:-https://api.anthropic.com}"
MODEL="${SKILLFORGE_PROVIDER_MODEL:-claude-sonnet-4-6}"
KEY_ENV="${SKILLFORGE_PROVIDER_KEY_ENV:-ANTHROPIC_API_KEY}"

case "$PROTOCOL" in
  claude|openai-compatible) ;;
  *) echo "ERROR: protocol must be claude or openai-compatible." >&2; exit 1 ;;
esac

export PROTOCOL NAME BASE_URL MODEL KEY_ENV
"$PYTHON_BIN" - <<'PY'
import json
import os
from pathlib import Path

payload = [
    {
        "id": "provider_local",
        "name": os.environ["NAME"],
        "protocol": os.environ["PROTOCOL"],
        "baseUrl": os.environ["BASE_URL"],
        "apiKeyRef": {"type": "env", "name": os.environ["KEY_ENV"]},
        "defaultModel": os.environ["MODEL"],
        "roles": [
            "generation",
            "repair",
            "activation-evaluation",
            "implementation-evaluation",
        ],
        "timeoutMs": 120000,
        "retries": 2,
        "streaming": True,
        "customHeaders": {},
        "enabled": True,
        "lastTest": None,
    }
]
Path("config/providers.local.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

echo "Provider config written to config/providers.local.json."
