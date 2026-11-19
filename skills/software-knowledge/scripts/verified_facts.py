#!/usr/bin/env python3
"""Project reusable facts against observed source digests; never promote claims to truth."""
from __future__ import annotations
import json
import re
import sys

def fields(v,keys):
    if not isinstance(v,dict) or set(v)!=set(keys): raise ValueError("invalid fields")
def txt(v,n=2048):
    if not isinstance(v,str) or not v.strip() or len(v.encode())>n: raise ValueError("invalid text")
    return v
def sha(v):
    if not isinstance(v,str) or not re.fullmatch(r"[a-f0-9]{64}",v): raise ValueError("invalid digest")
def rows(v):
    if not isinstance(v,list) or len(v)>64: raise ValueError("invalid inventory")
    return v
def assess(v):
    fields(v,("schemaVersion","kind","project","facts","currentSources","contradictedIds"))
    if type(v["schemaVersion"]) is not int or v["schemaVersion"]!=1 or v["kind"]!="fact-reuse-input": raise ValueError("invalid input")
    txt(v["project"])
    sources={}
    for s in rows(v["currentSources"]):
        fields(s,("ref","digest"))
        ref=txt(s["ref"]);sha(s["digest"])
        if ref in sources: raise ValueError("duplicate source")
        sources[ref]=s["digest"]
    contradicted=set(txt(x) for x in rows(v["contradictedIds"]))
    out=[];seen=set()
    for f in rows(v["facts"]):
        fields(f,("id","claim","scope","sourcePins","evidenceRef","kind"))
        fid=txt(f["id"]);txt(f["claim"]);txt(f["scope"]);txt(f["evidenceRef"])
        if fid in seen or f["kind"] not in ("static","runtime","permission","security"): raise ValueError("invalid fact")
        seen.add(fid)
        pins={}
        for p in rows(f["sourcePins"]):
            fields(p,("ref","digest"));ref=txt(p["ref"]);sha(p["digest"])
            if ref in pins: raise ValueError("duplicate pin")
            pins[ref]=p["digest"]
        if not pins: raise ValueError("source pins required")
        if fid in contradicted: state="CONTRADICTED"
        elif f["kind"]!="static": state="RECHECK_ON_USE"
        elif any(sources.get(k)!=x for k,x in pins.items()): state="REVALIDATE"
        else: state="REUSE_CANDIDATE"
        out.append({"id":fid,"state":state,"fact":f} if state=="REUSE_CANDIDATE" else {"id":fid,"state":state})
    if contradicted-seen: raise ValueError("unknown contradiction")
    return {"schemaVersion":1,"kind":"fact-reuse-assessment","project":v["project"],"facts":out,"runtimeVerified":False,"authorized":False}
def experiments(v):
    fields(v,("schemaVersion","kind","project","experiments","currentSources","contradictedIds"))
    if type(v["schemaVersion"]) is not int or v["schemaVersion"]!=1 or v["kind"]!="experiment-reuse-input":raise ValueError("invalid experiment input")
    facts=[];by_id={}
    for x in rows(v["experiments"]):
        fields(x,("id","hypothesis","outcome","scope","evidenceRef","recheckWhen","sourcePins"))
        ident=txt(x["id"])
        if ident in by_id or x["outcome"] not in ("falsified","inconclusive","confirmed"):raise ValueError("invalid experiment")
        txt(x["recheckWhen"])
        by_id[ident]=x
        facts.append({"id":ident,"claim":x["hypothesis"],"scope":x["scope"],"sourcePins":x["sourcePins"],"evidenceRef":x["evidenceRef"],"kind":"static"})
    assessed=assess({"schemaVersion":1,"kind":"fact-reuse-input","project":v["project"],"facts":facts,"currentSources":v["currentSources"],"contradictedIds":v["contradictedIds"]})
    out=[]
    for row in assessed["facts"]:
        ident=row["id"];experiment=by_id[ident];state=row["state"]
        if state=="REUSE_CANDIDATE" and experiment["outcome"]=="inconclusive":state="REVALIDATE"
        out.append({"id":ident,"state":state,"experiment":experiment} if state=="REUSE_CANDIDATE" else {"id":ident,"state":state})
    return {"schemaVersion":1,"kind":"experiment-reuse-assessment","project":v["project"],"experiments":out,"runtimeVerified":False,"authorized":False}
def main():
    try:
        raw=sys.stdin.buffer.read(131073)
        if len(raw)>131072: raise ValueError("input too large")
        v=json.loads(raw)
        print(json.dumps(experiments(v) if isinstance(v,dict) and v.get("kind")=="experiment-reuse-input" else assess(v),ensure_ascii=False,sort_keys=True))
        return 0
    except (ValueError,TypeError,KeyError,OSError) as e:
        print(str(e),file=sys.stderr);return 2
if __name__=="__main__": raise SystemExit(main())
