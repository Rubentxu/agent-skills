import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from cache_index import cache_path, indexed
from model import make_corpus, node
from retrieval import Navigator
from knowledge import parser, run
from sections import section_response


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / ".git").mkdir()
        self.source = self.repo / "snapshot.json"
        env = patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.root / "cache")})
        env.start()
        self.addCleanup(env.stop)
        self.corpus = make_corpus("demo", [
            node("a", "invariant", "Terminal", "Irreversible", body="# Safety\n\nÁrbol token_alpha.\n", contexts=["run"], aliases=["estado final"]),
            node("b", "contract", "Recovery", "Restart", body="token_beta"),
            node("c", "track", "Runtime", "Overview", level="L2")], [
            {"from": "c", "predicate": "contains", "to": "a"},
            {"from": "b", "predicate": "constrains", "to": "a"}])
        self.write()

    def write(self):
        self.source.write_text(json.dumps(self.corpus), encoding="utf-8")

    def test_external_cache_incremental_and_source_hash(self):
        with indexed(self.source, "snapshot", "demo") as (nav, stats):
            self.assertEqual(stats["nodes_reindexed"], 3)
            self.assertEqual(stats["edges_reindexed"], 2)
            self.assertFalse(Path(stats["cache_path"]).is_relative_to(self.repo))
            self.assertEqual(nav.search("token_alpha")[0], "a")
        with indexed(self.source, "snapshot", "demo") as (nav, stats):
            self.assertTrue(stats["reused"])
            self.assertEqual(stats["nodes_reindexed"], 0)
        before = self.source.stat()
        self.corpus["nodes"][0]["body"] = self.corpus["nodes"][0]["body"].replace("token_alpha", "token_gamma")
        self.write()
        os.utime(self.source, ns=(before.st_atime_ns, before.st_mtime_ns))
        with indexed(self.source, "snapshot", "demo") as (nav, stats):
            self.assertEqual(stats["nodes_reindexed"], 1)
            self.assertEqual(stats["edges_reindexed"], 0)
            self.assertEqual(nav.search("token_alpha"), [])
            self.assertEqual(nav.search("token_gamma"), ["a"])
        self.corpus["nodes"].pop(1)
        self.corpus["edges"].pop(1)
        self.write()
        with indexed(self.source, "snapshot", "demo") as (nav, stats):
            self.assertEqual(stats["nodes_removed"], 1)
            self.assertEqual(stats["edges_removed"], 1)
            self.assertNotIn("b", nav.nodes)
            self.assertEqual(nav.search("token_beta"), [])

    def test_navigation_and_sections_equivalence(self):
        expected = Navigator(self.corpus)
        with indexed(self.source, "snapshot", "demo") as (nav, stats):
            self.assertEqual(nav.search("ESTADO FINAL", context="run"), ["a"])
            self.assertEqual(nav.search("estado final", kind="contract"), [])
            self.assertEqual(nav.walk(["a"], 2), expected.walk(["a"], 2))
            self.assertEqual(nav.fingerprint("a"), expected.fingerprint("a"))
            self.assertEqual(nav.ids_for_level("L2"), ["c"])
            self.assertEqual(section_response(nav, "a"), section_response(expected, "a"))
            self.assertEqual(nav.search('" OR * --'), [])
        args = parser().parse_args(["--cache", "--corpus", str(self.source), "--project", "demo", "context", "--anchor", "a"])
        self.assertEqual(run(args)["results"][0]["id"], "a")

    def test_separation_and_failed_refresh(self):
        self.assertNotEqual(cache_path("demo", self.source, "snapshot"),
                            cache_path("other", self.source, "snapshot"))
        with indexed(self.source, "snapshot", "demo") as (_, stats):
            old = stats["source_digest"]
        self.source.write_text("broken")
        with self.assertRaises(ValueError):
            with indexed(self.source, "snapshot", "demo"):
                pass
        self.write()
        with indexed(self.source, "snapshot", "demo") as (_, stats):
            self.assertTrue(stats["reused"])
            self.assertEqual(stats["source_digest"], old)
        with self.assertRaisesRegex(ValueError, "Project mismatch"):
            with indexed(self.source, "snapshot", "other"):
                pass

    def test_repo_and_markdown_cache_rejected(self):
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.repo / "cache")}):
            with self.assertRaisesRegex(ValueError, "outside"):
                cache_path("demo", self.source, "snapshot")
        md = self.root / "standalone"
        md.mkdir()
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(md / "cache")}):
            with self.assertRaisesRegex(ValueError, "outside"):
                cache_path("demo", md, "markdown")

    def test_markdown_source_and_symlink_guard(self):
        md = self.root / "notes"
        md.mkdir()
        (md / "a.md").write_text('---\ntype: "invariant"\ntitle: "Test"\nx_knowledge: {"id":"a","level":"L1","summary":"Summary"}\n---\nUnique anchor\n')
        with indexed(md, "markdown", "demo") as (nav, stats):
            self.assertEqual(nav.search("unique anchor"), ["a"])
        with indexed(md, "markdown", "demo") as (_, stats):
            self.assertTrue(stats["reused"])
        path = cache_path("demo", self.source, "snapshot")
        target = self.root / "other"
        target.write_text("untouched")
        path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "symlink"):
            with indexed(self.source, "snapshot", "demo"):
                pass
        self.assertEqual(target.read_text(), "untouched")


    def test_source_reader_bounds_allocation_and_rejects_oversize(self):
        import tracemalloc
        from cache_index import source_input
        tracemalloc.start()
        try:
            fingerprint, load = source_input(self.source, "snapshot", "demo")
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(len(fingerprint), 64)
        self.assertEqual(load(), self.corpus)
        # This tiny fixture needs nowhere near the 16 MiB parser ceiling.
        self.assertLess(peak, 1024 * 1024)
        with patch("cache_index.MAX_BYTES", 16):
            with self.assertRaisesRegex(ValueError, "Oversized"):
                source_input(self.source, "snapshot", "demo")
