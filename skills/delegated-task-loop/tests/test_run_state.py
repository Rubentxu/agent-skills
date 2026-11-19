import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_state

class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.workspace = self.base / "workspace"
        self.workspace.mkdir()
        self.binding = "example/project"
        self.project = run_state.root_for(self.binding, self.workspace, self.base / "state")
        self.s = self.call("start", maxTasks=2, maxAttempts=2)

    def call(self, op, **req):
        return run_state.execute(self.project, self.binding, op, req)

    def mutate(self, op, **req):
        self.s = self.call(op, runId=self.s["runId"], expectedVersion=self.s["version"], **req)
        return self.s

    def claim(self):
        return self.mutate("claim", taskId="T-1", briefRef="private:brief-1")

    def attempt(self, op, **req):
        return self.mutate(op, attemptId=self.s["active"]["attemptId"], **req)

    def test_lifecycle(self):
        self.claim()
        self.attempt("attach", handle="native-id")
        self.attempt("checkpoint", checkpointRef="private:checkpoint")
        self.attempt("observe-stop", observation="terminated", observationRef="host:terminal")
        self.attempt("release", resultRef="private:result")
        self.mutate("supervisor-checkpoint", checkpointRef="private:supervisor")
        self.mutate("finish")
        self.assertTrue(self.s["finished"])
        second = self.call("start", maxTasks=1, maxAttempts=1, expectedVersion=self.s["version"])
        self.assertNotEqual(second["runId"], self.s["runId"])
        self.assertIsNone(second["active"])

    def test_refuse_concurrent_claim_and_stale_version(self):
        self.claim()
        with self.assertRaises(ValueError):
            self.mutate("claim", taskId="T-2", briefRef="private:brief-2")
        with self.assertRaises(ValueError):
            self.call("finish", runId=self.s["runId"], expectedVersion=self.s["version"] - 1)
        self.assertEqual(self.call("read"), self.s)

    def test_uncertain_launch_never_releases(self):
        self.claim()
        for op, req in (("release", {"resultRef": "result"}), ("replace", {"briefRef": "brief"}),
                        ("observe-stop", {"observation": "unknown", "observationRef": "timeout"})):
            with self.assertRaises(ValueError):
                self.attempt(op, **req)
        self.assertEqual(self.call("read")["active"]["state"], "reserved")

    def test_replacement_requires_checkpoint_and_confirmed_stop(self):
        self.claim()
        self.attempt("attach", handle="native-id")
        with self.assertRaises(ValueError):
            self.attempt("observe-stop", observation="never-launched", observationRef="host:unknown")
        self.attempt("observe-stop", observation="terminated", observationRef="host:terminal")
        with self.assertRaises(ValueError):
            self.attempt("replace", briefRef="brief2")
        self.attempt("checkpoint", checkpointRef="checkpoint")
        old = self.s["active"]["attemptId"]
        self.attempt("replace", briefRef="brief2")
        self.assertNotEqual(self.s["active"]["attemptId"], old)
        self.assertEqual(self.s["active"]["checkpointRef"], "checkpoint")
        self.assertEqual(self.s["active"]["number"], 2)
        self.assertEqual(self.s["tasksStarted"], 1)
        self.attempt("observe-stop", observation="never-launched", observationRef="host:confirmed")
        with self.assertRaises(ValueError):
            self.attempt("replace", briefRef="brief3")

    def test_task_budget(self):
        for i in range(2):
            self.mutate("claim", taskId="T-" + str(i), briefRef="brief")
            self.attempt("observe-stop", observation="never-launched", observationRef="host:confirmed")
            self.attempt("release", resultRef="result")
        with self.assertRaises(ValueError):
            self.mutate("claim", taskId="T-3", briefRef="brief")

    def test_project_isolation_and_private_paths(self):
        other = run_state.root_for("other/project", self.workspace, self.base / "state")
        self.assertNotEqual(other, self.project)
        self.assertIsNone(run_state.execute(other, "other/project", "read", {}))
        self.assertEqual((self.project / "state.json").stat().st_mode & 0o777, 0o600)
        with self.assertRaises(ValueError):
            run_state.root_for("bad", self.workspace, self.workspace / "state")
        self.assertFalse((self.workspace / "state").exists())

    def test_two_cli_claims_one_wins(self):
        env = os.environ | {"XDG_STATE_HOME": str(self.base / "state")}
        cmd = [sys.executable, str(ROOT / "scripts/run_state.py"), "--binding", self.binding,
               "--workspace", str(self.workspace), "claim"]
        payload = json.dumps({"runId": self.s["runId"], "expectedVersion": self.s["version"],
                              "taskId": "T-1", "briefRef": "brief"}).encode()
        procs = [subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env) for _ in range(2)]
        for p in procs:
            p.communicate(payload, timeout=10)
        self.assertEqual(sorted(p.returncode for p in procs), [0, 2])
        self.assertEqual(self.call("read")["tasksStarted"], 1)

if __name__ == "__main__":
    unittest.main()
