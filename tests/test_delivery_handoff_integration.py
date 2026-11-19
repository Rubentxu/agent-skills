"""Cross-skill integration through public process boundaries, never launch an LLM."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]/"skills"
def cli(skill,script,*args,payload=None):
    p=subprocess.run([sys.executable,str(ROOT/skill/"scripts"/script),*map(str,args)],
                     input=None if payload is None else json.dumps(payload),text=True,capture_output=True,timeout=10)
    if p.returncode:raise AssertionError(p.stderr)
    return json.loads(p.stdout)

class DeliveryHandoffIntegration(unittest.TestCase):
    def test_provider_outputs_compose_and_drift_fails(self):
        rev="a"*40;task="EXAMPLE-1"
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            t=root/"task.json";a=root/"assessment.json";h=root/"handoff.json"
            t.write_text(json.dumps(dict(schemaVersion=1,kind="task-view",task=dict(id=task,acceptanceCriteria=["Cancel safely"],references=[]))))
            a.write_text(json.dumps(dict(schemaVersion=1,kind="authority-assessment",records=[])))
            authority=cli("backlog-agile-workflow","context_handoff.py","prepare",t,a,"--revision",rev,"--agent","worker")
            h.write_text(json.dumps(authority))
            receipt=cli("backlog-agile-workflow","context_handoff.py","receive",h,a,"--revision",rev,"--task",task,"--task-view",t)
            pin=authority["taskDigest"]
            readiness=cli("backlog-agile-workflow","technical_readiness.py",payload=dict(schemaVersion=1,kind="technical-readiness-input",taskId=task,taskDigest=pin,boardReady=True,objectiveClear=True,criteriaClear=True,policyConflicts=[],materialQuestions=[],anchors=[dict(id="cancel",expectation="existing",state="present",evidenceRef="synthetic:symbol")]))
            plan=cli("delivery-first-testing","verification_plan.py",payload=dict(schemaVersion=1,kind="verification-plan-input",taskId=task,repository="repo",baseRevision=rev,scope="bounded",impactRef="synthetic:impact",selector="manual",budgetMs=10000,guarantees=[dict(id="AC-1",statement="Cancel safely",stage="acceptance")],candidates=[dict(id="cancel-test",argv=["fixture-runner","cancel"],cwd=".",covers=["AC-1"],stage="worker",mandatory=True,independent=False,costMs=100,sourceRef="synthetic:runner")]))
            facts=cli("software-knowledge","verified_facts.py",payload=dict(schemaVersion=1,kind="fact-reuse-input",project="demo",facts=[dict(id="F1",claim="cancel exists",scope="cancel",sourcePins=[dict(ref="symbol:cancel",digest="b"*64)],evidenceRef="synthetic:source",kind="static")],currentSources=[dict(ref="symbol:cancel",digest="b"*64)],contradictedIds=[]))
            draft=dict(schemaVersion=2,kind="delegation-envelope",project="demo",runId="r",attemptId="a",taskId=task,
                objective="Cancel safely",criteria=[dict(id="AC-1",kind="AC",text="Cancel safely")],
                repositories=[dict(id="repo",baseSha=rev,paths=["src"])],policyRefs=["policy:1"],authorityHandoffRef="private:authority",
                knowledgePackRef=None,reviewProfile="none",contextBudgetBytes=12000,resultBudgetBytes=4000,briefRevision=1,
                readinessRef="private:ready",effectivePolicies=[dict(id="P1",rule="No publication",sourceRef="policy:1",sourceDigest="c"*64)],
                liveResources=dict(status="reconciled",observedAt="2026-11-19T12:00:00Z",evidenceRef="synthetic:inventory",resources=[]),
                criterionOwners={"AC-1":"worker"},nonGoals=["full suite"],openQuestions=[],
                contingencies=dict(anchorMissing="ask-supervisor",newRisk="request-plan-amendment",backgroundWork="report-pending",ambiguity="ask-supervisor",stopWhen="worker criteria pass"),
                executionPolicy=dict(modelProfile="balanced",explorationBudgetMinutes=15,outputMode="compact",publication="forbidden",administrativeWork="delegated"))
            inp=dict(schemaVersion=1,kind="implementer-handoff-input",draft=draft,authorityHandoff=authority,
                     authorityReceipt=receipt,readiness=readiness,plans=[dict(ref="private:plan",plan=plan)],
                     planBundleRef="private:bundle",factAssessment=facts,budgetDecisionRef=None)
            compiled=cli("delegated-task-loop","handoff_compiler.py",payload=inp)
            self.assertEqual(compiled["envelope"]["verifiedFacts"][0]["id"],"F1")
            self.assertEqual(compiled["envelope"]["verificationPlan"]["workerChecks"][0]["id"],"cancel-test")
            self.assertFalse(compiled["authorized"])
            t.write_text(json.dumps(dict(schemaVersion=1,kind="task-view",task=dict(id=task,acceptanceCriteria=["Different behavior"],references=[]))))
            stale=cli("backlog-agile-workflow","context_handoff.py","receive",h,a,"--revision",rev,"--task",task,"--task-view",t)
            self.assertEqual(stale["status"],"PAUSED")
            inp["authorityReceipt"]=stale
            with self.assertRaises(AssertionError):cli("delegated-task-loop","handoff_compiler.py",payload=inp)
