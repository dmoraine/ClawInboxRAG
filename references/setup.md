# Setup

## 1) Required components

- Local ClawInboxRAG checkout.
- Python + `uv`.
- Gmail OAuth token with read-only scope.

## 2) Environment variables

```bash
export GMAIL_RAG_REPO="/absolute/path/to/claw-inbox-rag"
export GMAIL_RAG_UV_BIN="uv"
export MAIL_DEFAULT_MODE="hybrid"
export MAIL_DEFAULT_LIMIT="5"
export MAIL_MAX_LIMIT="25"
```

`GMAIL_RAG_REPO` is required by `scripts/run_cli.sh`.

## 3) Basic health checks

```bash
scripts/run_cli.sh status
scripts/run_cli.sh labels
python3 scripts/parse_mail.py "mail invoices max 3"
```

If semantic/hybrid retrieval is expected, ensure embeddings/index exist.
