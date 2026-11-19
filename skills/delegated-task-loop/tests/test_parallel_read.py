import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from parallel_read import plan

def candidate(i, **changes):
    return {"id": "q" + str(i), "taskId": "T1", "ready": True, "readOnly": True,
            "unresolvedDependencies": [], "question": "Question " + str(i),
            "snapshotRef": "private:snapshot", "snapshotDigest": "a" * 64,
            "contextBytes": 100} | changes

def call(candidates, **changes):
    return plan({"schemaVersion": 1, "kind": "read-only-fanout-input", "runId": "r1",
                 "capabilities": {"fresh": True, "background": True, "notify": True, "explorationReadOnly": True},
                 "maxAgents": 2, "activeRequests": [], "remainingContextBytes": 1000,
                 "candidates": candidates} | changes)

class FanoutTests(unittest.TestCase):
    def test_bounded_native_readers(self):
        r = call([candidate(i) for i in range(4)])
        self.assertEqual([x["id"] for x in r["selected"]], ["q0", "q1"])
        self.assertEqual(r["projectedContextBytes"], 200)
        self.assertEqual(r["writerConcurrency"], 1)
        self.assertFalse(r["authorized"])

    def test_no_parallel_writes_or_dependencies(self):
        r = call([candidate(1, readOnly=False), candidate(2, unresolvedDependencies=["T9"]),
                  candidate(3, snapshotRef=None), candidate(4)])
        self.assertEqual([x["id"] for x in r["selected"]], ["q4"])
        self.assertEqual([x["reason"] for x in r["deferred"]],
                         ["serial-writer-only", "not-ready", "immutable-source-unconfirmed"])

    def test_no_capability_no_reader(self):
        for missing in ("fresh", "background", "notify", "explorationReadOnly"):
            caps = dict.fromkeys(("fresh", "background", "notify", "explorationReadOnly"), True)
            caps[missing] = False
            self.assertEqual(call([candidate(1)], capabilities=caps)["selected"], [])

    def test_active_and_context_budget(self):
        r = call([candidate(1), candidate(2), candidate(3)], activeRequests=["q1"],
                 remainingContextBytes=100)
        self.assertEqual([x["id"] for x in r["selected"]], ["q2"])
        self.assertEqual(r["remainingContextBytes"], 0)
        self.assertEqual(r["deferred"][0]["reason"], "already-active")

    def test_redundant_question(self):
        r = call([candidate(1), candidate(2, question="Question 1")])
        self.assertEqual(len(r["selected"]), 1)
        self.assertEqual(r["deferred"][0]["reason"], "duplicate-question")

    def test_no_fake_snapshot(self):
        with self.assertRaises(ValueError):
            call([candidate(1, snapshotDigest="short")])
        with self.assertRaises(ValueError):
            call([candidate(1), candidate(1)])

if __name__ == "__main__":
    unittest.main()
