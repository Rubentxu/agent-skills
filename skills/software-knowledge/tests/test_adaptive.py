import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from adaptive import context_pack, size
from model import make_corpus,node
from retrieval import Navigator


class AdaptiveTests(unittest.TestCase):
    def setUp(self):
        self.nav = Navigator(make_corpus("p", [
            node("rule","invariant","Terminal","Irreversible",body="Full detail",
                 sources=[{"provider":"git","locator":"src/x"}]),
            node("dna","profile","Project","Overview",level="L3")],
            [{"from":"dna","predicate":"contains","to":"rule"}]))

    def test_aggregate_calls_and_bytes(self):
        req = {"schemaVersion":1,"kind":"context-pack-input","project":"p",
               "steps":[{"query":"Terminal","anchors":["rule"]}]*10}
        r = context_pack(self.nav,req,profile="quick")
        self.assertEqual(r["calls"],2)
        self.assertEqual(r["omitted_steps"],8)
        self.assertLessEqual(size(r),4000)
        self.assertGreater(r["steps"][1]["response"]["unchanged"],0)

    def test_evidence_is_not_suppressed_by_summary(self):
        req = {"schemaVersion":1,"kind":"context-pack-input","project":"p",
               "steps":[{"anchors":["rule"]},{"anchors":["rule"],"intent":"verify"}]}
        r = context_pack(self.nav,req)
        self.assertEqual(r["steps"][1]["detail"],"evidence")
        self.assertIn("sources",r["steps"][1]["response"]["results"][0])

    def test_orientation_and_section_selection(self):
        req = {"schemaVersion":1,"kind":"context-pack-input","project":"p",
               "steps":[{"intent":"understand"},{"mode":"sections","anchors":["rule"],"query":"detail"}]}
        r = context_pack(self.nav,req)
        self.assertEqual(r["steps"][0]["strategy"],"orientation")
        self.assertEqual(r["steps"][0]["response"]["results"][0]["id"],"dna")
        self.assertEqual(r["steps"][1]["strategy"],"sections")
        self.assertTrue(r["steps"][1]["response"]["results"])
