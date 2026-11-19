import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from pilot import manifest
from evaluate_runs import compare,template
class PilotTests(unittest.TestCase):
    def test_planned_runs_not_observed(self):
        p=manifest();r=compare(p,template(p))
        self.assertEqual(r["status"],"not-evaluated")
        self.assertEqual(r["plannedCases"],3)
        self.assertEqual(r["plannedRuns"],48)
        self.assertEqual(r["unrecordedRuns"],48)
        self.assertEqual(r["observedRuns"],0)
        self.assertIn("delegated-task-loop-before",r["aggregate"])
    def test_rotated_variant_order(self):
        p=manifest()
        orders=[x["order"] for x in p["pairs"] if x["case"]==p["cases"][0]["id"]]
        self.assertEqual({x[0] for x in orders},set(p["variants"]))
    def test_missing_pair_is_reported(self):
        p=manifest();r=compare(p,template(p))
        self.assertEqual(len(r["excluded"]),36)
