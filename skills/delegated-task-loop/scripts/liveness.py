#!/usr/bin/env python3
"""Single observed checkpoint. Silence is not evidence of termination."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from supervision import fields, number, string

def linux_identity(pid, boot_id, start_ticks, proc=Path("/proc")):
    if type(pid) is not int or pid<1 or pid>2**31-1: raise ValueError("invalid pid")
    string(boot_id,"boot id")
    number(start_ticks,"start ticks")
    try:
        boot=(proc/"sys/kernel/random/boot_id").read_text().strip()
        if boot!=boot_id: return "different-boot"
        # comm may contain spaces and parentheses; fields after final ')' are 3 onward.
        raw=(proc/str(pid)/"stat").read_text()
        tail=raw[raw.rfind(")")+1:].split()
        if int(tail[19])!=start_ticks: return "reused"
        return "zombie" if tail[0] in ("Z","X") else "match"
    except FileNotFoundError:
        return "absent" if (proc/"sys/kernel/random/boot_id").is_file() else "unknown"
    except (OSError,ValueError,IndexError):
        return "unknown"

def assess(v):
    fields(v,("schemaVersion","kind","identity","phase","hostState","hostEvidenceRef","process",
              "silentSeconds","withoutProgressSeconds","operation","steering","graceElapsed","inventoryComplete"))
    if type(v["schemaVersion"]) is not int or v["schemaVersion"]!=1 or v["kind"]!="liveness-observation":
        raise ValueError("invalid observation")
    string(v["identity"],"handle")
    string(v["hostEvidenceRef"],"host observation")
    if v["phase"] not in ("exploration","implementation","verification","waiting") or v["hostState"] not in ("running","waiting","terminal","unknown") or v["operation"] not in ("healthy","waiting","none","unknown"):
        raise ValueError("invalid lifecycle state")
    for k in ("steering","graceElapsed","inventoryComplete"):
        if type(v[k]) is not bool: raise ValueError("invalid flag")
    for k in ("silentSeconds","withoutProgressSeconds"):
        if v[k] is not None: number(v[k],k)
    p=v["process"]
    if p is None:
        process="not-applicable"
    else:
        fields(p,("pid","bootId","startTicks"))
        process=linux_identity(p["pid"],p["bootId"],p["startTicks"])
    threshold=900 if v["phase"]=="exploration" else 1500
    silent=v["silentSeconds"] is not None and v["silentSeconds"]>=threshold
    stagnant=v["withoutProgressSeconds"] is not None and v["withoutProgressSeconds"]>=threshold
    signal="normal"; action="WAIT"; classification="OBSERVATION_ONLY"
    if v["hostState"]=="terminal":
        signal="result";action="RECONCILE";classification="HOST_TERMINAL"
    elif process in ("absent","reused","zombie","different-boot"):
        signal="resource-drift";action="RECONCILE"
        classification="STALE_CANDIDATE" if v["inventoryComplete"] and v["operation"]=="none" else "UNKNOWN_EFFECTS"
    elif v["operation"] in ("healthy","waiting") or v["hostState"]=="waiting":
        signal="pending";action="AWAIT_EXISTING_OPERATION";classification="PENDING"
    elif silent or stagnant:
        signal="silence";action="STEER" if v["steering"] and not v["graceElapsed"] else "REASSESS"
        classification="SILENCE_NOT_DEATH"
    elif v["hostState"]=="unknown" or process=="unknown":
        signal="resource-drift";action="RECONCILE";classification="UNKNOWN"
    return {"kind":"liveness-assessment","schemaVersion":1,"identity":v["identity"],"processObservation":process,
            "signal":signal,"recommended":action,"classification":classification,
            "terminationConfirmed":False,"authorized":False,"runtimeVerified":False}
def main():
    try:
        raw=sys.stdin.buffer.read(65537)
        if len(raw)>65536: raise ValueError("input too large")
        print(json.dumps(assess(json.loads(raw)),sort_keys=True));return 0
    except (ValueError,TypeError,KeyError,OSError) as e:
        print(str(e),file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
