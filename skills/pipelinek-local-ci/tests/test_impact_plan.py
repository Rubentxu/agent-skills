#!/usr/bin/env python3
"""Behavior checks for the offline impact planner (temporary local Git only)."""
from pathlib import Path
import importlib.util
import subprocess
import tempfile
import unittest

source = Path(__file__).resolve().parents[1] / "scripts" / "impact-plan.py"
spec = importlib.util.spec_from_file_location("impact_plan", source)
impact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impact)


def git(path, *command):
    subprocess.run(["git", "-C", str(path), *command], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


class ImpactTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "test@example.invalid")
        git(self.root, "config", "user.name", "Test")
        (self.root / "Cargo.toml").write_text("[workspace]\nmembers=[]\n", encoding="utf-8")
        (self.root / "src").mkdir()
        (self.root / "src" / "main.rs").write_text("fn main() {}\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "base")
        self.base = impact.git(self.root, "rev-parse", "HEAD").decode().strip()

    def test_untracked_source_is_detected(self):
        (self.root / "src" / "other.rs").write_text("pub fn run() {}\n")
        changed = impact.changes(self.root, self.base)
        self.assertIn("src/other.rs", changed)
        report = impact.classify(self.root, changed)
        self.assertEqual(report["level"], "AFFECTED_CANDIDATE")
        self.assertEqual(report["coverage"], "PLANNING_ONLY")
        self.assertEqual(report["automaticallySelectedTests"], [])

    def test_modified_lockfile_requires_full_integration(self):
        (self.root / "Cargo.lock").write_text("# synthetic\n")
        changed = impact.changes(self.root, self.base)
        report = impact.classify(self.root, changed)
        self.assertEqual(report["level"], "FULL_REQUIRED_AT_INTEGRATION")

    def test_docs_only_uses_docs_gate_candidate(self):
        (self.root / "docs").mkdir()
        (self.root / "docs" / "guide.md").write_text("change")
        report = impact.classify(self.root, impact.changes(self.root, self.base))
        self.assertEqual(report["level"], "DOC_GATE_CANDIDATE")

    def test_unknown_file_never_claims_subset_coverage(self):
        (self.root / "unknown.data").write_text("??")
        report = impact.classify(self.root, impact.changes(self.root, self.base))
        self.assertEqual(report["level"], "FULL_REQUIRED_AT_INTEGRATION")
        self.assertFalse(report["reliableTestCoverageProved"])

    def test_no_changes_is_not_a_pass(self):
        report = impact.classify(self.root, impact.changes(self.root, self.base))
        self.assertEqual(report["level"], "NO_CHANGES")
        self.assertEqual(report["coverage"], "NOT_MEASURED")


if __name__ == "__main__":
    unittest.main()
