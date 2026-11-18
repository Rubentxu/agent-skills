#!/usr/bin/env python3
"""Evaluate retrieval against explicitly selected real documentation, not implementation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from architecture import path
from evaluate import evaluate
from model import MAX_BYTES, load_json, make_corpus, node, require


def build(root: Path, manifest: dict):
    require(manifest.get("schemaVersion")==1 and manifest.get("kind")=="documentation-evaluation",
            "Invalid documentation evaluation manifest")
    root=root.resolve()
    require(root.is_dir(), "Missing selected documentation root")
    docs=manifest.get("documents")
    require(isinstance(docs,list) and 1<=len(docs)<=100,"Invalid document inventory")
    nodes=[]
    total=0
    for d in docs:
        require(isinstance(d,dict),"Invalid document input")
        rel=path(d["path"])
        require(rel.endswith(".md"), "Only explicit Markdown documentation is accepted")
        target=root / rel
        require(not any(x.is_symlink() for x in [target,*target.parents] if x.is_relative_to(root)),
                "Refuse symlink documentation input")
        require(target.is_file() and target.stat().st_size<=1024*1024,"Missing or oversized documentation")
        with target.open("rb") as f:
            raw=f.read(1024*1024+1)
        total+=len(raw)
        require(len(raw)<=1024*1024 and total<=MAX_BYTES,"Documentation input exceeds budget")
        nodes.append(node(d["id"],d["kind"],d["title"],d["summary"],body=raw.decode("utf-8"),
                          contexts=d.get("contexts",[]),aliases=d.get("aliases",[]),level=d.get("level","L1"),
                          claim_state="unknown",
                          sources=[{"provider":"markdown","locator":rel,"digest":hashlib.sha256(raw).hexdigest()}]))
    return make_corpus(manifest["project"],nodes,manifest.get("edges",[]))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("manifest",type=Path)
    args=p.parse_args()
    m=load_json(args.manifest)
    c=build(args.root,m)
    report=evaluate(c,{"schemaVersion":1,"project":m["project"],"questions":m["questions"]})
    report["dataset"]={"kind":"repository-documentation","documents":len(c["nodes"]),
                       "labeling":"curated question relevance, not exhaustive ground truth",
                       "sources":[{"id":n["id"],**n["sources"][0]} for n in c["nodes"]]}
    print(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2))


if __name__=="__main__":
    main()
