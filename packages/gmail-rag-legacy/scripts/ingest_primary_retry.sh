#!/usr/bin/env bash
set -euo pipefail
cd /home/openclaw/dev/gmail-rag

LIMIT=${1:-20000}

echo "[$(date -u +%F' '%T'Z')] starting ingest-primary limit=$LIMIT"

while true; do
  out=$(/home/openclaw/.local/bin/uv run python -m gmail_rag.cli ingest-primary --limit "$LIMIT" 2>&1) || {
    rc=$?
    echo "[$(date -u +%F' '%T'Z')] ingest failed rc=$rc"
    echo "$out"
    sleep 20
    continue
  }
  echo "$out"
  echo "[$(date -u +%F' '%T'Z')] ingest run finished"
  break

done
