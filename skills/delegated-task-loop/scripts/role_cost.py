#!/usr/bin/env python3
"""Aggregate observed role/session costs, preserving missingness and concurrent wall time."""
import json
import sys
from evaluate_runs import obj,string,number

ROLES={"supervisor","implementer","steward","goldfish","explorer"}
def aggregate(v):
    obj(v,("schemaVersion","kind","runId","usageBasis","inventoryRef","inventoryComplete","sessions","observations","elapsedMs"))
    if type(v["schemaVersion"]) is not int or v["schemaVersion"]!=1 or v["kind"]!="role-cost-input":
        raise ValueError("invalid input")
    for k in ("runId","usageBasis","inventoryRef"):string(v[k],k)
    if type(v["inventoryComplete"]) is not bool:raise ValueError("inventory flag must be observed")
    if v["elapsedMs"] is not None:number(v["elapsedMs"],"wall elapsed")
    if not isinstance(v["sessions"],list) or not isinstance(v["observations"],list) or len(v["sessions"])>1024 or len(v["observations"])>1024:
        raise ValueError("invalid session inventory")
    sessions={}
    for s in v["sessions"]:
        obj(s,("id","role"))
        sid=string(s["id"],"session")
        if sid in sessions or s["role"] not in ROLES:raise ValueError("duplicate or invalid role")
        sessions[sid]=s["role"]
    seen={}
    for o in v["observations"]:
        obj(o,("id","usageBasis","totalTokens","outputTokens","evidenceRef"))
        sid=string(o["id"],"session")
        if sid not in sessions or sid in seen or o["usageBasis"]!=v["usageBasis"]:raise ValueError("session or usage basis mismatch")
        string(o["evidenceRef"],"usage source")
        for key in ("totalTokens","outputTokens"):
            if o[key] is not None:number(o[key],key)
        if o["totalTokens"] is not None and o["outputTokens"] is not None and o["outputTokens"]>o["totalTokens"]:raise ValueError("invalid token relation")
        seen[sid]=o
    def summarize(ids):
        vals=[seen.get(s,{}) for s in ids]
        def sums(k):
            known=[x[k] for x in vals if x.get(k) is not None]
            return {"observed":sum(known) if known else None,"complete":sum(known) if ids and len(known)==len(ids) else None,"sessionsWithValue":len(known)}
        return {"sessions":len(ids),"totalTokens":sums("totalTokens"),"outputTokens":sums("outputTokens")}
    roles={r:summarize([sid for sid,role in sessions.items() if role==r]) for r in sorted(ROLES) if r in sessions.values()}
    all_cost=summarize(list(sessions))
    total=all_cost["totalTokens"]["complete"] if v["inventoryComplete"] else None
    metrics={}
    if total is not None:metrics["totalTokens"]=total
    if v["elapsedMs"] is not None:metrics["elapsedMs"]=v["elapsedMs"]
    return {"kind":"role-cost-assessment","schemaVersion":1,"runId":v["runId"],"inventoryComplete":v["inventoryComplete"],
            "usageBasis":v["usageBasis"],"roles":roles,"observedAcrossSessions":all_cost,"metrics":metrics,
            "missingSessions":sorted(set(sessions)-set(seen)),"runtimeVerified":False}
def main():
    try:
        raw=sys.stdin.buffer.read(1048577)
        if len(raw)>1048576:raise ValueError("input too large")
        print(json.dumps(aggregate(json.loads(raw)),sort_keys=True));return 0
    except (ValueError,KeyError,TypeError,OSError) as e:
        print(str(e),file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
