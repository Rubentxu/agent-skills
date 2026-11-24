import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from io import BytesIO
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import agent_iteration as iteration
import agent_loop_report as report
import agent_preflight as preflight

class FakeResponse(BytesIO):
    pass
class Client:
    def __init__(self,payload):self.payload=payload;self.request=None
    def open(self,req,timeout):
        self.request=req
        return FakeResponse(json.dumps(self.payload).encode())

class RecoveryTests(unittest.TestCase):
    def test_empty_and_startup_error(self):
        for s in ({},{"is_error":True,"num_turns":0},{"is_error":False,"num_turns":0}):
            self.assertNotEqual(report.estado_sesion(s),"COMPLETED")
        self.assertEqual(report.estado_sesion({"session_id":"x","num_turns":1,"is_error":True}),"COMPLETED")
    def test_diagnostic(self):
        d=report.diagnostico({"is_error":True,"num_turns":0,"result":"unrecognized_model\napi_key=SECRET"} ,{},{},"NOT_RUN")
        self.assertEqual(d["category"],"MODEL_UNAVAILABLE")
        self.assertNotIn("SECRET",json.dumps(d))
        self.assertFalse(d["retryAuthorized"])
    def test_watchdog_deadline(self):
        text,soft,hard=iteration.deadline_prompt("custom",90)
        self.assertIn(soft,text);self.assertIn(hard,text);self.assertLess(soft,hard)
    def test_arc_and_no_remeasure(self):
        with tempfile.TemporaryDirectory() as root:
            d=Path(root)
            (d/"session.json").write_text('{"session_id":"s","is_error":false,"num_turns":2}')
            (d/"report.json").write_text('{"kind":"agent-loop-report","iteration":"1","verdict":"PASS","session":{"session_id":"s"}}')
            self.assertFalse(iteration.valid_report(d,"1"))  # legacy administrative PASS is not delivery
            a=iteration.archive_attempt(d,"obs:1")
            self.assertTrue((a/"report.json").exists());self.assertFalse((d/"report.json").exists())
    def test_catalog(self):
        profile={"env":{"ANTHROPIC_BASE_URL":"http://127.0.0.1:1234","ANTHROPIC_MODEL":"custom-model","ANTHROPIC_AUTH_TOKEN":"private"}}
        client=Client({"data":[{"id":"custom-model"}]})
        self.assertEqual(preflight.catalogo_modelos(profile,{},client),"READY")
        self.assertEqual(client.request.full_url,"http://127.0.0.1:1234/v1/models")
        with self.assertRaisesRegex(preflight.Fallo,"MODEL_UNAVAILABLE"):
            preflight.catalogo_modelos(profile,{},Client({"data":[{"id":"other"}]}))
        with self.assertRaisesRegex(preflight.Fallo,"UNSAFE_URL"):
            preflight.catalogo_modelos({"env":profile["env"]|{"ANTHROPIC_BASE_URL":"http://public.example"}},{},client)
    def test_catalog_no_native_claim(self):
        self.assertIn("CHECK_UNSUPPORTED",preflight.catalogo_modelos({},{}))
        with self.assertRaises(preflight.Fallo):preflight.catalogo_modelos({},{"AGENT_MODEL_CHECK":"required"})
    @unittest.skipUnless(Path("/proc/self/stat").exists(),"Linux proc required")
    def test_process_start_pin(self):
        with tempfile.TemporaryDirectory() as root:
            d=Path(root);identity=iteration.process_identity(os.getpid())
            iteration.write_json(d/"sesion-identity.json",identity)
            self.assertEqual(iteration.previous_process(d)[0],"running")
            identity["startTicks"]+=1;iteration.write_json(d/"sesion-identity.json",identity)
            self.assertEqual(iteration.previous_process(d)[0],"stopped")
