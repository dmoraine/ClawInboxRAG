from __future__ import annotations

import argparse
import ast
import json
import time
from pathlib import Path

from tqdm import tqdm

from . import db as dbmod
from .chunking import chunk_text
from .config import DEFAULT_EMBED_MODEL, PRIMARY_LABEL, SENT_LABEL, Paths
from .embed import append_meta, embed_texts, load_or_create, save
from .extract import extract_text_by_ext
from .gmail_client import (
    fetch_attachment_bytes,
    fetch_message,
    gmail_permalink,
    gmail_service,
    iter_message_ids,
    list_labels,
    load_creds,
    resolve_label_ids_by_prefix,
    should_keep_attachment,
    sha256_bytes,
)


SCOPES_READONLY = ["https://www.googleapis.com/auth/gmail.readonly"]


def cmd_init(args) -> None:
    p = Paths()
    con = dbmod.connect(p.db_path)
    dbmod.init_db(con)
    print(f"OK: db at {p.db_path}")


def _upsert_labels(con, labels: list[dict]) -> None:
    cur = con.cursor()
    for l in labels:
        lid = l.get("id")
        name = l.get("name")
        typ = l.get("type")
        if not lid:
            continue
        cur.execute(
            "INSERT INTO labels(id,name,type) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, type=excluded.type",
            (lid, name, typ),
        )
    con.commit()


def cmd_refresh_labels(args) -> None:
    """Refresh label definitions and message->label assignments.

    By default, only refreshes messages ingested in the last N days to avoid
    a full scan. Use --all to force a full refresh.
    """

    p = Paths()
    con = dbmod.connect(p.db_path)
    dbmod.init_db(con)
    creds = load_creds(p.gmail_token_path, SCOPES_READONLY)
    svc = gmail_service(creds)

    labels = list_labels(svc)
    _upsert_labels(con, labels)

    cur = con.cursor()

    if args.all:
        ids = [r[0] for r in cur.execute("SELECT gmail_id FROM messages").fetchall()]
        print(f"Refreshing labels for ALL {len(ids)} messages...")
    else:
        since_ms = int(time.time() * 1000) - int(args.days * 24 * 3600 * 1000)
        ids = [
            r[0]
            for r in cur.execute(
                "SELECT gmail_id FROM messages WHERE ingested_at_ms>=?",
                (since_ms,),
            ).fetchall()
        ]
        print(f"Refreshing labels for {len(ids)} recent messages (last {args.days} days)...")

    # Only fetch labelIds field (minimal payload).
    for mid in tqdm(ids):
        msg = (
            svc.users()
            .messages()
            .get(userId="me", id=mid, format="minimal", fields="labelIds")
            .execute()
        )
        label_ids = msg.get("labelIds", []) or []
        cur.execute("DELETE FROM message_labels WHERE gmail_id=?", (mid,))
        for lid in label_ids:
            cur.execute(
                "INSERT OR IGNORE INTO message_labels(gmail_id,label_id) VALUES(?,?)",
                (mid, lid),
            )
    con.commit()
    print("OK")


def _store_message(con, m) -> None:
    now = int(time.time() * 1000)
    cur = con.cursor()
    direction = _message_direction_from_labels(m.label_ids)
    cur.execute(
        """
        INSERT INTO messages(gmail_id, thread_id, internal_date_ms, rfc822_msgid, subject, from_, to_, date_header, snippet, body_text, size_estimate, message_direction, ingested_at_ms)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(gmail_id) DO NOTHING
        """,
        (
            m.gmail_id,
            m.thread_id,
            m.internal_date_ms,
            m.rfc822_msgid,
            m.subject,
            m.from_,
            m.to_,
            m.date_header,
            m.snippet,
            m.body_text,
            m.size_estimate,
            direction,
            now,
        ),
    )

    # labels
    cur.execute("DELETE FROM message_labels WHERE gmail_id=?", (m.gmail_id,))
    for lid in m.label_ids:
        cur.execute(
            "INSERT OR IGNORE INTO message_labels(gmail_id,label_id) VALUES(?,?)",
            (m.gmail_id, lid),
        )


def _store_attachments(con, svc, p: Paths, m) -> None:
    attachments = ast.literal_eval(m.headers.get("__attachments_json", "[]"))
    cur = con.cursor()

    for a in attachments:
        fn = a.get("filename")
        mt = a.get("mimeType")
        aid = a.get("attachmentId")
        size = a.get("size")
        if not should_keep_attachment(fn, mt, size):
            continue
        if not aid:
            continue

        # skip if already stored
        row = cur.execute(
            "SELECT id, stored_path, extracted_text FROM attachments WHERE gmail_id=? AND attachment_id=?",
            (m.gmail_id, aid),
        ).fetchone()
        if row and row[1] and Path(row[1]).exists() and (row[2] is not None):
            continue

        b = fetch_attachment_bytes(svc, m.gmail_id, aid)
        if not b:
            continue
        sha = sha256_bytes(b)

        out_dir = p.attachments_dir / m.gmail_id
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_fn = (fn or aid).replace("/", "_")
        out_path = out_dir / safe_fn
        out_path.write_bytes(b)
        out_path.chmod(0o600)

        text = extract_text_by_ext(out_path)

        now = int(time.time() * 1000)
        cur.execute(
            """
            INSERT INTO attachments(gmail_id, attachment_id, filename, mime_type, size_bytes, sha256, stored_path, extracted_text, ingested_at_ms)
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(gmail_id, attachment_id) DO UPDATE SET
              filename=excluded.filename,
              mime_type=excluded.mime_type,
              size_bytes=excluded.size_bytes,
              sha256=excluded.sha256,
              stored_path=excluded.stored_path,
              extracted_text=excluded.extracted_text,
              ingested_at_ms=excluded.ingested_at_ms
            """,
            (m.gmail_id, aid, fn, mt, len(b), sha, str(out_path), text, now),
        )


def _store_chunks(con, *, source_kind: str, gmail_id: str | None, attachment_rowid: int | None, text: str) -> int:
    cur = con.cursor()
    now = int(time.time() * 1000)
    chunks = chunk_text(text)
    n = 0
    for i, c in enumerate(chunks):
        cur.execute(
            """
            INSERT OR IGNORE INTO chunks(source_kind, gmail_id, attachment_rowid, chunk_ordinal, text, created_at_ms)
            VALUES(?,?,?,?,?,?)
            """,
            (source_kind, gmail_id, attachment_rowid, i, c, now),
        )
        if cur.rowcount:
            n += 1
    return n


def _message_direction_from_labels(label_ids: list[str] | None) -> str:
    labels = set(label_ids or [])
    if SENT_LABEL in labels:
        return "sent"
    if "INBOX" in labels or PRIMARY_LABEL in labels:
        return "received"
    return "unknown"


def _collect_unique_message_ids_for_labels(svc, *, label_ids: list[str], max_results: int | None) -> list[str]:
    ids: list[str] = []
    seen_ids: set[str] = set()

    for label_id in label_ids:
        for mid in iter_message_ids(svc, label_ids=[label_id], max_results=max_results):
            if mid in seen_ids:
                continue
            seen_ids.add(mid)
            ids.append(mid)
            if max_results and len(ids) >= max_results:
                return ids

    return ids


def _ingest_message_ids(con, svc, p: Paths, message_ids: list[str]) -> tuple[int, int]:
    cur = con.cursor()
    new_msgs = 0
    new_chunks = 0

    for mid in tqdm(message_ids):
        if cur.execute("SELECT 1 FROM messages WHERE gmail_id=?", (mid,)).fetchone():
            continue

        m = fetch_message(svc, mid)
        _store_message(con, m)
        con.commit()
        new_msgs += 1

        if m.body_text:
            new_chunks += _store_chunks(
                con,
                source_kind="email",
                gmail_id=m.gmail_id,
                attachment_rowid=None,
                text=m.body_text,
            )

        _store_attachments(con, svc, p, m)
        con.commit()

        rows = cur.execute(
            "SELECT id, extracted_text FROM attachments WHERE gmail_id=? AND extracted_text IS NOT NULL",
            (m.gmail_id,),
        ).fetchall()
        for rid, txt in rows:
            if txt:
                new_chunks += _store_chunks(
                    con,
                    source_kind="attachment",
                    gmail_id=m.gmail_id,
                    attachment_rowid=rid,
                    text=txt,
                )
        con.commit()

    return new_msgs, new_chunks


def cmd_ingest_primary(args) -> None:
    p = Paths()
    p.base.mkdir(parents=True, exist_ok=True)
    p.attachments_dir.mkdir(parents=True, exist_ok=True)

    con = dbmod.connect(p.db_path)
    dbmod.init_db(con)

    creds = load_creds(p.gmail_token_path, SCOPES_READONLY)
    svc = gmail_service(creds)

    labels = list_labels(svc)
    _upsert_labels(con, labels)

    max_n = args.limit
    print(f"Ingesting Primary ({PRIMARY_LABEL}) + Sent ({SENT_LABEL}) limit={max_n} ...")

    ids = _collect_unique_message_ids_for_labels(
        svc,
        label_ids=[PRIMARY_LABEL, SENT_LABEL],
        max_results=max_n,
    )
    new_msgs, new_chunks = _ingest_message_ids(con, svc, p, ids)

    print(f"OK: new messages={new_msgs}, new chunks={new_chunks}")


def cmd_ingest_label(args) -> None:
    p = Paths()
    con = dbmod.connect(p.db_path)
    dbmod.init_db(con)
    creds = load_creds(p.gmail_token_path, SCOPES_READONLY)
    svc = gmail_service(creds)

    all_labels = list_labels(svc)
    _upsert_labels(con, all_labels)

    label_name = args.label
    ids = resolve_label_ids_by_prefix(all_labels, label_name)
    if not ids:
        raise SystemExit(f"No labels found for prefix: {label_name}")

    mids = list(iter_message_ids(svc, label_ids=ids, max_results=args.limit))
    print(f"Ingesting label prefix {label_name} (ids={len(ids)}) candidates={len(mids)}")
    new_msgs, new_chunks = _ingest_message_ids(con, svc, p, mids)

    print(f"OK: new messages={new_msgs}, new chunks={new_chunks}")


def cmd_embed(args) -> None:
    p = Paths()
    con = dbmod.connect(p.db_path)
    dbmod.init_db(con)

    model_name = args.model or DEFAULT_EMBED_MODEL
    print(f"Loading embedding model: {model_name}")
    model = __import__("sentence_transformers").SentenceTransformer(model_name)

    cur = con.cursor()
    rows = cur.execute(
        """
        SELECT c.id, c.text, c.source_kind, c.gmail_id, c.attachment_rowid
        FROM chunks c
        LEFT JOIN chunk_embeddings e ON e.chunk_id=c.id AND e.model=?
        WHERE e.chunk_id IS NULL
        ORDER BY c.id
        LIMIT ?
        """,
        (model_name, args.limit),
    ).fetchall()

    if not rows:
        print("No new chunks to embed.")
        return

    texts = [r[1] for r in rows]
    emb = embed_texts(model, texts)
    dim = emb.shape[1]

    store = load_or_create(p.faiss_index_path, p.faiss_meta_path, dim)
    store.index.add(emb)

    meta_rows = []
    now = int(time.time() * 1000)
    for r in rows:
        chunk_id, _text, sk, gmail_id, att_rowid = r
        meta_rows.append(
            {
                "chunk_id": chunk_id,
                "source_kind": sk,
                "gmail_id": gmail_id,
                "attachment_rowid": att_rowid,
                "model": model_name,
            }
        )
        cur.execute(
            "INSERT OR REPLACE INTO chunk_embeddings(chunk_id, model, dim, embedded_at_ms) VALUES(?,?,?,?)",
            (chunk_id, model_name, dim, now),
        )

    con.commit()
    append_meta(p.faiss_meta_path, meta_rows)
    save(store, p.faiss_index_path)
    print(f"OK: embedded {len(rows)} chunks")


def _collapse_ws(s: str) -> str:
    return " ".join((s or "").split())


def _sanitize_fts_query(q: str) -> str:
    """Sanitize a user query for SQLite FTS5 MATCH.

    We treat input as plain text (no FTS operators). This avoids crashes on
    characters like '-' that FTS5 interprets as query syntax.

    Strategy: replace any non-word characters with spaces, then collapse.
    Example: "on-demand" -> "on demand".
    """
    import re

    q = (q or "").strip()
    # Replace anything that's not a unicode "word" char with a space.
    q = re.sub(r"[^\w]+", " ", q, flags=re.UNICODE)
    return _collapse_ws(q)


def _short_excerpt(s: str, *, max_len: int = 280) -> str:
    s = _collapse_ws(s)
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def _matches_contact_filter(raw_header: str | None, filter_value: str | None) -> bool:
    """Match a sender/recipient header with exact-email + substring fallback."""
    if not filter_value:
        return True

    needle = (filter_value or "").strip().lower()
    if not needle:
        return True

    header = raw_header or ""
    header_l = header.lower()

    # For email-like needles, prefer exact address matching first.
    if "@" in needle:
        from email.utils import getaddresses

        for _name, addr in getaddresses([header]):
            if (addr or "").strip().lower() == needle:
                return True

    return needle in header_l


def _resolve_label_ids(con, label_prefix: str | None) -> set[str] | None:
    if not label_prefix:
        return None
    labels = [dict(id=r[0], name=r[1]) for r in con.execute("SELECT id,name FROM labels").fetchall()]
    return set(resolve_label_ids_by_prefix(labels, label_prefix))


def _keyword_hits(
    con,
    *,
    query: str,
    limit: int,
    label_ids: set[str] | None,
    from_filter: str | None = None,
    to_filter: str | None = None,
    after_ms: int | None = None,
    before_ms: int | None = None,
):
    cur = con.cursor()

    fts_query = _sanitize_fts_query(query)
    if not fts_query:
        return []

    where_parts = ["chunks_fts MATCH ?"]
    params: list[object] = [fts_query]

    if after_ms is not None or before_ms is not None:
        # Filter on message date using messages.internal_date_ms.
        sub = ["SELECT gmail_id FROM messages WHERE 1=1"]
        if after_ms is not None:
            sub.append(" AND internal_date_ms >= ?")
            params.append(int(after_ms))
        if before_ms is not None:
            sub.append(" AND internal_date_ms < ?")
            params.append(int(before_ms))
        where_parts.append(f"c.gmail_id IN ({''.join(sub)})")

    where_sql = " AND ".join(where_parts)

    rows = cur.execute(
        f"""
        SELECT c.id, c.source_kind, c.gmail_id, c.attachment_rowid,
               snippet(chunks_fts, 0, '', '', '…', 12) AS snip
        FROM chunks_fts
        JOIN chunks c ON c.id = chunks_fts.rowid
        WHERE {where_sql}
        ORDER BY rank
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()

    out = []
    for cid, sk, gid, att, snip in rows:
        msg_row = None
        if gid:
            msg_row = cur.execute(
                "SELECT from_, to_ FROM messages WHERE gmail_id=?",
                (gid,),
            ).fetchone()
        from_ = msg_row[0] if msg_row else None
        to_ = msg_row[1] if msg_row else None

        if not _matches_contact_filter(from_, from_filter):
            continue
        if not _matches_contact_filter(to_, to_filter):
            continue

        if label_ids and gid:
            lids = {x[0] for x in cur.execute("SELECT label_id FROM message_labels WHERE gmail_id=?", (gid,)).fetchall()}
            if not (lids & label_ids):
                continue
        out.append(
            {
                "chunk_id": cid,
                "source_kind": sk,
                "gmail_id": gid,
                "attachment_rowid": att,
                "snippet": _collapse_ws(snip or ""),
            }
        )
    return out


def _semantic_hits(
    con,
    *,
    query: str,
    limit: int,
    label_ids: set[str] | None,
    from_filter: str | None = None,
    to_filter: str | None = None,
    model_name: str | None = None,
    after_ms: int | None = None,
    before_ms: int | None = None,
):
    p = Paths()
    if not p.faiss_index_path.exists() or not p.faiss_meta_path.exists():
        raise SystemExit(
            f"FAISS index not found. Run embed first (index={p.faiss_index_path}, meta={p.faiss_meta_path})."
        )

    # Lazy import so keyword-only usage doesn't require faiss.
    import json as _json
    import numpy as np
    import faiss

    if model_name is None:
        model_name = DEFAULT_EMBED_MODEL

    # Load model to embed the query only.
    model = __import__("sentence_transformers").SentenceTransformer(model_name)
    qemb = embed_texts(model, [query])

    idx = faiss.read_index(str(p.faiss_index_path))

    # Read all meta rows (one per vector) so we can map faiss positions -> chunk_id.
    meta = []
    with p.faiss_meta_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            meta.append(_json.loads(line))

    if len(meta) != idx.ntotal:
        raise SystemExit(f"FAISS index/meta mismatch: index ntotal={idx.ntotal} meta lines={len(meta)}")

    # Pull more candidates to survive filtering.
    k = min(max(limit * 20, 50), idx.ntotal)
    scores, ids = idx.search(qemb.astype(np.float32), k)
    scores = scores[0].tolist()
    ids = ids[0].tolist()

    cur = con.cursor()
    out = []
    seen = set()
    for pos, score in zip(ids, scores):
        if pos < 0:
            continue
        m = meta[pos]
        cid = int(m.get("chunk_id"))
        if cid in seen:
            continue
        seen.add(cid)

        # Ensure the chunk exists & has an embedding for this model.
        if not cur.execute(
            "SELECT 1 FROM chunk_embeddings WHERE chunk_id=? AND model=?",
            (cid, model_name),
        ).fetchone():
            continue

        row = cur.execute(
            """
            SELECT c.id, c.source_kind, c.gmail_id, c.attachment_rowid, c.text, m.internal_date_ms, m.from_, m.to_
            FROM chunks c
            LEFT JOIN messages m ON m.gmail_id=c.gmail_id
            WHERE c.id=?
            """,
            (cid,),
        ).fetchone()
        if not row:
            continue
        _cid, sk, gid, att, txt, internal_ms, from_, to_ = row

        if internal_ms is not None:
            if after_ms is not None and int(internal_ms) < int(after_ms):
                continue
            if before_ms is not None and int(internal_ms) >= int(before_ms):
                continue

        if not _matches_contact_filter(from_, from_filter):
            continue
        if not _matches_contact_filter(to_, to_filter):
            continue

        if label_ids and gid:
            lids = {x[0] for x in cur.execute("SELECT label_id FROM message_labels WHERE gmail_id=?", (gid,)).fetchall()}
            if not (lids & label_ids):
                continue

        out.append(
            {
                "chunk_id": _cid,
                "source_kind": sk,
                "gmail_id": gid,
                "attachment_rowid": att,
                "snippet": _short_excerpt(txt or ""),
                "score": float(score),
            }
        )
        if len(out) >= limit:
            break

    return out


def _rrf_fuse(keyword, semantic, *, limit: int):
    """Reciprocal Rank Fusion across two ranked lists."""

    k = 60.0
    fused = {}

    def add(lst, key: str):
        for rank, h in enumerate(lst, start=1):
            cid = h["chunk_id"]
            fused.setdefault(cid, {"chunk_id": cid, "kw": None, "sem": None, "score": 0.0})
            fused[cid]["score"] += 1.0 / (k + rank)
            if fused[cid][key] is None:
                fused[cid][key] = h

    add(keyword, "kw")
    add(semantic, "sem")

    ranked = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
    return ranked[:limit]


def _parse_date_bound(s: str | None, *, kind: str) -> int | None:
    """Parse a fuzzy date string into an epoch-ms bound.

    Supported inputs:
      - YYYY
      - MM/YYYY
      - YYYY-MM
      - YYYY-MM-DD

    Semantics:
      - kind="after": start boundary (inclusive)
      - kind="before": end boundary (exclusive)

    For month/year inputs, uses the first day of the month.
    For year-only, uses Jan 1.
    """

    if not s:
        return None

    import calendar
    import datetime as dt
    import re

    t = s.strip()

    m = re.fullmatch(r"(\d{4})", t)
    if m:
        y = int(m.group(1))
        d = dt.datetime(y, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
        return int(d.timestamp() * 1000)

    m = re.fullmatch(r"(\d{1,2})/(\d{4})", t)
    if m:
        mo = int(m.group(1))
        y = int(m.group(2))
        d = dt.datetime(y, mo, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
        return int(d.timestamp() * 1000)

    m = re.fullmatch(r"(\d{4})-(\d{1,2})", t)
    if m:
        y = int(m.group(1))
        mo = int(m.group(2))
        d = dt.datetime(y, mo, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
        return int(d.timestamp() * 1000)

    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        y = int(m.group(1))
        mo = int(m.group(2))
        da = int(m.group(3))
        d = dt.datetime(y, mo, da, 0, 0, 0, tzinfo=dt.timezone.utc)
        return int(d.timestamp() * 1000)

    raise SystemExit(f"Invalid {kind} date: {s} (expected YYYY, MM/YYYY, YYYY-MM, or YYYY-MM-DD)")


def cmd_search(args) -> None:
    p = Paths()
    con = dbmod.connect(p.db_path)
    dbmod.init_db(con)

    q = args.query
    limit = args.limit

    label_ids = _resolve_label_ids(con, args.label)

    after_ms = _parse_date_bound(getattr(args, "after", None), kind="after")
    before_ms = _parse_date_bound(getattr(args, "before", None), kind="before")

    mode = "keyword"
    if args.semantic:
        mode = "semantic"
    if args.hybrid:
        mode = "hybrid"

    cur = con.cursor()

    if mode == "keyword":
        kw = _keyword_hits(
            con,
            query=q,
            limit=limit,
            label_ids=label_ids,
            from_filter=getattr(args, "from_", None),
            to_filter=getattr(args, "to", None),
            after_ms=after_ms,
            before_ms=before_ms,
        )
        print(f"Top {len(kw)} keyword hits:")
        hits = [(h, None) for h in kw]
    elif mode == "semantic":
        sem = _semantic_hits(
            con,
            query=q,
            limit=limit,
            label_ids=label_ids,
            from_filter=getattr(args, "from_", None),
            to_filter=getattr(args, "to", None),
            model_name=args.model,
            after_ms=after_ms,
            before_ms=before_ms,
        )
        print(f"Top {len(sem)} semantic hits:")
        hits = [(None, h) for h in sem]
    else:
        kw = _keyword_hits(
            con,
            query=q,
            limit=limit * 5,
            label_ids=label_ids,
            from_filter=getattr(args, "from_", None),
            to_filter=getattr(args, "to", None),
            after_ms=after_ms,
            before_ms=before_ms,
        )
        sem = _semantic_hits(
            con,
            query=q,
            limit=limit * 5,
            label_ids=label_ids,
            from_filter=getattr(args, "from_", None),
            to_filter=getattr(args, "to", None),
            model_name=args.model,
            after_ms=after_ms,
            before_ms=before_ms,
        )
        fused = _rrf_fuse(kw, sem, limit=limit)
        print(f"Top {len(fused)} hybrid hits (RRF fusion):")
        hits = [(x.get("kw"), x.get("sem")) for x in fused]

    # Dedupe: in hybrid/semantic/keyword results we can get multiple chunks from the same Gmail message.
    # Keep the best-scoring instance per gmail_id (earliest rank in the hit list).
    seen_gids: set[str] = set()

    for kw_h, sem_h in hits:
        h = kw_h or sem_h
        cid = h["chunk_id"]
        sk = h["source_kind"]
        gid = h["gmail_id"]
        att = h["attachment_rowid"]
        snip = h.get("snippet") or ""

        if gid and gid in seen_gids:
            continue
        if gid:
            seen_gids.add(gid)

        m = (
            cur.execute(
                "SELECT date_header, from_, subject, thread_id FROM messages WHERE gmail_id=?",
                (gid,),
            ).fetchone()
            if gid
            else None
        )
        date_h, from_, subj, thread_id = m if m else (None, None, None, None)

        att_info = ""
        if sk == "attachment" and att is not None:
            arow = cur.execute("SELECT filename FROM attachments WHERE id=?", (att,)).fetchone()
            if arow and arow[0]:
                att_info = f" | attachment={arow[0]}"

        link = gmail_permalink(gid, thread_id=thread_id, view="inbox") if gid else ""

        extra = []
        if kw_h is not None and mode == "hybrid":
            extra.append("kw")
        if sem_h is not None and mode == "hybrid":
            extra.append("sem")
        tag = f" ({'+'.join(extra)})" if extra else ""

        # Compact snippet for stable summaries.
        snip = _collapse_ws(snip)
        if len(snip) > 240:
            snip = snip[:240].rstrip() + "…"

        print(f"- [{cid}] {date_h} | {from_} | {subj} | {link}{att_info}{tag}\n  {snip}")



def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gmail-rag")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("refresh-labels")
    sp.add_argument("--days", type=int, default=30, help="only refresh messages ingested in last N days")
    sp.add_argument("--all", action="store_true", help="refresh labels for all ingested messages (slow)")
    sp.set_defaults(func=cmd_refresh_labels)

    sp = sub.add_parser("ingest-primary", help="ingest personal inbox + sent mail")
    sp.add_argument("--limit", type=int, default=200, help="max unique messages across personal and sent")
    sp.set_defaults(func=cmd_ingest_primary)

    sp = sub.add_parser("ingest-label")
    sp.add_argument("label")
    sp.add_argument("--limit", type=int, default=200)
    sp.set_defaults(func=cmd_ingest_label)

    sp = sub.add_parser("embed")
    sp.add_argument("--limit", type=int, default=1000)
    sp.add_argument("--model", default=None)
    sp.set_defaults(func=cmd_embed)

    sp = sub.add_parser("search")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--label", default=None, help="label prefix filter (includes sublabels)")
    sp.add_argument("--from", dest="from_", default=None, help="sender filter (exact email or case-insensitive substring)")
    sp.add_argument("--to", default=None, help="recipient filter (exact email or case-insensitive substring)")
    sp.add_argument("--after", default=None, help="date lower bound (inclusive): YYYY | MM/YYYY | YYYY-MM | YYYY-MM-DD")
    sp.add_argument("--before", default=None, help="date upper bound (exclusive): YYYY | MM/YYYY | YYYY-MM | YYYY-MM-DD")
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--semantic", action="store_true", help="semantic (FAISS) search only")
    g.add_argument("--hybrid", action="store_true", help="hybrid keyword+semantic search (fusion)")
    sp.add_argument("--model", default=None, help="embedding model for semantic/hybrid query")
    sp.set_defaults(func=cmd_search)

    return p


def main(argv=None) -> None:
    p = build_parser()
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
