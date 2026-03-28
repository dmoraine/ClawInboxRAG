# ClawInboxRAG

**Local Gmail RAG + `mail ...` skill wrapper in one repo.**

ClawInboxRAG is the home for the local Gmail retrieval system used by OpenClaw fans.
It combines the retrieval engine, the chat-friendly skill layer, tests, docs, and operational scripts.

## What you get

- `gmail_rag/` — ingest, embed, search
- `clawinboxrag/` — skill adapter and parity harness
- `scripts/` — active wrapper scripts
- `packages/gmail-rag-legacy/` — archived legacy snapshot
- `tests/` — regression coverage
- `references/` — setup, commands, security, troubleshooting

## Why this repo exists

- One source of truth for behavior and safety
- Read-only Gmail posture by default
- `mail ...` command language for chat surfaces
- Hybrid search with keyword + semantic retrieval
- Easy to browse, test, and extend

## Quick start

```bash
uv sync --extra dev
export GMAIL_RAG_REPO="/absolute/path/to/claw-inbox-rag"
export GMAIL_RAG_UV_BIN="uv"
export MAIL_DEFAULT_MODE="hybrid"
export MAIL_DEFAULT_LIMIT="5"
export MAIL_MAX_LIMIT="25"

scripts/run_cli.sh status
scripts/run_cli.sh labels
scripts/run_cli.sh search "invoice" --hybrid --limit 5
```

## Command language

```text
mail <query> [keyword|semantic|hybrid] [max N|top N|limit N] [label <prefix>] [after <date>] [before <date>] [between <date> and <date>] [resume]
```

Examples:

```text
mail conference
mail budget review keyword max 8
mail invoices label finance/receivables between 2025-01 and 2025-03 resume
mail recents top 10
mail status
mail labels
mail sync
```

## Read-only safety

- Gmail access stays read-only.
- No send/delete operations in this skill.
- Result counts are clamped.
- Tokens and secrets stay out of the repo.
- Wrapper commands are allowlisted.

## Repository layout

- `gmail_rag/` — core engine and CLI code
- `clawinboxrag/` — skill adapter and parity harness
- `scripts/` — helper scripts
- `packages/gmail-rag-legacy/` — preserved legacy Gmail RAG snapshot
- `tests/` — automated tests
- `references/` — setup, commands, security, troubleshooting notes
- `docs/` — migration and validation docs

## Compatibility notes

- `GMAIL_RAG_REPO` should point to this repo.
- `uv` is the preferred runner.
- If semantic/hybrid search is empty, run `mail sync` first.
