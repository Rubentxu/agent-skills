#!/usr/bin/env python3
"""Compare actual in-memory and FTS5 retrieval on the same labeled documentary corpus."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import tempfile
import time

from adaptive import size, context_pack
from cache_index import indexed
from evaluate import evaluate, metrics
from evaluate_docs import build
from model import digest, load_json, require
from retrieval import Navigator


def compare(corpus, questions, *, k=5):
    """Run both navigators on identical labeled questions, including rendered output.

    Timing is in-process and excludes capture/installation, not agent wall clock.
    Cold and warm index construction are reported separately from query time.
    """
    require(type(k) is int and 1<=k<=50,"Invalid k")
    baseline=evaluate(corpus,questions,k)
    nav=Navigator(corpus)
    rows=[]
    with tempfile.TemporaryDirectory(prefix="knowledge-evaluation-") as tmp:
        source=Path(tmp)/"corpus.json"
        source.write_text(json.dumps(corpus,ensure_ascii=False),encoding="utf-8")
        start=time.perf_counter()
        with indexed(source,"snapshot",corpus["project"]) as (_,stats):
            path=Path(stats["cache_path"])
        cold=1000*(time.perf_counter()-start)
        try:
            start=time.perf_counter()
            with indexed(source,"snapshot",corpus["project"]) as (cached,stats):
                warm=1000*(time.perf_counter()-start)
                require(stats["reused"],"Expected reused index")
                for q in questions["questions"]:
                    request={"schemaVersion":1,"kind":"context-pack-input","project":corpus["project"],
                             "steps":[{"query":q["query"],"anchors":q.get("anchors",[]),
                                       "intent":q.get("intent","implement")}]}
                    row={"id":q["id"],"variants":{}}
                    for name,engine in (("memory",nav),("fts5",cached)):
                        start=time.perf_counter()
                        pack=context_pack(engine,request,max_results=k)
                        elapsed=1000*(time.perf_counter()-start)
                        ids=list(dict.fromkeys(n["id"] for s in pack["steps"]
                                               for n in s["response"]["results"]))[:k]
                        row["variants"][name]={"retrieved":ids,"metrics":metrics(ids,set(q["relevant"]),k),
                                              "response_bytes":size(pack),"query_ms":elapsed}
                    rows.append(row)
            index_bytes=path.stat().st_size
        finally:
            # Path belongs to the unique temporary snapshot; never delete user indexes.
            path.unlink(missing_ok=True)
    aggregate={}
    for name in ("memory","fts5"):
        values=[r["variants"][name] for r in rows]
        data={}
        for key in ("recall_at_k","precision_at_k","mrr","ndcg_at_k","correct_abstention"):
            observed=[v["metrics"][key] for v in values if v["metrics"][key] is not None]
            data[key]=statistics.mean(observed) if observed else None
        data["median_query_ms"]=round(statistics.median(v["query_ms"] for v in values),4)
        data["mean_response_bytes"]=statistics.mean(v["response_bytes"] for v in values)
        aggregate[name]=data
    return {"status":"measured","project":corpus["project"],"corpus_digest":digest(corpus),
            "questions_digest":digest(questions),"questions":len(rows),"k":k,"aggregate":aggregate,
            "baseline":baseline["aggregate"],"rows":rows,
            "index":{"cold_ms":round(cold,4),"warm_open_ms":round(warm,4),"bytes":index_bytes},
            "warning":"Curated document relevance only; not source implementation verification, live agent trials or production latency."}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("manifest",type=Path)
    p.add_argument("--k",type=int,default=5)
    a=p.parse_args()
    m=load_json(a.manifest)
    c=build(a.root,m)
    q={"schemaVersion":1,"project":m["project"],"questions":m["questions"]}
    result=compare(c,q,k=a.k)
    result["dataset"]={"repository":m.get("repository"),"declared_revision":m.get("revision"),
                       "documents":[{"id":n["id"],**n["sources"][0]} for n in c["nodes"]]}
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))


if __name__=="__main__":
    main()
