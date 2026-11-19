#!/usr/bin/env python3
"""Compare observed delivery trials. No agent execution or inferred metrics."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path

VARIANTS = ("single-agent", "supervised-task-loop", "delegated-task-loop")
TARGET = VARIANTS[-1]
METRICS = ("acceptedTasks", "totalTokens", "elapsedMs", "transferBytes", "supervisorPeakContextTokens",
           "repeatedReads", "interventions", "recoveryMs", "resourceLeaks", "reopenedTasks", "confirmedDefects")
STATUSES = ("completed", "failed", "blocked", "not-run")
MAX_BYTES = 1048576

def obj(v, keys):
    if not isinstance(v, dict) or set(v) != set(keys):
        raise ValueError("unexpected or missing fields")

def string(v, name, maxlen=512):
    if not isinstance(v, str) or not v.strip() or len(v.encode()) > maxlen or any(ord(c) < 32 for c in v):
        raise ValueError("invalid " + name)
    return v

def number(v, name, maximum=2**53-1):
    if type(v) is not int or not 0 <= v <= maximum:
        raise ValueError("invalid " + name)
    return v

def sha(v):
    if not isinstance(v, str) or not re.fullmatch(r"[a-f0-9]{64}", v):
        raise ValueError("invalid digest")
    return v

def digest(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

def cases_from(plan):
    obj(plan, ("schemaVersion", "kind", "cases"))
    if type(plan["schemaVersion"]) is not int or plan["schemaVersion"] != 1 or plan["kind"] != "delegated-loop-evaluation":
        raise ValueError("invalid plan")
    if not isinstance(plan["cases"], list) or not 1 <= len(plan["cases"]) <= 64:
        raise ValueError("invalid case list")
    cases = {}
    for c in plan["cases"]:
        obj(c, ("id", "workloadDigest", "maxTasks", "description"))
        cid = string(c["id"], "case id")
        if cid in cases:
            raise ValueError("duplicate case")
        sha(c["workloadDigest"])
        if number(c["maxTasks"], "maxTasks", 10000) < 1:
            raise ValueError("maxTasks must be positive")
        string(c["description"], "description", 2048)
        cases[cid] = c
    return cases

def template(plan):
    cases_from(plan)
    return {"schemaVersion": 1, "kind": "delegated-loop-observations", "planDigest": digest(plan), "trials": []}

def validate_trials(plan, obs):
    cases = cases_from(plan)
    obj(obs, ("schemaVersion", "kind", "planDigest", "trials"))
    if type(obs["schemaVersion"]) is not int or obs["schemaVersion"] != 1 or obs["kind"] != "delegated-loop-observations" or obs["planDigest"] != digest(plan):
        raise ValueError("observation plan identity mismatch")
    if not isinstance(obs["trials"], list) or len(obs["trials"]) > 384:
        raise ValueError("invalid trial inventory")
    groups, run_ids = {}, set()
    for r in obs["trials"]:
        obj(r, ("case", "pair", "variant", "runId", "workloadDigest", "environmentDigest",
                "status", "metrics", "acceptance", "reviewerRef", "evidenceRefs"))
        cid, pair, vid, rid = (string(r[k], k) for k in ("case", "pair", "variant", "runId"))
        if cid not in cases or vid not in VARIANTS or rid in run_ids:
            raise ValueError("unassigned case, variant or duplicate run")
        run_ids.add(rid)
        if r["workloadDigest"] != cases[cid]["workloadDigest"]:
            raise ValueError("workload mismatch")
        sha(r["environmentDigest"])
        if r["status"] not in STATUSES or r["acceptance"] not in ("pass", "fail", "unknown"):
            raise ValueError("invalid status or acceptance")
        m, refs = r["metrics"], r["evidenceRefs"]
        if not isinstance(m, dict) or set(m) - set(METRICS):
            raise ValueError("unsupported metric")
        for k, v in m.items():
            number(v, k)
        if m.get("acceptedTasks", 0) > cases[cid]["maxTasks"]:
            raise ValueError("accepted task count exceeds plan")
        if "reopenedTasks" in m and ("acceptedTasks" not in m or m["reopenedTasks"] > m["acceptedTasks"]):
            raise ValueError("reopens exceed observed accepted tasks")
        if not isinstance(refs, list) or len(refs) > 24:
            raise ValueError("invalid evidence inventory")
        for ref in refs:
            string(ref, "evidence reference", 1024)
        if r["status"] == "not-run":
            if m or refs or r["acceptance"] != "unknown" or r["reviewerRef"] is not None:
                raise ValueError("not-run cannot carry observed measurements")
        else:
            if not refs:
                raise ValueError("observed trial needs evidence")
            if r["reviewerRef"] is not None:
                string(r["reviewerRef"], "independent reviewer")
            if (r["acceptance"] != "unknown" or "acceptedTasks" in m) and r["reviewerRef"] is None:
                raise ValueError("acceptance/counts require independent evidence")
            if r["acceptance"] == "pass" and (r["status"] != "completed" or m.get("acceptedTasks") != cases[cid]["maxTasks"]):
                raise ValueError("passing run must complete all planned tasks")
        g = groups.setdefault((cid, pair), {})
        if vid in g:
            raise ValueError("duplicate variant in pair")
        g[vid] = r
    return cases, groups

def observed_metrics(r):
    m = dict(r["metrics"])
    # Never divide by zero or present failed/incomplete delivery as efficiency.
    if r["acceptance"] == "pass":
        n = m.get("acceptedTasks", 0)
        if n:
            if "totalTokens" in m:
                m["tokensPerAcceptedTask"] = m["totalTokens"] / n
            if "elapsedMs" in m:
                m["msPerAcceptedTask"] = m["elapsedMs"] / n
    return m

def compare(plan, obs):
    cases, groups = validate_trials(plan, obs)
    rows, excluded = [], []
    for (cid, pair), g in sorted(groups.items()):
        for baseline in VARIANTS[:-1]:
            a, b = g.get(baseline), g.get(TARGET)
            ident = {"case": cid, "pair": pair, "baseline": baseline}
            if a is None or b is None:
                excluded.append(ident | {"reason": "missing-variant"})
                continue
            if a["environmentDigest"] != b["environmentDigest"]:
                excluded.append(ident | {"reason": "different-environment"})
                continue
            if "not-run" in (a["status"], b["status"]):
                excluded.append(ident | {"reason": "not-run"})
                continue
            am, bm = observed_metrics(a), observed_metrics(b)
            deltas = {k: bm[k] - am[k] for k in sorted(am.keys() & bm.keys())}
            rows.append(ident | {"baselineStatus": a["status"], "candidateStatus": b["status"],
                        "baselineAcceptance": a["acceptance"], "candidateAcceptance": b["acceptance"],
                        "qualityComparable": "unknown" not in (a["acceptance"], b["acceptance"]),
                        "deltas": deltas})
    aggregate = {}
    for baseline in VARIANTS[:-1]:
        pairs = [p for p in rows if p["baseline"] == baseline]
        quality = [p for p in pairs if p["qualityComparable"]]
        measures = {}
        for metric in (*METRICS, "tokensPerAcceptedTask", "msPerAcceptedTask"):
            vals = [p["deltas"][metric] for p in pairs if metric in p["deltas"]]
            measures[metric] = {"pairs": len(vals), "medianDelta": statistics.median(vals) if vals else None}
        aggregate[baseline] = {"observedPairs": len(pairs), "qualityPairs": len(quality),
                               "completionRegressions": sum(p["baselineStatus"] == "completed" and p["candidateStatus"] != "completed" for p in pairs),
                               "qualityRegressions": sum(p["baselineAcceptance"] == "pass" and p["candidateAcceptance"] == "fail" for p in quality),
                               "metrics": measures}
    return {"kind": "delegated-loop-evaluation-report", "schemaVersion": 1,
            "status": "observed-pairs" if rows else "not-evaluated", "plannedCases": len(cases),
            "observedRuns": sum(r["status"] != "not-run" for r in obs["trials"]),
            "notRun": sum(r["status"] == "not-run" for r in obs["trials"]),
            "aggregate": aggregate, "pairs": rows, "excluded": excluded,
            "runtimeVerified": False, "warning": "Reported evidence and metrics are not independently verified by this helper."}

def read(p):
    with p.open("rb") as f:
        raw = f.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("input too large")
    return json.loads(raw)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("plan", type=Path)
    p.add_argument("observations", type=Path, nargs="?")
    args = p.parse_args()
    try:
        plan = read(args.plan)
        print(json.dumps(compare(plan, read(args.observations)) if args.observations else template(plan), sort_keys=True))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
