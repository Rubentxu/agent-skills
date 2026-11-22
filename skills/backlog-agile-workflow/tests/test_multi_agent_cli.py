"""Integration smoke: two independent clones, same bare authority, fake Backlog CLI.

The fake faithfully exercises JSON list/view and task edit with append comment,
labels, git staging and CAS; it is NOT a substitute for a Backlog.md canary.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "scripts" / "multi_agent_cli.py"
FAKE_CLI = r'''#!/usr/bin/env python3
import json, pathlib, sys
root = pathlib.Path.cwd()
args = sys.argv[1:]
if args[:2] == ['task','list']:
  all_tasks = [json.loads(p.read_text()) for p in sorted((root/'backlog'/'tasks').glob('*.json'))]
  print(json.dumps({'schemaVersion':1,'kind':'task-list','tasks':[{k:d[k] for k in
       ('id','title','isReady','archived','status','assignees','labels')} for d in all_tasks]}))
else:
  p = root/'backlog'/'tasks'/('task-'+args[2].split('-')[-1]+'.json') if len(args)>2 else None
  d = json.loads(p.read_text()) if p and p.exists() else {}
  if args[:2] == ['task','view']:
    print(json.dumps({'schemaVersion':1,'kind':'task-view','task':d}))
  elif args[:2] == ['task','edit']:
    i=3
    while i < len(args):
      k = args[i]; v = args[i+1]
      if k == '--comment': d['comments'].append({'body': v})
      if k == '--label': d['labels'] = [x for x in v.split(',') if x]
      if k == '--add-label' and v not in d['labels']: d['labels'].append(v)
      if k == '--status': d['status'] = v
      if k == '--remove-label' and v in d['labels']: d['labels'].remove(v)
      i+=2
    p.write_text(json.dumps(d,indent=2)+'\n')
  else:
    print('unknown CLI input: '+repr(args),file=sys.stderr);sys.exit(1)

'''


def git(*argv, cwd=None):
    cp = subprocess.run(["git", *argv], cwd=cwd, capture_output=True, text=True, timeout=20)
    if cp.returncode:
        raise RuntimeError(cp.stderr)
    return cp.stdout.strip()


class DistributedSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="coord-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cli = self.root/"backlog-cli"
        self.cli.write_text(FAKE_CLI)
        self.cli.chmod(0o755)
        self.remote = self.root/"backlog.git"
        git("init", "--bare", "--initial-branch=main", str(self.remote))
        initial = self.root/"initial"
        git("init", "--initial-branch=main", str(initial))
        git("config", "user.name", "Test", cwd=initial)
        git("config", "user.email", "test@example.test", cwd=initial)
        (initial/"backlog"/"tasks").mkdir(parents=True)
        task = {"id":"TASK-1", "title":"Work", "isReady":True, "archived":False,
                "status":"To Do", "assignees":[], "labels":[], "path":"backlog/tasks/task-1.json",
                "comments":[]}
        (initial/"backlog"/"tasks"/"task-1.json").write_text(json.dumps(task,indent=2)+'\n')
        git("add", ".", cwd=initial)
        git("commit", "-m", "init", cwd=initial)
        git("remote", "add", "origin", str(self.remote), cwd=initial)
        git("push", "origin", "main", cwd=initial)

    def cli_call(self, action, **opts):
        argv = [sys.executable, str(CLIENT), action, "--remote", str(self.remote),
                "--ref", "main", "--backlog", str(self.cli),
                "--at", "2026-11-22T11:00:00Z"]
        for k,v in opts.items():
            key = "--" + k.replace("_", "-")
            if v is True:
                argv.append(key)
            elif isinstance(v,list):
                for e in v: argv.extend([key,str(e)])
            elif v is not False and v is not None:
                argv.extend([key,str(v)])
        return subprocess.run(argv, capture_output=True, text=True, timeout=30)

    def test_claim_then_yield_checkpoint_and_release(self):
        first = self.cli_call("claim", task="TASK-1", actor="agent-a", harness="codex",
                claim_id="c-1", event_id="e-1", lease_until="2026-11-22T11:30:00Z",
                resource=["repo://project/src"])
        self.assertEqual(first.returncode,0,first.stderr+first.stdout)
        second = self.cli_call("yield-request", task="TASK-1", actor="supervisor-b", event_id="e-2",
                               reason="quota_exhausted", generation=1)
        self.assertEqual(second.returncode,0,second.stderr+second.stdout)
        checkpoint = self.cli_call("checkpoint", task="TASK-1", actor="agent-a", claim_id="c-1",
                                   event_id="e-3", evidence_ref="git:checkpoint", generation=1)
        self.assertEqual(checkpoint.returncode,0,checkpoint.stderr+checkpoint.stdout)
        done = self.cli_call("release", task="TASK-1", actor="agent-a", claim_id="c-1", event_id="e-4",
                             evidence_ref="verified-stopped", resources_clear=True, generation=1)
        self.assertEqual(done.returncode,0,done.stderr+done.stdout)
        other = self.cli_call("claim", task="TASK-1", actor="agent-b", harness="claude", claim_id="c-2",
                event_id="e-5", lease_until="2026-11-22T11:30:00Z", resource=["repo://project/src"], generation=1)
        self.assertEqual(other.returncode,0,other.stderr+other.stdout)
        self.assertEqual(json.loads(other.stdout)["generation"],2)

    def test_retry_same_event_id_is_idempotent(self):
        arguments=dict(task="TASK-1", actor="agent-a", harness="codex", claim_id="c-1",
                       event_id="evt-1", lease_until="2026-11-22T11:30:00Z",
                       resource=["repo://project/src"])
        first=self.cli_call("claim", **arguments)
        second=self.cli_call("claim", **arguments)
        self.assertEqual(first.returncode,0,first.stderr)
        self.assertEqual(second.returncode,0,second.stderr)
        self.assertEqual(json.loads(second.stdout)["result"],"ALREADY_CONFIRMED")

    def test_explicit_status_restores_ready_after_release(self):
        first = self.cli_call("claim", task="TASK-1", actor="agent-a", harness="codex", claim_id="c-1",
                        event_id="evt-1", lease_until="2026-11-22T11:30:00Z",
                        working_status="In Progress", resource=["repo://project/src"])
        self.assertEqual(first.returncode,0,first.stderr)
        release = self.cli_call("release", task="TASK-1", actor="agent-a", claim_id="c-1",
                          event_id="evt-2", evidence_ref="stop-verified", resources_clear=True,
                          generation=1, ready_status="To Do")
        self.assertEqual(release.returncode,0,release.stderr)
        second = self.cli_call("claim", task="TASK-1", actor="agent-b", harness="claude", claim_id="c-2",
                        event_id="evt-3", lease_until="2026-11-22T11:30:00Z",
                        resource=["repo://project/src"])
        self.assertEqual(second.returncode,0,second.stderr)

    def test_parallel_claim_race_only_one_wins(self):
        def worker(idx):
            return self.cli_call("claim", task="TASK-1", actor=f"agent-{idx}", harness="codex",
                      claim_id=f"c-{idx}", event_id=f"e-{idx}",
                      lease_until="2026-11-22T11:30:00Z", resource=["repo://project/src"])
        with ThreadPoolExecutor(max_workers=2) as pool:
            x, y = list(pool.map(worker, [1,2]))
        successes = [v for v in [x,y] if v.returncode==0]
        self.assertEqual(len(successes),1,[(v.returncode,v.stderr,v.stdout) for v in [x,y]])
        failed = next(v for v in [x,y] if v.returncode)
        self.assertIn(failed.returncode, [2,3])

    def test_writer_verify_fails_after_yield_request(self):
        first=self.cli_call("claim",task="TASK-1",actor="agent-a",harness="codex",claim_id="c-1",
                   event_id="evt-1",lease_until="2026-11-22T11:30:00Z",resource=["repo://project/src"])
        self.assertEqual(first.returncode,0,first.stderr)
        good=self.cli_call("verify",task="TASK-1",actor="agent-a",claim_id="c-1",generation=1)
        self.assertEqual(good.returncode,0,good.stderr)
        req=self.cli_call("yield-request",task="TASK-1",actor="supervisor",event_id="evt-2",
                          generation=1,reason="quota_exhausted")
        self.assertEqual(req.returncode,0,req.stderr)
        blocked=self.cli_call("verify",task="TASK-1",actor="agent-a",claim_id="c-1",generation=1)
        self.assertNotEqual(blocked.returncode,0)

    def test_cross_task_shared_resource_is_globally_exclusive(self):
        # Two separate task records contend for one effect scope in the same
        # authority branch; git CAS serializes the entire decision.
        base=self.root/"initial"/"backlog"/"tasks"
        second=json.loads((base/"task-1.json").read_text())
        second.update(id="TASK-2",title="Other work",path="backlog/tasks/task-2.json")
        (base/"task-2.json").write_text(json.dumps(second,indent=2)+'\n')
        git("add", ".", cwd=self.root/"initial")
        git("commit", "-m", "second", cwd=self.root/"initial")
        git("push", "origin", "main", cwd=self.root/"initial")
        def worker(task_id):
            return self.cli_call("claim", task=task_id, actor="agent-"+task_id,
                    harness="codex", claim_id="c-"+task_id,
                    event_id="evt-"+task_id, lease_until="2026-11-22T11:30:00Z",
                    resource=["repo://project/shared"])
        with ThreadPoolExecutor(max_workers=2) as pool:
            x,y=list(pool.map(worker,["TASK-1","TASK-2"]))
        self.assertEqual(sum(z.returncode==0 for z in [x,y]),1,[(z.returncode,z.stderr,z.stdout) for z in [x,y]])
        loser="TASK-1" if x.returncode else "TASK-2"
        rerun=worker(loser)
        self.assertEqual(rerun.returncode,2,rerun.stdout+rerun.stderr)
        self.assertIn("Resource scopes conflict",rerun.stderr)

    def test_quarantine_requires_expired_lease(self):
        one=self.cli_call("claim", task="TASK-1", actor="agent-a", harness="codex",
                    claim_id="c-1", event_id="e-1", lease_until="2026-11-22T11:30:00Z",
                    resource=["repo://project/src"])
        self.assertEqual(one.returncode,0,one.stderr)
        too_early = self.cli_call("quarantine", task="TASK-1", actor="supervisor", event_id="e-2",
                                  reason="unresponsive", evidence_ref="observed", grace_minutes=0)
        self.assertNotEqual(too_early.returncode,0)


if __name__ == '__main__': unittest.main()
