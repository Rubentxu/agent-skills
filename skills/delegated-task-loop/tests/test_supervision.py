import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from supervision import project
from affordances import route

I = {"runId": "r1", "attemptId": "a1", "taskId": "T1", "handle": "native1"}

def event(seq, kind, **kw):
    return {"seq": seq, "kind": kind, "identity": I, "ref": "event:" + str(seq), **kw}

def call(events=(), previous=None, acknowledged=()):
    return project({"schemaVersion": 1, "kind": "supervision-input", "identity": I,
                    "previous": previous, "events": list(events), "acknowledged": list(acknowledged)})

class SupervisionTests(unittest.TestCase):
    def test_routine_does_not_wake(self):
        r = call([event(i, "routine") for i in range(1, 65)])
        self.assertFalse(r["wakeRecommended"])
        self.assertEqual(r["signal"], "normal")
        self.assertLess(len(json.dumps(r["projection"])), 700)

    def test_repeat_coalesces(self):
        r = call([event(1, "error", fingerprint="f"), event(2, "error", fingerprint="f"),
                  event(3, "error", fingerprint="f")])
        self.assertEqual(r["newAlerts"], ["repeated-failure"])
        self.assertEqual(r["projection"]["pending"]["repeated-failure"]["seq"], 2)
        r = call([event(4, "error", fingerprint="f")], r["projection"])
        self.assertFalse(r["wakeRecommended"])
        self.assertEqual(r["signal"], "repeated-failure")
        self.assertEqual(r["projection"]["pending"]["repeated-failure"]["lastSeq"], 4)
        with self.assertRaises(ValueError):
            call([], r["projection"], [{"signal": "repeated-failure", "seq": 2}])

    def test_ack_exposes_other_pending(self):
        s = call([event(1, "question"), event(2, "budget-exhausted")])["projection"]
        r = call([], s, [{"signal": "budget-exhausted", "seq": 2}])
        self.assertEqual(r["signal"], "question")
        self.assertTrue(r["wakeRecommended"])

    def test_fresh_hypothesis_resets(self):
        r = call([event(1, "error", fingerprint="f"), event(2, "new-hypothesis"),
                  event(3, "error", fingerprint="f")])
        self.assertEqual(r["signal"], "normal")

    def test_replay_and_gaps(self):
        e = event(1, "question")
        s = call([e])["projection"]
        self.assertEqual(call([e], s)["processed"], 0)
        with self.assertRaises(ValueError):
            call([event(1, "result")], s)
        with self.assertRaises(ValueError):
            call([event(3, "routine")], s)

    def test_foreign_attempt_rejected(self):
        e = event(1, "routine")
        e["identity"] = I | {"attemptId": "other"}
        with self.assertRaises(ValueError):
            call([e])

    def test_ack_is_versioned(self):
        s = call([event(1, "question")])["projection"]
        with self.assertRaises(ValueError):
            call([], s, [{"signal": "question", "seq": 2}])
        self.assertEqual(call([], s, [{"signal": "question", "seq": 1}])["signal"], "normal")
        r = call([event(2, "question")], s, [{"signal": "question", "seq": 1}])
        self.assertTrue(r["wakeRecommended"])

    def test_active_time_not_wall_clock(self):
        r = call([event(1, "active-without-progress", activeSeconds=1800, operation="healthy"),
                  event(2, "active-without-progress", activeSeconds=1800, operation="unknown")])
        self.assertFalse(r["wakeRecommended"])
        r = call([event(3, "active-without-progress", activeSeconds=1200, operation="none")], r["projection"])
        self.assertEqual(r["signal"], "stalled")

    def test_result_not_stop_authority(self):
        r = call([event(1, "terminal")])
        self.assertEqual(r["signal"], "result")
        self.assertFalse(r["runtimeVerified"])
        self.assertFalse(r["authorized"])

    def test_priority_and_router_budget(self):
        r = call([event(1, "question"), event(2, "budget-exhausted")])
        self.assertEqual(r["signal"], "budget-exhausted")
        s = json.loads((ROOT / "examples/ready.json").read_text()) | {
            "phase": "running", "ownership": "active", "signal": r["signal"], "capabilities": {"cancel": True}}
        nav = route(s)
        self.assertEqual(nav["decision"], "CHECKPOINT")
        self.assertIn("interrupt-if-authorized", {a["rel"] for a in nav["_links"]})
        self.assertNotIn("delegate-after-preflight", {a["rel"] for a in nav["_links"]})

    def test_cli_example(self):
        p = subprocess.run([sys.executable, str(ROOT / "scripts/supervision.py")],
                           input=(ROOT / "examples/supervision.json").read_text(), text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["signal"], "normal")

if __name__ == "__main__":
    unittest.main()
