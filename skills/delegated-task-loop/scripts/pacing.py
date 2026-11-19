#!/usr/bin/env python3
"""Endurance policy: bounded wall-clock budgets, no scheduling or cancellation."""
from __future__ import annotations
import json
import sys
import time

DEFAULT={"attemptSeconds":3600,"taskSeconds":7200,"assessSeconds":2700,"checkpointSeconds":3000,"minSuccessorSeconds":300}
def number(v,name,minimum=0,maximum=2**53-1):
    if type(v) is not int or not minimum<=v<=maximum:raise ValueError("invalid "+name)
    return v
def policy(v):
    if v=="default":return dict(DEFAULT)
    if not isinstance(v,dict) or set(v)!=set(DEFAULT):raise ValueError("invalid relay policy")
    for k in DEFAULT:number(v[k],k,1,7200)
    if not 60<=v["attemptSeconds"]<=3600 or not v["attemptSeconds"]<=v["taskSeconds"]<=7200 or not 0<v["assessSeconds"]<v["checkpointSeconds"]<v["attemptSeconds"] or not 60<=v["minSuccessorSeconds"]<=v["attemptSeconds"]:
        raise ValueError("invalid pacing thresholds")
    return dict(v)
def now():
    return int(time.time())
def schedule(p,task_start,attempt_start):
    p=policy(p)
    number(task_start,"task start");number(attempt_start,"attempt start")
    if attempt_start<task_start:raise ValueError("attempt predates task")
    deadline=min(task_start+p["taskSeconds"],attempt_start+p["attemptSeconds"])
    duration=deadline-attempt_start
    if duration<=0:raise ValueError("task budget exhausted")
    return {"taskStartedAt":task_start,"attemptStartedAt":attempt_start,"taskDeadlineAt":task_start+p["taskSeconds"],
            "assessAt":attempt_start+min(p["assessSeconds"],duration*3//4),
            "checkpointAt":attempt_start+min(p["checkpointSeconds"],duration*5//6),
            "deadlineAt":deadline}
def validate_schedule(s):
    keys=("taskStartedAt","attemptStartedAt","taskDeadlineAt","assessAt","checkpointAt","deadlineAt")
    if not isinstance(s,dict) or set(s)!=set(keys):raise ValueError("invalid schedule")
    for k in keys:number(s[k],k)
    if not s["taskStartedAt"]<=s["attemptStartedAt"]<=s["assessAt"]<=s["checkpointAt"]<s["deadlineAt"]<=s["taskDeadlineAt"] or s["deadlineAt"]-s["attemptStartedAt"]>3600 or s["taskDeadlineAt"]-s["taskStartedAt"]>7200:
        raise ValueError("schedule exceeds bounded policy")
def assess(s,observed,operation="none",materialProgress=False,terminal=False):
    validate_schedule(s);number(observed,"observation time")
    if observed<s["attemptStartedAt"]:raise ValueError("clock moved backwards; reconcile")
    if operation not in ("none","healthy","waiting","unknown") or type(materialProgress) is not bool or type(terminal) is not bool:raise ValueError("invalid observation")
    remaining=max(0,s["deadlineAt"]-observed)
    if terminal:action="VERIFY_RESULT"
    elif observed>=s["deadlineAt"]:action="RECONCILE_DEADLINE"
    elif observed>=s["checkpointAt"]:action="PREPARE_RELAY"
    elif observed>=s["assessAt"]:action="CONTINUE_BOUNDED" if materialProgress and operation=="none" else "ASSESS_RELAY"
    elif operation in ("healthy","waiting"):action="WAIT_EXISTING_OPERATION"
    else:action="CONTINUE"
    return {"kind":"relay-pacing","schemaVersion":1,"action":action,"attemptElapsedSeconds":observed-s["attemptStartedAt"],
            "taskElapsedSeconds":observed-s["taskStartedAt"],"attemptRemainingSeconds":remaining,
            "taskRemainingSeconds":max(0,s["taskDeadlineAt"]-observed),"observedAt":observed,
            "operation":operation,"terminationConfirmed":False,"authorized":False}
def main():
    try:
        raw=sys.stdin.buffer.read(65537)
        if len(raw)>65536:raise ValueError("input too large")
        v=json.loads(raw)
        if set(v)!={"schedule","operation","materialProgress","terminal"}:raise ValueError("invalid observation")
        print(json.dumps(assess(v["schedule"],now(),v["operation"],v["materialProgress"],v["terminal"]),sort_keys=True));return 0
    except (OSError,ValueError,TypeError,KeyError) as e:
        print(str(e),file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
