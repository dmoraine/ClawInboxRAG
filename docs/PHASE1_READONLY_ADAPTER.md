# Phase 1 Status: Read-Only Legacy Adapter

Status date: 2026-02-11

## Scope delivered

- Read-only adapter implemented: `clawinboxrag/legacy_adapter.py`
- Data sources:
  - SQLite: `/home/openclaw/.openclaw/gmail-rag/db.sqlite`
  - FAISS index: `/home/openclaw/.openclaw/gmail-rag/index/chunks.faiss`
  - FAISS metadata: `/home/openclaw/.openclaw/gmail-rag/index/chunks_meta.jsonl`
- Search modes: `keyword`, `semantic`, `hybrid`
- Citation mode: Gmail permalink parity (`/u/<N>/#inbox/<thread_id>` with `#all/<gmail_id>` fallback)
- Write capabilities disabled by contract (`supports_write=false`, `supports_ingest=false`)

## Startup validation checks

- Existence/readability checks for DB/FAISS/meta paths
- Meta JSONL parsing and required key checks
- `faiss.ntotal == meta_line_count`
- FAISS dimension versus expected dimension (default `768`)
- `chunk_embeddings` dominant dimension/model assumptions
- Meta model consistency checks
- Sampled `chunk_id` resolution against `chunks` table

On validation mismatch, semantic/hybrid capability is disabled while keyword remains available.

## Usage (minimal)

```python
from clawinboxrag import LegacyGmailRagAdapter

adapter = LegacyGmailRagAdapter(
    db_path="/home/openclaw/.openclaw/gmail-rag/db.sqlite",
    faiss_index_path="/home/openclaw/.openclaw/gmail-rag/index/chunks.faiss",
    meta_path="/home/openclaw/.openclaw/gmail-rag/index/chunks_meta.jsonl",
    query_embedder=my_query_embedder,  # required for semantic/hybrid
)

payload = adapter.search(
    query="invoice",
    mode="hybrid",
    limit=5,
    filters={"after": "2025-01-01", "label": "finance"},
    resume=False,
)
```

## Guardrails

- No ingestion
- No re-embedding
- No schema migration
- No write operations against legacy artifacts
