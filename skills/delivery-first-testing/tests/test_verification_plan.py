import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from verification_plan import compile_plan, receipts, digest

def candidate(i,covers,stage="worker",mandatory=False,cost=10,independent=False):
    return dict(id=i,argv=["test",i],cwd=".",covers=covers,stage=stage,mandatory=mandatory,independent=independent,costMs=cost,sourceRef="observed:harness")
def fixture():
    return dict(schemaVersion=1,kind="verification-plan-input",taskId="T1",repository="repo",baseRevision="a"*40,scope="bounded",impactRef="observed:diff",selector="manual",budgetMs=100,guarantees=[dict(id=x,statement=x,stage="acceptance") for x in ("AC1","AC2")],candidates=[candidate("both",["AC1","AC2"]),candidate("slow",["AC1"],cost=100),candidate("critical",["AC2"],mandatory=True)])
class PlanTests(unittest.TestCase):
    def test_select_and_mandatory(self):
        p=compile_plan(fixture())
        self.assertEqual(p["status"],"PLANNED")
        self.assertEqual({x["id"] for x in p["checks"]},{"both","critical"})
        self.assertFalse(p["authorized"])
    def test_unknown_and_uncovered(self):
        f=fixture()
        self.assertEqual(compile_plan(f|{"scope":"unknown"})["status"],"NEEDS_REFINEMENT")
        self.assertEqual(compile_plan(f|{"candidates":[]})["uncovered"],["AC1","AC2"])
    def test_no_deferring_acceptance(self):
        f=fixture()
        f["candidates"]=[candidate("late",["AC1"],stage="integration")]
        with self.assertRaises(ValueError): compile_plan(f)
    def test_budget_not_waiver(self):
        p=compile_plan(fixture()|{"budgetMs":1})
        self.assertTrue(p["overBudget"])
        self.assertEqual(len(p["checks"]),2)
    def test_receipts(self):
        p=compile_plan(fixture())
        o=dict(schemaVersion=1,kind="verification-observations",planDigest=digest(p),treeDigest="a"*64,environmentDigest="b"*64,receipts=[])
        for c in p["checks"]:
            o["receipts"].append(dict(id=c["id"],treeDigest="a"*64,environmentDigest="b"*64,outcome="PASS",runnerRef="run:1",executed=1,failed=0,skipped=0,role="worker"))
        self.assertEqual(receipts(p,o)["status"],"EVIDENCE_CANDIDATES")
        o["receipts"][0]["executed"]=0
        self.assertEqual(receipts(p,o)["status"],"NEEDS_EVIDENCE")
        o["receipts"][0]["executed"]=1
        o["treeDigest"]="c"*64
        self.assertEqual(receipts(p,o)["status"],"NEEDS_EVIDENCE")
    def test_independent_not_satisfied_by_worker(self):
        f=fixture()
        f["candidates"].append(candidate("oracle",["AC1"],stage="supervisor",independent=True))
        p=compile_plan(f)
        o=dict(schemaVersion=1,kind="verification-observations",planDigest=digest(p),treeDigest="a"*64,environmentDigest="b"*64,receipts=[dict(id="oracle",treeDigest="a"*64,environmentDigest="b"*64,outcome="PASS",runnerRef="run:1",executed=1,failed=0,skipped=0,role="worker")])
        self.assertEqual(receipts(p,o)["checks"]["oracle"],"RECHECK")

    def test_explicit_global_gate(self):
        f=fixture();f['scope']='global'
        self.assertEqual(compile_plan(f)['status'],'NEEDS_REFINEMENT')
        f['candidates'][0].update(globalGate=True,mandatory=True)
        self.assertEqual(compile_plan(f)['status'],'PLANNED')

    def test_evidence_relay_scoped_and_mandatory_not_waived(self):
        p=compile_plan(fixture())
        o=dict(schemaVersion=1,kind="verification-observations",planDigest=digest(p),treeDigest="c"*64,environmentDigest="b"*64,receipts=[],scopeProofs=[])
        for c in p["checks"]:
            o["receipts"].append(dict(id=c["id"],treeDigest="a"*64,environmentDigest="b"*64,outcome="PASS",runnerRef="run:1",executed=1,failed=0,skipped=0,role="worker"))
            o["scopeProofs"].append(dict(id=c["id"],checkDigest=digest(c),fromTreeDigest="a"*64,toTreeDigest="c"*64,previousDependencyDigest="d"*64,currentDependencyDigest="d"*64,complete=True,proofRef="impact:observed"))
        res=receipts(p,o)
        self.assertEqual(res["checks"]["both"],"REUSABLE_CANDIDATE")
        self.assertEqual(res["checks"]["critical"],"RECHECK")
        self.assertEqual([x["id"] for x in res["remainingChecks"]],["critical"])
        o["scopeProofs"][0]["complete"]=False
        self.assertEqual(receipts(p,o)["status"],"NEEDS_EVIDENCE")
        self.assertFalse(receipts(p,o)["authorized"])
