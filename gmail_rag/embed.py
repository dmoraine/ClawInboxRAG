from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


@dataclass
class FaissStore:
    index: faiss.Index
    meta_path: Path
    dim: int


def load_or_create(index_path: Path, meta_path: Path, dim: int) -> FaissStore:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.parent.mkdir(parents=True, exist_ok=True)

    if index_path.exists():
        idx = faiss.read_index(str(index_path))
        return FaissStore(index=idx, meta_path=meta_path, dim=idx.d)

    idx = faiss.IndexFlatIP(dim)
    return FaissStore(index=idx, meta_path=meta_path, dim=dim)


def save(store: FaissStore, index_path: Path) -> None:
    faiss.write_index(store.index, str(index_path))


def append_meta(meta_path: Path, rows: list[dict]) -> None:
    with meta_path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def embed_texts(model: SentenceTransformer, texts: list[str]) -> np.ndarray:
    """Embed texts as normalized float32 vectors."""
    emb = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    if isinstance(emb, list):
        emb = np.array(emb, dtype="float32")
    return emb.astype("float32")
