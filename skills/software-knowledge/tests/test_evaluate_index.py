import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from evaluate_index import compare
from model import make_corpus,node


class EvaluateIndexTests(unittest.TestCase):
    def test_actual_index_and_memory_same_anchors_and_cleanup(self):
        c=make_corpus("p",[node("a","contract","A","Unique anchor"),node("b","term","B","Other")],[])
        q={"schemaVersion":1,"project":"p","questions":[
            {"id":"known","query":"unique anchor","relevant":["a"]},
            {"id":"unknown","query":"zebrasharkunrelated","relevant":[]}]}
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{"XDG_CACHE_HOME":d}):
            r=compare(c,q)
            self.assertEqual(r["questions"],2)
            self.assertEqual(r["aggregate"]["fts5"]["recall_at_k"],1)
            self.assertEqual(r["aggregate"]["fts5"]["correct_abstention"],1)
            self.assertEqual(r["rows"][0]["variants"]["fts5"]["retrieved"],["a"])
            self.assertEqual(list(Path(d).rglob("*.sqlite3")),[])
