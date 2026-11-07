"""Contract invariants and hostile review inputs; no LLM and no CLI."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("native_goldfish_contract", ROOT / "scripts/review_contract.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def example(name):
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


class ReviewContractTests(unittest.TestCase):
    def setUp(self):
        self.req = example("request.json")
        self.reports = example("reports.json")

    def test_request_schema_and_budget(self):
        self.assertEqual(mod.request(self.req)["scope"]["mode"], "focused")
        a = copy.deepcopy(self.req)
        a["limits"]["maxRounds"] = 3
        with self.assertRaises(ValueError):
            mod.request(a)

    def test_escape_and_unlisted_source_rejected(self):
        for path in ("../../secret", "/etc/passwd", "src\\outside.py", "https://evil.example/a", "src/../docs/design.md"):
            with self.subTest(path=path):
                a = copy.deepcopy(self.req)
                a["scope"]["allowedSources"].append(path)
                with self.assertRaises(ValueError):
                    mod.request(a)

    def test_duplicate_and_unknown_reviewer_rejected(self):
        for ids in (["architecture", "architecture"], ["architecture", "unknown"]):
            a = copy.deepcopy(self.req)
            a["reviewers"] = ids
            with self.assertRaises(ValueError):
                mod.request(a)

    def test_stale_report_must_fail(self):
        a = copy.deepcopy(self.reports)
        a[0]["target"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            mod.aggregate(self.req, a)

    def test_unlisted_evidence_rejected(self):
        a = copy.deepcopy(self.reports)
        a[0]["findings"][0]["evidence"] = ["secrets.env"]
        with self.assertRaises(ValueError):
            mod.aggregate(self.req, a)

    def test_complete_reports_are_not_a_safety_certificate(self):
        out = mod.aggregate(self.req, self.reports)
        self.assertEqual(out["status"], "REVIEWED_WITH_FINDINGS")
        self.assertEqual(out["assurance"], "HOST_REPORTED_ONLY")
        self.assertEqual(out["findings"][0]["disposition"], "UNVERIFIED")

    def test_missing_or_not_run_is_inconclusive(self):
        self.assertEqual(mod.aggregate(self.req, self.reports[:2])["status"], "INCONCLUSIVE")
        a = copy.deepcopy(self.reports)
        a[2]["execution"]["status"] = "not_run"
        self.assertEqual(mod.aggregate(self.req, a)["status"], "INCONCLUSIVE")

    def test_partial_isolation_not_clean(self):
        a = copy.deepcopy(self.reports)
        a[1]["execution"]["sourcesRestricted"] = False
        self.assertEqual(mod.aggregate(self.req, a)["status"], "INCONCLUSIVE")

    def test_same_finding_is_deduplicated_and_severity_preserved(self):
        a = copy.deepcopy(self.reports)
        second = copy.deepcopy(a[0]["findings"][0])
        second["severity"] = "Blocker"
        second["claim"] = " NO  se define  el comportamiento de reintentos "
        a[1]["findings"] = [second]
        out = mod.aggregate(self.req, a)
        self.assertEqual(len(out["findings"]), 1)
        self.assertEqual(out["findings"][0]["severity"], "Blocker")
        self.assertEqual(out["findings"][0]["reviewers"], ["comprehension", "architecture"])

    def test_duplicate_reports_rejected(self):
        with self.assertRaises(ValueError):
            mod.aggregate(self.req, [self.reports[0], self.reports[0]])

    def test_changed_fingerprint_is_not_semantic_drift(self):
        a = mod.drift(example("baseline.json"), example("current.json"))
        self.assertEqual(a["status"], "CHANGED")
        self.assertEqual(a["changed"], ["src/run.kt"])
        self.assertIn("not proven semantic", a["note"])

    def test_same_snapshot_is_unchanged(self):
        a = example("baseline.json")
        self.assertEqual(mod.drift(a, copy.deepcopy(a))["status"], "NO_HASH_CHANGE")

    def test_reports_cannot_claim_safe_with_false_host_assertion(self):
        a = copy.deepcopy(self.reports)
        a[0]["execution"]["hostReported"] = False
        self.assertEqual(mod.aggregate(self.req, a)["status"], "INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main()
