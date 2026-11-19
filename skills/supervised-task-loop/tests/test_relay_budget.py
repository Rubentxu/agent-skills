import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from agent_iteration import relay_remaining,Negativa

class ExternalRelayBudgetTests(unittest.TestCase):
    def test_budget_not_reset(self):
        state={"startedAt":1000,"lastObservedAt":4600,"attempts":1}
        self.assertEqual(relay_remaining(state,4600),3600)
        self.assertEqual(relay_remaining(state,8000),200)
        with self.assertRaises(Negativa):relay_remaining(state,4599)
    def test_invalid_state(self):
        with self.assertRaises(Negativa):relay_remaining({"startedAt":1000,"attempts":3},4600)

    def test_prepare_relay_preserves_state_and_original_evidence(self):
        import json
        import tempfile
        from unittest.mock import patch
        from agent_iteration import prepare_relay
        def board(status):
            return {"tasks":[{"id":"T1","status":status,"title":"T1"},{"id":"T2","status":"To Do","title":"T2"}]}
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            (d/"relay-state.json").write_text(json.dumps({"startedAt":1000,"lastObservedAt":1000,"attempts":1,"taskId":None}))
            (d/"board-before.json").write_text(json.dumps(board("To Do")))
            (d/"session.json").write_text("{}")
            def snapshot(rt,path):path.write_text(json.dumps(board("In Progress")))
            with patch("agent_iteration.time.time",return_value=4600),patch("agent_iteration.snapshot",side_effect=snapshot):
                with self.assertRaises(Negativa):prepare_relay(None,d,"1","running","obs","T1")
                with self.assertRaises(Negativa):prepare_relay(None,d,"1","stopped","obs","T2")
                state=prepare_relay(None,d,"1","stopped","obs","T1")
            self.assertEqual(state["startedAt"],1000)
            self.assertEqual(state["taskId"],"T1")
            self.assertTrue(list((d/"attempts").glob("*/session.json")))
            self.assertEqual(json.loads((d/"relay-state.json").read_text())["attempts"],1)
