#!/usr/bin/env python3
"""Local streaming JSONL telemetry. No content/arguments/results are emitted."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

MAX_LINE=2*1024*1024
MAX_IDS=16384
TOOLS={"Read","Write","Edit","MultiEdit","Grep","Glob","Bash","Agent","Task","SendMessage","WebSearch","WebFetch","TodoWrite","NotebookEdit"}

def hid(v):
    return hashlib.sha256(v.encode()).hexdigest() if isinstance(v,str) and v else None
def millisecond(v):
    if not isinstance(v,str):return None
    try:
        t=datetime.fromisoformat(v.replace("Z","+00:00"))
        return int(t.timestamp()*1000) if t.tzinfo else None
    except (ValueError,OverflowError):return None
def init(st):
    return {"device":st.st_dev,"inode":st.st_ino,"offset":0,"messages":{},"pending":{},"seenTools":{},
            "calls":{},"intervalMs":{},"pairs":{},"firstMs":None,"lastMs":None,"maxGapMs":0,
            "unionStartMs":None,"unionMs":0,"invalidRows":0,"outOfOrder":False,"limited":False}
def count(d,key,n=1):
    d[key]=d.get(key,0)+n
def valid_usage(u):
    if not isinstance(u,dict):return {}
    return {k:u[k] for k in ("input_tokens","output_tokens","cache_read_input_tokens","cache_creation_input_tokens") if type(u.get(k)) is int and 0<=u[k]<2**53}
def tool_name(n):
    return n if isinstance(n,str) and n in TOOLS else "MCP" if isinstance(n,str) and n.startswith("mcp__") else "OTHER"
def event(s,row):
    if not isinstance(row,dict):return
    t=millisecond(row.get("timestamp"))
    if t is not None:
        if s["firstMs"] is None:s["firstMs"]=t
        if s["lastMs"] is not None:
            if t<s["lastMs"]:s["outOfOrder"]=True
            else:s["maxGapMs"]=max(s["maxGapMs"],t-s["lastMs"])
        s["lastMs"]=max(s["lastMs"] or t,t)
    m=row.get("message")
    if not isinstance(m,dict):return
    if row.get("type")=="assistant":
        mid=hid(m.get("id"))
        if mid:
            if mid in s["messages"] or len(s["messages"])<MAX_IDS:
                s["messages"][mid]=s["messages"].get(mid,{})|valid_usage(m.get("usage"))
            else:s["limited"]=True
    if not isinstance(m.get("content"),list):return
    for b in m["content"]:
        if not isinstance(b,dict):continue
        if row.get("type")=="assistant" and b.get("type")=="tool_use":
            tid=hid(b.get("id"))
            if not tid or tid in s["seenTools"]:continue
            if len(s["seenTools"])>=MAX_IDS:s["limited"]=True;continue
            name=tool_name(b.get("name"));s["seenTools"][tid]=True;count(s["calls"],name)
            if not s["pending"]:s["unionStartMs"]=t
            s["pending"][tid]=[name,t]
        elif row.get("type")=="user" and b.get("type")=="tool_result":
            tid=hid(b.get("tool_use_id"))
            if tid not in s["pending"]:continue
            name,start=s["pending"].pop(tid)
            if start is not None and t is not None and t>=start:
                count(s["intervalMs"],name,t-start);count(s["pairs"],name)
            else:s["outOfOrder"]=True
            if not s["pending"]:
                start=s["unionStartMs"]
                if start is not None and t is not None and t>=start:s["unionMs"]+=t-start
                else:s["outOfOrder"]=True
                s["unionStartMs"]=None
def scan(path,previous=None,max_bytes=64*1024*1024):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,"rb") as f:
        st=os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode):raise ValueError("regular transcript required")
        s=init(st) if previous is None else previous
        if set(s)!=set(init(st)) or s["device"]!=st.st_dev or s["inode"]!=st.st_ino or type(s["offset"]) is not int or not 0<=s["offset"]<=st.st_size:
            raise ValueError("cursor mismatch or transcript rotated; reconcile")
        start=s["offset"];f.seek(start)
        while f.tell()-start<max_bytes:
            line=f.readline(MAX_LINE+1)
            if not line:break
            if len(line)>MAX_LINE:
                raise ValueError("oversized transcript row")
            if not line.endswith(b"\n"):
                break # retry incomplete final JSONL row on next checkpoint
            try:row=json.loads(line)
            except (ValueError,UnicodeError):s["invalidRows"]+=1
            else:event(s,row)
            s["offset"]=f.tell()
        sums=Counter();observed=Counter()
        for u in s["messages"].values():
            sums.update(u);observed.update(u.keys())
        output={k:(sums[k] if observed[k] else None) for k in ("input_tokens","output_tokens","cache_read_input_tokens","cache_creation_input_tokens")}
        status="PARTIAL" if s["limited"] or s["invalidRows"] or s["outOfOrder"] or s["offset"]<os.fstat(f.fileno()).st_size else "OBSERVED"
        if not s["messages"] and not s["calls"]: status="UNSUPPORTED_OR_EMPTY"
        metrics={"kind":"worker-metrics","schemaVersion":1,"status":status,
                 "assistantMessageIds":len(s["messages"]),"observedUsage":output,
                 "usageMessages":dict(observed),"toolCalls":s["calls"],"toolResultPairs":s["pairs"],
                 "toolRoundtripMs":s["intervalMs"],"completedToolUnionMs":s["unionMs"] if s["pairs"] and not s["outOfOrder"] else None,
                 "openToolCalls":len(s["pending"]),"lastEventEpochMs":s["lastMs"],"maxObservedGapMs":s["maxGapMs"] if s["lastMs"] is not None else None,
                 "transcriptMtimeEpochMs":st.st_mtime_ns//1000000,"invalidRows":s["invalidRows"],
                 "modelGenerationMs":None,"runtimeVerified":False}
        return {"metrics":metrics,"cursor":s}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("transcript",type=Path);p.add_argument("--cursor",type=Path);p.add_argument("--include-cursor",action="store_true")
    a=p.parse_args()
    try:
        previous=None
        if a.cursor:
            with a.cursor.open("rb") as f:
                raw=f.read(8*1024*1024+1)
            if len(raw)>8*1024*1024:raise ValueError("oversized cursor")
            previous=json.loads(raw)
        out=scan(a.transcript,previous)
        print(json.dumps(out if a.include_cursor else out["metrics"],sort_keys=True));return 0
    except (ValueError,TypeError,KeyError,OSError) as e:
        # Never echo input contents or provider errors.
        print(type(e).__name__+": telemetry unavailable; reconcile source/cursor",file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
