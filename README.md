# ClawInboxRAG

**Community skill for local Gmail retrieval, published as a GitHub repo with installation instructions.**

This repository is the public-facing home for the `mail ...` community skill that wraps a local Gmail RAG backend.
It focuses on:
- safe, read-only mailbox retrieval
- clear command parsing
- concise results with citations/permalinks
- simple GitHub-based installation

## What this repo contains

- `SKILL.md` — skill definition
- `scripts/parse_mail.py` — command parser
- `scripts/run_cli.sh` — safe CLI wrapper
- `references/` — setup, commands, security, troubleshooting
- `docs/` — release notes and validation docs
- `packages/gmail-rag-legacy/` — preserved legacy snapshot for maintainers

## What it does not aim to be

- not a public Gmail API client
- not a send/delete tool
- not a replacement for your own local backend installation

## Installation

### 1) Clone the repo

```bash
git clone https://github.com/dmoraine/ClawInboxRAG.git
cd ClawInboxRAG
```

### 2) Install Python dependencies

```bash
uv sync --extra dev
```

If you only need the skill wrapper, install the runtime dependencies without dev extras:

```bash
uv sync
```

### 3) Configure the local backend path

```bash
export GMAIL_RAG_REPO="/absolute/path/to/your/local/gmail-backend"
export GMAIL_RAG_UV_BIN="uv"
export GMAIL_RAG_BASE="$HOME/.openclaw/gmail-rag"
export GMAIL_TOKEN_PATH="$HOME/.openclaw/gmail/token.json"
```

> `GMAIL_RAG_REPO` must point to your **local backend checkout**. This repo only provides the skill/wrapper layer.

### 4) Smoke test the wrapper

```bash
scripts/run_cli.sh status
scripts/run_cli.sh labels
python3 scripts/parse_mail.py "mail invoices max 3"
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

## Safety model

- Read-only Gmail access only.
- No send/delete operations in this skill.
- Result counts are clamped.
- Tokens and secrets stay out of the repo.
- Wrapper commands are allowlisted.

## Configuration

- `GMAIL_RAG_REPO` — path to your local backend checkout
- `GMAIL_RAG_UV_BIN` — runner binary, defaults to `uv`
- `GMAIL_RAG_BASE` — backend data directory
- `GMAIL_TOKEN_PATH` — Gmail OAuth token path
- `MAIL_DEFAULT_MODE` — default search mode (`hybrid` by default)
- `MAIL_DEFAULT_LIMIT` — default result count (`5` by default)
- `MAIL_MAX_LIMIT` — max result count (`25` by default)

## References

- `SKILL.md`
- `references/setup.md`
- `references/commands.md`
- `references/security.md`
- `references/troubleshooting.md`

## Notes for maintainers

The code for the backend is intentionally kept in a separate local checkout. This repo is the skill publication and wrapper layer.
