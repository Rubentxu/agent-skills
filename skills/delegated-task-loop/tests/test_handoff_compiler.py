import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from handoff_compiler import compile_handoff
from test_handoff_v2 import fixture

def sample():
    e=fixture();r=e["repositories"][0];pin=e.pop("taskDigest")
    p=e.pop("verificationPlan");e.pop("verifiedFacts")
    checks=[]
    for key,stage in (("workerChecks","worker"),("supervisorChecks","supervisor")):
        checks.extend({**c,"stage":stage} for c in p[key])
    task=e["taskId"]
    plan=dict(schemaVersion=1,kind="verification-plan",taskId=task,repository=r["id"],
              baseRevision=r["baseSha"],status="PLANNED",blocking=[],uncovered=[],authorized=False,
              guarantees=[dict(id=c["id"],stage="acceptance") for c in e["criteria"]],checks=checks,overBudget=False,unknownCostChecks=0)
    return dict(schemaVersion=1,kind="implementer-handoff-input",draft=e,
                authorityHandoff=dict(kind="authority-handoff",schemaVersion=1,taskId=task,taskDigest=pin,
                                     sourceRevision=r["baseSha"],questions=[],editAuthorized=False),
                authorityReceipt=dict(kind="handoff-receipt",schemaVersion=1,status="CONTEXT_MATCHES_RUNTIME_UNVERIFIED",
                                     taskContentCompared=True,taskDigest=pin,sourceRevision=r["baseSha"],reasons=[],editAuthorized=False),
                readiness=dict(kind="technical-readiness-assessment",schemaVersion=1,status="CANDIDATE_READY",
                               taskId=task,taskDigest=pin,reasons=[],authorized=False),
                plans=[dict(ref="plan:1",plan=plan)],planBundleRef="bundle:1",factAssessment=None,budgetDecisionRef=None)
class CompilerTests(unittest.TestCase):
    def test_compiles_without_authority(self):
        r=compile_handoff(sample());self.assertEqual(r["envelope"]["schemaVersion"],2);self.assertFalse(r["authorized"])
    def test_conflicting_task_and_revision(self):
        v=sample();v["readiness"]["taskDigest"]="sha256:"+"b"*64
        with self.assertRaises(ValueError):compile_handoff(v)
        v=sample();v["plans"][0]["plan"]["baseRevision"]="f"*40
        with self.assertRaises(ValueError):compile_handoff(v)
    def test_budget_and_receipt(self):
        v=sample();v["plans"][0]["plan"]["overBudget"]=True
        with self.assertRaises(ValueError):compile_handoff(v)
        v["budgetDecisionRef"]="decision:budget";compile_handoff(v)
        v["authorityReceipt"]["taskDigest"]="sha256:"+"b"*64
        with self.assertRaises(ValueError):compile_handoff(v)
