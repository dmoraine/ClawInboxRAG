---
name: claw-inbox-rag
description: ClawInboxRAG community skill for querying a local Gmail RAG system through natural-language `mail ...` commands. Use when an agent must parse mailbox search requests, run a local gmail-rag CLI (search/recents/status/labels/sync), apply date/label/sender/recipient filters, and return concise citation-friendly results while enforcing read-only and privacy-safe behavior.
---

# ClawInboxRAG (Community Skill)

> Parse and execute `mail ...` commands against a local gmail-rag installation, with safe defaults and concise, user-facing output.

## Overview

Provide a portable command language for mailbox retrieval workflows backed by a local Gmail RAG stack. The skill supports:

- Search commands (`mail <query> ...`)
- Operational commands (`mail recents`, `mail status`, `mail labels`, `mail sync`, `mail help`)
- Date filters (`after`, `before`, `between ... and ...`)
- Label prefix filtering
- Optional concise result summarization (`resume`)

Design for community usage:

- Do not hardcode user names, local paths, or platform-specific assumptions
- Keep Gmail access read-only
- Return short snippets, never full raw email bodies

## Prerequisites

- A working local `gmail-rag` project checkout
- Python environment managed by `uv` (or equivalent runner)
- Valid Gmail OAuth token with **read-only** scopes
- Existing local data/index (SQLite + optional FAISS for semantic/hybrid)

Required environment variables (recommended):

- `GMAIL_RAG_REPO` — absolute path to gmail-rag repository
- `GMAIL_RAG_UV_BIN` — command for uv (default: `uv`)
- `MAIL_DEFAULT_MODE` — `hybrid` (default), `keyword`, or `semantic`
- `MAIL_DEFAULT_LIMIT` — default top-N result count (default `5`)
- `MAIL_MAX_LIMIT` — hard max result count (default `25`)

## Instructions

### Step 1: Parse command safely

- Trigger only when the incoming message starts with `mail` (case-insensitive).
- Parse action and options with `scripts/parse_mail.py`.
- If query is empty or malformed, return `mail help` guidance.

### Step 2: Map action to CLI command

Use `scripts/run_cli.sh` as the command wrapper.

Action map:

- `help` → print usage examples
- `search` → `search <query> [--hybrid|--semantic|--keyword] --limit N [--label-prefix <label>] [--after <iso>] [--before <iso>]`
- `recents` → `recents --limit N`
- `status` → `status`
- `labels` → `labels`
- `sync` (conservative):
  1. `ingest-primary --limit 50`
  2. `embed --limit 200`
  3. `refresh-labels`

### Step 3: Handle errors and degraded modes

- If semantic/hybrid is requested but vector index is missing, explain next step (`sync` or `embed`) and optionally retry keyword mode.
- If OAuth/token/repo is missing, return a setup-oriented error message.
- For CLI failures, return actionable diagnostics (what failed + suggested fix).

### Step 4: Format response for chat channels

For search:

- Return numbered items
- Include: `date | from | subject`
- Include permalink or stable reference when available
- Keep snippets short
- If `resume` is requested, add a 1–2 line summary per item
- Optionally add a compact global synthesis for larger result sets

For operations (`status`, `labels`, `sync`, `recents`):

- Keep outputs concise and human-readable
- Avoid raw machine dumps unless explicitly requested

## Examples

### Example 1: Default search

User: `mail conference`

Expected behavior:
- Parse as search, mode=`hybrid`, limit=`5`
- Execute CLI search
- Return top 5 concise results with references

### Example 2: Date and label filters

User: `mail conference March label business/external between 12/2025 and 02/2026 max 10 resume`

Expected behavior:
- Parse date range to ISO bounds
- Apply label prefix filter
- Return 10 results plus concise summaries

### Example 3: Maintenance

User: `mail sync`

Expected behavior:
- Run conservative maintenance sequence
- Return compact status summary for each step

## Configuration

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `GMAIL_RAG_REPO` | string | Yes | — | Absolute path to local gmail-rag repository |
| `GMAIL_RAG_UV_BIN` | string | No | `uv` | Runner command for Python module execution |
| `MAIL_DEFAULT_MODE` | enum | No | `hybrid` | Default search mode (`keyword`, `semantic`, `hybrid`) |
| `MAIL_DEFAULT_LIMIT` | int | No | `5` | Default top-N when user does not specify |
| `MAIL_MAX_LIMIT` | int | No | `25` | Maximum allowed top-N to protect latency/output |

## Troubleshooting

### Common Issue 1

**Problem:** `repo not found` or command fails immediately.

**Solution:** Verify `GMAIL_RAG_REPO` points to a valid checkout and contains the `gmail_rag` package.

### Common Issue 2

**Problem:** semantic/hybrid returns index-related errors.

**Solution:** Run maintenance (`mail sync`) or explicit embedding command to build/update vector index.

### Common Issue 3

**Problem:** auth errors when ingesting.

**Solution:** Verify Gmail OAuth token exists and uses read-only scopes.

## Security Considerations

- Require Gmail read-only scope for all operations.
- Never print OAuth tokens, secrets, or full sensitive message bodies.
- Truncate excerpts and sanitize displayed output.
- Validate numeric limits and date parsing before execution.
- Avoid shell interpolation of raw user input in helper scripts.

## References

- Setup guide: `references/setup.md`
- Command behavior: `references/commands.md`
- Security guidance: `references/security.md`
- Troubleshooting: `references/troubleshooting.md`
