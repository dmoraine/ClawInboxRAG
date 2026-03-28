from __future__ import annotations

import base64
import hashlib
import re
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import MAX_ATTACHMENT_BYTES, SUPPORTED_ATTACHMENT_EXTS, SUPPORTED_ATTACHMENT_MIMES


@dataclass
class GmailMessage:
    gmail_id: str
    thread_id: str | None
    internal_date_ms: int | None
    label_ids: list[str]
    headers: dict[str, str]
    snippet: str | None
    body_text: str | None
    size_estimate: int | None

    @property
    def subject(self) -> str | None:
        return self.headers.get("Subject")

    @property
    def from_(self) -> str | None:
        return self.headers.get("From")

    @property
    def to_(self) -> str | None:
        return self.headers.get("To")

    @property
    def date_header(self) -> str | None:
        return self.headers.get("Date")

    @property
    def rfc822_msgid(self) -> str | None:
        return self.headers.get("Message-Id") or self.headers.get("Message-ID")


HEADER_WANT = [
    "From",
    "To",
    "Cc",
    "Bcc",
    "Subject",
    "Date",
    "Message-Id",
    "Message-ID",
]


def load_creds(token_path: Path, scopes: list[str]) -> Credentials:
    return Credentials.from_authorized_user_file(str(token_path), scopes)


def gmail_service(creds: Credentials):
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def list_labels(service) -> list[dict[str, Any]]:
    res = service.users().labels().list(userId="me").execute()
    return res.get("labels", [])


def resolve_label_ids_by_prefix(labels: list[dict[str, Any]], prefix_name: str) -> list[str]:
    prefix = prefix_name.rstrip("/")
    ids: list[str] = []
    for l in labels:
        name = l.get("name")
        lid = l.get("id")
        if not name or not lid:
            continue
        if name == prefix or name.startswith(prefix + "/"):
            ids.append(lid)
    return sorted(set(ids))


def iter_message_ids(
    service,
    *,
    query: str | None = None,
    label_ids: list[str] | None = None,
    max_results: int | None = None,
) -> Iterator[str]:
    page_token = None
    fetched = 0
    while True:
        kwargs: dict[str, Any] = {"userId": "me"}
        if query:
            kwargs["q"] = query
        if label_ids:
            kwargs["labelIds"] = label_ids
        if page_token:
            kwargs["pageToken"] = page_token
        kwargs["maxResults"] = 500
        res = service.users().messages().list(**kwargs).execute()
        msgs = res.get("messages", [])
        for m in msgs:
            mid = m.get("id")
            if not mid:
                continue
            yield mid
            fetched += 1
            if max_results and fetched >= max_results:
                return
        page_token = res.get("nextPageToken")
        if not page_token:
            return


def _decode_body(data: str) -> str:
    raw = base64.urlsafe_b64decode(data.encode("utf-8"))
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    # remove scripts/styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    return normalize_text(text)


QUOTED_RE = re.compile(r"^>+", re.M)


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # drop very common quoted reply markers naively
    lines = []
    for line in text.split("\n"):
        if QUOTED_RE.match(line.strip()):
            continue
        lines.append(line)
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def extract_body_and_attachments(payload: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
    """Return body_text and attachment part metadata (filename, mimeType, body.attachmentId, body.size)."""

    attachments: list[dict[str, Any]] = []

    def walk(part: dict[str, Any]):
        mime = part.get("mimeType")
        filename = part.get("filename")
        body = part.get("body", {})
        if filename and body and body.get("attachmentId"):
            attachments.append(
                {
                    "filename": filename,
                    "mimeType": mime,
                    "attachmentId": body.get("attachmentId"),
                    "size": body.get("size"),
                }
            )
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)

    # body selection: prefer text/plain; fallback to text/html
    def find_first(part: dict[str, Any], want_mime: str) -> str | None:
        if part.get("mimeType") == want_mime and part.get("body", {}).get("data"):
            return _decode_body(part["body"]["data"])
        for child in part.get("parts", []) or []:
            r = find_first(child, want_mime)
            if r:
                return r
        return None

    plain = find_first(payload, "text/plain")
    if plain:
        return normalize_text(plain), attachments
    html = find_first(payload, "text/html")
    if html:
        return _html_to_text(html), attachments
    return None, attachments


def fetch_message(service, gmail_id: str) -> GmailMessage:
    msg = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=gmail_id,
            format="full",
            metadataHeaders=HEADER_WANT,
        )
        .execute()
    )
    payload = msg.get("payload", {})
    headers_list = payload.get("headers", [])
    headers = {h.get("name"): h.get("value") for h in headers_list if h.get("name") and h.get("value")}
    body_text, attachments = extract_body_and_attachments(payload)
    # stash attachments in a hidden header-like key so caller can use it without re-walking
    headers["__attachments_json"] = str(attachments)

    return GmailMessage(
        gmail_id=gmail_id,
        thread_id=msg.get("threadId"),
        internal_date_ms=int(msg["internalDate"]) if msg.get("internalDate") else None,
        label_ids=msg.get("labelIds", []) or [],
        headers=headers,
        snippet=msg.get("snippet"),
        body_text=body_text,
        size_estimate=msg.get("sizeEstimate"),
    )


def fetch_attachment_bytes(service, gmail_id: str, attachment_id: str) -> bytes:
    att = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=gmail_id, id=attachment_id)
        .execute()
    )
    data = att.get("data")
    if not data:
        return b""
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def should_keep_attachment(filename: str | None, mime_type: str | None, size: int | None) -> bool:
    if not filename or not mime_type:
        return False
    if size and size > MAX_ATTACHMENT_BYTES:
        return False
    ext = Path(filename).suffix.lower()
    if ext in SUPPORTED_ATTACHMENT_EXTS:
        return True
    if mime_type in SUPPORTED_ATTACHMENT_MIMES:
        return True
    return False


def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def gmail_permalink(gmail_id: str, *, thread_id: str | None = None, view: str = "inbox") -> str:
    """Best-effort link to open a message in Gmail web.

    Prefer `thread_id` (Gmail thread) because it matches what Gmail web uses in
    URLs like `#inbox/<threadId>`.

    Gmail's web UI uses an account "slot" in the URL (`/mail/u/<N>/`). In browsers
    with multiple Google accounts, this is not always `0`.

    We resolve `<N>` from (first match wins):
    - env var `GMAIL_RAG_GMAIL_U`
    - JSON settings file: `/home/openclaw/.openclaw/gmail-rag/settings.json` with key `gmail_web_user_index`
    - fallback: 0

    Args:
      gmail_id: Gmail API message id.
      thread_id: Gmail API thread id (preferred for web URLs).
      view: "inbox" (default) or "all".
    """

    import json
    import os

    u = os.environ.get("GMAIL_RAG_GMAIL_U")
    if u is None:
        try:
            with open("/home/openclaw/.openclaw/gmail-rag/settings.json", "r", encoding="utf-8") as f:
                u = str(json.load(f).get("gmail_web_user_index", "0"))
        except FileNotFoundError:
            u = "0"
        except Exception:
            u = "0"

    u = "".join(ch for ch in str(u) if ch.isdigit()) or "0"

    if view not in {"inbox", "all"}:
        view = "inbox"

    if thread_id:
        return f"https://mail.google.com/mail/u/{u}/#{view}/{thread_id}"

    # Fallback: Gmail API message id sometimes works under #all/<id>.
    return f"https://mail.google.com/mail/u/{u}/#all/{gmail_id}"
