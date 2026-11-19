import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from test_handoff_v2 import fixture
from delegation_contract import digest
from pacing import schedule
from relay import compile_baton,validate_successor
def sample():
    e=fixture();e["pacing"]=schedule("default",1000,1000)
    c={k:e[k] for k in ("schemaVersion","project","runId","attemptId","taskId","briefRevision")}
    c.update(kind="delegation-checkpoint",briefDigest=digest(e),completedCriteria=["AC-1"],pendingCriteria=["DOD-1"],stateRef="state",resourceRefs=[],nextAction="finish")
    o=dict(checkpoint=c,reason="time-budget",checkpointRef="ckpt",snapshots=[dict(repository=e["repositories"][0]["id"],baseSha=e["repositories"][0]["baseSha"],headSha="b"*40,treeDigest="c"*64,recoveryRef="worktree")],evidence=[],experiments=[],resources=e["liveResources"],stopRef="stop",observedAt=4600,decisionRef="decision")
    return e,o
def journal(e,b,n):
    return dict(kind="delegated-loop-journal",runId=e["runId"],version=7,active=dict(state="reserved",taskId=e["taskId"],attemptId=n["attemptId"],
        schedule=n["pacing"],batonRef="baton",checkpointRef=b["checkpointRef"],resourceStatus="clear",resourceInventoryRef="inventory",
        attemptHistory=[dict(attemptId=e["attemptId"],stopObservationRef=b["stopRef"],batonRef="baton")]))
class RelayTests(unittest.TestCase):
    def test_unverified_completion_reopens(self):
        e,o=sample();b=compile_baton(e,o)
        self.assertEqual(b["pendingCriteria"],["AC-1","DOD-1"])
        o["evidence"]=[dict(criterionId="AC-1",evidenceRefs=["check:1"],validationRef="supervisor:1")]
        b=compile_baton(e,o);self.assertEqual(b["pendingCriteria"],["DOD-1"])
    def test_successor_rejects_reset_and_criteria_changes(self):
        e,o=sample();b=compile_baton(e,o)
        n=e|dict(attemptId="next",pacing=schedule("default",1000,4600),continuity=dict(previousAttemptId=e["attemptId"],batonRef="baton",batonDigest=digest(b)))
        j=journal(e,b,n)
        self.assertTrue(validate_successor(e,b,n,o,j)["freshRequired"])
        with self.assertRaises(ValueError):validate_successor(e,b,n|{"pacing":schedule("default",4600,4600)},o,j)
        with self.assertRaises(ValueError):validate_successor(e,b,n|{"objective":"different"},o,j)
        with self.assertRaises(ValueError):validate_successor(e,b|{"nextAction":"different"},n,o,j)
        with self.assertRaises(ValueError):validate_successor(e,b,n,o,j|{"runId":"other"})
        with self.assertRaises(ValueError):validate_successor(e,b,n|{"verificationPlan":n["verificationPlan"]|{"digest":"f"*64}},o,j)
    def test_supervisor_only_does_not_spawn(self):
        e,o=sample();o["evidence"]=[dict(criterionId="AC-1",evidenceRefs=["check:1"],validationRef="supervisor:1")]
        b=compile_baton(e,o);self.assertEqual(b["nextRole"],"supervisor")
        n=e|dict(attemptId="next",pacing=schedule("default",1000,4600),continuity=dict(previousAttemptId=e["attemptId"],batonRef="baton",batonDigest=digest(b)))
        with self.assertRaises(ValueError):validate_successor(e,b,n,o,journal(e,b,n))
    def test_snapshot_mismatch(self):
        e,o=sample();o["snapshots"][0]["baseSha"]="f"*40
        with self.assertRaises(ValueError):compile_baton(e,o)
