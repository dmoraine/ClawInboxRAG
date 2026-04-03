# ClawInboxRAG Skill

This directory contains the publishable ClawInboxRAG skill payload.

## Contents

- `SKILL.md` — skill definition
- `README.md` — installation and usage overview
- `CHANGELOG.md` — release notes
- `references/` — setup, commands, security, troubleshooting
- `scripts/` — parser and safe wrapper

## Installation

```bash
git clone https://github.com/dmoraine/ClawInboxRAG.git
cd ClawInboxRAG/skill
uv sync --extra dev
```

Then configure the local runtime checkout:

```bash
export GMAIL_RAG_REPO="/absolute/path/to/your/local/gmail-backend"
export GMAIL_RAG_UV_BIN="uv"
export GMAIL_RAG_BASE="$HOME/.openclaw/gmail-rag"
export GMAIL_TOKEN_PATH="$HOME/.openclaw/gmail/token.json"
```

`GMAIL_RAG_REPO` must point to a checkout that exposes `python -m gmail_rag.cli`. That can be this repo or another compatible local backend checkout.

## Usage

```bash
python3 scripts/parse_mail.py "mail invoices max 3"
./scripts/run_cli.sh status
```

If the configured backend exposes them, passthrough operational commands are also available:

```bash
./scripts/run_cli.sh labels
./scripts/run_cli.sh recents --limit 5
```

## Notes

- Read-only Gmail access only.
- This skill layer expects a local checkout exposing `gmail_rag.cli`.
- Do not publish tokens or secrets.
