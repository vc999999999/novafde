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

The script writes .env and config/providers.local.json. It records only the
environment variable name used for credentials.
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

cd "$ROOT_DIR"
mkdir -p config

PROTOCOL="${SKILLFORGE_PROVIDER_PROTOCOL:-claude}"
NAME="${SKILLFORGE_PROVIDER_NAME:-${PROTOCOL}-primary}"
BASE_URL="${SKILLFORGE_PROVIDER_BASE_URL:-https://api.anthropic.com}"
MODEL="${SKILLFORGE_PROVIDER_MODEL:-claude-sonnet-4-5}"
KEY_ENV="${SKILLFORGE_PROVIDER_KEY_ENV:-ANTHROPIC_API_KEY}"

case "$PROTOCOL" in
  claude|openai-compatible) ;;
  *) echo "ERROR: protocol must be claude or openai-compatible." >&2; exit 1 ;;
esac

if [ ! -f .env ]; then
  touch .env
fi

if ! grep -q "^${KEY_ENV}=" .env; then
  printf '%s=\n' "$KEY_ENV" >> .env
  echo "Added ${KEY_ENV} placeholder to .env."
else
  echo "${KEY_ENV} already exists in .env; leaving it unchanged."
fi

cat > config/providers.local.json <<EOF
[
  {
    "id": "provider_local",
    "name": "${NAME}",
    "protocol": "${PROTOCOL}",
    "baseUrl": "${BASE_URL}",
    "apiKeyRef": { "type": "env", "name": "${KEY_ENV}" },
    "defaultModel": "${MODEL}",
    "roles": ["generation", "repair", "validation-explanation"],
    "timeoutMs": 120000,
    "retries": 2,
    "streaming": true,
    "customHeaders": {},
    "enabled": true,
    "lastTest": null
  }
]
EOF

echo "Provider config written to config/providers.local.json."
