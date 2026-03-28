#!/usr/bin/env bash
set -euo pipefail
cd /home/openclaw/dev/gmail-rag

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false

LIMIT=${1:-500}

echo "[$(date -u +%F' '%T'Z')] starting embed loop limit=$LIMIT"

while true; do
  out=$(/home/openclaw/.local/bin/uv run python -m gmail_rag.cli embed --limit "$LIMIT" 2>&1) || {
    rc=$?
    echo "[$(date -u +%F' '%T'Z')] embed failed rc=$rc"
    echo "$out"
    sleep 10
    continue
  }

  echo "$out"

  if echo "$out" | grep -q "No new chunks to embed"; then
    echo "[$(date -u +%F' '%T'Z')] DONE: no new chunks to embed"
    break
  fi

  sleep 2

done
