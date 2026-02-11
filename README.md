# ClawInboxRAG

ClawInboxRAG is a community skill that turns natural-language `mail ...` prompts into safe, structured commands for a local `gmail-rag` installation.

It gives agents a consistent way to query inbox data with practical defaults, bounded output, and read-only safety constraints.

## Value Proposition

- Fast mailbox retrieval from chat-style commands.
- Portable skill design with minimal environment assumptions.
- Safety-first execution: read-only Gmail scope, command allowlist, bounded results.
- Works with keyword, semantic, or hybrid retrieval modes (as supported by your `gmail-rag` setup).

## Prerequisites

- Local checkout of `gmail-rag` (with working CLI).
- Python environment with `uv` (or compatible runner).
- Gmail OAuth token with read-only scope.
- Local mailbox/index data initialized for your retrieval mode.

## Google OAuth (Read-Only, Recommended)

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

### Step-by-step OAuth on VPS (credentials.json -> token.json)

This is the concrete flow used in practice for a headless VPS setup.

1. **Create OAuth client in Google Cloud**
   - Enable **Gmail API** in your project.
   - Configure OAuth consent screen (add your account as a test user if app is in testing mode).
   - Create OAuth Client ID as **Desktop app**.
   - Download client credentials JSON.

2. **Place credentials on server**

```bash
mkdir -p /home/openclaw/.openclaw/gmail
chmod 700 /home/openclaw/.openclaw/gmail
# copy downloaded file to:
# /home/openclaw/.openclaw/gmail/credentials.json
chmod 600 /home/openclaw/.openclaw/gmail/credentials.json
```

3. **Use a local uv environment (recommended)**

```bash
cd /home/openclaw/.openclaw/gmail
uv venv
uv pip install -U google-auth-oauthlib google-api-python-client
```

4. **Create auth script** (`/home/openclaw/.openclaw/gmail/auth_gmail.py`)

```python
from google_auth_oauthlib.flow import InstalledAppFlow
import os

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
BASE = "/home/openclaw/.openclaw/gmail"
CREDS = os.path.join(BASE, "credentials.json")
TOKEN = os.path.join(BASE, "token.json")

def main():
    flow = InstalledAppFlow.from_client_secrets_file(CREDS, SCOPES)
    creds = flow.run_local_server(host="127.0.0.1", port=8088, open_browser=False)
    with open(TOKEN, "w") as f:
        f.write(creds.to_json())
    os.chmod(TOKEN, 0o600)
    print("OK: token written to", TOKEN)

if __name__ == "__main__":
    main()
```

> Note: some environments do not expose `run_console()`; `run_local_server()` is more broadly compatible.

5. **Run script on VPS**

```bash
cd /home/openclaw/.openclaw/gmail
uv run python auth_gmail.py
```

6. **Tunnel callback from your laptop to VPS** (keep this open while authenticating)

```bash
ssh -L 8088:127.0.0.1:8088 <your-vps-host>
```

7. **Open Google consent URL, approve access**
   - The callback hits `http://127.0.0.1:8088/` on your laptop.
   - SSH tunnel forwards callback to VPS auth script.
   - Script writes `/home/openclaw/.openclaw/gmail/token.json`.

8. **Verify token exists**

```bash
ls -la /home/openclaw/.openclaw/gmail/token.json
```

9. **Optional smoke test (read-only)**

```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

creds = Credentials.from_authorized_user_file(
    "/home/openclaw/.openclaw/gmail/token.json",
    ["https://www.googleapis.com/auth/gmail.readonly"],
)
service = build("gmail", "v1", credentials=creds)
print(service.users().messages().list(userId="me", maxResults=5).execute())
```

## Installation

1. Clone this repository.
2. Set required environment variables:

```bash
export GMAIL_RAG_REPO="/absolute/path/to/gmail-rag"
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

- `GMAIL_RAG_REPO is not set`: export `GMAIL_RAG_REPO` to a valid `gmail-rag` checkout.
- `runner not found in PATH`: install `uv` or set `GMAIL_RAG_UV_BIN` correctly.
- `ModuleNotFoundError: gmail_rag`: verify your repo path and Python environment.
- Sparse semantic/hybrid results: run `mail sync` (or explicit embedding flow) and retry.

More: `references/troubleshooting.md`.

## Roadmap

- Add lightweight parser tests for high-confidence command normalization.
- Add optional structured output mode (JSON) for downstream tooling.
- Document backend-specific query operator compatibility (`from:`, `to:`, `subject:`).
- Prepare ClawHub metadata and release artifacts (without auto-publishing).

## Repository Layout

- `SKILL.md` - community skill specification.
- `scripts/parse_mail.py` - parser for `mail ...` commands.
- `scripts/run_cli.sh` - safe wrapper for `gmail-rag` CLI execution.
- `references/` - setup, commands, security, troubleshooting notes.
- `docs/RELEASE_CHECKLIST.md` - pre-publish release checklist.

## License

MIT. See `LICENSE`.
