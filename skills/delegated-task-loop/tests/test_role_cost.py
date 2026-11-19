import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from role_cost import aggregate
def fixture():
    return dict(schemaVersion=1,kind="role-cost-input",runId="run",usageBasis="host:normalized-v1",inventoryRef="host:sessions",inventoryComplete=True,elapsedMs=120,
                sessions=[dict(id="s",role="supervisor"),dict(id="w1",role="implementer"),dict(id="w2",role="implementer"),dict(id="z",role="steward")],
                observations=[dict(id=i,usageBasis="host:normalized-v1",totalTokens=n,outputTokens=2,evidenceRef="host:usage") for i,n in (("s",20),("w1",100),("w2",50),("z",10))])
class RoleCostTests(unittest.TestCase):
    def test_failed_attempts_and_steward_included(self):
        r=aggregate(fixture())
        self.assertEqual(r["metrics"],{"elapsedMs":120,"totalTokens":180})
        self.assertEqual(r["roles"]["implementer"]["totalTokens"]["complete"],150)
    def test_missing_is_not_zero(self):
        f=fixture();f["observations"].pop()
        r=aggregate(f);self.assertNotIn("totalTokens",r["metrics"])
        self.assertEqual(r["missingSessions"],["z"])
    def test_inventory_incomplete(self):
        f=fixture()|{"inventoryComplete":False}
        self.assertNotIn("totalTokens",aggregate(f)["metrics"])
    def test_basis_mismatch(self):
        f=fixture();f["observations"][0]["usageBasis"]="other"
        with self.assertRaises(ValueError):aggregate(f)
