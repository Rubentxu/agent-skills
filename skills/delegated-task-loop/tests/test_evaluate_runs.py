import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from evaluate_runs import compare, template

P = json.loads((ROOT / "examples/evaluation-plan.json").read_text())

def row(variant, **changes):
    return {"case": "synthetic-example", "pair": "p1", "variant": variant, "runId": "run-" + variant,
            "workloadDigest": "0" * 64, "environmentDigest": "1" * 64, "status": "completed",
            "metrics": {"acceptedTasks": 2, "totalTokens": 100, "elapsedMs": 50},
            "acceptance": "pass", "reviewerRef": "review:synthetic", "evidenceRefs": ["ref:synthetic"]} | changes

def evaluate(*trials):
    return compare(P, template(P) | {"trials": list(trials)})

class EvaluationTests(unittest.TestCase):
    def test_empty_and_not_run(self):
        r = evaluate()
        self.assertEqual(r["status"], "not-evaluated")
        self.assertIsNone(r["aggregate"]["single-agent"]["metrics"]["totalTokens"]["medianDelta"])
        r = evaluate(row("single-agent", status="not-run", metrics={}, acceptance="unknown", reviewerRef=None, evidenceRefs=[]))
        self.assertEqual(r["observedRuns"], 0)
        self.assertEqual(r["notRun"], 1)

    def test_two_baselines(self):
        r = evaluate(row("single-agent"), row("supervised-task-loop"),
                     row("delegated-task-loop", metrics={"acceptedTasks": 2, "totalTokens": 80, "elapsedMs": 60}))
        for k in ("single-agent", "supervised-task-loop"):
            a = r["aggregate"][k]
            self.assertEqual(a["observedPairs"], 1)
            self.assertEqual(a["metrics"]["totalTokens"]["medianDelta"], -20)
            self.assertEqual(a["metrics"]["tokensPerAcceptedTask"]["medianDelta"], -10)
            self.assertEqual(a["metrics"]["elapsedMs"]["medianDelta"], 10)
            self.assertIsNone(a["metrics"]["resourceLeaks"]["medianDelta"])

    def test_failure_cost_not_dropped(self):
        r = evaluate(row("single-agent"), row("delegated-task-loop", status="failed", acceptance="fail",
                     metrics={"acceptedTasks": 0, "totalTokens": 200}))
        a = r["aggregate"]["single-agent"]
        self.assertEqual(a["completionRegressions"], 1)
        self.assertEqual(a["qualityRegressions"], 1)
        self.assertEqual(a["metrics"]["totalTokens"]["medianDelta"], 100)
        self.assertIsNone(a["metrics"]["tokensPerAcceptedTask"]["medianDelta"])

    def test_environment_mismatch(self):
        r = evaluate(row("single-agent"), row("delegated-task-loop", environmentDigest="2" * 64))
        self.assertEqual(r["status"], "not-evaluated")
        self.assertIn("different-environment", [e["reason"] for e in r["excluded"]])

    def test_unreviewed_or_fake_pass(self):
        for changes in ({"reviewerRef": None}, {"metrics": {"acceptedTasks": 1}}, {"evidenceRefs": []}):
            with self.assertRaises(ValueError):
                evaluate(row("delegated-task-loop", **changes))

    def test_different_workload_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(row("single-agent", workloadDigest="f" * 64))

    def test_nonobserved_metrics_not_invented(self):
        a = row("single-agent", acceptance="unknown", reviewerRef=None, metrics={"elapsedMs": 42})
        b = row("delegated-task-loop", acceptance="unknown", reviewerRef=None, metrics={"elapsedMs": 41})
        r = evaluate(a, b)["aggregate"]["single-agent"]
        self.assertEqual(r["metrics"]["elapsedMs"]["medianDelta"], -1)
        self.assertEqual(r["qualityPairs"], 0)
        self.assertIsNone(r["metrics"]["totalTokens"]["medianDelta"])

    def test_duplicate_run_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(row("single-agent"), row("delegated-task-loop", runId="run-single-agent"))

if __name__ == "__main__":
    unittest.main()
