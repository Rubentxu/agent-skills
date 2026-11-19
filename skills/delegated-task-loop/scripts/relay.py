#!/usr/bin/env python3
"""Compile a compact baton from validated checkpoint and observed continuity."""
from __future__ import annotations
import json
import sys
from delegation_contract import obj,text,items,refs,digest,sha,hash256,envelope,checkpoint,resource_inventory
from pacing import validate_schedule

REASONS={"time-budget","context-pressure","stalled","new-perspective","verification-only","recovery"}
def compile_baton(e,v):
    ids,repos=envelope(e)
    if e["schemaVersion"]!=2 or "pacing" not in e:raise ValueError("paced v2 envelope required")
    obj(v,("checkpoint","reason","checkpointRef","snapshots","evidence","experiments","resources","stopRef","observedAt","decisionRef"))
    c=v["checkpoint"];checkpoint(c,e)
    if v["reason"] not in REASONS:raise ValueError("unknown relay reason")
    for k in ("checkpointRef","stopRef","decisionRef"):text(v[k],k)
    if type(v["observedAt"]) is not int or v["observedAt"]<e["pacing"]["attemptStartedAt"]:raise ValueError("invalid observation time")
    snapshots={}
    for s in items(v["snapshots"],"snapshots",16):
        obj(s,("repository","baseSha","headSha","treeDigest","recoveryRef"))
        rid=text(s["repository"],"repository")
        if rid not in repos or rid in snapshots or s["baseSha"]!=repos[rid]["baseSha"]:raise ValueError("repository baseline mismatch")
        sha(s["headSha"]);hash256(s["treeDigest"]);text(s["recoveryRef"],"recoverable state")
        snapshots[rid]=s
    if set(snapshots)!=set(repos):raise ValueError("all repository states required")
    evidence={}
    for row in items(v["evidence"],"evidence",64):
        obj(row,("criterionId","evidenceRefs","validationRef"))
        cid=text(row["criterionId"],"criterion")
        if cid not in c["completedCriteria"] or cid in evidence:raise ValueError("unassigned or duplicate completed criterion")
        if not refs(row["evidenceRefs"],"evidence"):raise ValueError("completed claim needs evidence")
        text(row["validationRef"],"supervisor verification")
        evidence[cid]=row
    # Completed checkpoint claims without current evidence become pending again.
    remaining=sorted(ids-set(evidence))
    if not remaining:raise ValueError("verify completed delivery instead of opening successor")
    experiments=[];seen=set()
    for x in items(v["experiments"],"experiments",8):
        obj(x,("id","hypothesis","outcome","scope","evidenceRef","recheckWhen"))
        ident=text(x["id"],"experiment id")
        if ident in seen or x["outcome"] not in ("falsified","inconclusive","confirmed"):raise ValueError("invalid experiment")
        seen.add(ident)
        for k in ("hypothesis","scope","evidenceRef","recheckWhen"):text(x[k],k,512)
        experiments.append(x)
    resource_inventory(v["resources"])
    return {"schemaVersion":1,"kind":"endurance-baton","project":e["project"],"runId":e["runId"],"taskId":e["taskId"],
            "previousAttemptId":e["attemptId"],"previousBriefDigest":digest(e),"taskDigest":e["taskDigest"],
            "reason":v["reason"],"checkpointRef":v["checkpointRef"],"checkpointDigest":digest(c),
            "nextRole":"worker" if any(e["criterionOwners"][cid]=="worker" for cid in remaining) else "supervisor",
            "snapshots":list(snapshots.values()),"completed":list(evidence.values()),"pendingCriteria":remaining,
            "experiments":experiments,"resources":v["resources"],"stopRef":v["stopRef"],"observedAt":v["observedAt"],
            "decisionRef":v["decisionRef"],"nextAction":c["nextAction"],"taskStartedAt":e["pacing"]["taskStartedAt"],
            "taskDeadlineAt":e["pacing"]["taskDeadlineAt"],"authorized":False,"runtimeVerified":False}
def validate_successor(previous,baton,successor,observation,journal):
    expected=compile_baton(previous,observation)
    if baton!=expected:raise ValueError("baton does not match checkpoint/observation")
    if baton["nextRole"]!="worker":raise ValueError("only supervisor work remains; do not launch another implementer")
    envelope(successor)
    if successor["schemaVersion"]!=2 or "continuity" not in successor or "pacing" not in successor:raise ValueError("fresh paced successor required")
    for key in ("project","runId","taskId","taskDigest","objective","criteria","repositories","policyRefs","effectivePolicies","criterionOwners","nonGoals","verificationPlan"):
        if previous[key]!=successor[key]:raise ValueError("changed authority or criteria requires explicit replan: "+key)
    if successor["executionPolicy"]["publication"]!=previous["executionPolicy"]["publication"]:raise ValueError("publication authority changed")
    c=successor["continuity"];p=successor["pacing"];validate_schedule(p)
    if c["previousAttemptId"]!=previous["attemptId"] or c["batonDigest"]!=digest(baton) or successor["attemptId"]==previous["attemptId"]:raise ValueError("successor attribution mismatch")
    if p["taskStartedAt"]!=baton["taskStartedAt"] or p["taskDeadlineAt"]!=baton["taskDeadlineAt"] or p["attemptStartedAt"]<baton["observedAt"]:raise ValueError("task clock reset or stale successor")
    if successor["liveResources"]!=baton["resources"]:raise ValueError("resource adoption inventory changed; recompile baton")
    if not isinstance(journal,dict) or journal.get("kind")!="delegated-loop-journal" or journal.get("runId")!=successor["runId"]:
        raise ValueError("current journal required")
    a=journal.get("active")
    if not isinstance(a,dict) or a.get("state")!="reserved" or a.get("taskId")!=successor["taskId"] or a.get("attemptId")!=successor["attemptId"] or a.get("schedule")!=p or a.get("batonRef")!=c["batonRef"] or a.get("checkpointRef")!=baton["checkpointRef"]:
        raise ValueError("successor does not match reserved attempt")
    history=a.get("attemptHistory",[])
    if not history or history[-1].get("attemptId")!=previous["attemptId"] or history[-1].get("stopObservationRef")!=baton["stopRef"] or history[-1].get("batonRef")!=c["batonRef"]:
        raise ValueError("prior attempt or stop mismatch")
    if a.get("resourceStatus") not in ("clear","live") or not a.get("resourceInventoryRef") or (a.get("resourceStatus")=="live" and not a.get("adoptionRef")):
        raise ValueError("unreconciled operation inventory")
    if any(r["state"]=="running" for r in baton["resources"]["resources"]) != (a["resourceStatus"]=="live"):
        raise ValueError("journal and baton live resource state mismatch")
    # Fresh projection never removes the original obligations. Evidence remains
    # candidate, subject to revalidation after future changes.
    return {"kind":"relay-successor-assessment","schemaVersion":1,"status":"STRUCTURE_VALID","attemptId":successor["attemptId"],
            "briefDigest":digest(successor),"batonDigest":digest(baton),"pendingCriteria":baton["pendingCriteria"],
            "freshRequired":True,"authorized":False,"runtimeVerified":False,
            "journalVersion":journal["version"],
            "freshEyes":{"objective":successor["objective"],"criteria":[c for c in successor["criteria"] if c["id"] in baton["pendingCriteria"]],
                         "snapshots":baton["snapshots"],"pacing":p,"continuityRef":c["batonRef"]}}
def main():
    try:
        raw=sys.stdin.buffer.read(262145)
        if len(raw)>262144:raise ValueError("input too large")
        v=json.loads(raw)
        if set(v)=={"envelope","observation"}:out=compile_baton(v["envelope"],v["observation"])
        elif set(v)=={"envelope","observation","baton","successor","journal"}:out=validate_successor(v["envelope"],v["baton"],v["successor"],v["observation"],v["journal"])
        else:raise ValueError("invalid relay input")
        print(json.dumps(out,ensure_ascii=False,sort_keys=True));return 0
    except (ValueError,TypeError,KeyError,OSError) as e:
        print(str(e),file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
