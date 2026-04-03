# ClawInboxRAG commands

Input must start with `mail` (case-insensitive).

## Quick syntax

```text
mail <query> [keyword|semantic|hybrid] [max N|top N|limit N|limite N] [label <prefix>|tag <prefix>] [after <date>] [before <date>] [between <date> and <date>] [resume]
```

## Supported parser actions

- `mail help`
- `mail status`
- `mail sync`
- `mail labels`
- `mail recents`
- `mail <query>`

`mail labels` and `mail recents` should be documented as passthrough commands only when the configured backend checkout exposes matching CLI subcommands.

## Search behavior

Defaults come from:

- `MAIL_DEFAULT_MODE`
- `MAIL_DEFAULT_LIMIT`
- `MAIL_MAX_LIMIT`

Recognized modifiers:

- mode: `keyword`, `fts`, `semantic`, `semantique`, `sémantique`, `hybrid`, `mix`, `fusion`
- limit: `max`, `top`, `limit`, `limite`
- label filter: `label`, `tag`
- summary hint: `resume`, `résume`, `résumé`, `summary`
- date filters: `after`, `before`, `between ... and ...`

Accepted date formats:

- `YYYY`
- `MM/YYYY`
- `YYYY-MM`
- `YYYY-MM-DD`

`between` is converted to `after` plus an exclusive `before` bound:

- `between 2025 and 2025` -> `after=2025-01-01`, `before=2026-01-01`
- `between 2025-02 and 2025-03` -> `after=2025-02-01`, `before=2025-04-01`

## CLI mapping

The wrapper uses `scripts/run_cli.sh`.

Search maps to:

```text
search <query> --limit N [--label <prefix>] [--after <date>] [--before <date>]
```

Mode handling:

- keyword: no extra flag
- semantic: add `--semantic`
- hybrid: add `--hybrid`

Conservative sync sequence:

1. `ingest-primary --limit 50`
2. `embed --limit 200`
3. `refresh-labels`

## Output expectations

For search results:

- concise result blocks
- `date | from | subject`
- short excerpts only
- stable Gmail links when available

For operational output:

- short human-readable summaries
- no raw dumps unless explicitly requested
