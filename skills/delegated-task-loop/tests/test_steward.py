import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from steward_contract import validate
from delegation_contract import digest
def brief():
    return dict(schemaVersion=1,kind="steward-handoff",runId="r",attemptId="a",taskId="T1",taskDigest="sha256:"+"a"*64,operations=[dict(id="o1",operation="record-accepted-status",sourceRef="receipt:1")],effectDomains=["home:/demo"],budgetMinutes=5,acceptanceRef="supervisor:accept")
class StewardTests(unittest.TestCase):
    def test_acceptance_required(self):
        with self.assertRaises(ValueError): validate(brief()|{"acceptanceRef":None})
    def test_result_binding(self):
        b=brief();r=dict(schemaVersion=1,kind="steward-result",runId="r",attemptId="a",taskId="T1",briefDigest=digest(b),operations=[dict(id="o1",status="completed",evidenceRefs=["backlog:receipt"])])
        self.assertFalse(validate(b,r)["authorized"])
        with self.assertRaises(ValueError): validate(b,r|{"briefDigest":"b"*64})
    def test_no_product_write_operation(self):
        b=brief();b["operations"][0]["operation"]="edit-code"
        with self.assertRaises(ValueError): validate(b)
