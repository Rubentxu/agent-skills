"""Real local OS/Git canaries, NOT native LLM-host certification."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from liveness import linux_identity

@unittest.skipUnless(sys.platform.startswith("linux") and Path("/proc/self/stat").exists(),"Linux process identities required")
class OperationalCanaries(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.workspace=self.root/"product";self.workspace.mkdir()
        self.home=self.root/"home";self.home.mkdir()
        self.env=os.environ|{"XDG_STATE_HOME":str(self.root/"state"),"PYTHONDONTWRITEBYTECODE":"1"}
        self.command=[sys.executable,str(ROOT/"scripts/run_state.py"),"--binding","canary","--workspace",str(self.workspace)]
        self.s=self.call("start",maxTasks=2,maxAttempts=2)
    def call(self,op,ok=True,**values):
        p=subprocess.run([*self.command,op],input=json.dumps(values),text=True,capture_output=True,env=self.env,timeout=10)
        self.assertEqual(p.returncode,0 if ok else 2,p.stderr)
        if ok:return json.loads(p.stdout)["state"]
    def mutate(self,op,ok=True,attempt=False,**values):
        if attempt:values["attemptId"]=self.s["active"]["attemptId"]
        n=self.call(op,ok=ok,runId=self.s["runId"],expectedVersion=self.s["version"],**values)
        if ok:self.s=n
    def child(self,program,*args):
        p=subprocess.Popen([sys.executable,"-c",program,*map(str,args)],stdout=subprocess.PIPE,stdin=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        def cleanup():
            if p.poll() is None:p.kill()
            p.communicate(timeout=5)
        self.addCleanup(cleanup)
        return p
    def line(self,p):
        import select
        ready,_,_=select.select([p.stdout],[],[],5)
        self.assertTrue(ready,"child did not signal readiness")
        return p.stdout.readline().strip()
    def test_stopped_worker_does_not_release_live_operation(self):
        # Independent OS process deliberately outlives its simulated worker.
        operation=self.child("import sys; print('ready',flush=True); sys.stdin.readline(); print('complete',flush=True)")
        self.assertEqual(self.line(operation),"ready")
        worker=self.child("import sys; print('ready',flush=True); sys.stdin.readline()")
        self.assertEqual(self.line(worker),"ready")
        boot=Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        ticks=int(Path(f"/proc/{operation.pid}/stat").read_text().rsplit(")",1)[1].split()[19])
        self.mutate("claim",taskId="canary-1",briefRef="brief:1",effectDomains=["repo:product"])
        first=self.s["active"]["attemptId"]
        self.mutate("attach",attempt=True,handle=f"process:{worker.pid}")
        self.mutate("mark-pending",attempt=True,pendingRef=f"process:{operation.pid}")
        self.mutate("checkpoint",attempt=True,checkpointRef="checkpoint:1")
        worker.terminate();worker.wait(timeout=5)
        self.mutate("observe-stop",attempt=True,observation="terminated",observationRef="os:worker-wait")
        self.assertEqual(linux_identity(operation.pid,boot,ticks),"match")
        self.mutate("observe-resources",attempt=True,resourceStatus="live",inventoryRef="os:operation-start-ticks")
        self.mutate("release",attempt=True,ok=False,resultRef="not-authorized")
        self.mutate("replace",attempt=True,ok=False,briefRef="brief:2")
        self.mutate("replace",attempt=True,briefRef="brief:2",adoptionRef="operation:existing")
        self.assertNotEqual(first,self.s["active"]["attemptId"])
        self.assertEqual(self.s["active"]["pendingRef"],f"process:{operation.pid}")
        # No replacement operation is spawned; same PID produces actual result.
        operation.stdin.write("finish\n");operation.stdin.flush()
        self.assertEqual(self.line(operation),"complete")
        self.assertEqual(operation.wait(timeout=5),0)
        self.assertEqual(linux_identity(operation.pid,boot,ticks),"absent")
        self.mutate("observe-stop",attempt=True,observation="never-launched",observationRef="os:no-replacement-worker")
        self.mutate("observe-resources",attempt=True,resourceStatus="clear",inventoryRef="os:operation-wait")
        self.mutate("release",attempt=True,resultRef="os:complete")
        self.mutate("finish")
        self.assertTrue(self.s["finished"])
    def test_conflicting_steward_and_concurrent_real_claims(self):
        self.mutate("claim",taskId="canary-1",briefRef="brief:1",effectDomains=["repo:product"])
        version=self.s["version"]
        self.mutate("claim-steward",ok=False,briefRef="steward",effectDomains=["repo:product"],isolationObservationRef="test:collision")
        payload=json.dumps(dict(runId=self.s["runId"],expectedVersion=version,briefRef="steward",effectDomains=["repo:home"],isolationObservationRef="test:disjoint"))
        ps=[subprocess.Popen([*self.command,"claim-steward"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=self.env) for _ in range(2)]
        results=[p.communicate(payload,timeout=10) for p in ps]
        self.assertEqual(sorted(p.returncode for p in ps),[0,2])
        self.s=self.call("read")
        self.assertEqual(self.s["active"]["effectDomains"],["repo:product"])
        self.assertEqual(self.s["steward"]["effectDomains"],["repo:home"])
        self.mutate("finish",ok=False)
    @unittest.skipUnless(shutil.which("git"),"git required")
    def test_publication_observations_real_local_remote(self):
        remote=self.root/"remote.git"
        env=self.env|{"GIT_CONFIG_NOSYSTEM":"1","GIT_CONFIG_GLOBAL":"/dev/null","GIT_AUTHOR_NAME":"Canary","GIT_AUTHOR_EMAIL":"canary@example.invalid","GIT_COMMITTER_NAME":"Canary","GIT_COMMITTER_EMAIL":"canary@example.invalid"}
        def git(*args):
            return subprocess.run(["git","-C",str(self.workspace),*args],check=True,capture_output=True,text=True,env=env,timeout=10).stdout.strip()
        git("init","-q","-b","main")
        git("init","--bare","-q",str(remote))
        (self.workspace/"f").write_text("baseline")
        git("add","f");git("commit","-qm","baseline")
        git("remote","add","origin",str(remote));git("push","-q","origin","main")
        def snapshot():
            local=dict(reversed(line.split(" ",1)) for line in git("for-each-ref","--format=%(objectname) %(refname)","refs/heads").splitlines())
            refs=dict(reversed(line.split("\t",1)) for line in git("ls-remote","--refs","origin").splitlines())
            return {"local":local,"remote":refs}
        before=snapshot()
        git("push","-q","origin","HEAD:refs/heads/unexpected")
        after=snapshot()
        payload={"schemaVersion":1,"kind":"publication-audit-input","repositories":[dict(id="repo:tmp",baseline=before,after=after,allowedLocalRefs=[],allowedRemoteRefs=[],evidenceRef="git:local-bare")] }
        p=subprocess.run([sys.executable,str(ROOT/"scripts/publication_audit.py")],input=json.dumps(payload),text=True,capture_output=True,timeout=10,check=True)
        r=json.loads(p.stdout)
        self.assertEqual(r["status"],"INVESTIGATE")
        self.assertEqual(r["findings"][0]["ref"],"refs/heads/unexpected")
        self.assertEqual(r["findings"][0]["attribution"],"UNKNOWN")
