"""Adversarial provenance/recall/handoff tests; no live CLI or agent involved."""
import copy
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from authority_context import validate
from owner_memory import recall, feedback
from context_handoff import prepare, receive
from context_exchange import export, inspect


def sample():
    message = "Apruebo: PipelineK ejecuta los gates. No duplicar CI."
    digest = "sha256:" + hashlib.sha256(message.encode()).hexdigest()
    source = {"provider": "claude-code", "sessionId": "session-101",
              "messageId": "msg-55", "digest": digest,
              "timestamp": "2026-11-01T12:00:00Z"}
    claims = {"schemaVersion": 1, "kind": "authority-records", "records": [
        {"id": "authority-14", "backlogDecisionId": "decision-14",
         "state": "approved", "scope": ["pipeline-execution", "ci-gates"],
         "source": source, "exactQuote": message, "supersededBy": None}]}
    messages = {"schemaVersion": 1, "kind": "message-evidence", "messages": [
        {"provider": "claude-code", "sessionId": "session-101",
         "messageId": "msg-55", "authorKind": "human",
         "text": message, "explicitApproval": True,
         "timestamp": "2026-11-01T12:00:00Z"}]}
    decisions = {"schemaVersion": 1, "kind": "decision-list", "decisions": [
        {"id": "decision-14", "title": "No CI duplicado", "status": "accepted"}]}
    return claims, messages, decisions


class AuthorityTests(unittest.TestCase):
    def verdict(self, claims, messages, decisions):
        return validate(claims, messages, decisions)["records"][0]["verdict"]

    def test_original_human_message_and_backlog_can_correlate(self):
        a, m, d = sample()
        result = validate(a, m, d)
        self.assertEqual(result["records"][0]["verdict"], "VERIFIED")
        self.assertFalse(result["records"][0]["canAuthorizeExecution"])

    def test_missing_message_is_unverified(self):
        a, m, d = sample()
        m["messages"] = []
        self.assertEqual(self.verdict(a, m, d), "UNVERIFIED")

    def test_agent_speech_cannot_impersonate_owner(self):
        a, m, d = sample()
        m["messages"][0]["authorKind"] = "agent"
        self.assertEqual(self.verdict(a, m, d), "CONFLICTED")

    def test_tampered_message_is_conflict(self):
        a, m, d = sample()
        m["messages"][0]["text"] += " EXTRA"
        self.assertEqual(self.verdict(a, m, d), "CONFLICTED")

    def test_owner_message_is_not_approval_automatically(self):
        a, m, d = sample()
        m["messages"][0]["explicitApproval"] = False
        self.assertEqual(self.verdict(a, m, d), "UNVERIFIED")

    def test_backlog_status_is_not_human_authority(self):
        a, m, d = sample()
        d["decisions"][0]["status"] = "proposed"
        self.assertEqual(self.verdict(a, m, d), "CONFLICTED")

    def test_superseded_decision_is_stale(self):
        a, m, d = sample()
        a["records"][0]["supersededBy"] = "decision-15"
        self.assertEqual(self.verdict(a, m, d), "STALE")

    def test_inconsistent_source_timestamp_is_conflicted(self):
        a, m, d = sample()
        m["messages"][0]["timestamp"] = "2026-10-30T12:00:00Z"
        self.assertEqual(self.verdict(a, m, d), "CONFLICTED")

    def test_expired_decision_is_stale(self):
        a, m, d = sample()
        a["records"][0]["expiresAt"] = "2020-01-01T00:00:00Z"
        self.assertEqual(self.verdict(a, m, d), "STALE")

    def test_ambiguous_message_identity_is_conflicted(self):
        a, m, d = sample()
        m["messages"].append(copy.deepcopy(m["messages"][0]))
        self.assertEqual(self.verdict(a, m, d), "CONFLICTED")

    def test_reject_pagination_and_duplicate_claims(self):
        a, m, d = sample()
        d["nextSkip"] = 1
        with self.assertRaises(ValueError):
            validate(a, m, d)
        d.pop("nextSkip")
        a["records"].append(copy.deepcopy(a["records"][0]))
        with self.assertRaises(ValueError):
            validate(a, m, d)

    def test_recall_is_scoped_and_bounded(self):
        a, m, d = sample()
        assessment = validate(a, m, d)
        output = recall(assessment, d, scope=["pipeline-execution"])
        self.assertEqual([r["id"] for r in output["items"]], ["decision-14"])
        self.assertEqual(recall(assessment, d, scope=["other"])["items"], [])
        self.assertEqual(output["items"][0]["use"], "CONTEXT_ONLY")

    def test_agent_votes_do_not_approve(self):
        a, m, d = sample()
        assessment = validate(a, m, d)
        f = feedback(assessment, {"schemaVersion": 1, "kind": "agent-feedback",
                                 "votes": [{"recordId": "authority-14",
                                            "agentId": "reviewer", "value": "misleading"}]})
        self.assertEqual(f["changesToApprovals"], 0)
        self.assertEqual(f["changesToBacklog"], 0)

    def test_handoff_requires_revision_and_matching_source_pin(self):
        a, m, d = sample()
        assessment = validate(a, m, d)
        task = {"schemaVersion": 1, "kind": "task-view", "task": {
            "id": "TASK-42", "references": ["decision-14"]}}
        rev = "a" * 40
        handoff = prepare(task, assessment, revision=rev, agent="worker",
                          questions=["Confirm runtime"])
        self.assertFalse(handoff["editAuthorized"])
        good = receive(handoff, assessment, revision=rev, task_id="TASK-42")
        self.assertEqual(good["status"], "CONTEXT_MATCHES_RUNTIME_UNVERIFIED")
        self.assertEqual(receive(handoff, assessment,
                                 revision="b" * 40, task_id="TASK-42")["status"], "PAUSED")
        a["records"][0]["source"]["messageId"] = "msg-99"
        bad = receive(handoff, validate(a, m, d), revision=rev, task_id="TASK-42")
        self.assertIn("AUTHORITY_CHANGED_OR_MISSING", bad["reasons"])

    def test_offline_bundle_contains_only_refs_and_not_a_signature(self):
        a, m, d = sample()
        assessment = validate(a, m, d)
        memory = recall(assessment, d, scope=["ci-gates"])
        task = {"schemaVersion": 1, "kind": "task-view",
                "task": {"id": "TASK-42", "references": ["decision-14"]}}
        handoff = prepare(task, assessment, revision="a" * 40, agent="worker")
        bundle = export(memory, handoff)
        self.assertNotIn("Apruebo", str(bundle))
        self.assertIn("UNVERIFIED", inspect(bundle)["status"])
        bundle["decisions"][0]["scope"].append("malicious")
        with self.assertRaises(ValueError):
            inspect(bundle)


if __name__ == "__main__":
    unittest.main()
