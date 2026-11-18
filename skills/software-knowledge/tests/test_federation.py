import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from federation import navigate
from model import make_corpus,node


class FederationTests(unittest.TestCase):
    def setUp(self):
        self.a=make_corpus("a",[node("contract","contract","Local API","Local",claim_state="proposed")],[])
        self.b=make_corpus("b",[node("contract","contract","External API","External",claim_state="observed")],[])
        self.m={"schemaVersion":1,"kind":"knowledge-federation","projects":["a","b"],"links":[
            {"from":{"project":"a","node":"contract"},"to":{"project":"b","node":"contract"},"relation":"uses-contract"}]}

    def test_no_implicit_read_and_no_identity_collision(self):
        r=navigate(self.m,{"a":self.a},project="a",node="contract")
        self.assertEqual(r["results"][0]["links"][0]["status"],"explicit-source-required")
        r=navigate(self.m,{"a":self.a,"b":self.b},project="a",node="contract")
        self.assertEqual(r["cross_project_reads"],0)
        self.assertEqual(r["results"][0]["links"][0]["status"],"not-followed")
        r=navigate(self.m,{"a":self.a,"b":self.b},project="a",node="contract",follow=True)
        self.assertEqual(r["cross_project_reads"],1)
        self.assertEqual(r["results"][0]["claim_state"],"proposed")
        self.assertEqual(r["results"][0]["links"][0]["target_summary"]["claim_state"],"observed")

    def test_project_mismatch_and_partial_missing(self):
        with self.assertRaises(ValueError):
            navigate(self.m,{"a":self.b},project="a",node="contract")
        r=navigate(self.m,{"a":self.a,"b":make_corpus("b",[],[])},project="a",node="contract",follow=True)
        self.assertEqual(r["results"][0]["links"][0]["status"],"not-observed-in-snapshot")

    def test_query_does_not_global_scan_and_budget(self):
        r=navigate(self.m,{"a":self.a,"b":self.b},project="a",query="External")
        self.assertEqual(r["status"],"unknown")
        r=navigate(self.m,{"a":self.a,"b":self.b},project="a",node="contract",follow=True,budget=1024)
        self.assertLessEqual(len(json.dumps(r,ensure_ascii=False,separators=(",",":")).encode()),1024)
