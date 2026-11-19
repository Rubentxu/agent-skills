import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from liveness import assess,linux_identity
def sample():
    return dict(schemaVersion=1,kind="liveness-observation",identity="native:1",phase="exploration",hostState="running",hostEvidenceRef="host:obs",process=None,silentSeconds=1800,withoutProgressSeconds=None,operation="none",steering=True,graceElapsed=False,inventoryComplete=False)
class LivenessTests(unittest.TestCase):
    def test_silence_steer_not_kill(self):
        r=assess(sample());self.assertEqual(r["recommended"],"STEER");self.assertFalse(r["terminationConfirmed"])
    def test_healthy_operation_wait(self):
        self.assertEqual(assess(sample()|{"operation":"healthy"})["signal"],"pending")
    def test_missing_process_not_terminal(self):
        with patch("liveness.linux_identity",return_value="absent"):
            r=assess(sample()|{"process":{"pid":12,"bootId":"b","startTicks":1},"inventoryComplete":True})
        self.assertEqual(r["classification"],"STALE_CANDIDATE");self.assertFalse(r["terminationConfirmed"])
    def test_proc_identity_and_reuse(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/"sys/kernel/random").mkdir(parents=True);(p/"sys/kernel/random/boot_id").write_text("boot")
            (p/"12").mkdir();(p/"12/stat").write_text("12 (a (name)) "+" ".join(["S"]+["0"]*18+["42"]))
            self.assertEqual(linux_identity(12,"boot",42,p),"match")
            self.assertEqual(linux_identity(12,"boot",41,p),"reused")
            self.assertEqual(linux_identity(13,"boot",42,p),"absent")
