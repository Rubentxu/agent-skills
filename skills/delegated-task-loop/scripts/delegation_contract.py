#!/usr/bin/env python3
"""Validate compact delegation envelopes and attributed results, not runtime evidence."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from pathlib import PurePosixPath

MAX_INPUT = 262144
HEX_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
IDENTITY = ("project", "runId", "attemptId", "taskId")
OUTCOMES = {"READY_FOR_REVIEW", "PARTIAL", "BLOCKED", "FAILED"}
STATES = {"pass", "fail", "not-run", "unknown"}

def obj(v, required, optional=()):
    if not isinstance(v, dict) or set(required) - set(v) or set(v) - set(required) - set(optional):
        raise ValueError("unexpected or missing fields")

def text(v, label, limit=1024):
    if not isinstance(v, str) or not v.strip() or len(v.encode("utf-8")) > limit or "\x00" in v:
        raise ValueError("invalid " + label)
    return v

def sha(v):
    if not isinstance(v, str) or not HEX_SHA.fullmatch(v):
        raise ValueError("full Git revision required")

def items(v, label, limit=64):
    if not isinstance(v, list) or len(v) > limit:
        raise ValueError("invalid " + label)
    return v

def refs(v, label, limit=32):
    result = [text(x, label, 1024) for x in items(v, label, limit)]
    if len(result) != len(set(result)):
        raise ValueError("duplicate " + label)
    return result

def path(v):
    text(v, "path", 512)
    p = PurePosixPath(v)
    if p.is_absolute() or ".." in p.parts or p.as_posix() != v or v in ("", ".") or "\\" in v:
        raise ValueError("invalid relative path")

def header(v, kind, required, optional=()):
    obj(v, ("schemaVersion", "kind", *IDENTITY, *required), optional)
    if type(v["schemaVersion"]) is not int or v["schemaVersion"] != 1 or v["kind"] != kind:
        raise ValueError("unsupported schema")
    for k in IDENTITY:
        text(v[k], k, 256)

def envelope(v):
    header(v, "delegation-envelope", ("objective", "criteria", "repositories", "policyRefs",
           "authorityHandoffRef", "knowledgePackRef", "reviewProfile", "contextBudgetBytes", "resultBudgetBytes"))
    text(v["objective"], "objective", 4096)
    cs = items(v["criteria"], "criteria")
    if not cs:
        raise ValueError("effective criteria required")
    ids = set()
    for c in cs:
        obj(c, ("id", "text", "kind"))
        cid = text(c["id"], "criterion id", 128)
        text(c["text"], "criterion text", 4096)
        if c["kind"] not in ("AC", "DoD") or cid in ids:
            raise ValueError("invalid or duplicate criterion")
        ids.add(cid)
    repos = items(v["repositories"], "repositories", 16)
    if not repos:
        raise ValueError("repository revision required")
    names = set()
    for r in repos:
        obj(r, ("id", "baseSha", "paths"))
        name = text(r["id"], "repository id", 256)
        sha(r["baseSha"])
        paths = refs(r["paths"], "allowed paths")
        for p in paths:
            path(p)
        if name in names:
            raise ValueError("duplicate repository")
        names.add(name)
    if not refs(v["policyRefs"], "policy references"):
        raise ValueError("policy references required")
    text(v["authorityHandoffRef"], "authority handoff")
    if v["knowledgePackRef"] is not None:
        text(v["knowledgePackRef"], "knowledge pack")
    if v["reviewProfile"] not in ("none", "lite", "focused", "deep"):
        raise ValueError("invalid review profile")
    for k in ("contextBudgetBytes", "resultBudgetBytes"):
        if type(v[k]) is not int or not 256 <= v[k] <= MAX_INPUT:
            raise ValueError("invalid budget " + k)
    return ids, {r["id"]: r for r in repos}

def match(v, e):
    if any(v[k] != e[k] for k in IDENTITY):
        raise ValueError("result or checkpoint identity mismatch")

def result(v, e):
    ids, repos = envelope(e)
    header(v, "delegation-result", ("outcome", "criteria", "revisions", "remaining",
           "resourceRefs", "learningRefs", "nextAction"))
    match(v, e)
    if not isinstance(v["outcome"], str) or v["outcome"] not in OUTCOMES:
        raise ValueError("invalid worker outcome")
    seen = set()
    for c in items(v["criteria"], "criteria"):
        obj(c, ("id", "status", "evidenceRefs"))
        cid = text(c["id"], "criterion id", 128)
        if cid not in ids or cid in seen or not isinstance(c["status"], str) or c["status"] not in STATES:
            raise ValueError("unknown or duplicate criterion/status")
        evidence = refs(c["evidenceRefs"], "evidence")
        if c["status"] == "pass" and not evidence:
            raise ValueError("pass without evidence reference")
        if v["outcome"] == "READY_FOR_REVIEW" and c["status"] != "pass":
            raise ValueError("ready result has unsatisfied criterion")
        seen.add(cid)
    if seen != ids:
        raise ValueError("all criteria must be accounted for, including not-run")
    seen_repos = set()
    for r in items(v["revisions"], "revisions", 16):
        obj(r, ("id", "baseSha", "headSha"))
        rid = text(r["id"], "repository id", 256)
        if rid not in repos or rid in seen_repos or r["baseSha"] != repos[rid]["baseSha"]:
            raise ValueError("unassigned repository or base mismatch")
        sha(r["headSha"])
        seen_repos.add(rid)
    if seen_repos != set(repos):
        raise ValueError("all assigned revisions must be reported")
    remaining = refs(v["remaining"], "remaining references")
    if v["outcome"] == "READY_FOR_REVIEW" and remaining:
        raise ValueError("ready result has pending work")
    refs(v["resourceRefs"], "resource references")
    refs(v["learningRefs"], "learning references")
    text(v["nextAction"], "next action", 512)

def checkpoint(v, e):
    ids, _ = envelope(e)
    header(v, "delegation-checkpoint", ("completedCriteria", "pendingCriteria",
           "stateRef", "resourceRefs", "nextAction"))
    match(v, e)
    done = set(refs(v["completedCriteria"], "completed criteria"))
    pending = set(refs(v["pendingCriteria"], "pending criteria"))
    if done & pending or done | pending != ids:
        raise ValueError("checkpoint criteria partition mismatch")
    text(v["stateRef"], "checkpoint source")
    refs(v["resourceRefs"], "resources")
    text(v["nextAction"], "next action", 512)

def byte_size(v):
    return len(json.dumps(v, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

def validate(kind, e, v=None):
    envelope(e)
    if kind == "result":
        result(v, e)
    elif kind == "checkpoint":
        checkpoint(v, e)
    elif kind != "envelope":
        raise ValueError("unknown contract")
    size = byte_size(e if kind == "envelope" else v)
    budget = e["contextBudgetBytes"] if kind == "envelope" else e["resultBudgetBytes"]
    # Byte budgets are advisory; never truncate acceptance criteria or evidence.
    return {"status": "STRUCTURE_VALID", "kind": kind, "bytes": size,
            "budgetBytes": budget, "overBudget": size > budget,
            "runtimeVerified": False, "authorized": False}

def read(name):
    with Path(name).open("rb") as f:
        data = f.read(MAX_INPUT + 1)
    if len(data) > MAX_INPUT:
        raise ValueError("input too large")
    return json.loads(data)

def main():
    try:
        if len(sys.argv) not in (3, 4) or (sys.argv[1] == "envelope") != (len(sys.argv) == 3):
            raise ValueError("usage: delegation_contract.py envelope FILE | result/checkpoint ENVELOPE FILE")
        k = sys.argv[1]
        e = read(sys.argv[2])
        v = read(sys.argv[3]) if len(sys.argv) == 4 else None
        print(json.dumps(validate(k, e, v), sort_keys=True))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
