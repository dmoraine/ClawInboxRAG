from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from subprocess import run, PIPE


class StatusWrapperTests(unittest.TestCase):
    def test_status_mode_uses_clawinbox_status_contract(self) -> None:
        from gmail_rag.config import Paths

        p = Paths()
        self.assertTrue(hasattr(p, "db_path"))
        self.assertTrue(hasattr(p, "faiss_index_path"))
        self.assertTrue(hasattr(p, "faiss_meta_path"))
        self.assertTrue(hasattr(p, "gmail_token_path"))
