#!/usr/bin/env python3
"""Bounded projection of host-observed events; no polling, timers or agent execution."""
from __future__ import annotations
import hashlib
import json
import sys

MAX_BYTES = 65536
IDENTITY = ("runId", "attemptId", "taskId", "handle")
PRIORITY = ("scope-drift", "result", "relay-deadline", "budget-exhausted", "relay-checkpoint", "question", "relay-assess",
            "context-pressure", "resource-drift", "silence", "repeated-failure", "stalled", "pending")
KINDS = {"progress", "error", "new-hypothesis", "routine", "operation-running",
         "active-without-progress", "question", "scope-drift", "context-pressure",
         "budget-exhausted", "result", "terminal", "pending", "silence", "resource-drift", "relay-assess", "relay-checkpoint", "relay-deadline"}
SIMPLE = {"question", "scope-drift", "context-pressure", "budget-exhausted", "result", "pending", "silence", "resource-drift", "relay-assess", "relay-checkpoint", "relay-deadline"}

def fields(v, expected):
    if not isinstance(v, dict) or set(v) != set(expected):
        raise ValueError("unexpected or missing fields")

def string(v, label, limit=512):
    if not isinstance(v, str) or not v.strip() or len(v.encode()) > limit or any(ord(c) < 32 for c in v):
        raise ValueError("invalid " + label)
    return v

def number(v, label, maximum=2**53-1):
    if type(v) is not int or not 0 <= v <= maximum:
        raise ValueError("invalid " + label)
    return v

def identity(v):
    fields(v, IDENTITY)
    return {k: string(v[k], k) for k in IDENTITY}

def digest(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()

def initial(i):
    return {"schemaVersion": 1, "kind": "supervision-projection", "identity": i,
            "cursor": 0, "lastDigest": None, "lastProgressRef": None,
            "failureFingerprint": None, "failureCount": 0, "pending": {}}

def validate_projection(s, i):
    fields(s, ("schemaVersion", "kind", "identity", "cursor", "lastDigest",
               "lastProgressRef", "failureFingerprint", "failureCount", "pending"))
    if type(s["schemaVersion"]) is not int or s["schemaVersion"] != 1 or s["kind"] != "supervision-projection" or identity(s["identity"]) != i:
        raise ValueError("projection identity mismatch")
    number(s["cursor"], "cursor")
    for k in ("lastDigest", "lastProgressRef", "failureFingerprint"):
        if s[k] is not None:
            string(s[k], k)
    number(s["failureCount"], "failureCount", 2)
    if not isinstance(s["pending"], dict) or set(s["pending"]) - set(PRIORITY):
        raise ValueError("invalid pending signals")
    for a in s["pending"].values():
        fields(a, ("seq", "ref", "lastSeq", "lastRef"))
        if not 1 <= number(a["seq"], "alert sequence") <= s["cursor"]:
            raise ValueError("invalid alert sequence")
        string(a["ref"], "alert reference")
        string(a["lastRef"], "latest alert reference")
        if not a["seq"] <= number(a["lastSeq"], "latest alert sequence") <= s["cursor"]:
            raise ValueError("invalid latest alert sequence")

def project(request):
    fields(request, ("schemaVersion", "kind", "identity", "previous", "events", "acknowledged"))
    if type(request["schemaVersion"]) is not int or request["schemaVersion"] != 1 or request["kind"] != "supervision-input":
        raise ValueError("invalid input")
    i = identity(request["identity"])
    previous = request["previous"]
    if previous is None:
        s = initial(i)
    else:
        validate_projection(previous, i)
        # Copy the bounded projection, not a transcript.
        s = previous | {"pending": dict(previous["pending"])}
    acks = request["acknowledged"]
    if not isinstance(acks, list) or len(acks) > len(PRIORITY):
        raise ValueError("invalid acknowledgements")
    seen = set()
    for a in acks:
        fields(a, ("signal", "seq"))
        k = string(a["signal"], "signal")
        if k in seen or k not in s["pending"] or number(a["seq"], "ack sequence") != s["pending"][k]["lastSeq"]:
            raise ValueError("stale or unknown acknowledgement")
        seen.add(k)
        del s["pending"][k]
    es = request["events"]
    if not isinstance(es, list) or len(es) > 64:
        raise ValueError("invalid event batch")
    initial_cursor = s["cursor"]
    newly_seen = set()
    def alert(k, e):
        # Coalesce repeated events until an explicit acknowledgement.
        if k not in s["pending"]:
            s["pending"][k] = {"seq": e["seq"], "ref": e["ref"], "lastSeq": e["seq"], "lastRef": e["ref"]}
            newly_seen.add(k)
        else:
            s["pending"][k] = s["pending"][k] | {"lastSeq": e["seq"], "lastRef": e["ref"]}
    for e in es:
        if not isinstance(e, dict):
            raise ValueError("invalid event")
        kind = string(e.get("kind"), "event kind")
        if kind not in KINDS:
            raise ValueError("unknown event kind")
        extra = {"fingerprint"} if kind == "error" else {"activeSeconds", "operation"} if kind == "active-without-progress" else set()
        fields(e, {"seq", "kind", "identity", "ref"} | extra)
        if identity(e["identity"]) != i:
            raise ValueError("event from another attempt or handle")
        seq = number(e["seq"], "event sequence")
        string(e["ref"], "event reference")
        h = digest(e)
        if seq == s["cursor"] and seq > 0 and h == s["lastDigest"]:
            continue  # exact retry of the latest event only
        if seq != s["cursor"] + 1:
            raise ValueError("gap, stale event or conflicting replay: reconcile source")
        s["cursor"], s["lastDigest"] = seq, h
        if kind in ("progress", "new-hypothesis"):
            s["failureCount"], s["failureFingerprint"] = 0, None
            if kind == "progress":
                s["lastProgressRef"] = e["ref"]
        elif kind == "error":
            f = string(e["fingerprint"], "error fingerprint")
            s["failureCount"] = min(2, s["failureCount"] + 1) if f == s["failureFingerprint"] else 1
            s["failureFingerprint"] = f
            if s["failureCount"] >= 2:
                alert("repeated-failure", e)
        elif kind == "active-without-progress":
            seconds = number(e["activeSeconds"], "observed active seconds")
            if e["operation"] not in ("healthy", "waiting", "none", "unknown"):
                raise ValueError("invalid operation status")
            if seconds >= 1200 and e["operation"] == "none":
                alert("stalled", e)
        elif kind in SIMPLE:
            alert(kind, e)
        elif kind == "terminal":
            # A terminal observation prompts reconciliation, not ownership release.
            alert("result", e)
    signal = next((k for k in PRIORITY if k in s["pending"]), "normal")
    return {"kind": "supervision-observation", "schemaVersion": 1, "projection": s,
            "signal": signal, "newAlerts": [k for k in PRIORITY if k in newly_seen],
            "processed": s["cursor"] - initial_cursor, "wakeRecommended": bool(newly_seen or (acks and s["pending"])),
            "authorized": False, "runtimeVerified": False}

def main():
    try:
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("input too large")
        print(json.dumps(project(json.loads(raw)), sort_keys=True))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
