import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from worker_metrics import scan

class WorkerMetricsTests(unittest.TestCase):
    def test_stream_dedup_partial_and_no_content(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"session.jsonl"
            start=dict(type="assistant",timestamp="2026-11-19T12:00:00Z",message=dict(id="m1",usage={"output_tokens":10},content=[dict(type="tool_use",id="t1",name="Bash",input={"command":"SECRET-MARKER"})]))
            done=dict(type="user",timestamp="2026-11-19T12:00:02Z",message=dict(content=[dict(type="tool_result",tool_use_id="t1",content="SECRET-MARKER")]))
            p.write_text(json.dumps(start)+"\n"+json.dumps(start)+"\n"+json.dumps(done))
            a=scan(p);self.assertEqual(a["metrics"]["toolCalls"],{"Bash":1});self.assertEqual(a["metrics"]["status"],"PARTIAL")
            with p.open("a") as f:f.write("\n")
            b=scan(p,a["cursor"]);m=b["metrics"]
            self.assertEqual(m["toolRoundtripMs"],{"Bash":2000});self.assertEqual(m["observedUsage"]["output_tokens"],10)
            self.assertEqual(m["completedToolUnionMs"],2000);self.assertIsNone(m["modelGenerationMs"])
            self.assertNotIn("SECRET-MARKER",json.dumps(b))
    def test_duplicate_message_usage_not_summed(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"s";r=dict(type="assistant",message=dict(id="m",usage=dict(output_tokens=10),content=[]))
            p.write_text(json.dumps(r)+"\n"+json.dumps(r|{"message":r["message"]|{"usage":{"output_tokens":20}}})+"\n")
            self.assertEqual(scan(p)["metrics"]["observedUsage"]["output_tokens"],20)
