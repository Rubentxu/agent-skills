#!/usr/bin/env python3
"""Independent real-code pilot oracle. No LLM launch, no mutations of trial checkout."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from evaluate_runs import digest

ROOT=Path(__file__).resolve().parents[1]
SPEC=ROOT/"examples/pilot-workloads.json"
def spec():
    return json.loads(SPEC.read_text())
def git(root,*args):
    return subprocess.run(["git","-C",str(root),*args],capture_output=True,text=True,check=True,timeout=10).stdout.strip()
def run(root,script,payload=None,args=()):
    p=subprocess.run([sys.executable,"-B",str(root/script),*map(str,args)],input=None if payload is None else json.dumps(payload),text=True,capture_output=True,timeout=10,cwd=root)
    if p.returncode==2:return None
    if p.returncode:raise RuntimeError("oracle invocation failed")
    return json.loads(p.stdout)
def router(root):
    script=Path("skills/delegated-task-loop/scripts/affordances.py")
    s=json.loads((root/"skills/delegated-task-loop/examples/ready.json").read_text())
    s.update(phase="accept",ownership="terminated",evidence="sufficient",review="none",resourceState="clear",availableSkills=["backlog-agile-workflow"])
    def allowed(outcome):
        r=run(root,script,s|{"outcome":outcome},["-"])
        return r is not None and any(x["rel"]=="accept-after-authority-check" for x in r["_links"])
    return {"blocked-not-accepted":not allowed("blocked"),"normal-acceptance":allowed("unknown")}
def paths(root):
    script=Path("skills/delivery-first-testing/scripts/verification_plan.py")
    p=json.loads((root/"skills/delivery-first-testing/examples/verification-plan-input.json").read_text())
    def accepted(cwd):
        p["candidates"][0]["cwd"]=cwd
        r=run(root,script,p)
        return r is not None and r["status"]=="PLANNED"
    return {"drive-rejected":not accepted("C:/outside"),"empty-segment-rejected":not accepted("src//tests"),
            "dot-segment-rejected":not accepted("src/./tests"),"parent-rejected":not accepted("../outside"),
            "absolute-rejected":not accepted("/outside"),"normal-root":accepted("."),"normal-relative":accepted("src/tests")}
def telemetry(root):
    script=Path("skills/delegated-task-loop/scripts/worker_metrics.py")
    with tempfile.TemporaryDirectory() as td:
        f=Path(td)/"transcript.jsonl"
        def row(i,usage):
            return dict(type="assistant",message=dict(id=i,content=[],usage=usage))
        f.write_text("\n".join(json.dumps(x) for x in [row("1",{"input_tokens":4,"output_tokens":10}),row("2",{"input_tokens":6})])+"\n")
        partial=run(root,script,args=[f])
        f.write_text("\n".join(json.dumps(x) for x in [row("1",{"output_tokens":10}),row("2",{"output_tokens":20})])+"\n")
        complete=run(root,script,args=[f])
        f.write_text('{"unrecognized":"format"}\n');unknown=run(root,script,args=[f])
        return {"partial-not-total":"output_tokens" in partial.get("completeUsage",{}) and partial["completeUsage"]["output_tokens"] is None,
                "known-field-total":partial.get("completeUsage",{}).get("input_tokens")==10,
                "observed-preserved":partial["observedUsage"]["output_tokens"]==10,
                "complete-total":complete.get("completeUsage",{}).get("output_tokens")==30,
                "unknown-not-zero":"output_tokens" in unknown.get("completeUsage",{}) and unknown["completeUsage"]["output_tokens"] is None}
ORACLES={"PILOT-01":router,"PILOT-02":paths,"PILOT-03":telemetry}
CONTROLS={"PILOT-01":{"normal-acceptance"},"PILOT-02":{"parent-rejected","absolute-rejected","normal-root","normal-relative"},"PILOT-03":{"observed-preserved"}}
def assess(root,case_id,baseline=False):
    s=spec();case=next(c for c in s["cases"] if c["id"]==case_id)
    head=git(root,"rev-parse","HEAD")
    if git(root,"status","--porcelain","--untracked-files=all"):
        raise ValueError("trial must be clean")
    if baseline:
        if head!=s["baseRevision"]:raise ValueError("baseline revision mismatch")
    else:
        git(root,"merge-base","--is-ancestor",s["baseRevision"],head)
        changed=set(git(root,"diff","--name-only","--no-renames",s["baseRevision"],head).splitlines())
        if not changed or changed-set(case["allowedPaths"]):raise ValueError("empty or out-of-scope change")
    start=time.monotonic()
    checks=ORACLES[case_id](root)
    if git(root,"status","--porcelain","--untracked-files=all"):raise ValueError("oracle changed checkout")
    controls=all(checks[k] for k in CONTROLS[case_id])
    passed=all(checks.values())
    return {"kind":"pilot-oracle-observation","case":case_id,"baseRevision":s["baseRevision"],"headRevision":head,
            "workloadDigest":digest({"baseRevision":s["baseRevision"],"case":case,"oracleDigest":digest(Path(__file__).read_text())}),
            "checks":checks,"controlsPass":controls,"status":"BASELINE_NEGATIVE" if baseline and controls and not passed else "PASS" if not baseline and passed else "FAIL",
            "oracleElapsedMs":round((time.monotonic()-start)*1000),"agentRun":False}
def manifest():
    s=spec()
    cases=[dict(id=c["id"],workloadDigest=digest({"baseRevision":s["baseRevision"],"case":c,"oracleDigest":digest(Path(__file__).read_text())}),maxTasks=1,description=c["objective"]) for c in s["cases"]]
    variants=[v["id"] for v in s["variants"]]
    # Rotated order, fixed complete pair for each workload and repetition.
    pairs=[dict(case=c["id"],id=f"r{i+1}",order=variants[i:]+variants[:i]) for c in cases for i in range(len(variants))]
    return {"schemaVersion":2,"kind":"delegated-loop-evaluation","cases":cases,
            "variants":variants,"candidate":"delegated-task-loop","pairs":pairs}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation",choices=("plan","baseline-check","verify"))
    p.add_argument("--checkout",type=Path)
    p.add_argument("--case",choices=ORACLES)
    a=p.parse_args()
    try:
        if a.operation=="plan":
            print(json.dumps(manifest(),sort_keys=True));return 0
        if a.checkout is None:raise ValueError("checkout required")
        if a.operation=="verify" and a.case is None:raise ValueError("case required")
        cases=[a.case] if a.case else list(ORACLES)
        rows=[assess(a.checkout.resolve(),c,a.operation=="baseline-check") for c in cases]
        print(json.dumps(rows,sort_keys=True))
        return 0 if all(r["status"] in ("PASS","BASELINE_NEGATIVE") for r in rows) else 2
    except (ValueError,RuntimeError,KeyError,StopIteration,OSError,subprocess.SubprocessError) as e:
        print(type(e).__name__+": pilot could not be verified",file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
