import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from architecture import review, capsule_reference, groma_references
from model import make_corpus, node


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.corpus = make_corpus("demo", [
            node("inv", "invariant", "Terminal states", "Irreversible", sources=[{"provider":"cognicode","locator":"capsule-a"}]),
            node("rule", "contract", "Recovery", "Safe restart"),
            node("map", "track", "Execution", "Model", level="L2"),
            node("other", "term", "Unrelated", "Other")], [
                {"from":"rule","predicate":"constrains","to":"inv"},
                {"from":"map","predicate":"contains","to":"inv"}])
        self.request = {"schemaVersion":1,"kind":"architecture-review-input","project":"demo",
                        "revision":"new","changedPaths":["src/run.kt"],
                        "observations":[{"provider":"cognicode","locator":"capsule-a","project":"demo",
                                         "plane":"static","coverage":"partial","revision":"old",
                                         "paths":["src/run.kt"]}]}

    def test_review_exact_and_transitive_only_candidates(self):
        before = json.dumps(self.corpus)
        r = review(self.corpus, self.request)
        self.assertEqual(r["results"][0]["id"], "inv")
        self.assertEqual({n["id"] for n in r["results"]}, {"inv","rule","map"})
        self.assertEqual(r["results"][0]["reasons"][0]["freshness"], "different-declared-revision")
        self.assertFalse(r["edit_authorized"])
        self.assertEqual(json.dumps(self.corpus), before)

    def test_no_match_and_cross_project_fail(self):
        self.request["revision"] = "old"
        self.request["changedPaths"] = ["src/another.kt"]
        self.assertEqual(review(self.corpus, self.request)["status"], "unknown")
        self.request["observations"][0]["project"] = "wrong"
        with self.assertRaises(ValueError):
            review(self.corpus,self.request)

    def test_findings_need_bound_reference_and_budget(self):
        self.request["findings"] = [{"node":"rule","provider":"cognicode","locator":"capsule-a",
                                     "kind":"possible-contradiction","reason":"Check the exit contract"}]
        with self.assertRaises(ValueError):
            review(self.corpus,self.request)
        self.request["bindings"] = [{"node":"rule","provider":"cognicode","locator":"capsule-a"}]
        r = review(self.corpus,self.request,limit=1,budget=1024)
        self.assertEqual(r["status"], "partial")
        self.assertLessEqual(len(json.dumps(r,ensure_ascii=False,separators=(",",":")).encode()),1024)

    def test_adapters_do_not_copy_graph_or_infer_ownership(self):
        capsule = {"generator":"cognicode-diagrams-capsule-v1","schema_version":1,"kind":"agent-handoff",
                   "status":"PARTIAL_HANDOFF","target":{"symbol_id":"App::run"},
                   "evidence":{"authority":"cognicode","plane":"static","basis":{"revision":"abc"},
                               "derivation_sha256":"a"*64,"revision_freshness":"UNVERIFIED_WITH_RUNTIME",
                               "claim_ids":["C1"],"query_ids":["Q1"]},
                   "observed_relations":[{"secret":"not copied"}]}
        ref = capsule_reference(capsule,"capsule-a","demo")
        self.assertEqual(ref["revision"],"abc")
        self.assertNotIn("observed_relations",ref)
        g = groma_references({"schemaVersion":1,"kind":"groma-task-link-input","task":{"id":"TASK-1"},
                              "confirmedElementIds":["runtime"],"changedFiles":["src/run.kt"]},"demo","work")
        self.assertEqual(g[0]["paths"],[])
        self.assertEqual(g[0]["plane"],"curated")


    def test_pinned_source_change_is_review_even_at_same_revision(self):
        self.corpus["nodes"][0]["sources"][0]["digest"]="a"*64
        self.request["revision"]="old"
        self.request["changedPaths"]=[]
        self.request["observations"][0]["digest"]="b"*64
        r=review(self.corpus,self.request)
        reason=r["results"][0]["reasons"][0]
        self.assertTrue(reason["source_pin_mismatch"])
        self.assertEqual(reason["digest"],"b"*64)
        self.assertEqual(reason["plane"],"static")
