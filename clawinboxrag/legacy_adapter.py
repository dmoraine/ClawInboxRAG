from __future__ import annotations

import datetime as dt
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from email.utils import getaddresses
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.parse import quote


DEFAULT_MODEL = "intfloat/multilingual-e5-base"
DEFAULT_DIM = 768


class LegacyValidationError(RuntimeError):
    """Raised when strict startup validation fails."""


@dataclass(frozen=True)
class ValidationReport:
    semantic_ready: bool
    errors: list[str]
    warnings: list[str]
    meta_count: int
    index_ntotal: int | None
    index_dim: int | None
    detected_models: list[str]
    detected_dims: list[int]


class LegacyGmailRagAdapter:
    backend_name = "gmail-rag-legacy"

    def __init__(
        self,
        *,
        db_path: str | Path,
        faiss_index_path: str | Path,
        meta_path: str | Path,
        settings_path: str | Path | None = None,
        model_name: str = DEFAULT_MODEL,
        expected_dim: int = DEFAULT_DIM,
        query_embedder: Callable[[str], Sequence[float]] | None = None,
        faiss_reader: Callable[[str], Any] | None = None,
        strict_validation: bool = False,
    ) -> None:
        self.db_path = Path(db_path).expanduser()
        self.faiss_index_path = Path(faiss_index_path).expanduser()
        self.meta_path = Path(meta_path).expanduser()
        self.settings_path = (
            Path(settings_path).expanduser()
            if settings_path is not None
            else self.db_path.parent / "settings.json"
        )

        self.model_name = model_name
        self.expected_dim = expected_dim
        self.query_embedder = query_embedder
        self.faiss_reader = faiss_reader or self._default_faiss_reader

        self._meta_rows: list[dict[str, Any]] | None = None
        self._faiss_index: Any | None = None

        self.validation = self.validate_startup()
        if strict_validation and self.validation.errors:
            raise LegacyValidationError("; ".join(self.validation.errors))

    @property
    def capabilities(self) -> dict[str, Any]:
        return {
            "supports_write": False,
            "supports_ingest": False,
            "supports_hybrid_search": self._semantic_enabled(),
            "supports_filters": ["after", "before", "label", "from", "to", "direction"],
            "citation_mode": "gmail_permalink",
        }

    def validate_startup(self) -> ValidationReport:
        errors: list[str] = []
        warnings: list[str] = []
        meta_count = 0
        index_ntotal: int | None = None
        index_dim: int | None = None

        if not self.db_path.exists():
            errors.append(f"SQLite db not found: {self.db_path}")

        if not self.faiss_index_path.exists():
            errors.append(f"FAISS index not found: {self.faiss_index_path}")
        if not self.meta_path.exists():
            errors.append(f"FAISS metadata not found: {self.meta_path}")

        models: list[str] = []
        dims: list[int] = []
        if self.db_path.exists():
            with self._connect_ro() as con:
                model_rows = con.execute(
                    "SELECT model, COUNT(*) AS n FROM chunk_embeddings GROUP BY model ORDER BY n DESC"
                ).fetchall()
                dim_rows = con.execute(
                    "SELECT dim, COUNT(*) AS n FROM chunk_embeddings GROUP BY dim ORDER BY n DESC"
                ).fetchall()
                models = [str(r[0]) for r in model_rows if r[0] is not None]
                dims = [int(r[0]) for r in dim_rows if r[0] is not None]

        meta_rows: list[dict[str, Any]] = []
        if self.meta_path.exists():
            try:
                with self.meta_path.open("r", encoding="utf-8") as handle:
                    for line_no, line in enumerate(handle, start=1):
                        line = line.strip()
                        if not line:
                            continue
                        row = json.loads(line)
                        for key in ("chunk_id", "source_kind", "gmail_id", "attachment_rowid", "model"):
                            if key not in row:
                                errors.append(f"Meta line {line_no} missing required key: {key}")
                                break
                        else:
                            meta_rows.append(row)
            except json.JSONDecodeError as exc:
                errors.append(f"Failed parsing meta jsonl: {exc}")
        meta_count = len(meta_rows)

        if self.faiss_index_path.exists():
            try:
                idx = self._load_faiss_index()
                index_ntotal = int(idx.ntotal)
                index_dim = int(idx.d)
            except Exception as exc:  # pragma: no cover - depends on runtime faiss setup.
                errors.append(f"Failed reading FAISS index: {exc}")

        if index_ntotal is not None and meta_count and index_ntotal != meta_count:
            errors.append(f"FAISS index/meta mismatch: index ntotal={index_ntotal} meta lines={meta_count}")
        if index_dim is not None and index_dim != self.expected_dim:
            errors.append(f"FAISS index dim={index_dim} does not match expected dim={self.expected_dim}")
        if dims:
            dominant_dim = dims[0]
            if dominant_dim != self.expected_dim:
                errors.append(f"chunk_embeddings dominant dim={dominant_dim} does not match expected dim={self.expected_dim}")
            if index_dim is not None and dominant_dim != index_dim:
                errors.append(f"FAISS dim={index_dim} does not match chunk_embeddings dominant dim={dominant_dim}")
        if models:
            dominant_model = models[0]
            if dominant_model != self.model_name:
                errors.append(
                    f"chunk_embeddings dominant model={dominant_model!r} does not match configured model={self.model_name!r}"
                )
            if len(set(models)) > 1:
                warnings.append(f"Multiple embedding models detected in chunk_embeddings: {models}")

        if meta_rows:
            meta_models = sorted({str(r.get("model") or "") for r in meta_rows})
            if meta_models and (len(meta_models) > 1 or meta_models[0] != self.model_name):
                errors.append(
                    f"Meta model mismatch (meta models={meta_models}, configured model={self.model_name!r})"
                )

            if self.db_path.exists():
                with self._connect_ro() as con:
                    sample_ids = [int(r["chunk_id"]) for r in meta_rows[:1000] if "chunk_id" in r]
                    if sample_ids:
                        placeholders = ",".join("?" for _ in sample_ids)
                        resolved = con.execute(
                            f"SELECT COUNT(*) FROM chunks WHERE id IN ({placeholders})",
                            sample_ids,
                        ).fetchone()[0]
                        if int(resolved) != len(set(sample_ids)):
                            errors.append("Some sampled meta chunk_id values do not resolve in chunks table")

        semantic_ready = (
            not errors
            and self.query_embedder is not None
            and index_ntotal is not None
            and index_ntotal > 0
            and meta_count > 0
        )
        if self.query_embedder is None:
            warnings.append("No query_embedder configured; semantic and hybrid search disabled.")

        self._meta_rows = meta_rows if meta_rows else None
        return ValidationReport(
            semantic_ready=semantic_ready,
            errors=errors,
            warnings=warnings,
            meta_count=meta_count,
            index_ntotal=index_ntotal,
            index_dim=index_dim,
            detected_models=models,
            detected_dims=dims,
        )

    def search(
        self,
        *,
        query: str,
        mode: str = "hybrid",
        filters: dict[str, Any] | None = None,
        limit: int = 5,
        resume: bool = False,
    ) -> dict[str, Any]:
        if not query or not query.strip():
            return {"results": [], "meta": self._meta_block()}

        filters = filters or {}
        mode = (mode or "hybrid").strip().lower()
        if mode not in {"keyword", "semantic", "hybrid"}:
            raise ValueError(f"Unsupported mode: {mode}")

        limit = max(1, int(limit))
        after_ms = self._parse_date_bound(filters.get("after"))
        before_ms = self._parse_date_bound(filters.get("before"))
        direction_filter = self._normalize_direction(filters.get("direction"))

        with self._connect_ro() as con:
            label_ids = self._resolve_label_ids(con, filters.get("label"))

            if mode == "keyword":
                kw_hits = self._keyword_hits(
                    con,
                    query=query,
                    limit=limit,
                    label_ids=label_ids,
                    from_filter=filters.get("from"),
                    to_filter=filters.get("to"),
                    after_ms=after_ms,
                    before_ms=before_ms,
                )
                fused_hits = [{"kw": h, "sem": None, "score": float(1.0 / (60.0 + i + 1))} for i, h in enumerate(kw_hits)]
            elif mode == "semantic":
                sem_hits = self._semantic_hits(
                    con,
                    query=query,
                    limit=limit,
                    label_ids=label_ids,
                    from_filter=filters.get("from"),
                    to_filter=filters.get("to"),
                    after_ms=after_ms,
                    before_ms=before_ms,
                )
                fused_hits = [{"kw": None, "sem": h, "score": float(h["score"])} for h in sem_hits]
            else:
                kw_hits = self._keyword_hits(
                    con,
                    query=query,
                    limit=limit * 5,
                    label_ids=label_ids,
                    from_filter=filters.get("from"),
                    to_filter=filters.get("to"),
                    after_ms=after_ms,
                    before_ms=before_ms,
                )
                sem_hits = self._semantic_hits(
                    con,
                    query=query,
                    limit=limit * 5,
                    label_ids=label_ids,
                    from_filter=filters.get("from"),
                    to_filter=filters.get("to"),
                    after_ms=after_ms,
                    before_ms=before_ms,
                )
                fused_hits = self._rrf_fuse(kw_hits, sem_hits, limit=limit * 2)

            results = self._hydrate_results(
                con=con,
                hits=fused_hits,
                limit=limit,
                direction_filter=direction_filter,
                resume=resume,
            )

        return {"results": results, "meta": self._meta_block()}

    def _meta_block(self) -> dict[str, Any]:
        dim = self.validation.index_dim
        if dim is None and self.validation.detected_dims:
            dim = self.validation.detected_dims[0]
        return {"backend": self.backend_name, "model": self.model_name, "dim": dim}

    def _hydrate_results(
        self,
        *,
        con: sqlite3.Connection,
        hits: list[dict[str, Any]],
        limit: int,
        direction_filter: str | None,
        resume: bool,
    ) -> list[dict[str, Any]]:
        cur = con.cursor()
        out: list[dict[str, Any]] = []
        seen_gmail_ids: set[str] = set()

        for item in hits:
            kw_h = item.get("kw")
            sem_h = item.get("sem")
            h = kw_h or sem_h
            if not h:
                continue

            gmail_id = h.get("gmail_id")
            if gmail_id and gmail_id in seen_gmail_ids:
                continue

            message_row = (
                cur.execute(
                    """
                    SELECT thread_id, date_header, from_, to_, subject, message_direction
                    FROM messages
                    WHERE gmail_id=?
                    """,
                    (gmail_id,),
                ).fetchone()
                if gmail_id
                else None
            )
            thread_id, date_header, from_, to_, subject, message_direction = (
                message_row if message_row else (None, None, None, None, None, "unknown")
            )

            direction = self._normalize_direction(message_direction) or "unknown"
            if not self._direction_allows(direction_filter, direction):
                continue

            source_kind = h.get("source_kind") or "email"
            if source_kind not in {"email", "attachment"}:
                continue

            attachment = {"id": None, "filename": None, "mime_type": None}
            attachment_rowid = h.get("attachment_rowid")
            if source_kind == "attachment" and attachment_rowid is not None:
                arow = cur.execute(
                    "SELECT filename, mime_type FROM attachments WHERE id=?",
                    (int(attachment_rowid),),
                ).fetchone()
                if arow:
                    attachment = {"id": int(attachment_rowid), "filename": arow[0], "mime_type": arow[1]}
                else:
                    attachment = {"id": int(attachment_rowid), "filename": None, "mime_type": None}

            snippet = self._collapse_ws(h.get("snippet") or "")
            if resume:
                snippet = self._short_excerpt(snippet, max_len=140)

            if gmail_id:
                seen_gmail_ids.add(gmail_id)
            match_mode = self._match_mode(kw_h, sem_h)
            out.append(
                {
                    "gmail_id": gmail_id,
                    "thread_id": thread_id,
                    "date": date_header,
                    "from": from_,
                    "to": to_,
                    "subject": subject,
                    "snippet": snippet,
                    "source_kind": source_kind,
                    "attachment": attachment,
                    "direction": direction,
                    "score": float(item.get("score") or 0.0),
                    "match_mode": match_mode,
                    "link": self.gmail_permalink(gmail_id=gmail_id, thread_id=thread_id, view="inbox"),
                }
            )
            if len(out) >= limit:
                break
        return out

    def _keyword_hits(
        self,
        con: sqlite3.Connection,
        *,
        query: str,
        limit: int,
        label_ids: set[str] | None,
        from_filter: str | None,
        to_filter: str | None,
        after_ms: int | None,
        before_ms: int | None,
    ) -> list[dict[str, Any]]:
        fts_query = self._sanitize_fts_query(query)
        if not fts_query:
            return []

        where_parts = ["chunks_fts MATCH ?"]
        params: list[Any] = [fts_query]

        if after_ms is not None or before_ms is not None:
            sub = ["SELECT gmail_id FROM messages WHERE 1=1"]
            if after_ms is not None:
                sub.append(" AND internal_date_ms >= ?")
                params.append(after_ms)
            if before_ms is not None:
                sub.append(" AND internal_date_ms < ?")
                params.append(before_ms)
            where_parts.append(f"c.gmail_id IN ({''.join(sub)})")

        rows = con.execute(
            f"""
            SELECT c.id, c.source_kind, c.gmail_id, c.attachment_rowid,
                   snippet(chunks_fts, 0, '', '', '…', 12) AS snip
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.rowid
            WHERE {' AND '.join(where_parts)}
            ORDER BY rank
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()

        out: list[dict[str, Any]] = []
        for chunk_id, source_kind, gmail_id, attachment_rowid, snip in rows:
            from_to = (
                con.execute("SELECT from_, to_ FROM messages WHERE gmail_id=?", (gmail_id,)).fetchone()
                if gmail_id
                else None
            )
            from_ = from_to[0] if from_to else None
            to_ = from_to[1] if from_to else None

            if not self._matches_contact_filter(from_, from_filter):
                continue
            if not self._matches_contact_filter(to_, to_filter):
                continue
            if label_ids and gmail_id:
                labels = {
                    row[0]
                    for row in con.execute(
                        "SELECT label_id FROM message_labels WHERE gmail_id=?",
                        (gmail_id,),
                    ).fetchall()
                }
                if not labels.intersection(label_ids):
                    continue
            out.append(
                {
                    "chunk_id": int(chunk_id),
                    "source_kind": source_kind,
                    "gmail_id": gmail_id,
                    "attachment_rowid": attachment_rowid,
                    "snippet": self._collapse_ws(snip or ""),
                }
            )
        return out

    def _semantic_hits(
        self,
        con: sqlite3.Connection,
        *,
        query: str,
        limit: int,
        label_ids: set[str] | None,
        from_filter: str | None,
        to_filter: str | None,
        after_ms: int | None,
        before_ms: int | None,
    ) -> list[dict[str, Any]]:
        if not self._semantic_enabled():
            raise LegacyValidationError(
                "Semantic path unavailable (missing FAISS/meta/embedder or failed startup validation)."
            )
        if not self._meta_rows:
            raise LegacyValidationError("Semantic metadata unavailable.")

        qemb = list(self.query_embedder(query))  # type: ignore[misc]
        idx = self._load_faiss_index()
        scores, ids = idx.search(self._to_query_matrix(qemb), min(max(limit * 20, 50), int(idx.ntotal)))
        # Works with both faiss arrays and python lists from tests.
        scores0 = scores[0].tolist() if hasattr(scores[0], "tolist") else list(scores[0])
        ids0 = ids[0].tolist() if hasattr(ids[0], "tolist") else list(ids[0])

        out: list[dict[str, Any]] = []
        seen_chunks: set[int] = set()
        for pos, score in zip(ids0, scores0):
            if int(pos) < 0:
                continue
            pos_i = int(pos)
            if pos_i >= len(self._meta_rows):
                continue
            meta = self._meta_rows[pos_i]
            chunk_id = int(meta.get("chunk_id"))
            if chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk_id)

            if not con.execute(
                "SELECT 1 FROM chunk_embeddings WHERE chunk_id=? AND model=?",
                (chunk_id, self.model_name),
            ).fetchone():
                continue

            row = con.execute(
                """
                SELECT c.id, c.source_kind, c.gmail_id, c.attachment_rowid, c.text,
                       m.internal_date_ms, m.from_, m.to_
                FROM chunks c
                LEFT JOIN messages m ON m.gmail_id=c.gmail_id
                WHERE c.id=?
                """,
                (chunk_id,),
            ).fetchone()
            if not row:
                continue

            _cid, source_kind, gmail_id, attachment_rowid, text, internal_ms, from_, to_ = row
            if internal_ms is not None:
                if after_ms is not None and int(internal_ms) < int(after_ms):
                    continue
                if before_ms is not None and int(internal_ms) >= int(before_ms):
                    continue
            elif after_ms is not None or before_ms is not None:
                continue

            if not self._matches_contact_filter(from_, from_filter):
                continue
            if not self._matches_contact_filter(to_, to_filter):
                continue
            if label_ids and gmail_id:
                labels = {
                    r[0]
                    for r in con.execute(
                        "SELECT label_id FROM message_labels WHERE gmail_id=?",
                        (gmail_id,),
                    ).fetchall()
                }
                if not labels.intersection(label_ids):
                    continue

            out.append(
                {
                    "chunk_id": int(_cid),
                    "source_kind": source_kind,
                    "gmail_id": gmail_id,
                    "attachment_rowid": attachment_rowid,
                    "snippet": self._short_excerpt(text or ""),
                    "score": float(score),
                }
            )
            if len(out) >= limit:
                break
        return out

    def _rrf_fuse(self, keyword: list[dict[str, Any]], semantic: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
        k = 60.0
        fused: dict[int, dict[str, Any]] = {}

        def add(items: list[dict[str, Any]], key: str) -> None:
            for rank, item in enumerate(items, start=1):
                chunk_id = int(item["chunk_id"])
                existing = fused.setdefault(
                    chunk_id,
                    {"kw": None, "sem": None, "score": 0.0, "chunk_id": chunk_id},
                )
                existing["score"] += 1.0 / (k + rank)
                if existing[key] is None:
                    existing[key] = item

        add(keyword, "kw")
        add(semantic, "sem")
        ordered = sorted(fused.values(), key=lambda row: row["score"], reverse=True)
        return ordered[:limit]

    def gmail_permalink(self, *, gmail_id: str | None, thread_id: str | None, view: str = "inbox") -> str:
        if not gmail_id:
            return ""
        user_index = self._resolve_gmail_user_index()
        base = f"https://mail.google.com/mail/u/{user_index}/#"
        if thread_id:
            safe_thread = quote(str(thread_id), safe="")
            return f"{base}{view}/{safe_thread}"
        safe_gmail_id = quote(str(gmail_id), safe="")
        return f"{base}all/{safe_gmail_id}"

    def _resolve_gmail_user_index(self) -> int:
        env_value = os.getenv("GMAIL_RAG_GMAIL_U")
        if env_value is not None:
            try:
                return int(env_value)
            except ValueError:
                pass

        if self.settings_path.exists():
            try:
                payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
                val = payload.get("gmail_web_user_index")
                if val is not None:
                    return int(val)
            except Exception:
                pass
        return 0

    def _semantic_enabled(self) -> bool:
        return bool(self.validation.semantic_ready)

    def _connect_ro(self) -> sqlite3.Connection:
        uri = f"file:{self.db_path}?mode=ro"
        con = sqlite3.connect(uri, uri=True)
        con.row_factory = sqlite3.Row
        return con

    def _load_faiss_index(self) -> Any:
        if self._faiss_index is None:
            self._faiss_index = self.faiss_reader(str(self.faiss_index_path))
        return self._faiss_index

    @staticmethod
    def _default_faiss_reader(path: str) -> Any:
        import faiss

        return faiss.read_index(path)

    @staticmethod
    def _to_query_matrix(vec: Sequence[float]) -> Any:
        try:
            import numpy as np

            arr = np.asarray([list(vec)], dtype="float32")
            return arr
        except Exception:
            return [list(vec)]

    @staticmethod
    def _collapse_ws(value: str) -> str:
        return " ".join((value or "").split())

    @staticmethod
    def _short_excerpt(value: str, *, max_len: int = 280) -> str:
        text = LegacyGmailRagAdapter._collapse_ws(value)
        if len(text) <= max_len:
            return text
        return text[: max_len - 1].rstrip() + "…"

    @staticmethod
    def _sanitize_fts_query(query: str) -> str:
        q = (query or "").strip()
        q = re.sub(r"[^\w]+", " ", q, flags=re.UNICODE)
        return LegacyGmailRagAdapter._collapse_ws(q)

    @staticmethod
    def _matches_contact_filter(raw_header: str | None, filter_value: str | None) -> bool:
        if not filter_value:
            return True
        needle = (filter_value or "").strip().lower()
        if not needle:
            return True

        header = raw_header or ""
        header_l = header.lower()
        if "@" in needle:
            for _name, addr in getaddresses([header]):
                if (addr or "").strip().lower() == needle:
                    return True
        return needle in header_l

    @staticmethod
    def _parse_date_bound(raw: str | None) -> int | None:
        if not raw:
            return None
        day = dt.date.fromisoformat(str(raw))
        stamp = dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc)
        return int(stamp.timestamp() * 1000)

    @staticmethod
    def _normalize_direction(raw: Any) -> str | None:
        if raw is None:
            return None
        value = str(raw).strip().lower()
        if value in {"sent", "received", "unknown"}:
            return value
        return "unknown"

    @staticmethod
    def _direction_allows(requested: str | None, actual: str) -> bool:
        if not requested:
            return True
        if requested == "unknown":
            return actual == "unknown"
        # Legacy data is dominated by "unknown"; do not hard-exclude unknown for sent/received filters in phase 1.
        return actual == requested or actual == "unknown"

    @staticmethod
    def _match_mode(kw_h: dict[str, Any] | None, sem_h: dict[str, Any] | None) -> str:
        if kw_h and sem_h:
            return "kw+sem"
        if kw_h:
            return "kw"
        return "sem"

    @staticmethod
    def _resolve_label_ids(con: sqlite3.Connection, label_prefix: str | None) -> set[str] | None:
        if not label_prefix:
            return None
        prefix = str(label_prefix).rstrip("/")
        labels = con.execute("SELECT id, name FROM labels").fetchall()
        out = set()
        for label_id, name in labels:
            if not name or not label_id:
                continue
            if name == prefix or str(name).startswith(prefix + "/"):
                out.add(str(label_id))
        return out
