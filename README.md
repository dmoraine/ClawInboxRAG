# ClawInboxRAG

**Community skill and local wrapper for Gmail retrieval, published as a GitHub repo with installation instructions.**

This repository is the public-facing home for the `mail ...` community skill and the local wrapper it uses to run `gmail_rag.cli`.
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
- not a hosted Gmail service

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

> `GMAIL_RAG_REPO` must point to a checkout that exposes `python -m gmail_rag.cli`. That can be this repo or another compatible local backend checkout.

### 4) Smoke test the wrapper

```bash
GMAIL_RAG_REPO=/absolute/path/to/your/local/gmail-backend scripts/run_cli.sh status
python3 scripts/parse_mail.py "mail invoices max 3"
```

`status` reports the local database/index/token health plus counts for messages, labels, attachments, chunks, and embeddings.

If the configured backend exposes passthrough operational commands, these checks may also be useful:

```bash
GMAIL_RAG_REPO=/absolute/path/to/your/local/gmail-backend scripts/run_cli.sh labels
GMAIL_RAG_REPO=/absolute/path/to/your/local/gmail-backend scripts/run_cli.sh recents --limit 5
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
mail status
mail sync
```

`mail labels` and `mail recents` are parser-recognized passthrough commands. Document them as available only when the configured backend checkout exposes matching CLI subcommands.

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

The skill and wrapper live in this repo. The runtime target is whichever local checkout `GMAIL_RAG_REPO` points at, as long as it exposes `gmail_rag.cli`.
