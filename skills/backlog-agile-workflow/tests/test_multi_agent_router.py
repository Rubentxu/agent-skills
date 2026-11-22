"""HATEOAS regression checks for portable multi-harness workflow discovery."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("backlog_affordances", ROOT / "scripts" / "affordances.py")
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)


def observed(intent, **kwargs):
    state = {"intent": intent, "basis": "observed", "cli": "available",
             "project": "initialized", "mode": "read"}
    state.update(kwargs)
    return state


class MultiAgentHateoas(unittest.TestCase):
    def test_new_intents_discover_one_lens_and_existing_href(self):
        cases = {
            "coordinate-work": "multi-agent-coordination",
            "schedule-work": "multi-agent-coordination",
            "claim-task": "multi-agent-coordination",
            "yield-task": "yield-negotiation",
            "inspect-stalled": "stalled-work-recovery",
            "recover-task": "stalled-work-recovery",
        }
        for intent, expected in cases.items():
            with self.subTest(intent=intent):
                kwargs = {"task": {"id": "TASK-1"}} if intent in {"claim-task", "yield-task", "recover-task"} else {}
                result = router.affordances(observed(intent, **kwargs))
                self.assertEqual(result["status"], "NAVIGATION_ONLY")
                self.assertIn(expected, result["lenses"])
                self.assertLessEqual(len(result["lenses"]), 2)
                self.assertNotEqual(result["decision"], "AUTHORIZED_ACTION")
                for link in result["_links"]:
                    if "href" in link:
                        self.assertTrue((ROOT / link["href"]).is_file(), link)

    def test_no_invented_skill_delegation(self):
        result = router.affordances(observed("coordinate-work"))
        self.assertFalse(any(x["rel"] == "delegate-skill" for x in result["_links"]))
        discovered = router.affordances(observed("coordinate-work", available_skills=["delegated-task-loop"]))
        self.assertEqual([x["skill_id"] for x in discovered["_links"] if x["rel"] == "delegate-skill"],
                         ["delegated-task-loop"])

    def test_write_intent_is_never_host_authority(self):
        result = router.affordances(observed("claim-task", task={"id": "TASK-1"}, mode="apply"))
        self.assertEqual(result["decision"], "PROPOSE_ONLY")

    def test_missing_id_requires_inspection(self):
        result = router.affordances(observed("recover-task"))
        self.assertEqual(result["decision"], "INSPECT_MORE")


if __name__ == '__main__':
    unittest.main()
