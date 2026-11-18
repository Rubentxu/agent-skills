import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from benchmark_index import benchmark


class BenchmarkTests(unittest.TestCase):
    def test_small_fixture_reports_real_work_counts(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {"XDG_CACHE_HOME": d}):
            r = benchmark(20, 1)
            self.assertEqual(r["variants"]["cold"]["nodes_reindexed"], 21)
            self.assertEqual(r["variants"]["warm"]["nodes_reindexed"], 0)
            self.assertEqual(r["variants"]["one_change"]["nodes_reindexed"], 1)
            self.assertEqual(list(Path(d).rglob("*.sqlite3")), [])
