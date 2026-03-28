# Phase 2 Status: Parity Validation and UX Parity

Status date: 2026-02-11

## Scope delivered

- Golden-query parity harness added: `clawinboxrag/parity_harness.py`
- Deterministic parity tests added: `tests/test_phase2_parity.py`
- Runnable parity report script added: `scripts/run_phase2_parity.py`
- Query classes validated:
  - `date_after`
  - `date_before`
  - `label+from`
  - `to_filter`
  - `direction_received`
  - `direction_sent`
- Citation link quality validated against Gmail permalink shape:
  - `https://mail.google.com/mail/u/<N>/#inbox/<thread_id>`
  - `https://mail.google.com/mail/u/<N>/#all/<gmail_id>`

## Method

- Deterministic fixture dataset is created in temp files (SQLite + FAISS metadata + fake FAISS index).
- Baseline is encoded as golden expected Gmail IDs per query, representing current `gmail-rag` flow outputs for this fixture.
- Adapter path runs `LegacyGmailRagAdapter.search(...)` with the same query/mode/filter inputs.
- Harness compares ordered Gmail IDs and citation-link validity for each query.

No ingestion, re-embedding, schema migration, or write operations are performed.

## Results

Command:

```bash
PYTHONPATH=. python3 scripts/run_phase2_parity.py
```

Output summary:

- Overall parity: `6/6 (100.0%)`
- Class parity:
  - `date_after`: `1/1`
  - `date_before`: `1/1`
  - `direction_received`: `1/1`
  - `direction_sent`: `1/1`
  - `label+from`: `1/1`
  - `to_filter`: `1/1`
- Gaps: `none` (for deterministic fixture baseline)

## Residual gaps / risks

- Live private baseline replay is not bundled in this repository; current Phase 2 parity is deterministic-fixture parity.
- FTS query parser behavior (token/boolean semantics) is backend-sensitive and may differ for complex multi-term queries.

## Verification commands

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPATH=. python3 scripts/run_phase2_parity.py
```
