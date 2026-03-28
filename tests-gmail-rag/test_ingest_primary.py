from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gmail_rag import cli
from gmail_rag import db as dbmod
from gmail_rag.gmail_client import GmailMessage


class IngestPrimaryTests(unittest.TestCase):
    def _msg(self, gmail_id: str, label_ids: list[str]) -> GmailMessage:
        return GmailMessage(
            gmail_id=gmail_id,
            thread_id=f"t-{gmail_id}",
            internal_date_ms=1,
            label_ids=label_ids,
            headers={"Subject": f"subj-{gmail_id}", "From": "from@example.com", "To": "to@example.com"},
            snippet="snippet",
            body_text="body",
            size_estimate=123,
        )

    def test_message_direction_from_labels(self) -> None:
        self.assertEqual(cli._message_direction_from_labels(["SENT"]), "sent")
        self.assertEqual(cli._message_direction_from_labels(["CATEGORY_PERSONAL"]), "received")
        self.assertEqual(cli._message_direction_from_labels(["INBOX"]), "received")
        self.assertEqual(cli._message_direction_from_labels(["STARRED"]), "unknown")

    def test_ingest_primary_includes_sent_and_dedupes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            db_path = base / "db.sqlite"

            # Pre-seed one existing message to ensure cmd_ingest_primary skips it.
            con = dbmod.connect(db_path)
            dbmod.init_db(con)
            con.execute(
                """
                INSERT INTO messages(gmail_id, thread_id, internal_date_ms, rfc822_msgid, subject, from_, to_, date_header, snippet, body_text, size_estimate, ingested_at_ms)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                ("m1", "t-m1", 1, None, "existing", "x", "y", None, None, None, None, 1),
            )
            con.commit()
            con.close()

            class _Paths:
                def __init__(self, root: Path):
                    self.base = root

                @property
                def db_path(self) -> Path:
                    return self.base / "db.sqlite"

                @property
                def attachments_dir(self) -> Path:
                    return self.base / "attachments"

                @property
                def gmail_token_path(self) -> Path:
                    return self.base / "token.json"

            def _iter_ids(_svc, *, query=None, label_ids=None, max_results=None):
                del _svc, query, max_results
                if label_ids == ["CATEGORY_PERSONAL"]:
                    yield "m1"
                    yield "m2"
                elif label_ids == ["SENT"]:
                    yield "m2"
                    yield "m3"

            msg_map = {
                "m2": self._msg("m2", ["CATEGORY_PERSONAL", "SENT"]),
                "m3": self._msg("m3", ["SENT"]),
            }

            with (
                mock.patch.object(cli, "Paths", return_value=_Paths(base)),
                mock.patch.object(cli, "load_creds", return_value=object()),
                mock.patch.object(cli, "gmail_service", return_value=object()),
                mock.patch.object(
                    cli,
                    "list_labels",
                    return_value=[
                        {"id": "CATEGORY_PERSONAL", "name": "CATEGORY_PERSONAL", "type": "system"},
                        {"id": "SENT", "name": "SENT", "type": "system"},
                    ],
                ),
                mock.patch.object(cli, "iter_message_ids", side_effect=_iter_ids),
                mock.patch.object(cli, "fetch_message", side_effect=lambda _svc, mid: msg_map[mid]) as fetch_mock,
                mock.patch.object(cli, "_store_attachments"),
                mock.patch.object(cli, "_store_chunks", return_value=0),
            ):
                cli.cmd_ingest_primary(argparse.Namespace(limit=10))

            con = dbmod.connect(db_path)
            rows = con.execute(
                "SELECT gmail_id, message_direction FROM messages ORDER BY gmail_id"
            ).fetchall()
            con.close()

            self.assertEqual(rows, [("m1", "unknown"), ("m2", "sent"), ("m3", "sent")])
            self.assertEqual(fetch_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
