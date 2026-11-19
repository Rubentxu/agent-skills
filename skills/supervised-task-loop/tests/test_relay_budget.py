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
