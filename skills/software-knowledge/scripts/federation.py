#!/usr/bin/env python3
"""Federate explicit project snapshots without merging identities or authorities."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from model import identifier, require, validate, load_json
from retrieval import Navigator, INTENTS

RELATIONS = {"uses-contract", "reuses-pattern", "depends-on-project", "references", "supersedes-reference"}


def reference(value):
    require(isinstance(value, dict) and set(value) == {"project", "node"}
            and identifier(value["project"]) and identifier(value["node"]), "Expected qualified project/node reference")
    return value["project"], value["node"]


def registry(manifest, corpora):
    require(manifest.get("schemaVersion") == 1 and manifest.get("kind") == "knowledge-federation",
            "Invalid federation contract")
    projects = manifest.get("projects")
    require(isinstance(projects,list) and 1<=len(projects)<=32 and all(identifier(x) for x in projects)
            and len(projects)==len(set(projects)), "Invalid project inventory")
    require(set(corpora)<=set(projects), "Unregistered corpus project")
    for project, c in corpora.items():
        validate(c)
        require(c["project"] == project, "Project/source identity mismatch")
    links = manifest.get("links", [])
    require(isinstance(links,list) and len(links)<=500, "Invalid link inventory")
    seen = set()
    result = []
    for e in links:
        require(isinstance(e,dict) and set(e)=={"from","to","relation"}
                and e["relation"] in RELATIONS, "Invalid federation link")
        a,b = reference(e["from"]),reference(e["to"])
        require(a[0] in projects and b[0] in projects and a[0]!=b[0], "Expected registered cross-project link")
        k = (a,e["relation"],b)
        require(k not in seen, "Duplicate federation link")
        seen.add(k)
        result.append((a,e["relation"],b))
    return result


def navigate(manifest, corpora, *, project, node=None, query=None, intent="understand",
             limit=5, budget=12000, follow=False):
    links = registry(manifest,corpora)
    require(project in corpora, "Select an explicit loaded project")
    require((node is None)!=(query is None), "Select node or query")
    require(1<=limit<=20 and 1024<=budget<=64000 and intent in INTENTS, "Invalid federation budget")
    nav = Navigator(corpora[project])
    if node is not None:
        require(node in nav.nodes, "Unknown qualified node")
        ids = [node]
    else:
        require(isinstance(query,str) and 0<len(query)<=1200, "Invalid federation query")
        ids = nav.search(query,intent=intent)[:limit]
    result = {"schemaVersion":1,"kind":"federated-navigation","status":"partial",
              "project":project,"results":[],"omitted":0,"cross_project_reads":0,
              "warning":"Declared external links only; target content retains its original authority. No implicit global search."}
    def size():
        return len(json.dumps(result,ensure_ascii=False,separators=(",",":")).encode())
    for i in ids:
        n = nav.nodes[i]
        result["results"].append({"project":project,"id":i,"title":n["title"],"kind":n["kind"],
                                  "claim_state":n.get("claim_state","unknown"),"links":[]})
        if size()>budget-64:
            result["results"].pop()
            result["omitted"]+=1
            continue
        item=result["results"][-1]
        for a,relation,b in links:
            if a!=(project,i) and b!=(project,i):
                continue
            target = b if a==(project,i) else a
            direction="out" if a==(project,i) else "in"
            target_available=target[0] in corpora
            entry={"relation":relation,"direction":direction,
                   "target":{"project":target[0],"node":target[1]},
                   "status":"explicit-source-required" if not target_available else "not-followed"}
            # Loaded corpora are authorized as inputs; only explicit follow resolves external data.
            read_target=False
            if follow and target_available:
                found=next((x for x in corpora[target[0]]["nodes"] if x["id"]==target[1]),None)
                entry["status"]="resolved" if found else "not-observed-in-snapshot"
                if found:
                    entry["target_summary"]={"title":found["title"],"kind":found["kind"],
                                             "claim_state":found.get("claim_state","unknown"),
                                             "coverage":corpora[target[0]]["coverage"]}
                    read_target=True
            item["links"].append(entry)
            if size()>budget-64:
                item["links"].pop()
                result["omitted"]+=1
            elif read_target:
                result["cross_project_reads"]+=1
    if not ids:
        result["status"]="unknown"
    require(size()<=budget, "Federation envelope exceeds budget")
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest",type=Path)
    p.add_argument("--source",action="append",default=[],help="Explicit PROJECT=PATH snapshot")
    p.add_argument("--project",required=True)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--node")
    group.add_argument("--query")
    p.add_argument("--intent",choices=INTENTS,default="understand")
    p.add_argument("--follow",action="store_true")
    p.add_argument("--limit",type=int,default=5)
    p.add_argument("--budget-bytes",type=int,default=12000)
    a=p.parse_args()
    try:
        require(1<=len(a.source)<=32,"Select explicit source snapshots")
        corpora={}
        for spec in a.source:
            project,sep,filename=spec.partition("=")
            require(bool(sep) and identifier(project) and project not in corpora and bool(filename),"Invalid source binding")
            corpora[project]=load_json(Path(filename))
        result=navigate(load_json(a.manifest),corpora,project=a.project,node=a.node,query=a.query,
                        intent=a.intent,follow=a.follow,limit=a.limit,budget=a.budget_bytes)
        print(json.dumps(result,ensure_ascii=False,separators=(",",":")))
    except (ValueError,TypeError,KeyError,OSError) as exc:
        print(json.dumps({"status":"invalid-input","error":str(exc)}),file=sys.stderr)
        return 2
    return 0


if __name__=="__main__":
    raise SystemExit(main())
