"""Provider lifecycle hooks: normalize only known structured fields, never text."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from harness_bridge import normalize
from harness_signal import classify


def event(provider, payload):
    return normalize(provider, payload, task_id="TASK-2", agent_id="worker-1",
                     claim_id="claim-1", observed_at="2026-11-22T12:00:00Z",
                     evidence_ref="ref:observed")


class HookBridgeTests(unittest.TestCase):
    def test_claude_code_stop_failure_typed_quota_and_auth(self):
        out = event("claude-code", {"hook_event_name":"StopFailure", "error":"rate_limit",
                                    "error_details":"secret", "last_assistant_message":"private"})
        self.assertEqual(out["code"], "rate_limited")
        self.assertNotIn("error_details", str(out))
        self.assertEqual(classify(out)["recommendation"], "RETRY_OR_YIELD")
        a = event("claude-code", {"hook_event_name":"StopFailure", "error":"authentication_failed"})
        self.assertEqual(classify(a)["classification"], "AUTH_BLOCKED")
        billing = event("claude-code", {"hook_event_name":"StopFailure", "error":"billing_error"})
        self.assertEqual(classify(billing)["classification"], "BILLING_BLOCKED")

    def test_session_end_never_certifies_stop(self):
        for provider, payload in (("claude-code",{"hook_event_name":"SessionEnd"}),
                                  ("qwen-code",{"hook_event_name":"SessionEnd"})):
            with self.subTest(provider=provider):
                out = event(provider, payload)
                self.assertEqual(classify(out)["recommendation"], "OBSERVE_HOST_STOP_NO_AUTO_RELEASE")
                self.assertNotIn("processStopped", out)

    def test_qwen_tool_failure_cannot_be_assumed_quota(self):
        out = event("qwen-code", {"hook_event_name":"PostToolUseFailure",
                                  "error":"quota exhausted", "tool_input":{"token":"secret"}})
        self.assertEqual(classify(out)["classification"], "TOOL_FAILED")
        self.assertNotIn("secret", str(out))
        self.assertNotIn("quota exhausted", str(out))

    def test_codex_notify_is_turn_only(self):
        out = event("codex", {"type":"agent-turn-complete", "last-assistant-message":"Secret prompt",
                              "input-messages":["never store"]})
        self.assertEqual(classify(out)["classification"], "TURN_COMPLETED")
        self.assertNotIn("Secret prompt", str(out))

    def test_acp_error_requires_typed_code(self):
        out = event("acp", {"event":"provider_error", "error":{"code":"quota_exhausted", "httpStatus":429}})
        self.assertEqual(classify(out)["classification"], "CAPACITY_BLOCKED")
        with self.assertRaises(ValueError):
            event("acp", {"event":"provider_error", "error":{"message":"private"}})

    def test_unrecognized_provider_events_do_not_claim_authority(self):
        for p, v in (("codex",{"type":"model-failed"}),
                     ("claude-code",{"hook_event_name":"PreToolUse"}),
                     ("qwen-code",{"hook_event_name":"Notification"})):
            with self.subTest(p=p), self.assertRaises(ValueError): event(p,v)

if __name__ == '__main__':
    unittest.main()
