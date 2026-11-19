#!/usr/bin/env python3
"""Assemble a role-specific envelope from observed public provider contracts."""
from __future__ import annotations
import json
import sys
from delegation_contract import obj, text, digest, envelope, items, refs

def compile_handoff(v):
    obj(v,("schemaVersion","kind","draft","authorityHandoff","authorityReceipt","readiness",
           "plans","planBundleRef","factAssessment","budgetDecisionRef"))
    if type(v["schemaVersion"]) is not int or v["schemaVersion"]!=1 or v["kind"]!="implementer-handoff-input":
        raise ValueError("invalid compiler input")
    draft=v["draft"]
    if not isinstance(draft,dict) or draft.get("schemaVersion")!=2:
        raise ValueError("v2 draft required")
    if set(draft)&{"verificationPlan","verifiedFacts","taskDigest"}:
        raise ValueError("compiler owns projected fields")
    task=draft.get("taskId")
    authority=v["authorityHandoff"];receipt=v["authorityReceipt"];ready=v["readiness"]
    if (authority.get("kind")!="authority-handoff" or authority.get("schemaVersion")!=1
        or authority.get("taskId")!=task or authority.get("questions")
        or authority.get("editAuthorized") is not False):
        raise ValueError("authority handoff unresolved")
    if (receipt.get("kind")!="handoff-receipt" or receipt.get("schemaVersion")!=1
        or receipt.get("status")!="CONTEXT_MATCHES_RUNTIME_UNVERIFIED"
        or receipt.get("taskContentCompared") is not True or receipt.get("reasons")
        or receipt.get("editAuthorized") is not False
        or receipt.get("taskDigest")!=authority.get("taskDigest")
        or receipt.get("sourceRevision")!=authority.get("sourceRevision")):
        raise ValueError("current authority receipt required")
    pin=authority.get("taskDigest")
    if (not pin or ready.get("kind")!="technical-readiness-assessment"
        or ready.get("schemaVersion")!=1 or ready.get("status")!="CANDIDATE_READY"
        or ready.get("taskId")!=task or ready.get("taskDigest")!=pin or ready.get("reasons")
        or ready.get("authorized") is not False):
        raise ValueError("readiness does not match task")
    repos={r["id"]:r["baseSha"] for r in draft["repositories"]}
    criteria={c["id"] for c in draft["criteria"]}
    worker=[]; supervisor=[]; bundle=[]; seen=set()
    for item in items(v["plans"],"plans",16):
        obj(item,("ref","plan"))
        ref=text(item["ref"],"plan reference")
        p=item["plan"]
        rid=p.get("repository")
        if (p.get("schemaVersion")!=1 or p.get("kind")!="verification-plan"
            or p.get("status")!="PLANNED" or p.get("taskId")!=task
            or rid not in repos or p.get("baseRevision")!=repos[rid]
            or p.get("blocking") or p.get("uncovered")
            or p.get("authorized") is not False):
            raise ValueError("unresolved or mismatched verification plan")
        if p.get("overBudget") or p.get("unknownCostChecks"):
            text(v["budgetDecisionRef"],"explicit budget decision")
        guarantees={g["id"]:g["stage"] for g in p["guarantees"]}
        if any(gid not in criteria for gid,stage in guarantees.items() if stage=="acceptance"):
            raise ValueError("plan contains an unassigned acceptance guarantee")
        key=(rid,ref)
        if key in seen: raise ValueError("duplicate plan")
        seen.add(key)
        bundle.append({"ref":ref,"repository":rid,"digest":digest(p)})
        for c in p["checks"]:
            if c["stage"]=="integration":
                if set(c["covers"])&criteria:raise ValueError("criterion deferred to integration")
                continue
            if c["stage"] not in ("worker","supervisor"):
                raise ValueError("unknown check stage")
            covers=[x for x in c["covers"] if x in criteria]
            # Project only assigned guarantees; original plan retains full inventory.
            if not covers:continue
            row={k:c[k] for k in ("id","argv","cwd")}
            row.update(repository=rid,covers=covers)
            (worker if c["stage"]=="worker" else supervisor).append(row)
    if not bundle:raise ValueError("verification plan required")
    facts=[]
    f=v["factAssessment"]
    if f is not None:
        if f.get("kind")!="fact-reuse-assessment" or f.get("schemaVersion")!=1 or f.get("project")!=draft.get("project") or f.get("authorized") is not False:
            raise ValueError("fact assessment mismatch")
        for row in items(f["facts"],"facts",64):
            if row.get("state")=="REUSE_CANDIDATE":facts.append(row["fact"])
    envelope_v2=draft|{"taskDigest":pin,"verifiedFacts":facts,
                        "verificationPlan":{"ref":text(v["planBundleRef"],"bundle ref"),"digest":digest(bundle),
                                            "workerChecks":worker,"supervisorChecks":supervisor}}
    envelope(envelope_v2)
    return {"kind":"compiled-implementer-handoff","schemaVersion":1,"envelope":envelope_v2,
            "briefDigest":digest(envelope_v2),"verificationPlanBundle":bundle,
            "authorized":False,"runtimeVerified":False}
def main():
    try:
        raw=sys.stdin.buffer.read(262145)
        if len(raw)>262144:raise ValueError("input too large")
        print(json.dumps(compile_handoff(json.loads(raw)),sort_keys=True,ensure_ascii=False));return 0
    except (ValueError,TypeError,KeyError,AttributeError,OSError) as e:
        print("invalid handoff input: "+str(e),file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
