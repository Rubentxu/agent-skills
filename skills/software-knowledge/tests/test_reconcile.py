import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from model import make_corpus, node
from reconcile import reconcile, map_candidates


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.atom = node("a", "invariant", "Title", "Guarantee", contexts=["runtime"])
        self.c = make_corpus("p", [self.atom], [])

    def test_identity_and_claim_reconciliation(self):
        self.assertEqual(reconcile(self.c, self.c)["action"], "KEEP_AS_IS")
        changed = make_corpus("p", [{**self.atom, "summary": "Changed"}], [])
        self.assertEqual(reconcile(self.c, changed)["action"], "REVIEW_EXISTING")
        duplicate = make_corpus("p", [{**self.atom, "id": "b"}], [])
        self.assertEqual(reconcile(self.c, duplicate)["action"], "REVIEW_DUPLICATE")
        novel = make_corpus("p", [{**self.atom, "id": "b", "summary": "Other"}], [])
        self.assertEqual(reconcile(self.c, novel)["action"], "PROPOSE_STORE")
        self.assertEqual(self.c["nodes"], [self.atom])

    def test_scope_and_project_not_inferred(self):
        other = make_corpus("p", [{**self.atom, "id": "b", "contexts": ["other"]}], [])
        self.assertEqual(reconcile(self.c, other)["action"], "PROPOSE_STORE")
        with self.assertRaises(ValueError):
            reconcile(self.c, make_corpus("q", [self.atom], []))

    def test_structure_candidates(self):
        r = map_candidates(self.c)
        self.assertEqual(r["unlocated_atoms"], ["a"])
        self.assertEqual(r["contexts"], [{"context": "runtime", "atoms": ["a"]}])
        self.assertFalse(r["has_profile"])
        with_track = make_corpus("p", [self.atom, node("track", "track", "Runtime", "Runtime", level="L2")],
                                 [{"from": "track", "predicate": "contains", "to": "a"}])
        self.assertEqual(map_candidates(with_track)["unlocated_atoms"], [])
