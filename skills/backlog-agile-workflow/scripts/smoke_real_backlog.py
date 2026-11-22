#!/usr/bin/env python3
"""Opt-in E2E canary for an installed, real Backlog.md CLI and local bare Git.

Creates a disposable Home Repo. Never mutates the caller's repo or uses
credentials/network. CI calls this after installing backlog.md.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

CLIENT = Path(__file__).with_name("multi_agent_cli.py")


def run(argv, cwd=None, okay=False):
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=180)
    if not okay and proc.returncode:
        raise RuntimeError(f"{argv[0]} failed ({proc.returncode}): {proc.stderr[-1800:]}\n{proc.stdout[-1800:]}")
    return proc


def utc(dt):
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def main():
    backlog = shutil.which("backlog")
    if not backlog:
        print("SKIP: Backlog.md CLI is not installed")
        return
    with tempfile.TemporaryDirectory(prefix="backlog-coordination-live-") as temp:
        root = Path(temp)
        remote = root / "authority.git"
        home = root / "home"
        run(["git", "init", "--bare", "--initial-branch=main", str(remote)])
        run(["git", "init", "--initial-branch=main", str(home)])
        run(["git", "config", "user.name", "Coordination Canary"], home)
        run(["git", "config", "user.email", "canary@example.invalid"], home)
        run([backlog, "init", "Multiagent Canary", "--defaults", "--no-git"], home)
        run([backlog, "task", "create", "A safe test task", "--ac", "Show coordination"], home)
        data = json.loads(run([backlog, "task", "list", "--json"], home).stdout)
        assert data["kind"] == "task-list" and len(data["tasks"]) == 1
        tid = data["tasks"][0]["id"]
        run(["git", "add", "."], home)
        run(["git", "commit", "-m", "initialize disposable home backlog"], home)
        run(["git", "remote", "add", "origin", str(remote)], home)
        run(["git", "push", "origin", "main"], home)
        now = datetime.now(timezone.utc)
        at = utc(now)
        lease = utc(now + timedelta(minutes=30))

        def command(action, actor, eid, extra, expect_success=True):
            args = [sys.executable, str(CLIENT), action, "--remote", str(remote),
                    "--ref", "main", "--backlog", backlog, "--at", at,
                    "--actor", actor, "--task", tid, "--event-id", eid] + extra
            result = run(args, okay=True)
            if expect_success and result.returncode:
                raise AssertionError(f"{action} unexpectedly failed: {result.stderr}\n{result.stdout}")
            if not expect_success and not result.returncode:
                raise AssertionError(f"{action} unexpectedly succeeded: {result.stdout}")
            return json.loads(result.stdout or result.stderr)

        first = command("claim", "agent-a", "evt-1", ["--harness", "codex", "--claim-id", "claim-1",
                 "--lease-until", lease, "--resource", "repo://canary/src",
                 "--working-status", "In Progress"])
        assert first["result"] == "CONFIRMED", first
        command("claim", "agent-b", "evt-2", ["--harness", "claude", "--claim-id", "claim-2",
                "--lease-until", lease, "--resource", "repo://canary/src"], False)
        command("verify", "agent-a", "evt-3", ["--claim-id", "claim-1", "--generation", "1"])
        command("yield-request", "supervisor", "evt-4", ["--reason", "quota_exhausted", "--generation", "1"])
        command("verify", "agent-a", "evt-5", ["--claim-id", "claim-1", "--generation", "1"], False)
        command("yield-ack", "agent-a", "evt-6", ["--claim-id", "claim-1", "--generation", "1",
                                                      "--request-id", "evt-4"])
        command("checkpoint", "agent-a", "evt-7", ["--claim-id", "claim-1", "--generation", "1",
                                                     "--evidence-ref", "git:checkpoint"])
        command("release", "agent-a", "evt-8", ["--claim-id", "claim-1", "--generation", "1",
                                                  "--resources-clear", "--evidence-ref", "stop-verified",
                                                  "--ready-status", "To Do"])
        second = command("claim", "agent-b", "evt-9", ["--harness", "claude", "--claim-id", "claim-2",
                 "--lease-until", lease, "--resource", "repo://canary/src"])
        assert second["result"] == "CONFIRMED" and second["generation"] == 2, second
        print(json.dumps({"status": "PASS", "taskId": tid, "generation": 2,
                          "events": 9, "authority": str(remote)}, indent=2))


if __name__ == "__main__":
    main()
