# ClawInboxRAG

ClawInboxRAG is the single repo for the local Gmail RAG system and its community skill wrapper.

It provides:
- the `gmail-rag` engine (ingest, embed, search)
- the `mail ...` chat/skill interface
- safe, read-only mailbox retrieval defaults
- docs, tests, and operational scripts in one place

## Value Proposition

- Fast mailbox retrieval from chat-style commands.
- Portable skill design with minimal environment assumptions.
- Safety-first execution: read-only Gmail scope, command allowlist, bounded results.
- Works with keyword, semantic, or hybrid retrieval modes.

## Repository Layout

- `gmail_rag/` — core engine and CLI code
- `clawinboxrag/` — skill adapter and parity harness
- `scripts/` — helper scripts for the chat wrapper and CLI
- `tests/` — automated tests
- `references/` — setup, commands, security, troubleshooting notes
- `docs/` — migration and validation docs

## Prerequisites

- Python environment with `uv` (or compatible runner).
- Gmail OAuth token with read-only scope.
- Local mailbox/index data initialized for your retrieval mode.

## Gmail OAuth (Read-Only, Recommended)

ClawInboxRAG is designed for mailbox retrieval, not mailbox mutation.

Use Gmail OAuth with **read-only scope**:

- `https://www.googleapis.com/auth/gmail.readonly`

Avoid write scopes unless you intentionally need write actions in another tool:

- `gmail.modify`
- `gmail.send`
- `mail.google.com`

### Why this matters

- Limits blast radius if token is leaked.
- Keeps behavior aligned with this skill's safety model.
- Simplifies compliance and auditing.

### Practical checks

- Verify token file permissions are restrictive (`600` where possible).
- Keep token outside the repository.
- If uncertain about granted scopes, re-run OAuth with read-only only.

## Installation

1. Clone this repository.
2. Set required environment variables:

```bash
export GMAIL_RAG_REPO="/absolute/path/to/claw-inbox-rag"
export GMAIL_RAG_UV_BIN="uv"
export MAIL_DEFAULT_MODE="hybrid"   # keyword|semantic|hybrid
export MAIL_DEFAULT_LIMIT="5"
export MAIL_MAX_LIMIT="25"
```

3. Validate connectivity:

```bash
scripts/run_cli.sh status
scripts/run_cli.sh labels
```

## Usage

### Core command shape

```text
mail <query> [keyword|semantic|hybrid] [max N|top N|limit N] [label <prefix>] [after <date>] [before <date>] [between <date> and <date>] [resume]
```

### Syntax quick reference

- Search: `mail <query>`
- Mode: `keyword` | `semantic` | `hybrid`
- Result size: `max N` / `top N` / `limit N`
- Labels: `label <prefix>`
- Date window:
  - `after <date>`
  - `before <date>`
  - `between <date> and <date>`
- Summary mode: `resume`
- Ops commands:
  - `mail recents [top N]`
  - `mail status`
  - `mail labels`
  - `mail sync`

Supported date formats:

- `YYYY`
- `MM/YYYY`
- `YYYY-MM`
- `YYYY-MM-DD`

### Examples

```text
mail conference
mail budget review keyword max 8
mail invoices label finance/receivables between 2025-01 and 2025-03 resume
mail recents top 10
mail status
mail labels
mail sync
```

### Sender/recipient filtering

The parser does not implement dedicated `from`/`to` flags. Use provider query operators inside `<query>` when your backend supports them, for example:

```text
mail from:alice@example.com to:me subject:contract max 5
```

## Safety Model

- Read-only Gmail access only.
- Wrapper allowlists CLI subcommands: `search`, `recents`, `status`, `labels`, `ingest-primary`, `embed`, `refresh-labels`.
- Numeric limits are clamped to `MAIL_MAX_LIMIT`.
- Dates are parsed and normalized before command execution.
- Do not return full raw message bodies or secrets in default responses.

## Troubleshooting

- `GMAIL_RAG_REPO is not set`: export `GMAIL_RAG_REPO` to a valid `claw-inbox-rag` checkout.
