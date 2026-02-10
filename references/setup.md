# Setup

## 1) Required components

- Local `gmail-rag` checkout
- Python + `uv`
- Gmail OAuth token with read-only scope

## 2) Environment variables

```bash
export GMAIL_RAG_REPO="/absolute/path/to/gmail-rag"
export GMAIL_RAG_UV_BIN="uv"
export MAIL_DEFAULT_MODE="hybrid"
export MAIL_DEFAULT_LIMIT="5"
export MAIL_MAX_LIMIT="25"
```

## 3) Basic health checks

```bash
cd "$GMAIL_RAG_REPO"
$GMAIL_RAG_UV_BIN run python -m gmail_rag.cli status
$GMAIL_RAG_UV_BIN run python -m gmail_rag.cli labels
```

If semantic/hybrid is intended, ensure embeddings/index exist before production usage.
