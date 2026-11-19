import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from delegation_contract import validate

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.e = json.loads((ROOT / "examples/envelope.json").read_text())
        self.r = json.loads((ROOT / "examples/result.json").read_text())

    def test_examples_never_authorize(self):
        for kind, v in (("envelope", None), ("result", self.r)):
            r = validate(kind, self.e, v)
            self.assertEqual(r["status"], "STRUCTURE_VALID")
            self.assertFalse(r["runtimeVerified"])
            self.assertFalse(r["authorized"])

    def test_reject_other_attempt(self):
        self.r["attemptId"] = "different"
        with self.assertRaises(ValueError):
            validate("result", self.e, self.r)

    def test_reject_wrong_base(self):
        self.r["revisions"][0]["baseSha"] = "c" * 40
        with self.assertRaises(ValueError):
            validate("result", self.e, self.r)

    def test_pass_without_evidence_or_missing_criterion(self):
        for criteria in ([self.r["criteria"][0]], [{"id": "AC-1", "status": "pass", "evidenceRefs": []}, self.r["criteria"][1]]):
            with self.assertRaises(ValueError):
                validate("result", self.e, self.r | {"criteria": criteria})

    def test_partial_reports_not_run(self):
        self.r["criteria"][0] = {"id": "AC-1", "status": "not-run", "evidenceRefs": []}
        with self.assertRaises(ValueError):
            validate("result", self.e, self.r)
        validate("result", self.e, self.r | {"outcome": "PARTIAL", "remaining": ["backlog:AC-1"]})

    def test_full_revision_and_path(self):
        for path in ("../other", "/etc", "src/../tests", "."):
            e = copy.deepcopy(self.e)
            e["repositories"][0]["paths"] = [path]
            with self.assertRaises(ValueError):
                validate("envelope", e)
        self.e["repositories"][0]["baseSha"] = "aabbcc"
        with self.assertRaises(ValueError):
            validate("envelope", self.e)

    def test_budget_is_observed_not_truncated(self):
        self.e["resultBudgetBytes"] = 256
        self.assertTrue(validate("result", self.e, self.r)["overBudget"])

    def test_checkpoint_partitions(self):
        c = {k: self.e[k] for k in ("schemaVersion", "project", "taskId", "runId", "attemptId")}
        c.update(kind="delegation-checkpoint", completedCriteria=["AC-1"], pendingCriteria=["DOD-1"],
                 stateRef="private:checkpoint", resourceRefs=[], nextAction="test")
        validate("checkpoint", self.e, c)
        c["pendingCriteria"].append("AC-1")
        with self.assertRaises(ValueError):
            validate("checkpoint", self.e, c)

if __name__ == "__main__":
    unittest.main()
