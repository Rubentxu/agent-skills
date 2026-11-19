import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import pacing
import run_state

class PacingTests(unittest.TestCase):
    def test_thresholds_and_wait_not_exemption(self):
        s=pacing.schedule("default",1000,1000)
        for t,op,want in ((0,"none","CONTINUE"),(2700,"none","ASSESS_RELAY"),(3000,"healthy","PREPARE_RELAY"),(3600,"healthy","RECONCILE_DEADLINE")):
            self.assertEqual(pacing.assess(s,1000+t,op)["action"],want)
        self.assertEqual(pacing.assess(s,4600,terminal=True)["action"],"VERIFY_RESULT")
    def test_task_deadline_caps_successor(self):
        s=pacing.schedule("default",1000,7500)
        self.assertEqual(s["deadlineAt"],8200)
        with self.assertRaises(ValueError):pacing.schedule("default",1000,8200)
    def test_journal_preserves_budget_and_requires_baton(self):
        s=run_state.change(None,"start",dict(maxTasks=1,maxAttempts=2,relayPolicy="default"),"demo")
        def call(op,**kw):
            nonlocal s
            s=run_state.change(s,op,dict(runId=s["runId"],expectedVersion=s["version"],**kw),"demo")
        with patch("pacing.now",return_value=1000):
            call("claim",taskId="T1",briefRef="brief:1")
            old=s["active"]["attemptId"]
            call("attach",attemptId=old,handle="native")
            call("checkpoint",attemptId=old,checkpointRef="ckpt")
        with patch("pacing.now",return_value=4600):
            call("observe-stop",attemptId=old,observation="terminated",observationRef="host:stop")
            call("observe-resources",attemptId=old,resourceStatus="clear",inventoryRef="obs:clear")
            with self.assertRaises(ValueError):call("replace",attemptId=old,briefRef="brief:2")
            call("replace",attemptId=old,briefRef="brief:2",batonRef="baton:1",relayReason="time-budget")
        a=s["active"];self.assertEqual(a["schedule"]["taskStartedAt"],1000)
        self.assertEqual(a["schedule"]["taskDeadlineAt"],8200)
        self.assertEqual(a["schedule"]["deadlineAt"],8200)
        self.assertEqual(a["attemptHistory"][0]["attemptId"],old)
        self.assertEqual(s["tasksStarted"],1)
    def test_clock_rollback_and_invalid_policy(self):
        with self.assertRaises(ValueError):pacing.assess(pacing.schedule("default",100,100),99)
        with self.assertRaises(ValueError):pacing.policy(pacing.DEFAULT|{"attemptSeconds":3601})
