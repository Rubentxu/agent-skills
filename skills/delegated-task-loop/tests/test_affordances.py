import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from affordances import route

def state(**kw):
    s = json.loads((ROOT / "examples/ready.json").read_text())
    return s | kw

def rels(result):
    return {v["rel"] for v in result["_links"]}

class RouterTests(unittest.TestCase):
    def test_ready_composition(self):
        r = route(state())
        self.assertEqual(rels(r), {"prepare-handoff", "prepare-context", "delegate-after-preflight"})
        self.assertFalse(r["authorized"])
        self.assertLessEqual(len(r["lenses"]), 2)

    def test_fail_closed_no_fresh(self):
        r = route(state(capabilities={}))
        self.assertEqual(r["decision"], "NOT_RUN")
        self.assertNotIn("delegate-after-preflight", rels(r))

    def test_no_board_no_selection(self):
        r = route(state(availableSkills=[]))
        self.assertEqual(r["decision"], "DEGRADED")
        self.assertEqual(rels(r), set())

    def test_active_or_unknown_writer(self):
        for ownership in ("active", "unknown", "terminated"):
            self.assertEqual(rels(route(state(ownership=ownership))), {"reconcile-ownership"})

    def test_budget(self):
        self.assertEqual(route(state(budgetRemaining=0))["decision"], "STOP")

    def test_sync_degradation(self):
        r = route(state(phase="running", ownership="active", capabilities={"fresh": True}))
        self.assertEqual(rels(r), {"await-native-result"})
        self.assertTrue(r["limitations"])

    def test_intervention_only_if_capable(self):
        s = state(phase="running", ownership="active", signal="repeated-failure")
        self.assertNotIn("steer", rels(route(s)))
        self.assertIn("recover-flow", rels(route(s)))
        self.assertIn("steer", rels(route(s | {"capabilities": {"steer": True}})))

    def test_recovery_never_duplicate(self):
        s = state(phase="interrupted", ownership="unknown", capabilities={"fresh": True, "resume": True})
        self.assertEqual(rels(route(s)), {"reconcile-ownership"})
        r = route(s | {"ownership": "terminated"})
        self.assertIn("resume-after-revalidation", rels(r))
        self.assertNotIn("replace-after-revalidation", rels(r))

    def test_accept_requires_evidence_review_ownership(self):
        s = state(phase="accept", ownership="terminated", evidence="sufficient", review="none")
        self.assertIn("accept-after-authority-check", rels(route(s)))
        for change in ({"evidence": "unknown"}, {"review": "required"}, {"review": "not-run"}, {"ownership": "active"}, {"availableSkills": []}):
            self.assertNotIn("accept-after-authority-check", rels(route(s | change)))

    def test_missing_goldfish_is_not_pass(self):
        r = route(state(phase="review", review="required", ownership="terminated", availableSkills=["backlog-agile-workflow"]))
        self.assertEqual(r["decision"], "REVIEW_PENDING")
        self.assertNotIn("request-independent-review", rels(r))

    def test_strict_inputs(self):
        for change in ({"capabilities": {"fresh": "yes"}}, {"phase": []}, {"budgetRemaining": True}, {"taskId": None, "phase": "running"}, {"schemaVersion": True}, {"extra": 1}):
            with self.assertRaises(ValueError):
                route(state(**change))

    def test_cli(self):
        p = subprocess.run([sys.executable, str(ROOT / "scripts/affordances.py"), "-"], input=json.dumps(state()), text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["kind"], "delegated-loop-affordances")
        p = subprocess.run([sys.executable, str(ROOT / "scripts/affordances.py"), "-"], input="{}", text=True, capture_output=True)
        self.assertEqual(p.returncode, 2)

if __name__ == "__main__":
    unittest.main()
