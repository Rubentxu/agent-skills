"""Generic structured harness signals do not assume any specific LLM provider."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from harness_signal import classify


def observed(**kw):
    obj = {"kind":"harness-observation-v1", "taskId":"TASK-42", "agentId":"agent-a",
           "claimId":"c-1", "harness":"codex", "signal":"provider_error",
           "observedAt":"2026-11-22T11:00:00Z", "evidenceRef":"trace-ref"}
    obj.update(kw)
    return obj


class HarnessSignalTests(unittest.TestCase):
    def test_quota_and_rate_are_not_conflated(self):
        self.assertEqual(classify(observed(code="insufficient_quota",httpStatus=429))["classification"],"CAPACITY_BLOCKED")
        self.assertEqual(classify(observed(httpStatus=429))["classification"],"RATE_LIMITED")
        self.assertEqual(classify(observed(code="rate_limit_exceeded",retryAfterSeconds=90))["recommendation"],"RETRY_OR_YIELD")

    def test_stop_requires_distinct_resource_inventory(self):
        self.assertEqual(classify(observed(signal="process_stopped",processStopped=True))["classification"],"STOPPED_OPERATIONS_UNKNOWN")
        self.assertEqual(classify(observed(signal="process_stopped",processStopped=True,operationsClear=True))["classification"],"STOPPED_RESOURCES_CLEAR")
        self.assertEqual(classify(observed(signal="process_stopped",processStopped=False,operationsClear=True))["classification"],"UNVERIFIED_STOP")

    def test_suspicion_is_never_automatic_release(self):
        a=classify(observed(signal="heartbeat_lost"))
        self.assertEqual(a["recommendation"],"TRIAGE_NO_AUTO_RELEASE")
        self.assertIn("not authenticated",a["notice"])

    def test_rejects_untrusted_freeform_content_and_bool_as_status(self):
        for data in (observed(transcript="private"), observed(httpStatus=True),
                     observed(retryAfterSeconds=-1),observed(signal="not-a-signal")):
            with self.subTest(data=data), self.assertRaises(ValueError): classify(data)


if __name__=='__main__': unittest.main()
