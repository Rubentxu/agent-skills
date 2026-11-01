"""New authority intents select portable lenses and never grant writes by reading."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("backlog_authority_router", ROOT / "scripts/affordances.py")
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)

class AuthorityRoutingTests(unittest.TestCase):
    def state(self, intent, **extra):
        return {"intent":intent,"basis":"observed","cli":"available",
                "project":"initialized","mode":"read", **extra}

    def test_decision_reuses_backlog_native_cli(self):
        result = router.affordances(self.state("decide"))
        self.assertIn("decision-provenance", result["lenses"])
        self.assertIn(["backlog","decision","list","--json"],result["suggested_reads"])
        self.assertEqual(result["decision"],"READY")

    def test_apply_requires_observed_side_effects(self):
        result = router.affordances(self.state("decide",mode="apply"))
        self.assertEqual(result["decision"],"INSPECT_MORE")
        result = router.affordances(self.state("decide",mode="apply",
                       config={"autoCommit":False,"remoteOperations":False,
                               "bypassGitHooks":False,"onStatusChange":False}))
        self.assertEqual(result["decision"],"AUTHORIZED_ACTION")
        self.assertTrue(any("permiso declarado" in x["why"] for x in result["_links"]))

    def test_read_only_context_can_work_without_installed_cli_snapshots(self):
        for intent in ("authority-check","handoff","memory-feedback","context-exchange"):
            result=router.affordances({"intent":intent,"basis":"observed",
                                      "cli":"missing","project":"absent","mode":"read"})
            self.assertEqual(result["decision"],"READY",intent)
            self.assertGreater(len(result["lenses"]),0)

    def test_spec_packet_can_reference_existing_decision_without_approval(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from spec_projection import project
        packet=json.loads((ROOT/"examples/spec-packet.json").read_text())
        tasks=json.loads((ROOT/"examples/spec-existing-tasks.json").read_text())
        packet["tasks"][0]["authorityRefs"]=["decision-14"]
        out=project(packet,tasks)
        entry=next(x for x in out["actions"] if x["key"]==packet["tasks"][0]["key"])
        self.assertEqual(entry["authorityRefs"],["decision-14"])
        self.assertEqual(out["status"],"PROPOSAL_ONLY")
        packet["tasks"][0]["authorityRefs"]=["../../bad"]
        with self.assertRaises(ValueError):
            project(packet,tasks)

if __name__ == "__main__":
    unittest.main()
