import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from model import make_corpus, node
from projection import compare, export_markdown


class ProjectionTests(unittest.TestCase):
    def fixture(self, summary="Before"):
        return make_corpus("demo", [
            node("dna", "profile", "DNA", "DNA", level="L3"),
            node("track", "track", "Track", "Track", level="L2"),
            node("atom", "invariant", "Atom", summary)], [
            {"from": "dna", "predicate": "contains", "to": "track"},
            {"from": "track", "predicate": "contains", "to": "atom"}])

    def test_incremental_candidates_propagate(self):
        result = compare(self.fixture(), self.fixture("After"))
        self.assertEqual(result["changed"], ["atom"])
        self.assertEqual(result["review_maps"], ["dna", "track"])
        self.assertEqual(compare(self.fixture(), self.fixture())["changed"], [])

    def test_missing_is_not_deleted(self):
        result = compare(self.fixture(), make_corpus("demo", [], []))
        self.assertEqual(result["missing_from_after"], ["atom", "dna", "track"])
        self.assertNotIn("deleted", result)

    def test_cross_project_rejected(self):
        with self.assertRaises(ValueError):
            compare(self.fixture(), make_corpus("other", [], []))

    def test_snapshot_is_navigable_and_preserves_complete_model(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out"
            fixture = self.fixture()
            export_markdown(fixture, out)
            self.assertEqual(json.loads((out / "corpus.json").read_text()), fixture)
            notes = list((out / "notes").glob("*.md"))
            self.assertEqual(len(notes), 3)
            self.assertTrue(any("backlink (contains)" in p.read_text() for p in notes))
            for p in notes:
                self.assertIn("../index.md", p.read_text())
            with self.assertRaises(ValueError):
                export_markdown(fixture, out)
