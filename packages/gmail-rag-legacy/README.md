# gmail-rag

Local Gmail retrieval with keyword, semantic (FAISS), and hybrid search.

## Ingestion

```bash
uv run python -m gmail_rag.cli ingest-primary --limit 200
```

`ingest-primary` ingests a union of:
- `CATEGORY_PERSONAL` (primary/personal inbox)
- `SENT` (sent mail)

Duplicate messages are skipped by `gmail_id` primary key. Message metadata includes a lightweight `message_direction` value (`sent`, `received`, or `unknown`) inferred from Gmail labels at ingest time.

## Search CLI

```bash
uv run python -m gmail_rag.cli search "<query>" [options]
```

Common options:

- `--limit N`
- `--label <prefix>`
- `--after <date>` and `--before <date>` where date is `YYYY`, `MM/YYYY`, `YYYY-MM`, or `YYYY-MM-DD`
- `--from <sender>` sender filter (exact email match first, then case-insensitive substring fallback)
- `--to <recipient>` recipient filter (exact email match first, then case-insensitive substring fallback)
- `--semantic` semantic-only search
- `--hybrid` keyword + semantic fusion
- `--model <embedding-model>` for semantic/hybrid query embedding

Examples:

```bash
# Default keyword search
uv run python -m gmail_rag.cli search "renewal terms"

# Hybrid search scoped to a sender email
uv run python -m gmail_rag.cli search "pricing update" --hybrid --from didier@example.com

# Recipient + label + date window
uv run python -m gmail_rag.cli search "launch plan" --to pvs@example.com --label work --after 2025-01 --before 2025-03

# Sender substring fallback (case-insensitive)
uv run python -m gmail_rag.cli search "roadmap" --from "didier lab"
```
