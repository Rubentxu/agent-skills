#!/usr/bin/env python3
"""Compile observed guarantee coverage into a proportional plan; never execute commands."""
from __future__ import annotations
import hashlib
import json
import re
import sys

MAX = 262144

def obj(v, keys):
    if not isinstance(v, dict) or set(v) != set(keys):
        raise ValueError("unexpected or missing fields")
def txt(v, n=1024):
    if not isinstance(v, str) or not v.strip() or len(v.encode()) > n or any(ord(c)<32 for c in v):
        raise ValueError("invalid string")
    return v
def digest(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
def sha(v):
    if not isinstance(v,str) or not re.fullmatch(r"[0-9a-f]{64}",v):
        raise ValueError("full SHA-256 required")
def rev(v):
    if not isinstance(v,str) or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})",v):
        raise ValueError("full Git revision required")
def rows(v, limit=64):
    if not isinstance(v,list) or len(v)>limit:
        raise ValueError("invalid inventory")
    return v
def names(v):
    a=[txt(x) for x in rows(v)]
    if len(a)!=len(set(a)):
        raise ValueError("duplicate identifier")
    return set(a)
def integer(v, maxv=10**9):
    if type(v) is not int or not 0<=v<=maxv:
        raise ValueError("invalid number")
    return v

def compile_plan(v):
    obj(v, ("schemaVersion","kind","taskId","repository","baseRevision","scope","impactRef","selector",
            "budgetMs","guarantees","candidates"))
    if type(v["schemaVersion"]) is not int or v["schemaVersion"]!=1 or v["kind"]!="verification-plan-input":
        raise ValueError("invalid plan input")
    for k in ("taskId","repository","impactRef"):
        txt(v[k])
    rev(v["baseRevision"])
    if v["scope"] not in ("docs","bounded","global","unknown") or v["selector"] not in ("verified","manual","unverified"):
        raise ValueError("invalid impact or selector")
    budget=integer(v["budgetMs"])
    guarantees={}
    for g in rows(v["guarantees"]):
        obj(g, ("id","statement","stage"))
        gid=txt(g["id"])
        if gid in guarantees or g["stage"] not in ("acceptance","integration"):
            raise ValueError("invalid guarantee")
        txt(g["statement"])
        guarantees[gid]=g
    if not guarantees:
        raise ValueError("guarantees required")
    candidates={}
    commands=set()
    for c in rows(v["candidates"]):
        if not isinstance(c,dict):raise ValueError("invalid candidate")
        global_gate=c.get("globalGate",False)
        c=c.copy();c.pop("globalGate",None)
        obj(c, ("id","argv","cwd","covers","stage","mandatory","independent","costMs","sourceRef"))
        if type(global_gate) is not bool or (global_gate and (c["mandatory"] is not True or c["stage"]=="integration")):
            raise ValueError("global gate must be explicit mandatory acceptance check")
        if global_gate:c["globalGate"]=True
        cid=txt(c["id"])
        if cid in candidates:
            raise ValueError("duplicate test")
        argv=rows(c["argv"])
        if not argv:
            raise ValueError("empty command")
        for a in argv:
            txt(a,4096)
        cwd=txt(c["cwd"])
        if cwd.startswith("/") or "\\" in cwd or ".." in cwd.split("/"):
            raise ValueError("cwd must be relative")
        key=(cwd,tuple(argv),c["stage"])
        if key in commands:
            raise ValueError("duplicate invocation; combine guarantees")
        commands.add(key)
        covers=names(c["covers"])
        if not covers or covers-set(guarantees):
            raise ValueError("unmapped coverage")
        if c["stage"] not in ("worker","supervisor","integration") or type(c["mandatory"]) is not bool or type(c["independent"]) is not bool:
            raise ValueError("invalid stage/flags")
        if c["independent"] and c["stage"]!="supervisor":
            raise ValueError("independent check belongs to supervisor")
        if c["stage"]=="integration" and any(guarantees[x]["stage"]=="acceptance" for x in covers):
            raise ValueError("cannot defer an acceptance guarantee")
        if c["costMs"] is not None:
            integer(c["costMs"])
        txt(c["sourceRef"])
        candidates[cid]=c
    selected=set()
    uncovered=set(guarantees)
    for cid,c in candidates.items():
        if c["mandatory"] or c["independent"]:
            selected.add(cid)
            uncovered-=set(c["covers"])
    while uncovered:
        options=[c for cid,c in candidates.items() if cid not in selected and uncovered.intersection(c["covers"])]
        if not options:
            break
        # Unknown costs are not zero; prefer known cost, otherwise maximize coverage.
        def rank(c):
            gain=len(uncovered.intersection(c["covers"]))
            cost=c["costMs"]
            return (cost is None, -(gain/max(1,cost)) if cost is not None else -gain, c["id"])
        c=min(options,key=rank)
        selected.add(c["id"])
        uncovered-=set(c["covers"])
    ordered=sorted((candidates[x] for x in selected),key=lambda c: (("worker","supervisor","integration").index(c["stage"]),c["costMs"] is None,c["costMs"] or 0,c["id"]))
    blocking=[]
    if v["scope"]=="unknown" or v["selector"]=="unverified" or (v["scope"]=="global" and not any(c.get("globalGate") for c in ordered)):
        blocking.append("RESOLVE_IMPACT_OR_CONFIRM_REQUIRED_GLOBAL_GATE")
    if uncovered:
        blocking.append("UNCOVERED_GUARANTEES")
    costs=[c["costMs"] for c in ordered if c["stage"]!="integration"]
    known=sum(x for x in costs if x is not None)
    return {"schemaVersion":1,"kind":"verification-plan","taskId":v["taskId"],"repository":v["repository"],
            "baseRevision":v["baseRevision"],"inputDigest":digest(v),"scope":v["scope"],
            "status":"NEEDS_REFINEMENT" if blocking else "PLANNED","blocking":blocking,
            "guarantees":list(guarantees.values()),"checks":ordered,
            "excluded":[{"id":c,"reason":"coverage-already-planned"} for c in sorted(set(candidates)-selected)],
            "uncovered":sorted(uncovered),"knownAcceptanceCostMs":known,"unknownCostChecks":sum(x is None for x in costs),
            "overBudget":known>budget,"budgetMs":budget,"authorized":False,"runtimeVerified":False}

def receipts(plan, observations):
    if not isinstance(plan,dict) or plan.get("kind")!="verification-plan" or plan.get("status")!="PLANNED":
        raise ValueError("requires planned verification")
    proofs=observations.get("scopeProofs",[])
    obj(observations, ("schemaVersion","kind","planDigest","treeDigest","environmentDigest","receipts",*(("scopeProofs",) if "scopeProofs" in observations else ())))
    if type(observations["schemaVersion"]) is not int or observations["schemaVersion"]!=1 or observations["kind"]!="verification-observations" or observations["planDigest"]!=digest(plan):
        raise ValueError("plan mismatch")
    sha(observations["treeDigest"]);sha(observations["environmentDigest"])
    checks={c["id"]:c for c in plan["checks"]}
    scoped={}
    for p in rows(proofs):
        obj(p,("id","checkDigest","fromTreeDigest","toTreeDigest","previousDependencyDigest","currentDependencyDigest","complete","proofRef"))
        cid=txt(p["id"])
        if cid not in checks or cid in scoped:raise ValueError("unknown or duplicate scope proof")
        for k in ("checkDigest","fromTreeDigest","toTreeDigest","previousDependencyDigest","currentDependencyDigest"):sha(p[k])
        if type(p["complete"]) is not bool:raise ValueError("invalid proof completeness")
        txt(p["proofRef"])
        c=checks[cid]
        # Scope evidence cannot waive global, mandatory or independent checks after tree change.
        if (plan.get("scope")=="bounded" and p["checkDigest"]==digest(c) and p["toTreeDigest"]==observations["treeDigest"]
            and p["previousDependencyDigest"]==p["currentDependencyDigest"] and p["complete"] and not(c["mandatory"] or c["independent"] or c.get("globalGate"))):
            scoped[cid]=p["fromTreeDigest"]
    seen={}
    for r in rows(observations["receipts"]):
        obj(r,("id","treeDigest","environmentDigest","outcome","runnerRef","executed","failed","skipped","role"))
        cid=txt(r["id"])
        if cid not in checks or cid in seen:
            raise ValueError("unknown or repeated check")
        sha(r["treeDigest"]);sha(r["environmentDigest"])
        txt(r["runnerRef"])
        for k in ("executed","failed","skipped"):
            integer(r[k])
        if r["failed"]>r["executed"] or r["outcome"] not in ("PASS","FAIL","BLOCKED","NOT_RUN") or r["role"] not in ("worker","supervisor","ci"):
            raise ValueError("invalid outcome")
        current=(r["treeDigest"]==observations["treeDigest"] or scoped.get(cid)==r["treeDigest"]) and r["environmentDigest"]==observations["environmentDigest"]
        good=(current and r["outcome"]=="PASS" and r["executed"]>0 and r["failed"]==0 and r["skipped"]==0
              and (not checks[cid]["independent"] or r["role"]=="supervisor"))
        seen[cid]="REUSABLE_CANDIDATE" if good else "RECHECK"
    required=[c["id"] for c in checks.values() if c["stage"]!="integration"]
    return {"kind":"verification-evidence-assessment","schemaVersion":1,
            "status":"EVIDENCE_CANDIDATES" if all(seen.get(k)=="REUSABLE_CANDIDATE" for k in required) else "NEEDS_EVIDENCE",
            "checks":{k:seen.get(k,"NOT_RUN") for k in checks},
            "planDigest":digest(plan),
            "remainingChecks":[c for c in plan["checks"] if seen.get(c["id"])!="REUSABLE_CANDIDATE"],
            "reuseCandidates":[{"id":r["id"],"runnerRef":r["runnerRef"],"scopeProofRequired":r["treeDigest"]!=observations["treeDigest"]} for r in observations["receipts"] if seen.get(r["id"])=="REUSABLE_CANDIDATE"],
            "authorized":False,"runtimeVerified":False}

def main():
    try:
        raw=sys.stdin.buffer.read(MAX+1)
        if len(raw)>MAX: raise ValueError("input too large")
        v=json.loads(raw)
        result=receipts(v["plan"],v["observations"]) if isinstance(v,dict) and set(v)=={"plan","observations"} else compile_plan(v)
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
        return 0
    except (ValueError,TypeError,KeyError,OSError) as e:
        print(str(e),file=sys.stderr)
        return 2
if __name__=="__main__":
    raise SystemExit(main())
