#!/usr/bin/env python3
"""Check observed task anchors and material questions, not semantic readiness or authority."""
from __future__ import annotations
import json
import re
import sys

def text(v,n=1024):
    if not isinstance(v,str) or not v.strip() or len(v.encode())>n:
        raise ValueError("invalid text")
    return v
def fields(v,keys):
    if not isinstance(v,dict) or set(v)!=set(keys):
        raise ValueError("unexpected or missing fields")
def rows(v):
    if not isinstance(v,list) or len(v)>32:
        raise ValueError("invalid inventory")
    return v
def assess(v):
    fields(v,("schemaVersion","kind","taskId","taskDigest","boardReady","objectiveClear","criteriaClear","policyConflicts","materialQuestions","anchors"))
    if type(v["schemaVersion"]) is not int or v["schemaVersion"]!=1 or v["kind"]!="technical-readiness-input":
        raise ValueError("invalid input")
    text(v["taskId"])
    if not isinstance(v["taskDigest"],str) or not re.fullmatch(r"sha256:[0-9a-f]{64}",v["taskDigest"]):
        raise ValueError("task digest required")
    reasons=[]
    for key in ("boardReady","objectiveClear","criteriaClear"):
        if type(v[key]) is not bool:
            raise ValueError("invalid observed flag")
        if not v[key]: reasons.append(key)
    for k in ("policyConflicts","materialQuestions"):
        for t in rows(v[k]): text(t)
        if v[k]: reasons.append(k)
    seen=set()
    for a in rows(v["anchors"]):
        fields(a,("id","expectation","state","evidenceRef"))
        key=text(a["id"])
        if key in seen: raise ValueError("duplicate anchor")
        seen.add(key)
        if a["expectation"] not in ("existing","create") or a["state"] not in ("present","missing","unknown"):
            raise ValueError("invalid anchor state")
        if a["state"]!="unknown": text(a["evidenceRef"])
        elif a["evidenceRef"] is not None: text(a["evidenceRef"])
        if a["expectation"]=="existing" and a["state"]!="present":
            reasons.append("ANCHOR_"+a["state"].upper()+":"+key)
        if a["expectation"]=="create" and a["state"]!="missing":
            reasons.append("CREATE_TARGET_"+a["state"].upper()+":"+key)
    return {"kind":"technical-readiness-assessment","schemaVersion":1,"taskId":v["taskId"],"taskDigest":v["taskDigest"],
            "status":"NEEDS_REFINEMENT" if reasons else "CANDIDATE_READY",
            "reasons":reasons,"runtimeVerified":False,"authorized":False}
def main():
    try:
        raw=sys.stdin.buffer.read(65537)
        if len(raw)>65536: raise ValueError("input too large")
        print(json.dumps(assess(json.loads(raw)),sort_keys=True))
        return 0
    except (ValueError,TypeError,KeyError,OSError) as e:
        print(str(e),file=sys.stderr)
        return 2
if __name__=="__main__": raise SystemExit(main())
