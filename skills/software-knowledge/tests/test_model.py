import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from model import make_corpus, node, validate, v1_to_v2, include_backlog
from providers import markdown_corpus


class ContractTests(unittest.TestCase):
    def test_contract_rejects_identity_and_unknown_edge(self):
        n = node("a", "term", "A", "A")
        with self.assertRaises(ValueError):
            make_corpus("p", [n, n], [])
        with self.assertRaises(ValueError):
            make_corpus("p", [n], [{"from": "a", "to": "b", "predicate": "related"}])

    def test_contains_descends_and_semantic_cycles_allowed(self):
        nodes = [node("a", "track", "A", "A", level="L2"), node("b", "term", "B", "B")]
        make_corpus("p", nodes, [{"from": "a", "to": "b", "predicate": "contains"},
                                {"from": "b", "to": "a", "predicate": "related"}])
        with self.assertRaises(ValueError):
            make_corpus("p", nodes, [{"from": "b", "to": "a", "predicate": "contains"}])

    def test_evidence_requires_source_not_approval(self):
        with self.assertRaises(ValueError):
            make_corpus("p", [node("x", "invariant", "X", "X", claim_state="verified")], [])

    def test_v1_and_backlog_envelopes_preserve_source(self):
        v1 = {"schemaVersion": 1, "kind": "knowledge-corpus",
              "terms": [{"id": "run.id", "context": "run", "label": "Run", "definition": "A run"}],
              "documents": [{"id": "doc-1", "title": "Guarantee", "type": "other",
                             "content": "Body", "tags": ["term:run.id", "ctx:run", "kind:invariant"]}]}
        c = v1_to_v2(v1, "demo")
        self.assertEqual(c["nodes"][1]["body"], "Body")
        orig = copy.deepcopy(c)
        c2 = include_backlog(c, {"schemaVersion": 1, "kind": "decision-list",
                                 "decisions": [{"id": "decision-1", "title": "Choose", "status": "accepted"}]})
        self.assertEqual(c, orig)
        self.assertEqual(c2["nodes"][-1]["claim_state"], "observed")
        self.assertEqual(c2["coverage"], "partial")
        validate(c2)

    def test_markdown_subset(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "note.md"
            p.write_text('---\ntype: "invariant"\ntitle: "Title"\nx_knowledge: '
                         '{"id":"a","level":"L1","summary":"Summary"}\n---\nBody\n')
            c = markdown_corpus(Path(d), "demo")
            self.assertEqual(c["nodes"][0]["body"], "Body")
            p.write_text("---\ntype: arbitrary yaml\n---\n")
            with self.assertRaises(ValueError):
                markdown_corpus(Path(d), "demo")

    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "root"
            root.mkdir()
            outside = Path(d) / "note.md"
            outside.write_text("private")
            (root / "note.md").symlink_to(outside)
            with self.assertRaises(ValueError):
                markdown_corpus(root, "demo")
