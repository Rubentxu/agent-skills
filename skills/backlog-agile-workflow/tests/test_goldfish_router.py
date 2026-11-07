import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("goldfish_router", ROOT / "scripts/affordances.py")
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)


def state(intent, installed=False, mode="read"):
    return {"intent": intent, "basis": "observed", "cli": "missing", "project": "absent",
            "mode": mode, "task": {}, "available_skills": ["goldfish-review"] if installed else []}


class GoldfishRouterTests(unittest.TestCase):
    def test_navigation_offline(self):
        for intent in ("independent-review", "review-resolution", "context-drift"):
            with self.subTest(intent=intent):
                out = router.affordances(state(intent))
                self.assertEqual(out["lenses"], [intent])
                self.assertEqual(out["decision"], "READY")
                self.assertEqual(out["suggested_reads"], [])

    def test_delegation_only_if_skill_installed(self):
        self.assertNotIn("delegate-skill", [x["rel"] for x in router.affordances(state("independent-review"))["_links"]])
        out = router.affordances(state("independent-review", installed=True))
        self.assertEqual([x["skill_id"] for x in out["_links"] if x["rel"] == "delegate-skill"], ["goldfish-review"])

    def test_apply_never_authorizes_writes(self):
        for intent in ("independent-review", "review-resolution", "context-drift"):
            out = router.affordances(state(intent, installed=True, mode="apply"))
            self.assertEqual(out["decision"], "KEEP_AS_IS")
            self.assertFalse(any(x["rel"] == "propose-cli-write" for x in out["_links"]))

    def test_stale_basis_refused(self):
        s = state("independent-review", True)
        s["basis"] = "stale"
        self.assertEqual(router.affordances(s)["decision"], "INSPECT_MORE")


if __name__ == "__main__":
    unittest.main()
