from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    base: Path = Path("/home/openclaw/.openclaw/gmail-rag")

    @property
    def db_path(self) -> Path:
        return self.base / "db.sqlite"

    @property
    def attachments_dir(self) -> Path:
        return self.base / "attachments"

    @property
    def index_dir(self) -> Path:
        return self.base / "index"

    @property
    def faiss_index_path(self) -> Path:
        return self.index_dir / "chunks.faiss"

    @property
    def faiss_meta_path(self) -> Path:
        return self.index_dir / "chunks_meta.jsonl"

    @property
    def gmail_token_path(self) -> Path:
        return Path("/home/openclaw/.openclaw/gmail/token.json")


DEFAULT_EMBED_MODEL = "intfloat/multilingual-e5-base"

# Gmail system label for Primary.
PRIMARY_LABEL = "CATEGORY_PERSONAL"
SENT_LABEL = "SENT"

# Attachment limits
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024

SUPPORTED_ATTACHMENT_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
}

SUPPORTED_ATTACHMENT_EXTS = {".pdf", ".docx"}
