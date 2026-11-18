import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from model import make_corpus, node, digest
from retrieval import Navigator, fusion
from knowledge import parser, run


def demo():
    nodes = [node("dna", "profile", "Project", "A project", level="L3"),
             node("track", "track", "Execution lifecycle", "Runtime", level="L2"),
             node("inv", "invariant", "Terminal state", "Terminal is irreversible", aliases=["Estado terminal"]),
             node("conflict", "finding", "Counterexample", "Observed conflicting behavior"),
             node("test", "test", "Property test", "Transition check", level="L0",
                  sources=[{"provider": "git", "locator": "tests/state.py"}])]
    edges = [{"from": "dna", "predicate": "contains", "to": "track"},
             {"from": "track", "predicate": "contains", "to": "inv"},
             {"from": "inv", "predicate": "verified_by", "to": "test"},
             {"from": "conflict", "predicate": "contradicts", "to": "inv"},
             {"from": "inv", "predicate": "related", "to": "track"}]
    return make_corpus("demo", nodes, edges)


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.nav = Navigator(demo())

    def test_exact_and_accent_alias(self):
        self.assertEqual(self.nav.search("inv")[0], "inv")
        self.assertEqual(self.nav.search("ESTÁDO TERMINAL")[0], "inv")

    def test_no_lexical_result_not_random(self):
        self.assertEqual(self.nav.search("xyzunknown"), [])

    def test_bidirectional_and_cycle_safe(self):
        reached, cut = self.nav.walk(["inv"], 2)
        self.assertEqual(set(reached), {"dna", "track", "inv", "test", "conflict"})
        self.assertFalse(cut)

    def test_conflict_promoted_and_anchor_preserved(self):
        ids, paths, cut = self.nav.plan("", ["inv"], "refactor", 2)
        self.assertEqual(ids[:2], ["inv", "conflict"])
        self.assertFalse(cut)
        self.assertEqual(paths["conflict"][1][0]["predicate"], "contradicts")

    def test_no_unbounded_walk(self):
        reached, cut = self.nav.walk(["inv"], 2, max_nodes=2)
        self.assertEqual(len(reached), 2)
        self.assertTrue(cut)

    def test_output_bytes_and_fingerprint(self):
        r = self.nav.render(["inv", "conflict", "test"], budget=1300,
                            known={digest(self.nav.nodes["inv"])})
        self.assertEqual(r["unchanged"], 1)
        self.assertLessEqual(len(json.dumps(r, ensure_ascii=False, separators=(",", ":")).encode()), 1300)
        self.assertEqual(r["status"], "partial")
        self.assertNotIn("inv", [x["id"] for x in r["results"]])

    def test_no_silent_truncation(self):
        r = self.nav.render(["inv"], budget=512)
        self.assertEqual(len(r["results"]) + r["omitted"], 1)

    def test_rrf_deduplicates(self):
        self.assertEqual(fusion([["b", "b", "a"], ["a"]])[0], "a")

    def test_cli_example(self):
        fixture = Path(__file__).resolve().parents[1] / "examples" / "corpus.json"
        args = parser().parse_args(["--corpus", str(fixture), "context", "--anchor", "execution.terminal"])
        r = run(args)
        self.assertEqual(r["results"][0]["id"], "execution.terminal")
