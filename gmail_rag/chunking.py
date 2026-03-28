from __future__ import annotations

import re
from typing import Iterable, Iterator


def chunk_text(text: str, *, max_chars: int = 2800, overlap_chars: int = 200) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []

    # paragraph-based split
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0

    def flush():
        nonlocal buf, buf_len
        if not buf:
            return
        s = "\n\n".join(buf).strip()
        if s:
            chunks.append(s)
        buf = []
        buf_len = 0

    for p in paras:
        if len(p) > max_chars:
            # hard split long paragraph
            for i in range(0, len(p), max_chars):
                part = p[i : i + max_chars]
                if part.strip():
                    chunks.append(part.strip())
            continue

        if buf_len + len(p) + 2 <= max_chars:
            buf.append(p)
            buf_len += len(p) + 2
        else:
            flush()
            buf.append(p)
            buf_len = len(p) + 2

    flush()

    # add overlap by duplicating tail chars from previous chunk
    if overlap_chars > 0 and len(chunks) > 1:
        out: list[str] = [chunks[0]]
        for prev, cur in zip(chunks, chunks[1:]):
            tail = prev[-overlap_chars:]
            out.append((tail + "\n" + cur).strip())
        return out

    return chunks
