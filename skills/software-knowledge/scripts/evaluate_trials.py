#!/usr/bin/env python3
"""Compare paired externally observed agent trials. Never launch agents or invent evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import statistics
import sys

from model import digest, identifier, load_json, require

VARIANTS = ("baseline", "knowledge")
METRICS = ("input_tokens", "output_tokens", "tool_calls", "elapsed_ms", "retrieval_bytes")
MAX_TRIALS = 400


def sha(value):
    return isinstance(value,str) and re.fullmatch(r"[0-9a-f]{64}",value) is not None


def nonempty(value):
    return isinstance(value,str) and 0<len(value.strip())<=256 and not any(ord(c)<32 for c in value)


def cases_from(plan):
    require(plan.get("schemaVersion")==1 and plan.get("kind")=="paired-agent-evaluation",
            "Invalid agent evaluation plan")
    cases=plan.get("cases")
    require(isinstance(cases,list) and 0<len(cases)<=100,"Invalid case inventory")
    result={}
    for case in cases:
        i=case.get("id")
        require(identifier(i) and i not in result and identifier(case.get("project"))
                and nonempty(case.get("revision")) and isinstance(case.get("prompt"),str)
                and 0<len(case["prompt"])<=4000,"Invalid or duplicate evaluation case")
        checks=case.get("checks")
        require(isinstance(checks,list) and 0<len(checks)<=30,"Invalid rubric")
        keys=set()
        for check in checks:
            k=check.get("id")
            require(identifier(k) and k not in keys and isinstance(check.get("required"),bool)
                    and nonempty(check.get("description")),"Invalid rubric check")
            keys.add(k)
        require(any(c["required"] for c in checks),"At least one required check")
        participants=case.get("access_policy")
        require(nonempty(participants),"Explicit access policy required")
        result[i]=case
    return result


def compare(plan, observations):
    cases=cases_from(plan)
    require(observations.get("schemaVersion")==1 and observations.get("kind")=="agent-trial-observations"
            and observations.get("plan_digest")==digest(plan),"Observation plan identity mismatch")
    raw=observations.get("trials")
    require(isinstance(raw,list) and len(raw)<=MAX_TRIALS,"Invalid trial inventory")
    groups={}
    seen_run_ids=set()
    for row in raw:
        require(isinstance(row,dict) and row.get("case") in cases
                and row.get("variant") in VARIANTS and identifier(row.get("pair"))
                and identifier(row.get("run_id")) and row["run_id"] not in seen_run_ids,"Invalid or duplicate run")
        seen_run_ids.add(row["run_id"])
        c=cases[row["case"]]
        require(row.get("project")==c["project"] and row.get("revision")==c["revision"],
                "Trial project/revision mismatch")
        env=row.get("environment")
        require(isinstance(env,dict) and set(env)=={"harness","model","settings_digest","toolset_digest","access_policy","prompt_digest"}
                and nonempty(env["harness"]) and nonempty(env["model"])
                and all(sha(env[k]) for k in ("settings_digest","toolset_digest","prompt_digest"))
                and env["prompt_digest"]==digest(c["prompt"]) and env["access_policy"]==c["access_policy"],"Invalid or incomparable environment")
        require(row.get("status") in {"completed","failed","blocked","not-run"},"Unknown trial status")
        if row["status"]=="not-run":
            require(row.get("metrics")=={} and row.get("checks")=={} and row.get("evidence")==[],"Not-run trial cannot have measurements")
        else:
            e=row.get("evidence")
            require(isinstance(e,list) and 0<len(e)<=20 and all(sha(x.get("digest")) and
                    nonempty(x.get("locator")) for x in e if isinstance(x,dict))
                    and all(isinstance(x,dict) for x in e),"Observed run requires evidence references")
            m=row.get("metrics")
            require(isinstance(m,dict) and set(m)<=set(METRICS) and all(type(v) is int and v>=0 for v in m.values()),
                    "Invalid measured metrics; omit unavailable fields")
            checks=row.get("checks")
            allowed={k["id"] for k in c["checks"]}
            require(isinstance(checks,dict) and set(checks)<=allowed
                    and all(v in {"pass","fail","unknown"} for v in checks.values()),"Invalid observed rubric")
            require(nonempty(row.get("reviewer")),"Explicit reviewer required")
        key=(row["case"],row["pair"])
        group=groups.setdefault(key,{})
        require(row["variant"] not in group,"Duplicate trial variant in pair")
        group[row["variant"]]=row
    paired=[]
    unmatched=[]
    completion_pairs=[]
    for (case,pair), group in sorted(groups.items()):
        if set(group)!=set(VARIANTS):
            unmatched.append({"case":case,"pair":pair,"reason":"missing-variant"})
            continue
        a,b=(group[v] for v in VARIANTS)
        if a["environment"]!=b["environment"]:
            unmatched.append({"case":case,"pair":pair,"reason":"different-environment"})
            continue
        if all(x["status"]!="not-run" for x in (a,b)):
            completion_pairs.append({"case":case,"pair":pair,"baseline":a["status"],"knowledge":b["status"]})
        if any(x["status"]!="completed" for x in (a,b)):
            unmatched.append({"case":case,"pair":pair,"reason":"incomplete-run",
                              "baseline":a["status"],"knowledge":b["status"]})
            continue
        required={x["id"] for x in cases[case]["checks"] if x["required"]}
        def success(row):
            observed=[row["checks"].get(x,"unknown") for x in required]
            return False if "fail" in observed else None if "unknown" in observed else True
        quality={v:success(group[v]) for v in VARIANTS}
        deltas={}
        for k in METRICS:
            if k in a["metrics"] and k in b["metrics"]:
                av,bv=a["metrics"][k],b["metrics"][k]
                deltas[k]={"baseline":av,"knowledge":bv,"delta":bv-av,
                           "relative_delta":(bv-av)/av if av else None}
        paired.append({"case":case,"pair":pair,"quality":quality,"metrics":deltas})
    aggregate={}
    quality_pairs=[p for p in paired if all(v is not None for v in p["quality"].values())]
    for k in METRICS:
        values=[p["metrics"][k] for p in paired if k in p["metrics"]]
        aggregate[k]={"pairs":len(values),"median_delta":statistics.median(v["delta"] for v in values) if values else None}
    status = "measured-pairs" if paired else "measured-completion-only" if completion_pairs else "not-evaluated"
    return {"status":status,"plan_digest":digest(plan),
            "planned_cases":len(cases),"observed_runs":len(raw),"comparable_pairs":len(paired),
            "completion_pairs":len(completion_pairs),
            "completion_by_variant":{v:{status:sum(x[v]==status for x in completion_pairs)
                                         for status in ("completed","failed","blocked")} for v in VARIANTS},
            "completion_regressions":sum(x["baseline"]=="completed" and x["knowledge"]!="completed" for x in completion_pairs),
            "quality_pairs":len(quality_pairs),"quality_passes":{v:sum(p["quality"][v] for p in quality_pairs) for v in VARIANTS},
            "quality_regressions":sum(p["quality"]["baseline"] and not p["quality"]["knowledge"] for p in quality_pairs),
            "aggregate":aggregate,"pairs":paired,"unmatched":unmatched,
            "warning":"Host-reported metrics and independent rubric judgments, not verified transcripts; no model or tool invoked. Missing metrics remain unknown."}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("plan",type=Path)
    p.add_argument("observations",type=Path,nargs="?")
    a=p.parse_args()
    try:
        plan=load_json(a.plan)
        if a.observations:
            result=compare(plan,load_json(a.observations))
        else:
            cases_from(plan)
            result={"schemaVersion":1,"kind":"agent-trial-observations","plan_digest":digest(plan),"trials":[]}
        print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    except (ValueError,TypeError,KeyError,OSError,AttributeError) as exc:
        print(json.dumps({"status":"invalid-input","error":str(exc)}),file=sys.stderr)
        return 2
    return 0


if __name__=="__main__":
    raise SystemExit(main())
