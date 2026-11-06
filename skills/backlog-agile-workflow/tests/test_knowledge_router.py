import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("knowledge_router", ROOT / "scripts/affordances.py")
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)


class KnowledgeRouterTests(unittest.TestCase):
    def state(self, intent, mode="read", cli="available", project="initialized"):
        return {"intent": intent, "basis": "observed", "cli": cli, "project": project,
                "mode": mode, "task": {}, "config": {"autoCommit": False,
                "remoteOperations": False, "bypassGitHooks": False, "onStatusChange": False}}

    def test_each_intent_loads_one_lens(self):
        for name in ("ubiquitous-language", "semantic-tagging", "okf-documentation",
                     "semantic-consistency", "research-orchestration", "emergent-architecture"):
            with self.subTest(name=name):
                outcome = router.affordances(self.state(name))
                self.assertEqual(outcome["decision"], "READY")
                self.assertEqual(outcome["lenses"], [name])
                self.assertEqual(outcome["status"], "NAVIGATION_ONLY")
                self.assertIn("inspect-knowledge-contract", [x["rel"] for x in outcome["_links"]])

    def test_authoring_requires_explicit_apply_and_config(self):
        self.assertEqual(router.affordances(self.state("semantic-tagging", mode="propose"))["decision"], "PROPOSE_ONLY")
        self.assertEqual(router.affordances(self.state("ubiquitous-language", mode="apply"))["decision"], "AUTHORIZED_ACTION")
        self.assertEqual(router.affordances(self.state("semantic-consistency", mode="apply"))["decision"], "KEEP_AS_IS")

    def test_research_delegates_only_when_skill_is_available(self):
        base = self.state("research-orchestration")
        self.assertFalse(any(x["rel"] == "delegate-skill" for x in router.affordances(base)["_links"]))
        base["available_skills"] = ["mosat-technology-learning"]
        self.assertEqual([x["skill_id"] for x in router.affordances(base)["_links"]
                          if x["rel"] == "delegate-skill"], ["mosat-technology-learning"])

    def test_offline_export_does_not_invent_cli(self):
        outcome = router.affordances(self.state("okf-documentation", cli="missing", project="absent"))
        self.assertEqual(outcome["decision"], "READY")
        self.assertFalse(any(x[:2] == ["backlog", "doc"] for x in outcome["suggested_reads"]))
        self.assertEqual(router.affordances(self.state("semantic-tagging", cli="missing"))["decision"], "DISCOVER")


if __name__ == "__main__":
    unittest.main()
