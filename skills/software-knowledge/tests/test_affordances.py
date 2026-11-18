import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from affordances import affordances, INTENTS, ROOT
from model import make_corpus, node
from retrieval import Navigator


class AffordancesTests(unittest.TestCase):
    def state(self, intent, **extra):
        return dict(intent=intent, project="demo", basis="observed", corpus="ready",
                    source="snapshot", **extra)

    def operations(self, r):
        return [x for x in r["_links"] if "operation" in x]

    def test_catalog_and_all_routes_consistent_and_bounded(self):
        self.assertGreater(len(affordances({})["available"]), 3)
        for intent in INTENTS - {"catalog"}:
            r=affordances(self.state(intent))
            self.assertEqual(r["status"],"NAVIGATION_ONLY")
            self.assertLessEqual(len(r["lenses"]),2)
            for x in r["_links"]:
                self.assertTrue(x["rel"] and x["why"])
                if "href" in x:
                    self.assertTrue((ROOT/x["href"]).is_file())

    def test_missing_project_stale_and_absent_corpus_never_issue_operations(self):
        for state in ({"intent":"verify"},
                      {"intent":"verify","project":"demo","basis":"stale","corpus":"ready"},
                      {"intent":"verify","project":"demo","basis":"observed","corpus":"absent"}):
            self.assertFalse(self.operations(affordances(state)))

    def test_snapshot_navigation_without_provider_and_optional_delegation(self):
        r=affordances(self.state("verify",anchors=["inv"],cli="missing"))
        self.assertEqual(r["decision"],"READY")
        self.assertEqual(self.operations(r)[0]["operation"]["command"],"context")
        self.assertFalse(any(x["rel"]=="delegate-skill" for x in r["_links"]))
        r=affordances(self.state("verify",query="check",available_skills=["cognicode-diagrams"]))
        self.assertEqual(self.operations(r)[0]["operation"]["command"],"search")
        self.assertTrue(any(x.get("skill_id")=="cognicode-diagrams" for x in r["_links"]))

    def test_capture_requires_observed_policy_and_does_not_infer_permissions(self):
        s=dict(intent="capture",project="demo",basis="observed",source="backlog",
               cli="available",backlog_project="initialized",mode="apply")
        self.assertFalse(self.operations(affordances(s)))
        s.update(remote_policy="local-only",read_authorized=True)
        self.assertEqual(self.operations(affordances(s))[0]["rel"],"capture-backlog")

    def test_follow_the_actual_navigation_response(self):
        n=node("doc:doc-1","contract","Rule","Rule",sources=[{"provider":"backlog","locator":"doc-1"}])
        n["content_state"]="metadata-only"
        nav=Navigator(make_corpus("demo",[n],[]))
        actual=nav.render(["doc:doc-1"])["results"][0]["_links"][0]
        self.assertEqual(actual["action"],"capture-doc")
        state=self.state("follow",selected_link=actual)
        self.assertFalse(self.operations(affordances(state)))
        state.update(cli="available",backlog_project="initialized",remote_policy="local-only",read_authorized=True)
        self.assertEqual(self.operations(affordances(state))[0]["operation"]["arguments"]["doc"],"doc-1")
        state["selected_link"]={"action":"get","id":"doc:doc-1","detail":"evidence"}
        self.assertEqual(self.operations(affordances(state))[0]["operation"]["command"],"get")
        state["selected_link"]["script"]="arbitrary"
        with self.assertRaises(ValueError):
            affordances(state)

    def test_proposals_and_index_opt_in(self):
        self.assertEqual(affordances(self.state("checkpoint",input_ready=True,mode="apply"))["decision"],"PROPOSE_ONLY")
        self.assertFalse(self.operations(affordances(self.state("index"))))
        self.assertEqual(self.operations(affordances(self.state("index",reuse_index=True)))[0]["operation"]["arguments"]["cache"],True)
        with self.assertRaises(ValueError):
            affordances(self.state("understand",unknown=True))
