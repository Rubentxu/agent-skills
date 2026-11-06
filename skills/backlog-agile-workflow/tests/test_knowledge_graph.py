import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("knowledge_graph", ROOT / "scripts/knowledge_graph.py")
kg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kg)


def fixture():
    return {"schemaVersion": 1, "kind": "knowledge-corpus",
            "terms": [{"id": "execution.run", "context": "execution", "label": "Run",
                       "definition": "An identifiable execution", "status": "validated"}],
            "documents": [{"id": "doc-12", "type": "specification", "title": "Run recovery",
                           "content": "# Run recovery\n\nAn invariant.",
                           "tags": ["ctx:execution", "term:execution.run"],
                           "relations": [{"predicate": "constrains", "target": "execution.run", "terms": ["execution.run"]}]}]}


class KnowledgeProjectionTests(unittest.TestCase):
    def test_valid_snapshot_and_derived_graph(self):
        data = fixture()
        self.assertEqual(kg.validate(data), [])
        result = kg.graph(data)
        self.assertEqual(len(result["nodes"]), 2)
        self.assertEqual({e["predicate"] for e in result["edges"]}, {"about", "constrains"})
        self.assertEqual(kg.graph(data), result)

    def test_unknown_terms_are_not_created_by_similarity(self):
        data = fixture()
        data["documents"][0]["tags"].append("term:execution.worker")
        self.assertIn("UNKNOWN_TERM", [p["code"] for p in kg.validate(data)])

    def test_cannot_mislabel_contexts(self):
        data = fixture()
        data["documents"][0]["tags"].remove("ctx:execution")
        self.assertIn("CONTEXT_TAG", [p["code"] for p in kg.validate(data)])

    def test_relationship_requires_known_target_and_domain_terms(self):
        data = fixture()
        data["documents"][0]["relations"] = [{"predicate": "motivates", "target": "missing", "terms": []}]
        self.assertEqual({p["code"] for p in kg.validate(data)}, {"UNRESOLVED", "RELATION_TERMS"})

    def test_rejects_duplicate_terms_and_unsafe_identifiers(self):
        data = fixture()
        data["terms"].append(copy.deepcopy(data["terms"][0]))
        data["documents"][0]["id"] = "../../escape"
        self.assertTrue({"DUPLICATE_TERM", "DOCUMENT_ID"} <= {p["code"] for p in kg.validate(data)})

    def test_malformed_types_produce_diagnostics_instead_of_crashes(self):
        data = fixture()
        data["terms"][0]["status"] = {"unexpected": True}
        data["documents"][0]["status"] = ["draft"]
        data["documents"][0]["sources"] = [{"title": "no resource"}]
        data["documents"][0]["relations"][0]["predicate"] = []
        self.assertTrue({"TERM_STATUS", "DOCUMENT_STATUS", "SOURCES", "PREDICATE"} <=
                        {p["code"] for p in kg.validate(data)})

    def test_export_revalidates_even_when_called_as_library(self):
        data = fixture()
        data["documents"][0]["id"] = "../../outside"
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "bundle"
            with self.assertRaisesRegex(ValueError, "Invalid knowledge corpus"):
                kg.export_okf(data, target)
            self.assertFalse(target.exists())

    def test_export_is_okf_markdown_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "bundle"
            files = kg.export_okf(fixture(), target)
            self.assertEqual(len(files), 3)
            content = (target / "concepts/doc-12.md").read_text()
            self.assertTrue(content.startswith('---\ntype: "specification"'))
            self.assertIn("x_domain:", content)
            self.assertIn("/glossary/execution.run.md", content)
            self.assertTrue((target / "index.md").is_file())
            with self.assertRaises(ValueError):
                kg.export_okf(fixture(), target)
            self.assertEqual(content, (target / "concepts/doc-12.md").read_text())


if __name__ == "__main__":
    unittest.main()
