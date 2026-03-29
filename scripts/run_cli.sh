#!/usr/bin/env bash
set -euo pipefail

# Community wrapper for running gmail-rag CLI commands safely.
# Usage examples:
#   run_cli.sh status
#   run_cli.sh search "spot on" --hybrid --limit 5

GMAIL_RAG_REPO="${GMAIL_RAG_REPO:-}"
GMAIL_RAG_UV_BIN="${GMAIL_RAG_UV_BIN:-uv}"

if [[ -z "$GMAIL_RAG_REPO" ]]; then
  echo "ERROR: GMAIL_RAG_REPO is not set" >&2
  exit 2
fi

if [[ ! -d "$GMAIL_RAG_REPO" ]]; then
  echo "ERROR: GMAIL_RAG_REPO does not exist: $GMAIL_RAG_REPO" >&2
  exit 2
fi

if [[ $# -lt 1 ]]; then
  echo "ERROR: missing gmail-rag CLI subcommand" >&2
  exit 2
fi

if ! command -v "$GMAIL_RAG_UV_BIN" >/dev/null 2>&1; then
  echo "ERROR: runner not found in PATH: $GMAIL_RAG_UV_BIN" >&2
  exit 2
fi

subcommand="$1"
case "$subcommand" in
  search|recents|status|labels|ingest-primary|embed|refresh-labels)
    ;;
  *)
    echo "ERROR: subcommand not allowed by community skill policy: $subcommand" >&2
    exit 2
    ;;
esac

if [[ "$subcommand" == "status" ]]; then
  exec "$GMAIL_RAG_UV_BIN" run python - <<'PY'
from __future__ import annotations

import sqlite3
from gmail_rag.config import Paths

p = Paths()
print("ClawInboxRAG status")
print(f"- base: {p.base}")
print(f"- db: {p.db_path} ({'ok' if p.db_path.exists() else 'missing'})")
print(f"- index: {p.faiss_index_path} ({'ok' if p.faiss_index_path.exists() else 'missing'})")
print(f"- meta: {p.faiss_meta_path} ({'ok' if p.faiss_meta_path.exists() else 'missing'})")
print(f"- token: {p.gmail_token_path} ({'ok' if p.gmail_token_path.exists() else 'missing'})")
if p.db_path.exists():
    con = sqlite3.connect(str(p.db_path))
    try:
        for table in ["messages", "labels", "message_labels", "attachments", "chunks", "chunk_embeddings"]:
            try:
                count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except Exception:
                count = "n/a"
            print(f"- {table}: {count}")
    finally:
        con.close()
PY
fi

cd "$GMAIL_RAG_REPO"
exec "$GMAIL_RAG_UV_BIN" run python -m gmail_rag.cli "$@"
