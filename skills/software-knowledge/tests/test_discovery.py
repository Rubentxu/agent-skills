import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from discovery import checkpoint, constitution
from model import make_corpus, node
from retrieval import Navigator


class DiscoveryTests(unittest.TestCase):
    def test_checkpoint_is_advisory_and_deduplicates_batch(self):
        c = make_corpus("p", [], [])
        a = node("a", "pattern", "Retry", "Bounded retry", contexts=["run"],
                 sources=[{"provider":"git","locator":"src/run.kt"}])
        b = dict(a, id="b")
        request = {"schemaVersion":1,"kind":"knowledge-checkpoint","project":"p","candidates":[a,b]}
        r = checkpoint(c, request)
        self.assertEqual([x["action"] for x in r["results"]], ["PROPOSE_STORE","REVIEW_DUPLICATE"])
        self.assertEqual(c["nodes"],[])
        self.assertFalse(r["write_authorized"])
        request["candidates"] = [dict(a,claim_state="verified")]
        with self.assertRaises(ValueError):
            checkpoint(c,request)

    def test_negative_knowledge_requires_scope_and_outcome(self):
        a = node("a","failed-experiment","Retry","Failed",contexts=["run"],
                 sources=[{"provider":"external","locator":"test-1"}])
        req = {"schemaVersion":1,"kind":"knowledge-checkpoint","project":"p","candidates":[a]}
        with self.assertRaises(ValueError):
            checkpoint(make_corpus("p",[],[]),req)
        a["learning"] = {"attempted":"retry forever","outcome":"hung","applicability":"local timeout"}
        self.assertEqual(checkpoint(make_corpus("p",[],[]),req)["results"][0]["action"],"PROPOSE_STORE")

    def test_constitution_does_not_hide_conflicts_or_promote_claims(self):
        c = make_corpus("p",[node("rule","contract","Rule","Rule",contexts=["run"]),
                             node("finding","finding","Observed issue","Issue",claim_state="observed"),
                             node("other","contract","Other","Other",contexts=["else"])],
                        [{"from":"finding","predicate":"contradicts","to":"rule"}])
        r = constitution(Navigator(c),[],context="run")
        self.assertEqual({n["id"] for n in r["results"]},{"rule","finding"})
        self.assertEqual(next(n for n in r["results"] if n["id"]=="rule")["claim_state"],"unknown")
        with self.assertRaises(ValueError):
            constitution(Navigator(c),[])
