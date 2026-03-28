from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import faiss
import numpy as np


@dataclass
class SemanticHit:
    chunk_id: int
    score: float
    source_kind: str
    gmail_id: str | None
    attachment_rowid: int | None


def load_faiss(index_path: Path) -> faiss.Index:
    return faiss.read_index(str(index_path))


def load_meta(meta_path: Path) -> list[dict]:
    rows: list[dict] = []
    if not meta_path.exists():
        return rows
    with meta_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def search(index: faiss.Index, meta: list[dict], query_vec: np.ndarray, topk: int) -> list[SemanticHit]:
    """Search FAISS and map vector positions -> chunk_id via meta jsonl alignment."""
    if query_vec.ndim == 1:
        query_vec = query_vec.reshape(1, -1)
    scores, idxs = index.search(query_vec.astype("float32"), topk)

    out: list[SemanticHit] = []
    for score, pos in zip(scores[0].tolist(), idxs[0].tolist()):
        if pos < 0:
            continue
        if pos >= len(meta):
            # meta and index out of sync
            continue
        m = meta[pos]
        out.append(
            SemanticHit(
                chunk_id=int(m["chunk_id"]),
                score=float(score),
                source_kind=m.get("source_kind") or "",
                gmail_id=m.get("gmail_id"),
                attachment_rowid=m.get("attachment_rowid"),
            )
        )
    return out
