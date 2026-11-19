#!/usr/bin/env python3
"""Small, non-authorizing management handoff and result."""
from __future__ import annotations
import json
import re
import sys
from delegation_contract import obj, text, items, refs, digest, hash256, positive

OPS={"record-progress","record-evidence","record-accepted-status","reconcile-knowledge","prepare-next-context"}
def validate_brief(b):
    obj(b,("schemaVersion","kind","runId","attemptId","taskId","taskDigest","operations","effectDomains","budgetMinutes","acceptanceRef"))
    if type(b["schemaVersion"]) is not int or b["schemaVersion"]!=1 or b["kind"]!="steward-handoff": raise ValueError("invalid brief")
    for k in ("runId","attemptId","taskId"): text(b[k],k)
    if not isinstance(b["taskDigest"],str) or not re.fullmatch(r"sha256:[0-9a-f]{64}",b["taskDigest"]): raise ValueError("task pin required")
    positive(b["budgetMinutes"],5)
    ds=refs(b["effectDomains"],"effect domains",8)
    if not ds or "*" in ds: raise ValueError("explicit domains required")
    if b["acceptanceRef"] is not None: text(b["acceptanceRef"],"acceptance evidence")
    seen=set()
    for o in items(b["operations"],"operations",8):
        obj(o,("id","operation","sourceRef"))
        oid=text(o["id"],"operation id")
        if oid in seen or o["operation"] not in OPS: raise ValueError("invalid operation")
        seen.add(oid);text(o["sourceRef"],"source reference")
        if o["operation"]=="record-accepted-status" and not b["acceptanceRef"]: raise ValueError("cannot record closure without acceptance")
    if not seen: raise ValueError("empty operations")
    return seen
def validate(b,r=None):
    ids=validate_brief(b)
    if r is not None:
        obj(r,("schemaVersion","kind","runId","attemptId","taskId","briefDigest","operations"))
        if r["schemaVersion"]!=1 or r["kind"]!="steward-result" or r["briefDigest"]!=digest(b) or any(r[k]!=b[k] for k in ("runId","attemptId","taskId")): raise ValueError("result mismatch")
        seen=set()
        for o in items(r["operations"],"operations",8):
            obj(o,("id","status","evidenceRefs"))
            oid=text(o["id"],"id")
            if oid not in ids or oid in seen or o["status"] not in ("completed","pending","conflict","not-run"): raise ValueError("invalid result")
            seen.add(oid)
            if not refs(o["evidenceRefs"],"evidence") and o["status"]=="completed": raise ValueError("completed requires evidence")
        if seen!=ids: raise ValueError("unaccounted operation")
    return {"status":"STRUCTURE_VALID","briefDigest":digest(b),"authorized":False,"runtimeVerified":False}
def main():
    try:
        raw=sys.stdin.buffer.read(65537)
        if len(raw)>65536: raise ValueError("input too large")
        v=json.loads(raw)
        print(json.dumps(validate(v["brief"],v.get("result")),sort_keys=True))
        return 0
    except (ValueError,TypeError,KeyError,OSError) as e:
        print(str(e),file=sys.stderr);return 2
if __name__=="__main__": raise SystemExit(main())
