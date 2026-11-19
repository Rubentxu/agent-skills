import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from delegation_contract import validate,digest

def fixture():
    e=json.loads((ROOT/"examples/envelope.json").read_text())
    repo=e["repositories"][0]["id"]
    ids=[c["id"] for c in e["criteria"]]
    e.update(schemaVersion=2,briefRevision=1,taskDigest="sha256:"+"a"*64,readinessRef="ready:1",
             effectivePolicies=[dict(id="P1",rule="No publish",sourceRef=e["policyRefs"][0],sourceDigest="a"*64)],
             verifiedFacts=[],liveResources=dict(status="reconciled",observedAt="2026-11-19T12:00:00Z",evidenceRef="inventory:1",resources=[]),
             verificationPlan=dict(ref="plan:1",digest="a"*64,workerChecks=[dict(id="test",repository=repo,argv=["test","target"],cwd=".",covers=[ids[0]])],
                                   supervisorChecks=[dict(id="audit",repository=repo,argv=["git","status"],cwd=".",covers=ids[1:])]),
             criterionOwners={ids[0]:"worker",**{x:"supervisor" for x in ids[1:]}},nonGoals=["full suite"],openQuestions=[],
             contingencies=dict(anchorMissing="ask-supervisor",newRisk="request-plan-amendment",backgroundWork="report-pending",ambiguity="ask-supervisor",stopWhen="worker criteria pass"),
             executionPolicy=dict(modelProfile="balanced",explorationBudgetMinutes=15,outputMode="compact",publication="forbidden",administrativeWork="delegated"))
    return e
def result(e):
    r=json.loads((ROOT/"examples/result.json").read_text())
    r.update(schemaVersion=2,briefRevision=e["briefRevision"],briefDigest=digest(e),pendingOperations=[],contradictedFacts=[])
    for c in r["criteria"]:
        if e["criterionOwners"][c["id"]]=="supervisor": c.update(status="not-run",evidenceRefs=[])
    return r
def delta(e,changes):
    return {k:e[k] for k in ("schemaVersion","project","runId","attemptId","taskId")}|dict(kind="handoff-amendment",baseRevision=e["briefRevision"],baseDigest=digest(e),newRevision=e["briefRevision"]+1,reason="observed change",changes=changes)
class HandoffTests(unittest.TestCase):
    def test_worker_not_responsible_for_supervisor_criterion(self):
        e=fixture();self.assertEqual(validate("result",e,result(e))["status"],"STRUCTURE_VALID")
    def test_missing_context_and_coverage(self):
        e=fixture()
        for v in (e|{"openQuestions":["Which contract?"]},e|{"effectivePolicies":[]},e|{"verificationPlan":e["verificationPlan"]|{"workerChecks":[]}}):
            with self.assertRaises(ValueError):validate("envelope",v)
    def test_pending(self):
        e=fixture();r=result(e)|dict(outcome="PENDING",pendingOperations=["operation:1"],remaining=["waiting"])
        validate("result",e,r)
        with self.assertRaises(ValueError):validate("result",e,r|{"pendingOperations":[]})
    def test_delta_version_and_no_publish(self):
        e=fixture();d=delta(e,{"knowledgePackRef":"pack:new"})
        updated=validate("amendment",e,d)["envelope"];self.assertEqual(updated["briefRevision"],2)
        with self.assertRaises(ValueError):validate("result",updated,result(e))
        with self.assertRaises(ValueError):validate("amendment",updated,d)
        with self.assertRaises(ValueError):validate("amendment",e,delta(e,{"executionPolicy":e["executionPolicy"]|{"publication":"explicit-authority"}}))
    def test_receipt(self):
        e=fixture()
        r={k:e[k] for k in ("schemaVersion","project","runId","attemptId","taskId")}|dict(kind="handoff-receipt",briefRevision=1,briefDigest=digest(e),status="NEEDS_CONTEXT",firstAction=None,questions=["Which anchor?"])
        validate("receipt",e,r)
        with self.assertRaises(ValueError):validate("receipt",e,r|{"questions":[]})
    def test_duplicate_live_operation(self):
        e=fixture()
        item=dict(id="r1",kind="job",operationKey="op1",originAttempt="prev",state="running",identityRef="native:1",evidenceRef="obs:1",verifiedAt="2026-11-19T12:00:00Z",effects=["build"],adoption="observe-only",resultRef="test:1")
        e["liveResources"]["resources"]=[item,item|{"id":"r2"}]
        with self.assertRaises(ValueError):validate("envelope",e)
