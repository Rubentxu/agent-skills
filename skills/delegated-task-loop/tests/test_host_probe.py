import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from host_probe import evaluate

def observed(*names):
    return {"schemaVersion": 1, "kind": "delegation-host-observations",
            "host": "example", "version": "1", "sessionRef": "opaque:session",
            "cases": [{"id": k, "status": "PASS", "evidenceRefs": ["opaque:" + k]} for k in names]}

class HostProbeTests(unittest.TestCase):
    def test_no_observation_no_capability(self):
        r = evaluate(observed())
        self.assertEqual(r["level"], "NOT_RUN")
        self.assertFalse(any(r["capabilities"].values()))
        self.assertFalse(r["runtimeVerified"])

    def test_fresh_does_not_imply_readonly(self):
        r = evaluate(observed("fresh-context", "nonblocking-launch"))
        self.assertEqual(r["level"], "RESULT_ONLY")
        self.assertFalse(r["reviewReadOnlyObserved"])
        self.assertFalse(r["capabilities"]["notify"])

    def test_async_and_reactive(self):
        names = ("fresh-context", "nonblocking-launch", "native-notification")
        self.assertEqual(evaluate(observed(*names))["level"], "ASYNC")
        self.assertEqual(evaluate(observed(*names, "live-progress", "live-steering"))["level"], "REACTIVE")
        self.assertFalse(evaluate(observed(*names))["capabilities"]["cancel"])

    def test_steward_requires_native_capabilities_and_own_canary(self):
        base=("fresh-context","nonblocking-launch","native-notification","isolated-writer")
        self.assertFalse(evaluate(observed(*base))["stewardIsolationObserved"])
        self.assertTrue(evaluate(observed(*base,"steward-isolation"))["stewardIsolationObserved"])
        self.assertFalse(evaluate(observed("steward-isolation"))["stewardIsolationObserved"])

    def test_evidence_required(self):
        r = observed("fresh-context")
        r["cases"][0]["evidenceRefs"] = []
        with self.assertRaises(ValueError):
            evaluate(r)

    def test_duplicate_case_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(observed("fresh-context", "fresh-context"))

    def test_failed_case_not_pass(self):
        r = observed("fresh-context")
        r["cases"][0]["status"] = "FAIL"
        self.assertFalse(evaluate(r)["capabilities"]["fresh"])

    def test_cli(self):
        p = subprocess.run([sys.executable, str(ROOT / "scripts/host_probe.py")],
                           input=json.dumps(observed()), text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["level"], "NOT_RUN")

if __name__ == "__main__":
    unittest.main()
