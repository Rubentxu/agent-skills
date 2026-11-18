import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from capture_backlog import capture, doc_list, document_body, declared_links, project_root
from retrieval import Navigator


def env(kind, **kw):
    return json.dumps({"schemaVersion": 1, "kind": kind, **kw})


def document(i, title, tags):
    return {"type": "document", "data": {"id": i, "title": title, "type": "other",
                                         "path": f"backlog/docs/{i}.md", "tags": tags}}


class Fake:
    def __init__(self):
        self.calls = []
        self.remote = "false"
        self.records = [
            document("doc-1", "Run", ["kind:term", "ctx:execution", "term:execution.run"]),
            document("doc-2", "Guarantee", ["kind:invariant", "ctx:execution", "term:execution.run"]),
            document("doc-3", "Execution track", ["kind:track", "ctx:execution"]),
        ]
        self.responses = {
            ("doc", "view", "doc-1", "--plain"): "---\nid: doc-1\n---\n\nAn identifiable execution.",
            ("doc", "view", "doc-2", "--plain"): "---\nid: 'doc-2'\n---\n\nTerminal states are irreversible.",
            ("doc", "view", "doc-3", "--plain"): "---\nid: doc-3\n---\n\nOverview.\n\n"
                '<!-- knowledge-links:v1 -->\n[{"predicate":"contains","to":"doc:doc-2"}]\n'
                '<!-- /knowledge-links:v1 -->',
        }
        self.inventory_reads = 0
        self.change_inventory = False

    def __call__(self, *args):
        self.calls.append(args)
        if args in self.responses:
            return self.responses[args]
        if args == ("config", "get", "remoteOperations"):
            return self.remote
        if args == ("config", "get", "filesystemOnly"):
            return "false"
        if args == ("--version",):
            return "1.56.0"
        if args == ("doc", "list", "--plain"):
            return "\n".join(f"{r['data']['id']} - {r['data']['title']}" for r in self.records)
        if args == ("search", "--type", "document", "--json"):
            self.inventory_reads += 1
            rows = self.records
            if self.change_inventory and self.inventory_reads > 1:
                rows = rows[:-1]
            return env("search", results=rows)
        if args == ("search", "irreversible", "--type", "document", "--json"):
            return env("search", results=[self.records[1]])
        if args == ("decision", "list", "--json"):
            return env("decision-list", decisions=[{"id":"decision-1","title":"Design","status":"accepted"}])
        if args == ("decision", "view", "decision-1", "--json"):
            return env("decision-view", decision={"id":"decision-1","title":"Design","status":"accepted",
                                                   "content":"## Decision\nChoice"})
        if args == ("task", "view", "TASK-1", "--json"):
            return env("task-view", task={"id":"TASK-1","title":"Work","status":"To Do",
                                           "documentation":["backlog/docs/doc-2.md"]})
        raise AssertionError(args)


class CaptureTests(unittest.TestCase):
    def test_full_body_and_pyramid_links(self):
        c = capture(Fake(), project="demo", all_docs=True, tasks=("TASK-1",), decisions=("decision-1",))
        nodes = {n["id"]: n for n in c["nodes"]}
        self.assertEqual(nodes["doc:doc-3"]["level"], "L2")
        self.assertEqual(nodes["doc:doc-2"]["claim_state"], "unknown")
        self.assertIn("irreversible", nodes["doc:doc-2"]["body"])
        self.assertEqual(nodes["doc:doc-2"]["content_state"], "captured")
        self.assertEqual(nodes["decision:decision-1"]["body"], "## Decision\nChoice")
        self.assertEqual(len(nodes["doc:doc-2"]["sources"][0]["digest"]), 64)
        edges = {(e["from"], e["predicate"], e["to"]) for e in c["edges"]}
        self.assertIn(("task:TASK-1", "about", "doc:doc-2"), edges)
        self.assertIn(("doc:doc-2", "about", "doc:doc-1"), edges)
        self.assertIn(("doc:doc-3", "contains", "doc:doc-2"), edges)
        self.assertEqual(Navigator(c).search("irreversible")[0], "doc:doc-2")
        self.assertFalse(c["capture"]["atomic"])

    def test_focused_capture_and_budget(self):
        cli = Fake()
        c = capture(cli, project="demo", tasks=("TASK-1",), all_docs=True, max_docs=1)
        self.assertEqual(c["capture"]["captured_documents"], ["doc-2"])
        self.assertEqual(c["capture"]["omitted_documents"], ["doc-1", "doc-3"])
        self.assertNotIn(("doc", "view", "doc-1", "--plain"), cli.calls)
        c = capture(Fake(), project="demo", query="irreversible")
        self.assertEqual(c["capture"]["captured_documents"], ["doc-2"])

    def test_fail_closed_on_remote_or_race(self):
        cli = Fake()
        cli.remote = "true"
        with self.assertRaisesRegex(ValueError, "Local capture"):
            capture(cli, project="demo", all_docs=True)
        self.assertEqual(len(cli.calls), 2)
        cli = Fake()
        cli.change_inventory = True
        with self.assertRaisesRegex(ValueError, "changed during capture"):
            capture(cli, project="demo", all_docs=True)

    def test_native_format_and_safe_relationship_block(self):
        self.assertEqual(doc_list("No docs found.\n"), {})
        with self.assertRaises(ValueError):
            doc_list("doc-1 - One\ndoc-1 - Another")
        with self.assertRaises(ValueError):
            document_body("---\nid: doc-2\n---\n", "doc-1")
        self.assertEqual(declared_links("\x60\x60\x60md\n<!-- knowledge-links:v1 -->\nbogus\n"
                                        "<!-- /knowledge-links:v1 -->\n\x60\x60\x60"), [])
        with self.assertRaises(ValueError):
            declared_links('<!-- knowledge-links:v1 -->\n[{"predicate":"depends_on","to":"task:TASK-1"}]\n'
                           '<!-- /knowledge-links:v1 -->')

    def test_unresolved_not_fabricated_and_explicit_id_budget(self):
        cli = Fake()
        cli.responses[("doc", "view", "doc-3", "--plain")] = (
            "---\nid: doc-3\n---\n<!-- knowledge-links:v1 -->\n"
            '[{"predicate":"contains","to":"doc:missing"}]\n<!-- /knowledge-links:v1 -->')
        c = capture(cli, project="demo", documents=("doc-3",))
        self.assertTrue(c["capture"]["unresolved_links"])
        self.assertNotIn("doc:missing", {n["id"] for n in c["nodes"]})
        with self.assertRaisesRegex(ValueError, "exceed"):
            capture(Fake(), project="demo", documents=("doc-1","doc-2"), max_docs=1)

    def test_root_guard(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaises(ValueError):
                project_root(root)
            (root / "backlog").mkdir()
            (root / "backlog" / "config.yml").write_text("project_name: Test")
            self.assertEqual(project_root(root), root.resolve())


    def test_navigation_distinguishes_metadata_only_from_captured_content(self):
        c = capture(Fake(), project="demo", documents=("doc-2",))
        nav = Navigator(c)
        r = nav.render(["doc:doc-1", "doc:doc-2"], detail="full")
        a, b = r["results"]
        self.assertEqual(a["content_state"], "metadata-only")
        self.assertNotIn("body", a)
        self.assertIn({"action": "capture-doc", "id": "doc-1"}, a["_links"])
        self.assertNotIn({"action": "get", "id": "doc:doc-1", "detail": "full"}, a["_links"])
        self.assertEqual(b["content_state"], "captured")
        self.assertIn("irreversible", b["body"])
        self.assertIn({"action": "get", "id": "doc:doc-2", "detail": "full"}, b["_links"])
