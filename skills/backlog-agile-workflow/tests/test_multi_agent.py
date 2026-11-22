"""Regression tests for decentralized Backlog.md claims, no runtime dependencies."""
import importlib.util
import json
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "multi_agent.py"
spec = importlib.util.spec_from_file_location("multi_agent", SCRIPT)
ma = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ma)


def ev(t, gen, actor="agent-a", at="2026-11-22T11:00:00Z", **kw):
    return {"v": 1, "type": t, "id": f"e-{len(kw)}-{t}-{gen}",
            "actor": actor, "generation": gen, "at": at, **kw}


def claim():
    return ev("CLAIM", 1, claimId="c-1", harness="codex", leaseUntil="2026-11-22T11:30:00Z",
              resources=["repo://project/src"])


def task(events, id="T-1", status="To Do", ready=True):
    return {"id": id, "title": "Something", "isReady": ready, "archived": False,
            "status": status, "assignees": [],
            "comments": [{"body": ma.PREFIX + json.dumps(x)} for x in events]}


class ReducerTests(unittest.TestCase):
    def test_claim_then_release_then_other_agent(self):
        one = claim()
        rel = ev("RELEASE", 1, claimId="c-1", resourcesClear=True, evidenceRef="stop-ref")
        another = ev("CLAIM", 2, actor="agent-b", claimId="c-2", harness="claude",
                     leaseUntil="2026-11-22T12:30:00Z", resources=[])
        s = ma.task_state(task([one, rel, another]))
        self.assertEqual((s["owner"], s["generation"], s["phase"]), ("agent-b", 2, "ACTIVE"))

    def test_duplicate_owner_and_stale_worker_refused(self):
        with self.assertRaises(ma.Conflict):
            ma.task_state(task([claim(), claim()]))
        with self.assertRaises(ma.Conflict):
            ma.task_state(task([claim(), ev("RELEASE", 1, actor="agent-b", claimId="c-1",
                                              resourcesClear=True, evidenceRef="x")]))

    def test_quarantine_fences_old_owner_and_keeps_resources(self):
        quarantine = ev("QUARANTINE", 1, actor="supervisor", reason="lost worker")
        s = ma.task_state(task([claim(), quarantine]))
        self.assertEqual(s["generation"], 2)
        self.assertEqual(s["resources"], ["repo://project/src"])
        self.assertEqual(s["phase"], "QUARANTINED")
        with self.assertRaises(ma.Conflict):
            ma.task_state(task([claim(), quarantine, ev("HEARTBEAT", 1, claimId="c-1",
                        leaseUntil="2026-11-22T12:30:00Z")]))
        recovery = ev("RECOVER", 2, actor="supervisor", resourcesClear=True, evidenceRef="inventory-verified")
        self.assertEqual(ma.task_state(task([claim(), quarantine, recovery]))["phase"], "AVAILABLE")

    def test_cannot_recover_without_resource_evidence(self):
        with self.assertRaises(ValueError):
            ma.task_state(task([claim(), ev("QUARANTINE", 1, actor="supervisor", reason="lost"),
                                 ev("RECOVER", 2, actor="supervisor", resourcesClear=False, evidenceRef="unknown")]))

    def test_yield_negotiation(self):
        request = ev("YIELD_REQUESTED", 1, actor="supervisor", reason="capacity")
        answer = ev("YIELD_ACK", 1, claimId="c-1")
        done = ev("CHECKPOINT_READY", 1, claimId="c-1", evidenceRef="git:sha")
        s = ma.task_state(task([claim(), request, answer, done]))
        self.assertEqual(s["phase"], "YIELD_REQUESTED")
        self.assertEqual(s["checkpointRef"], "git:sha")

    def test_nonmaterial_heartbeat_does_not_mask_stalled(self):
        tick = ev("HEARTBEAT", 1, at="2026-11-22T11:40:00Z", claimId="c-1",
                  leaseUntil="2026-11-22T12:10:00Z")
        rows = ma.triage([task([claim(), tick])], "2026-11-22T11:45:00Z", 30)
        self.assertEqual(rows["tasks"][0]["health"], "STALLED")
        self.assertFalse(rows["tasks"][0]["leaseExpired"])

    def test_suspected_when_lease_expired_without_auto_release(self):
        rows = ma.triage([task([claim()])], "2026-11-22T12:00:00Z")
        self.assertEqual(rows["tasks"][0]["health"], "SUSPECT")
        self.assertEqual(rows["tasks"][0]["owner"], "agent-a")

    def test_rejects_unmanaged_in_progress_and_assignee(self):
        self.assertEqual(ma.task_candidate(task([], status="In Progress"), ma.replay([])),
                         "UNMANAGED_ACTIVE_OR_TERMINAL")
        t = task([])
        t["assignees"] = ["@someone"]
        self.assertEqual(ma.task_candidate(t, ma.replay([])), "ASSIGNED_WITHOUT_COORDINATION")

    def test_checkpoint_survives_handoff(self):
        first=claim()
        cp=ev("CHECKPOINT_READY",1,claimId="c-1",evidenceRef="git:checkpoint")
        release=ev("RELEASE",1,claimId="c-1",resourcesClear=True,evidenceRef="stop")
        successor=ev("CLAIM",2,actor="agent-b",claimId="c-2",harness="claude",
                     leaseUntil="2026-11-22T12:30:00Z",resources=["repo://project/src"])
        self.assertEqual(ma.task_state(task([first,cp,release,successor]))["checkpointRef"],"git:checkpoint")

    def test_resources_conflict_in_hierarchy(self):
        active = task([claim()], id="T-1")
        self.assertEqual(ma.conflict_with_active(["repo://project/src/main.py"], [active], "T-2"), ["T-1"])
        self.assertFalse(ma.scope_conflict("repo://project/src", "repo://other/src"))
        self.assertTrue(ma.scope_conflict("k8s://cluster/ns/*", "k8s://cluster/ns/database"))

    def test_invalid_event_and_duplicate_ids_fail_closed(self):
        with self.assertRaises(ma.Conflict):
            ma.task_state(task([claim(), claim()]))
        with self.assertRaises(ValueError):
            ma.task_state(task([{"v": 2, "type": "CLAIM", "id": "a"}]))
        with self.assertRaises(ValueError):
            ma.make_event("CLAIM", actor="a", id="e1", at="2026-11-22T11:00:00Z",
                          generation=1, claimId="c", harness="codex", resources=["../../etc"],
                          leaseUntil="2026-11-22T12:00:00Z")

    def test_labels_are_projection_not_authority(self):
        self.assertEqual(ma.labels_for_phase("QUARANTINED"), {"coord:quarantined", "coord:needs-recovery"})
        t = task([])
        t["labels"] = ["coord:claimed"]
        self.assertEqual(ma.task_candidate(t, ma.task_state(t)), "CANDIDATE")
        # A stale label can cause a discovery false positive; it does not create a claim.


if __name__ == "__main__":
    unittest.main()
