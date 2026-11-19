#!/usr/bin/env python3
"""Validate compact delegation envelopes and attributed results, not runtime evidence."""
from __future__ import annotations
import json
import hashlib
from datetime import datetime
import re
import sys
from pathlib import Path
from pathlib import PurePosixPath

MAX_INPUT = 262144
HEX_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
IDENTITY = ("project", "runId", "attemptId", "taskId")
OUTCOMES = {"READY_FOR_REVIEW", "PARTIAL", "BLOCKED", "FAILED", "PENDING"}
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

def header(v, kind, required, optional=(), version=1):
    obj(v, ("schemaVersion", "kind", *IDENTITY, *required), optional)
    if type(v["schemaVersion"]) is not int or v["schemaVersion"] != version or v["kind"] != kind:
        raise ValueError("unsupported schema")
    for k in IDENTITY:
        text(v[k], k, 256)

def envelope(v):
    version = v.get("schemaVersion") if isinstance(v, dict) else None
    if type(version) is not int or version not in (1, 2):
        raise ValueError("unsupported envelope version")
    extra = ("briefRevision", "taskDigest", "readinessRef", "effectivePolicies", "verifiedFacts",
             "liveResources", "verificationPlan", "executionPolicy", "criterionOwners", "nonGoals",
             "contingencies", "openQuestions") if version == 2 else ()
    header(v, "delegation-envelope", ("objective", "criteria", "repositories", "policyRefs",
           "authorityHandoffRef", "knowledgePackRef", "reviewProfile", "contextBudgetBytes", "resultBudgetBytes", *extra), version=version)
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
    if version == 2:
        extended(v, ids, names)
    return ids, {r["id"]: r for r in repos}

def digest(v):
    return hashlib.sha256(json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def hash256(v):
    if not isinstance(v, str) or not re.fullmatch(r"[a-f0-9]{64}", v):
        raise ValueError("SHA-256 required")

def positive(v, limit=10000):
    if type(v) is not int or not 1 <= v <= limit:
        raise ValueError("invalid positive number")

def timestamp(v):
    text(v, "observation time", 40)
    t = datetime.fromisoformat(v.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("timezone required")

def resource_inventory(v):
    obj(v, ("status", "observedAt", "evidenceRef", "resources"))
    if v["status"] != "reconciled":
        raise ValueError("resource inventory must be reconciled")
    timestamp(v["observedAt"])
    text(v["evidenceRef"], "inventory evidence")
    keys, ids = set(), set()
    for r in items(v["resources"], "resources", 24):
        obj(r, ("id", "kind", "operationKey", "originAttempt", "state", "identityRef", "evidenceRef",
                "verifiedAt", "effects", "adoption", "resultRef"))
        for k in ("id", "kind", "operationKey", "originAttempt", "identityRef", "evidenceRef", "resultRef"):
            text(r[k], k)
        if r["id"] in ids or r["operationKey"] in keys:
            raise ValueError("duplicate resource or operation")
        ids.add(r["id"]); keys.add(r["operationKey"])
        timestamp(r["verifiedAt"])
        if r["state"] not in ("running", "completed", "failed") or r["adoption"] not in ("observe-only", "manage-existing"):
            raise ValueError("unknown resource state or adoption")
        if not refs(r["effects"], "resource effects"):
            raise ValueError("declare resource effects")
    return keys

def extended(v, ids, repos):
    positive(v["briefRevision"])
    if not isinstance(v["taskDigest"], str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", v["taskDigest"]):
        raise ValueError("task content pin required")
    text(v["readinessRef"], "readiness source")
    policies = items(v["effectivePolicies"], "policies", 32)
    if not policies:
        raise ValueError("effective policy statements required")
    seen=set()
    for p in policies:
        obj(p, ("id", "rule", "sourceRef", "sourceDigest"))
        ident=text(p["id"], "policy id")
        if ident in seen or p["sourceRef"] not in v["policyRefs"]:
            raise ValueError("duplicate or unpinned policy")
        seen.add(ident)
        text(p["rule"], "effective rule", 4096)
        hash256(p["sourceDigest"])
    seen=set()
    for f in items(v["verifiedFacts"], "facts", 32):
        obj(f, ("id", "claim", "scope", "sourcePins", "evidenceRef", "kind"))
        fid=text(f["id"], "fact id")
        if fid in seen or f["kind"] != "static":
            raise ValueError("only distinct static reuse candidates")
        seen.add(fid)
        for k in ("claim","scope","evidenceRef"): text(f[k], k, 2048)
        pins=set()
        for p in items(f["sourcePins"], "pins", 16):
            obj(p, ("ref","digest")); ref=text(p["ref"],"source")
            hash256(p["digest"])
            if ref in pins: raise ValueError("duplicate source pin")
            pins.add(ref)
        if not pins: raise ValueError("fact sources required")
    resource_inventory(v["liveResources"])
    owners=v["criterionOwners"]
    if not isinstance(owners,dict) or set(owners)!=ids or any(x not in ("worker","supervisor") for x in owners.values()):
        raise ValueError("criteria ownership incomplete")
    plan=v["verificationPlan"]
    obj(plan, ("ref", "digest", "workerChecks", "supervisorChecks"))
    text(plan["ref"], "plan reference")
    hash256(plan["digest"])
    covered=set(); checkids=set()
    for stage in ("workerChecks","supervisorChecks"):
        owner="worker" if stage=="workerChecks" else "supervisor"
        for c in items(plan[stage],"checks",32):
            obj(c, ("id","repository","argv","cwd","covers"))
            cid=text(c["id"],"check id")
            if cid in checkids or c["repository"] not in repos: raise ValueError("invalid or duplicate check")
            checkids.add(cid)
            if c["cwd"]!=".": path(c["cwd"])
            argv=items(c["argv"],"command arguments",64)
            if not argv: raise ValueError("missing argv")
            for a in argv: text(a,"argument",4096)
            covered_ids=set(refs(c["covers"],"covered criteria"))
            if not covered_ids or covered_ids-ids: raise ValueError("unassigned criterion")
            covered|={i for i in covered_ids if owners[i]==owner}
    if covered!=ids:
        raise ValueError("criteria without assigned verification")
    policy=v["executionPolicy"]
    obj(policy, ("modelProfile","explorationBudgetMinutes","outputMode","publication","administrativeWork"))
    if policy["modelProfile"] not in ("economy","balanced","deep") or policy["outputMode"]!="compact" or policy["publication"] not in ("forbidden","explicit-authority") or policy["administrativeWork"]!="delegated":
        raise ValueError("invalid execution policy")
    positive(policy["explorationBudgetMinutes"],120)
    refs(v["nonGoals"],"non-goals")
    contingencies=v["contingencies"]
    obj(contingencies,("anchorMissing","newRisk","backgroundWork","ambiguity","stopWhen"))
    if any(contingencies[k]!=x for k,x in {"anchorMissing":"ask-supervisor","newRisk":"request-plan-amendment","backgroundWork":"report-pending","ambiguity":"ask-supervisor"}.items()):
        raise ValueError("invalid contingency")
    text(contingencies["stopWhen"],"stop condition")
    if refs(v["openQuestions"],"material questions"):
        raise ValueError("resolve material questions before implementation")

def receipt(v, e):
    envelope(e)
    if e["schemaVersion"]!=2: raise ValueError("receipt requires v2")
    header(v,"handoff-receipt",("briefRevision","briefDigest","status","firstAction","questions"),version=2)
    match(v,e)
    if v["status"] not in ("UNDERSTOOD","NEEDS_CONTEXT","CONFLICT","BLOCKED"):
        raise ValueError("invalid receipt")
    qs=refs(v["questions"],"questions",10)
    if v["status"]=="UNDERSTOOD":
        text(v["firstAction"],"first action")
        if qs: raise ValueError("understood receipt with questions")
    else:
        if not qs: raise ValueError("specific question required")
        if v["firstAction"] is not None: raise ValueError("no action before resolution")

def amendment(v,e):
    envelope(e)
    if e["schemaVersion"]!=2: raise ValueError("amendment requires v2")
    header(v,"handoff-amendment",("baseRevision","baseDigest","newRevision","reason","changes"),version=2)
    if any(v[k]!=e[k] for k in IDENTITY) or v["baseRevision"]!=e["briefRevision"] or v["baseDigest"]!=digest(e) or type(v["newRevision"]) is not int or v["newRevision"]!=e["briefRevision"]+1:
        raise ValueError("stale or out-of-order amendment")
    text(v["reason"],"amendment reason")
    changes=v["changes"]
    if not isinstance(changes,dict) or not changes or set(changes)-{"verifiedFacts","liveResources","verificationPlan","knowledgePackRef","executionPolicy"}:
        raise ValueError("material authority or scope change requires new authorized brief")
    if "executionPolicy" in changes and changes["executionPolicy"].get("publication")!=e["executionPolicy"]["publication"]:
        raise ValueError("amendment cannot grant publication")
    updated=e|changes|{"briefRevision":v["newRevision"]}
    envelope(updated)
    return updated

def match(v, e):
    if any(v[k] != e[k] for k in IDENTITY):
        raise ValueError("result or checkpoint identity mismatch")
    if e["schemaVersion"] == 2 and (v.get("briefRevision") != e["briefRevision"] or v.get("briefDigest") != digest(e)):
        raise ValueError("brief version or digest mismatch")

def result(v, e):
    ids, repos = envelope(e)
    version=e["schemaVersion"]
    extra=("briefRevision","briefDigest","pendingOperations","contradictedFacts") if version==2 else ()
    header(v, "delegation-result", ("outcome", "criteria", "revisions", "remaining",
           "resourceRefs", "learningRefs", "nextAction", *extra), version=version)
    match(v, e)
    if not isinstance(v["outcome"], str) or v["outcome"] not in OUTCOMES:
        raise ValueError("invalid worker outcome")
    if version == 1 and v["outcome"] == "PENDING":
        raise ValueError("PENDING requires v2")
    seen = set()
    for c in items(v["criteria"], "criteria"):
        obj(c, ("id", "status", "evidenceRefs"))
        cid = text(c["id"], "criterion id", 128)
        if cid not in ids or cid in seen or not isinstance(c["status"], str) or c["status"] not in STATES:
            raise ValueError("unknown or duplicate criterion/status")
        evidence = refs(c["evidenceRefs"], "evidence")
        if version==2 and e["criterionOwners"][cid]=="supervisor" and c["status"]=="pass":
            raise ValueError("worker cannot claim supervisor acceptance criterion")
        if c["status"] == "pass" and not evidence:
            raise ValueError("pass without evidence reference")
        if v["outcome"] == "READY_FOR_REVIEW" and c["status"] != "pass" and (version==1 or e["criterionOwners"][cid]=="worker"):
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
    if version==2:
        pending=refs(v["pendingOperations"],"pending operations")
        if (v["outcome"]=="PENDING") != bool(pending) and v["outcome"] in ("PENDING","READY_FOR_REVIEW"):
            raise ValueError("pending operation/result mismatch")
        if v["outcome"]=="PENDING" and not remaining:
            raise ValueError("pending result requires remaining work")
        if set(refs(v["contradictedFacts"],"contradictions"))-{f["id"] for f in e["verifiedFacts"]}:
            raise ValueError("unknown contradicted fact")
        if v["outcome"]=="READY_FOR_REVIEW" and v["contradictedFacts"]:
            raise ValueError("resolve contradicted facts before ready")

def checkpoint(v, e):
    ids, _ = envelope(e)
    version=e["schemaVersion"]
    extra=("briefRevision","briefDigest") if version==2 else ()
    header(v, "delegation-checkpoint", ("completedCriteria", "pendingCriteria",
           "stateRef", "resourceRefs", "nextAction", *extra),version=version)
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
    elif kind == "receipt":
        receipt(v,e)
    elif kind == "amendment":
        return {"status":"STRUCTURE_VALID","envelope":amendment(v,e),"runtimeVerified":False,"authorized":False}
    elif kind != "envelope":
        raise ValueError("unknown contract")
    size = byte_size(e if kind == "envelope" else v)
    budget = e["contextBudgetBytes"] if kind == "envelope" else e["resultBudgetBytes"]
    # Byte budgets are advisory; never truncate acceptance criteria or evidence.
    return {"status": "STRUCTURE_VALID", "kind": kind, "bytes": size,
            "budgetBytes": budget, "overBudget": size > budget,
            "runtimeVerified": False, "authorized": False, "briefDigest": digest(e)}

def read(name):
    with Path(name).open("rb") as f:
        data = f.read(MAX_INPUT + 1)
    if len(data) > MAX_INPUT:
        raise ValueError("input too large")
    return json.loads(data)

def main():
    try:
        if len(sys.argv) not in (3, 4) or (sys.argv[1] == "envelope") != (len(sys.argv) == 3):
            raise ValueError("usage: delegation_contract.py envelope FILE | result/checkpoint/receipt/amendment ENVELOPE FILE")
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
