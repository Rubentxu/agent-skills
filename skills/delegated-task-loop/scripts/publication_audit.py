#!/usr/bin/env python3
"""Compare explicit Git observations against permitted effects; no Git/network writes."""
import json
import re
import sys
from supervision import fields,string

def refs(v):
    if not isinstance(v,dict) or len(v)>4096:raise ValueError("invalid ref inventory")
    for k,r in v.items():
        string(k,"ref",1024)
        if not k.startswith("refs/") or not isinstance(r,str) or not re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})",r):
            raise ValueError("invalid ref")
    return v
def audit(v):
    fields(v,("schemaVersion","kind","repositories"))
    if type(v["schemaVersion"]) is not int or v["schemaVersion"]!=1 or v["kind"]!="publication-audit-input" or not isinstance(v["repositories"],list) or not v["repositories"] or len(v["repositories"])>16:
        raise ValueError("invalid inventory")
    findings=[];seen=set();unknown=False
    for r in v["repositories"]:
        fields(r,("id","baseline","after","allowedLocalRefs","allowedRemoteRefs","evidenceRef"))
        rid=string(r["id"],"repo")
        if rid in seen:raise ValueError("duplicate repository")
        seen.add(rid);string(r["evidenceRef"],"observation")
        for k in ("allowedLocalRefs","allowedRemoteRefs"):
            if not isinstance(r[k],list) or len(r[k])>128 or any(not isinstance(x,str) or not x.startswith("refs/") for x in r[k]):
                raise ValueError("explicit allowed refs required")
        for x in (r["baseline"],r["after"]):
            fields(x,("local","remote"))
            refs(x["local"])
            if x["remote"] is not None:refs(x["remote"])
        for scope,allowed in (("local",r["allowedLocalRefs"]),("remote",r["allowedRemoteRefs"])):
            a,b=r["baseline"][scope],r["after"][scope]
            if a is None or b is None:
                unknown=True;continue
            for k in sorted(a.keys()|b.keys()):
                if a.get(k)!=b.get(k) and k not in allowed:
                    findings.append({"repository":rid,"scope":scope,"ref":k,"change":"created" if k not in a else "deleted" if k not in b else "changed","attribution":"UNKNOWN"})
    return {"kind":"publication-audit","schemaVersion":1,"status":"INVESTIGATE" if findings else "UNKNOWN" if unknown else "NO_UNEXPECTED_REF_DIFF_OBSERVED",
            "findings":findings,"completeRemoteObservation":not unknown,"runtimeVerified":False,"authorized":False}
def main():
    try:
        raw=sys.stdin.buffer.read(262145)
        if len(raw)>262144:raise ValueError("input too large")
        print(json.dumps(audit(json.loads(raw)),sort_keys=True));return 0
    except (ValueError,TypeError,KeyError,OSError) as e:
        print(str(e),file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
