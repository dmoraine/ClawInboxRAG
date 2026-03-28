from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = r"""
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS messages (
  gmail_id TEXT PRIMARY KEY,
  thread_id TEXT,
  internal_date_ms INTEGER,
  rfc822_msgid TEXT,
  subject TEXT,
  from_ TEXT,
  to_ TEXT,
  date_header TEXT,
  snippet TEXT,
  body_text TEXT,
  size_estimate INTEGER,
  message_direction TEXT NOT NULL DEFAULT 'unknown', -- 'sent'|'received'|'unknown'
  ingested_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS labels (
  id TEXT PRIMARY KEY,
  name TEXT,
  type TEXT
);

CREATE TABLE IF NOT EXISTS message_labels (
  gmail_id TEXT NOT NULL,
  label_id TEXT NOT NULL,
  PRIMARY KEY (gmail_id, label_id),
  FOREIGN KEY (gmail_id) REFERENCES messages(gmail_id) ON DELETE CASCADE,
  FOREIGN KEY (label_id) REFERENCES labels(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attachments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  gmail_id TEXT NOT NULL,
  attachment_id TEXT,
  filename TEXT,
  mime_type TEXT,
  size_bytes INTEGER,
  sha256 TEXT,
  stored_path TEXT,
  extracted_text TEXT,
  ingested_at_ms INTEGER NOT NULL,
  UNIQUE(gmail_id, attachment_id),
  FOREIGN KEY (gmail_id) REFERENCES messages(gmail_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_kind TEXT NOT NULL, -- 'email'|'attachment'
  gmail_id TEXT,
  attachment_rowid INTEGER,
  chunk_ordinal INTEGER NOT NULL,
  text TEXT NOT NULL,
  created_at_ms INTEGER NOT NULL,
  UNIQUE(source_kind, gmail_id, attachment_rowid, chunk_ordinal),
  FOREIGN KEY (gmail_id) REFERENCES messages(gmail_id) ON DELETE CASCADE,
  FOREIGN KEY (attachment_rowid) REFERENCES attachments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chunk_embeddings (
  chunk_id INTEGER PRIMARY KEY,
  model TEXT NOT NULL,
  dim INTEGER NOT NULL,
  -- embeddings live in faiss; this table tracks membership
  embedded_at_ms INTEGER NOT NULL,
  FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  text,
  content='chunks',
  content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES('delete', old.id, old.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES('delete', old.id, old.text);
  INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TABLE IF NOT EXISTS kv (
  key TEXT PRIMARY KEY,
  value TEXT
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)
    _migrate_messages_direction(con)
    con.commit()


def _migrate_messages_direction(con: sqlite3.Connection) -> None:
    cols = {row[1] for row in con.execute("PRAGMA table_info(messages)").fetchall()}
    if "message_direction" not in cols:
        con.execute(
            "ALTER TABLE messages ADD COLUMN message_direction TEXT NOT NULL DEFAULT 'unknown'"
        )
