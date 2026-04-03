# ClawInboxRAG setup guide

This guide is for the community skill and wrapper layer that powers `mail ...` commands.

## Required components

- A local backend checkout referenced by `GMAIL_RAG_REPO`
- A Python runner, usually `uv`
- A Gmail OAuth token with read-only scope
- Local data under `GMAIL_RAG_BASE`

If semantic or hybrid search is expected, the local FAISS index and metadata must exist.

## Environment variables

Recommended configuration:

```bash
export GMAIL_RAG_REPO="/absolute/path/to/claw-inbox-rag"
export GMAIL_RAG_UV_BIN="uv"
export GMAIL_RAG_BASE="$HOME/.openclaw/gmail-rag"
export GMAIL_TOKEN_PATH="$HOME/.openclaw/gmail/token.json"
export MAIL_DEFAULT_MODE="hybrid"
export MAIL_DEFAULT_LIMIT="5"
export MAIL_MAX_LIMIT="25"
```

Notes:

- `GMAIL_RAG_REPO` is required by `scripts/run_cli.sh`
- `GMAIL_RAG_BASE` controls the SQLite DB, attachments, and FAISS index location
- `GMAIL_TOKEN_PATH` controls where the Gmail token is read from

## OAuth setup

Document the local Gmail OAuth flow conservatively:

1. Enable the Gmail API for the backend's Google Cloud project.
2. Configure OAuth consent and create client credentials for the local workflow.
3. Authorize only Gmail read-only scope.
4. Save the token at the path expected by the backend.
5. Validate with a read-only command.

If the token already exists locally and is valid, reuse it.

## Basic health checks

```bash
GMAIL_RAG_REPO=/absolute/path/to/claw-inbox-rag scripts/run_cli.sh status
python3 scripts/parse_mail.py "mail invoices max 3"
```

If the configured backend supports them, the following passthrough checks are also useful:

```bash
GMAIL_RAG_REPO=/absolute/path/to/claw-inbox-rag scripts/run_cli.sh labels
GMAIL_RAG_REPO=/absolute/path/to/claw-inbox-rag scripts/run_cli.sh recents --limit 5
```

`status` reports local DB/index/token health and table counts for messages, labels, message_labels, attachments, chunks, and chunk_embeddings.

## Failure patterns

- Missing repo path: verify `GMAIL_RAG_REPO`
- Missing runner: verify `GMAIL_RAG_UV_BIN`
- Auth failure: verify `GMAIL_TOKEN_PATH` and Gmail read-only scope
- Semantic/hybrid failure: run sync or build embeddings/index
