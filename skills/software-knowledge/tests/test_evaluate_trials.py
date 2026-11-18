import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from evaluate_trials import compare
from model import digest


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.plan={"schemaVersion":1,"kind":"paired-agent-evaluation","cases":[{
            "id":"case","project":"p","revision":"rev","prompt":"Explain",
            "access_policy":"read-only","checks":[{"id":"fact","required":True,"description":"Correct fact"}]}]}
        self.obs={"schemaVersion":1,"kind":"agent-trial-observations","plan_digest":digest(self.plan),"trials":[]}

    def row(self,variant,tokens=100):
        return {"case":"case","variant":variant,"pair":"p1","run_id":variant,"project":"p","revision":"rev",
                "environment":{"harness":"h","model":"m","settings_digest":"a"*64,"toolset_digest":"b"*64,
                               "prompt_digest":digest("Explain"),"access_policy":"read-only"},
                "status":"completed","metrics":{"input_tokens":tokens},"checks":{"fact":"pass"},
                "reviewer":"human","evidence":[{"locator":"local:redacted","digest":"c"*64}]}

    def test_empty_is_not_evaluated(self):
        r=compare(self.plan,self.obs)
        self.assertEqual(r["status"],"not-evaluated")
        self.assertIsNone(r["aggregate"]["input_tokens"]["median_delta"])

    def test_matched_metrics_and_quality_separate(self):
        self.obs["trials"]=[self.row("baseline"),self.row("knowledge",70)]
        r=compare(self.plan,self.obs)
        self.assertEqual(r["comparable_pairs"],1)
        self.assertEqual(r["aggregate"]["input_tokens"]["median_delta"],-30)
        self.assertEqual(r["aggregate"]["elapsed_ms"]["pairs"],0)
        self.obs["trials"][1]["checks"]["fact"]="fail"
        self.assertEqual(compare(self.plan,self.obs)["quality_regressions"],1)

    def test_mismatched_unknown_or_not_run(self):
        self.obs["trials"]=[self.row("baseline"),self.row("knowledge")]
        self.obs["trials"][1]["environment"]["model"]="different"
        self.assertEqual(compare(self.plan,self.obs)["unmatched"][0]["reason"],"different-environment")
        self.obs["trials"][1]=self.row("knowledge")
        self.obs["trials"][1]["checks"]={}
        self.assertEqual(compare(self.plan,self.obs)["quality_pairs"],0)
        self.obs["trials"][1]["status"]="not-run"
        with self.assertRaises(ValueError):
            compare(self.plan,self.obs)

    def test_fail_closed_on_wrong_plan_or_missing_evidence(self):
        self.obs["trials"]=[self.row("baseline")]
        self.obs["trials"][0]["evidence"]=[]
        with self.assertRaises(ValueError):
            compare(self.plan,self.obs)
        self.obs["trials"]=[]
        self.obs["plan_digest"]="0"*64
        with self.assertRaises(ValueError):
            compare(self.plan,self.obs)


    def test_failed_matched_trial_remains_visible_in_completion_statistics(self):
        self.obs["trials"]=[self.row("baseline"),self.row("knowledge")]
        self.obs["trials"][1]["status"]="failed"
        r=compare(self.plan,self.obs)
        self.assertEqual(r["completion_pairs"],1)
        self.assertEqual(r["completion_regressions"],1)
        self.assertEqual(r["completion_by_variant"]["knowledge"]["failed"],1)
        self.assertEqual(r["comparable_pairs"],0)
