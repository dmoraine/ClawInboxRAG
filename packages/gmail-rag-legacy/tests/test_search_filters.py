from __future__ import annotations

import datetime as dt
import unittest
from pathlib import Path

from gmail_rag import cli
from gmail_rag import db as dbmod


def _ms(year: int, month: int, day: int) -> int:
    d = dt.datetime(year, month, day, 0, 0, 0, tzinfo=dt.timezone.utc)
    return int(d.timestamp() * 1000)


def _seed_basic(con) -> None:
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO messages(gmail_id, thread_id, internal_date_ms, from_, to_, date_header, subject, ingested_at_ms)
        VALUES(?,?,?,?,?,?,?,?)
        """,
        ("m1", "t1", _ms(2025, 1, 10), "Didier <didier@example.com>", "PVS <pvs@example.com>", "2025-01-10", "S1", 1),
    )
    cur.execute(
        """
        INSERT INTO messages(gmail_id, thread_id, internal_date_ms, from_, to_, date_header, subject, ingested_at_ms)
        VALUES(?,?,?,?,?,?,?,?)
        """,
        ("m2", "t2", _ms(2025, 2, 10), "didier lab <team@example.com>", "ops@example.com", "2025-02-10", "S2", 1),
    )
    cur.execute("INSERT INTO labels(id,name,type) VALUES('L1','work','user')")
    cur.execute("INSERT INTO labels(id,name,type) VALUES('L2','personal','user')")
    cur.execute("INSERT INTO message_labels(gmail_id,label_id) VALUES('m1','L1')")
    cur.execute("INSERT INTO message_labels(gmail_id,label_id) VALUES('m2','L2')")
    cur.execute(
        """
        INSERT INTO chunks(source_kind, gmail_id, attachment_rowid, chunk_ordinal, text, created_at_ms)
        VALUES('email','m1',NULL,0,'launch plan alpha',1)
        """
    )
    cur.execute(
        """
        INSERT INTO chunks(source_kind, gmail_id, attachment_rowid, chunk_ordinal, text, created_at_ms)
        VALUES('email','m2',NULL,0,'launch plan beta',1)
        """
    )
    con.commit()


class SearchFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.con = dbmod.connect(Path(":memory:"))
        dbmod.init_db(self.con)
        _seed_basic(self.con)

    def tearDown(self) -> None:
        self.con.close()

    def test_contact_filter_prefers_exact_email_then_fallback_substring(self) -> None:
        exact = cli._keyword_hits(
            self.con,
            query="launch",
            limit=10,
            label_ids=None,
            from_filter="didier@example.com",
            to_filter=None,
        )
        self.assertEqual([h["gmail_id"] for h in exact], ["m1"])

        fallback = cli._keyword_hits(
            self.con,
            query="launch",
            limit=10,
            label_ids=None,
            from_filter="DIDIER",
            to_filter=None,
        )
        self.assertEqual([h["gmail_id"] for h in fallback], ["m1", "m2"])

    def test_contact_filters_combine_with_label_and_date(self) -> None:
        hits = cli._keyword_hits(
            self.con,
            query="launch",
            limit=10,
            label_ids={"L1"},
            from_filter="didier@example.com",
            to_filter="pvs@example.com",
            after_ms=_ms(2025, 1, 1),
            before_ms=_ms(2025, 2, 1),
        )

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["gmail_id"], "m1")


if __name__ == "__main__":
    unittest.main()
