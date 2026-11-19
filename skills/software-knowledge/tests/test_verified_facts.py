import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from verified_facts import assess
def fixture():
    return dict(schemaVersion=1,kind="fact-reuse-input",project="demo",facts=[dict(id="F1",claim="parser exists",scope="parser",sourcePins=[dict(ref="code:parser",digest="a"*64)],evidenceRef="observation:1",kind="static")],currentSources=[dict(ref="code:parser",digest="a"*64)],contradictedIds=[])
class FactTests(unittest.TestCase):
    def test_reuse(self):
        self.assertEqual(assess(fixture())["facts"][0]["state"],"REUSE_CANDIDATE")
    def test_changed_missing_or_contradicted(self):
        for sources in ([],[dict(ref="code:parser",digest="b"*64)]):
            self.assertEqual(assess(fixture()|{"currentSources":sources})["facts"][0]["state"],"REVALIDATE")
        self.assertEqual(assess(fixture()|{"contradictedIds":["F1"]})["facts"][0]["state"],"CONTRADICTED")
    def test_permissions_live(self):
        f=fixture();f["facts"][0]["kind"]="permission"
        self.assertEqual(assess(f)["facts"][0]["state"],"RECHECK_ON_USE")
