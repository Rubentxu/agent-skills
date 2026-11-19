import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from technical_readiness import assess
def task():
    return dict(schemaVersion=1,kind="technical-readiness-input",taskId="T1",taskDigest="sha256:"+"a"*64,boardReady=True,objectiveClear=True,criteriaClear=True,policyConflicts=[],materialQuestions=[],anchors=[dict(id="parser",expectation="existing",state="present",evidenceRef="git:parser")])
class ReadinessTests(unittest.TestCase):
    def test_clear(self):
        self.assertEqual(assess(task())["status"],"CANDIDATE_READY")
        self.assertFalse(assess(task())["authorized"])
    def test_anchor_missing_not_ready(self):
        f=task();f["anchors"][0]["state"]="missing"
        self.assertIn("ANCHOR_MISSING:parser",assess(f)["reasons"])
        f["anchors"][0]["expectation"]="create"
        self.assertEqual(assess(f)["status"],"CANDIDATE_READY")
    def test_conflict(self):
        self.assertEqual(assess(task()|{"materialQuestions":["which protocol?"]})["status"],"NEEDS_REFINEMENT")
    def test_no_observation(self):
        f=task();f["anchors"][0]["evidenceRef"]=None
        with self.assertRaises(ValueError): assess(f)
