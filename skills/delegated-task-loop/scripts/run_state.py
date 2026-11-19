#!/usr/bin/env python3
"""Private single-writer operational state. Does not launch, authorize or verify agents."""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
import stat
import sys
import tempfile
import uuid
from pathlib import Path
from contextlib import contextmanager

MAX_BYTES = 32768

def string(value, name, limit=512):
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > limit or any(ord(c) < 32 for c in value):
        raise ValueError("invalid " + name)
    return value

def integer(value, name, minimum=0, maximum=10000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid " + name)
    return value

def keys(req, required=(), optional=()):
    if not isinstance(req, dict) or set(required) - set(req) or set(req) - set(required) - set(optional):
        raise ValueError("unexpected or missing request fields")

def private_dir(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("state directory must be private and owned by current user: " + str(path))

def root_for(binding, workspace, state_home=None):
    string(binding, "binding", 1024)
    ws = Path(workspace).resolve(strict=True)
    if not ws.is_dir():
        raise ValueError("workspace must be a directory")
    base = Path(state_home or os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    if not base.is_absolute():
        raise ValueError("state home must be absolute")
    root = base.resolve() / "agent-skills" / "delegated-task-loop"
    if root.resolve().is_relative_to(ws):
        raise ValueError("state may not be stored inside workspace")
    for ancestor in (root, *root.parents):
        if (ancestor / ".git").exists():
            raise ValueError("state may not be stored in a Git checkout")
    # Check each component owned by this skill; never follow a symlink there.
    for p in (root.parent, root):
        if p.is_symlink():
            raise ValueError("symlink in state path")
    root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent_info = root.parent.lstat()
    if not stat.S_ISDIR(parent_info.st_mode) or parent_info.st_uid != os.getuid() or parent_info.st_mode & 0o022:
        raise ValueError("unsafe shared agent-skills directory")
    private_dir(root)
    project = root / hashlib.sha256(binding.encode()).hexdigest()
    if project.is_symlink():
        raise ValueError("symlink in project state")
    private_dir(project)
    return project

@contextmanager
def locked(project):
    fd = os.open(project / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("unsafe lock file")
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)

def load(project):
    path = project / "state.json"
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("unsafe state file")
        raw = f.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("state too large")
    s = json.loads(raw)
    if not isinstance(s, dict) or s.get("schemaVersion") != 1 or s.get("kind") != "delegated-loop-journal":
        raise ValueError("invalid journal; reconcile manually")
    return s

def save(project, s):
    raw = (json.dumps(s, ensure_ascii=False, sort_keys=True) + "\n").encode()
    if len(raw) > MAX_BYTES:
        raise ValueError("state too large")
    fd, name = tempfile.mkstemp(prefix=".state-", dir=project)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, project / "state.json")
        dfd = os.open(project, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def new_attempt(task, number, brief, checkpoint=None):
    return {"taskId": task, "attemptId": str(uuid.uuid4()), "number": number,
            "state": "reserved", "briefRef": brief, "handle": None,
            "checkpointRef": checkpoint, "stopObservationRef": None}

def change(s, op, req, binding):
    if op == "start":
        keys(req, ("maxTasks", "maxAttempts"), ("objectiveRef", "expectedVersion"))
        if s:
            if s["active"] or not s["finished"]:
                raise ValueError("active run exists; reconcile or finish")
            if req.get("expectedVersion") != s["version"] or type(req.get("expectedVersion")) is not int:
                raise ValueError("version conflict")
        elif "expectedVersion" in req:
            raise ValueError("no existing version")
        return {"schemaVersion": 1, "kind": "delegated-loop-journal", "binding": binding,
                "runId": str(uuid.uuid4()), "version": (s["version"] + 1 if s else 1),
                "objectiveRef": string(req["objectiveRef"], "objectiveRef", 1024) if "objectiveRef" in req else None,
                "maxTasks": integer(req["maxTasks"], "maxTasks", 1),
                "maxAttempts": integer(req["maxAttempts"], "maxAttempts", 1, 20),
                "tasksStarted": 0, "active": None, "lastRelease": None,
                "supervisorCheckpointRef": None, "finished": False}
    if not s or s["binding"] != binding or s["finished"]:
        raise ValueError("no active run")
    common = ("runId", "expectedVersion")
    if not isinstance(req, dict) or req.get("runId") != s["runId"] or type(req.get("expectedVersion")) is not int or req["expectedVersion"] != s["version"]:
        raise ValueError("run or version conflict")
    a = s["active"]
    if op == "claim":
        keys(req, (*common, "taskId", "briefRef"))
        if a or s["tasksStarted"] >= s["maxTasks"]:
            raise ValueError("writer reserved or task budget exhausted")
        s["active"] = new_attempt(string(req["taskId"], "taskId", 128), 1,
                                  string(req["briefRef"], "briefRef", 1024))
        s["tasksStarted"] += 1
    elif op == "supervisor-checkpoint":
        keys(req, (*common, "checkpointRef"))
        s["supervisorCheckpointRef"] = string(req["checkpointRef"], "checkpointRef", 1024)
    elif op == "finish":
        keys(req, common)
        if a:
            raise ValueError("cannot finish with active reservation")
        s["finished"] = True
    else:
        common = (*common, "attemptId")
        if not a or req.get("attemptId") != a["attemptId"]:
            raise ValueError("attempt conflict")
        if op == "attach":
            keys(req, (*common, "handle"))
            if a["state"] != "reserved":
                raise ValueError("attempt already attached or stopped")
            a["handle"] = string(req["handle"], "handle")
            a["state"] = "attached"
        elif op == "checkpoint":
            keys(req, (*common, "checkpointRef"))
            a["checkpointRef"] = string(req["checkpointRef"], "checkpointRef", 1024)
        elif op == "observe-stop":
            keys(req, (*common, "observation", "observationRef"))
            if a["state"] == "stopped":
                raise ValueError("stop already recorded")
            if req["observation"] not in ("terminated", "never-launched"):
                raise ValueError("running, timeout and unknown do not prove termination")
            if req["observation"] == "never-launched" and a["state"] != "reserved":
                raise ValueError("attached attempt cannot be never-launched")
            a["state"] = "stopped"
            a["stopObservationRef"] = string(req["observationRef"], "observationRef", 1024)
        elif op == "replace":
            keys(req, (*common, "briefRef"))
            if a["state"] != "stopped" or not a["checkpointRef"]:
                raise ValueError("replacement requires observed stop and checkpoint")
            if a["number"] >= s["maxAttempts"]:
                raise ValueError("attempt budget exhausted")
            s["active"] = new_attempt(a["taskId"], a["number"] + 1,
                                      string(req["briefRef"], "briefRef", 1024), a["checkpointRef"])
        elif op == "release":
            keys(req, (*common, "resultRef"))
            if a["state"] != "stopped":
                raise ValueError("cannot release unconfirmed writer")
            s["lastRelease"] = {"taskId": a["taskId"], "attemptId": a["attemptId"],
                                "resultRef": string(req["resultRef"], "resultRef", 1024),
                                "stopObservationRef": a["stopObservationRef"]}
            s["active"] = None
        else:
            raise ValueError("unknown operation")
    s["version"] += 1
    return s

def execute(project, binding, op, req):
    with locked(project):
        s = load(project)
        if s and s.get("binding") != binding:
            raise ValueError("binding mismatch")
        if op == "read":
            keys(req)
            return s
        updated = change(s, op, req, binding)
        save(project, updated)
        return updated

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("operation", choices=("read", "start", "claim", "attach", "checkpoint",
                        "observe-stop", "replace", "release", "supervisor-checkpoint", "finish"))
    args = parser.parse_args()
    try:
        if args.operation == "read":
            req = {}
        else:
            raw = sys.stdin.buffer.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("request too large")
            req = json.loads(raw)
        project = root_for(args.binding, args.workspace)
        result = execute(project, args.binding, args.operation, req)
        print(json.dumps({"state": result, "runtimeVerified": False, "authorized": False}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
