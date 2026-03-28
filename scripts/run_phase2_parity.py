#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from clawinboxrag import LegacyGmailRagAdapter
from clawinboxrag.parity_harness import (
    BaselineGoldenResult,
    GoldenQuery,
    format_parity_report,
    run_golden_parity,
)

SCHEMA = """
CREATE TABLE messages (
  gmail_id TEXT PRIMARY KEY,
  thread_id TEXT,
  internal_date_ms INTEGER,
  subject TEXT,
  from_ TEXT,
  to_ TEXT,
  date_header TEXT,
  message_direction TEXT NOT NULL DEFAULT 'unknown'
);
CREATE TABLE labels (
  id TEXT PRIMARY KEY,
  name TEXT
);
CREATE TABLE message_labels (
  gmail_id TEXT NOT NULL,
  label_id TEXT NOT NULL
);
CREATE TABLE attachments (
  id INTEGER PRIMARY KEY,
  filename TEXT,
  mime_type TEXT
);
CREATE TABLE chunks (
  id INTEGER PRIMARY KEY,
  source_kind TEXT NOT NULL,
  gmail_id TEXT,
  attachment_rowid INTEGER,
  text TEXT NOT NULL
);
CREATE TABLE chunk_embeddings (
  chunk_id INTEGER PRIMARY KEY,
  model TEXT NOT NULL,
  dim INTEGER NOT NULL
);
CREATE VIRTUAL TABLE chunks_fts USING fts5(text, content='chunks', content_rowid='id');
"""


class FakeFaissIndex:
    def __init__(self, *, ntotal: int, d: int, scores: list[float], ids: list[int]) -> None:
        self.ntotal = ntotal
        self.d = d
        self._scores = [scores]
        self._ids = [ids]

    def search(self, _query_vec, _k):
        return self._scores, self._ids


def _mk_db(db_path: Path) -> None:
    con = sqlite3.connect(str(db_path))
    con.executescript(SCHEMA)
    con.execute(
        """
        INSERT INTO messages(gmail_id, thread_id, internal_date_ms, subject, from_, to_, date_header, message_direction)
        VALUES(?,?,?,?,?,?,?,?)
        """,
        ("g1", "t1", 1735689600000, "Invoice Jan", "Alice <alice@example.com>", "me@example.com", "2025-01-01", "unknown"),
    )
    con.execute(
        """
        INSERT INTO messages(gmail_id, thread_id, internal_date_ms, subject, from_, to_, date_header, message_direction)
        VALUES(?,?,?,?,?,?,?,?)
        """,
        ("g2", "t2", 1735776000000, "Roadmap", "Bob <bob@example.com>", "me@example.com", "2025-01-02", "received"),
    )
    con.execute("INSERT INTO labels(id, name) VALUES(?,?)", ("L_FIN", "finance"))
    con.execute("INSERT INTO message_labels(gmail_id, label_id) VALUES(?,?)", ("g1", "L_FIN"))
    con.execute(
        "INSERT INTO chunks(id, source_kind, gmail_id, attachment_rowid, text) VALUES(?,?,?,?,?)",
        (1, "email", "g1", None, "invoice updated and approved"),
    )
    con.execute(
        "INSERT INTO chunks(id, source_kind, gmail_id, attachment_rowid, text) VALUES(?,?,?,?,?)",
        (2, "email", "g2", None, "roadmap planning"),
    )
    con.execute("INSERT INTO chunk_embeddings(chunk_id, model, dim) VALUES(?,?,?)", (1, "intfloat/multilingual-e5-base", 768))
    con.execute("INSERT INTO chunk_embeddings(chunk_id, model, dim) VALUES(?,?,?)", (2, "intfloat/multilingual-e5-base", 768))
    con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
    con.commit()
    con.close()


def _mk_meta(meta_path: Path, rows: list[dict]) -> None:
    payload = "\n".join(json.dumps(row) for row in rows) + "\n"
    meta_path.write_text(payload, encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db_path = root / "db.sqlite"
        index_path = root / "chunks.faiss"
        meta_path = root / "chunks_meta.jsonl"
        settings_path = root / "settings.json"
        settings_path.write_text(json.dumps({"gmail_web_user_index": 2}), encoding="utf-8")

        _mk_db(db_path)
        _mk_meta(
            meta_path,
            [
                {
                    "chunk_id": 1,
                    "source_kind": "email",
                    "gmail_id": "g1",
                    "attachment_rowid": None,
                    "model": "intfloat/multilingual-e5-base",
                },
                {
                    "chunk_id": 2,
                    "source_kind": "email",
                    "gmail_id": "g2",
                    "attachment_rowid": None,
                    "model": "intfloat/multilingual-e5-base",
                },
            ],
        )
        index_path.write_bytes(b"fake")

        adapter = LegacyGmailRagAdapter(
            db_path=db_path,
            faiss_index_path=index_path,
            meta_path=meta_path,
            settings_path=settings_path,
            query_embedder=lambda _q: [0.1, 0.2, 0.3],
            faiss_reader=lambda _p: FakeFaissIndex(ntotal=2, d=768, scores=[0.8, 0.7], ids=[0, 1]),
        )

        golden_queries = [
            GoldenQuery(
                name="label_and_from_keyword",
                query_class="label+from",
                query="invoice",
                mode="keyword",
                filters={"label": "finance", "from": "alice@example.com"},
                limit=5,
            ),
            GoldenQuery(
                name="date_after_keyword",
                query_class="date_after",
                query="roadmap",
                mode="keyword",
                filters={"after": "2025-01-02"},
                limit=5,
            ),
            GoldenQuery(
                name="date_before_keyword",
                query_class="date_before",
                query="invoice",
                mode="keyword",
                filters={"before": "2025-01-02"},
                limit=5,
            ),
            GoldenQuery(
                name="to_filter_keyword",
                query_class="to_filter",
                query="roadmap",
                mode="keyword",
                filters={"to": "me@example.com"},
                limit=5,
            ),
            GoldenQuery(
                name="received_semantic",
                query_class="direction_received",
                query="invoice roadmap",
                mode="semantic",
                filters={"direction": "received"},
                limit=5,
            ),
            GoldenQuery(
                name="sent_semantic",
                query_class="direction_sent",
                query="invoice roadmap",
                mode="semantic",
                filters={"direction": "sent"},
                limit=5,
            ),
        ]
        baseline_results = {
            "label_and_from_keyword": BaselineGoldenResult(gmail_ids=["g1"]),
            "date_after_keyword": BaselineGoldenResult(gmail_ids=["g2"]),
            "date_before_keyword": BaselineGoldenResult(gmail_ids=["g1"]),
            "to_filter_keyword": BaselineGoldenResult(gmail_ids=["g2"]),
            "received_semantic": BaselineGoldenResult(gmail_ids=["g1", "g2"]),
            "sent_semantic": BaselineGoldenResult(gmail_ids=["g1"]),
        }

        report = run_golden_parity(
            golden_queries=golden_queries,
            baseline_results=baseline_results,
            adapter_runner=adapter,
        )
        print(format_parity_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
