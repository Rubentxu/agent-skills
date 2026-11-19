"""Real wrapper death with a harmless local executable; no model invocation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from agent_iteration import previous_process

@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("timeout") and Path("/proc/self/stat").exists(),"Linux/GNU timeout required")
class WatchdogOperational(unittest.TestCase):
    def test_watchdog_survives_wrapper_sigterm(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            conf=p/".config/claude-profiles";conf.mkdir(parents=True)
            (conf/"test.json").write_text("{}")
            bin=p/"bin";bin.mkdir()
            # Fake CLI deliberately does not finish until TERM. No external agent or credentials.
            fake=bin/"claude"
            fake.write_text("#!"+sys.executable+"\nimport signal,time,os\nfrom pathlib import Path\nPath('fake.pid').write_text(str(os.getpid()))\ndef stop(*_):\n Path('term-observed').write_text('TERM')\n raise SystemExit(0)\nsignal.signal(signal.SIGTERM,stop)\nwhile True: time.sleep(0.1)\n")
            fake.chmod(0o700)
            (p/"prompt.md").write_text("watchdog test")
            code="import sys;from pathlib import Path;from types import SimpleNamespace;sys.path.insert(0,sys.argv[1]);from agent_iteration import lanzar_sesion;p=Path(sys.argv[2]);lanzar_sesion(SimpleNamespace(profile='test',bare=False,workspace=p),p/'prompt.md',p/'session.json',p/'session.err',20)"
            env={"HOME":str(p),"PATH":str(bin)+os.pathsep+os.environ["PATH"],"PYTHONDONTWRITEBYTECODE":"1"}
            wrapper=subprocess.Popen([sys.executable,"-c",code,str(ROOT/"scripts"),str(p)],env=env,cwd=p)
            pid=None
            try:
                limit=time.monotonic()+6
                while time.monotonic()<limit and not ((p/"sesion-identity.json").exists() and (p/"fake.pid").exists()):
                    time.sleep(.05)
                self.assertTrue((p/"fake.pid").is_file())
                state,pid=previous_process(p);self.assertEqual(state,"running")
                wrapper.terminate();wrapper.wait(timeout=5)
                self.assertEqual(previous_process(p)[0],"running")
                limit=time.monotonic()+25
                while time.monotonic()<limit and previous_process(p)[0]=="running":
                    time.sleep(.1)
                self.assertEqual(previous_process(p)[0],"stopped")
                self.assertTrue((p/"term-observed").exists())
                deadline=json.loads((p/"deadline.json").read_text())
                self.assertIn(deadline["soft"],(p/"prompt-launch.md").read_text())
            finally:
                if wrapper.poll() is None:wrapper.kill();wrapper.wait(timeout=5)
                if pid and previous_process(p)[0]=="running":
                    os.killpg(pid,9)
