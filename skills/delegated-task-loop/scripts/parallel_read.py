#!/usr/bin/env python3
"""Suggest small read-only native fan-outs from observed, ordered work candidates."""
from __future__ import annotations
import json
import re
import sys

MAX_BYTES = 65536
CAPABILITIES = ("fresh", "background", "notify", "explorationReadOnly")
SHA = re.compile(r"[0-9a-f]{64}\Z")

def fields(v, keys):
    if not isinstance(v, dict) or set(v) != set(keys):
        raise ValueError("unexpected or missing fields")

def string(v, label, n=512):
    if not isinstance(v, str) or not v.strip() or len(v.encode()) > n or any(ord(c) < 32 for c in v):
        raise ValueError("invalid " + label)
    return v

def integer(v, label, lo, hi):
    if type(v) is not int or not lo <= v <= hi:
        raise ValueError("invalid " + label)
    return v

def strings(v, label, limit=32):
    if not isinstance(v, list) or len(v) > limit:
        raise ValueError("invalid " + label)
    result = [string(x, label) for x in v]
    if len(result) != len(set(result)):
        raise ValueError("duplicate " + label)
    return result

def plan(request):
    fields(request, ("schemaVersion", "kind", "runId", "capabilities", "maxAgents", "activeRequests",
                     "remainingContextBytes", "candidates"))
    if type(request["schemaVersion"]) is not int or request["schemaVersion"] != 1 or request["kind"] != "read-only-fanout-input":
        raise ValueError("invalid plan input")
    string(request["runId"], "runId")
    caps = request["capabilities"]
    fields(caps, CAPABILITIES)
    if any(type(v) is not bool for v in caps.values()):
        raise ValueError("invalid capabilities")
    max_agents = integer(request["maxAgents"], "maxAgents", 1, 3)
    active = strings(request["activeRequests"], "active requests", 3)
    remaining = integer(request["remainingContextBytes"], "remaining context bytes", 0, 262144)
    candidates = request["candidates"]
    if not isinstance(candidates, list) or len(candidates) > 16:
        raise ValueError("invalid candidate inventory")
    for c in candidates:
        fields(c, ("id", "taskId", "ready", "readOnly", "unresolvedDependencies", "question",
                   "snapshotRef", "snapshotDigest", "contextBytes"))
        for k in ("id", "taskId", "question"):
            string(c[k], k, 1024 if k == "question" else 512)
        if type(c["ready"]) is not bool or type(c["readOnly"]) is not bool:
            raise ValueError("invalid readiness or effect")
        strings(c["unresolvedDependencies"], "dependencies")
        if c["snapshotRef"] is not None:
            string(c["snapshotRef"], "snapshotRef", 1024)
        if c["snapshotDigest"] is not None and (not isinstance(c["snapshotDigest"], str) or not SHA.fullmatch(c["snapshotDigest"])):
            raise ValueError("invalid snapshot digest")
        integer(c["contextBytes"], "context bytes", 1, 65536)
    ids = [c["id"] for c in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate candidate id")
    selected, deferred, spent = [], [], 0
    questions = set()
    slots = max(0, max_agents - len(active))
    for c in candidates:
        reason = None
        key = (c["taskId"], c["snapshotDigest"], c["question"])
        if not c["readOnly"]:
            reason = "serial-writer-only"
        elif not c["ready"] or c["unresolvedDependencies"]:
            reason = "not-ready"
        elif c["id"] in active:
            reason = "already-active"
        elif not all(caps.values()):
            reason = "native-read-only-capabilities-unconfirmed"
        elif c["snapshotRef"] is None or c["snapshotDigest"] is None:
            reason = "immutable-source-unconfirmed"
        elif key in questions:
            reason = "duplicate-question"
        elif len(selected) >= slots:
            reason = "slot-budget"
        elif spent + c["contextBytes"] > remaining:
            reason = "context-budget"
        if reason:
            deferred.append({"id": c["id"], "reason": reason})
        else:
            selected.append({"id": c["id"], "taskId": c["taskId"],
                             "snapshotRef": c["snapshotRef"], "snapshotDigest": c["snapshotDigest"]})
            questions.add(key)
            spent += c["contextBytes"]
    return {"schemaVersion": 1, "kind": "read-only-fanout-candidates",
            "runId": request["runId"], "selected": selected, "deferred": deferred,
            "projectedContextBytes": spent, "remainingContextBytes": remaining - spent,
            "writerConcurrency": 1, "authorized": False, "runtimeVerified": False}

def main():
    try:
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("input too large")
        print(json.dumps(plan(json.loads(raw)), sort_keys=True))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
