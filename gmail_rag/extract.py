from __future__ import annotations

import subprocess
from pathlib import Path

from docx import Document


def extract_pdf_text(path: Path) -> str:
    # poppler-utils pdftotext
    res = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if res.returncode != 0:
        return ""
    return res.stdout.decode("utf-8", errors="replace").strip()


def extract_docx_text(path: Path) -> str:
    doc = Document(str(path))
    paras = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    return "\n".join(paras).strip()


def extract_text_by_ext(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf_text(path)
    if ext == ".docx":
        return extract_docx_text(path)
    return ""
