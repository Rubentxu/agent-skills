#!/usr/bin/env python3
"""Evaluate deterministic retrieval on explicitly labeled questions, never model fitness."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from model import load_json, require
from retrieval import Navigator
from adaptive import context_pack


def metrics(ranked: list[str], expected: set[str], k: int) -> dict:
    ranked = list(dict.fromkeys(ranked))[:k]
    hits = [int(i in expected) for i in ranked]
    dcg = sum(hit / math.log2(i + 2) for i, hit in enumerate(hits))
    ideal = sum(1 / math.log2(i + 2) for i in range(min(k, len(expected))))
    return {"precision_at_k": sum(hits) / k,
            "recall_at_k": sum(hits) / len(expected) if expected else None,
            "mrr": next((1 / (i + 1) for i, hit in enumerate(hits) if hit), 0),
            "ndcg_at_k": dcg / ideal if ideal else None,
            "correct_abstention": not ranked if not expected else None}


def evaluate(corpus: dict, questions: dict, k: int = 5) -> dict:
    nav = Navigator(corpus)
    require(1 <= k <= 50, "Invalid k")
    require(questions.get("schemaVersion") == 1 and questions.get("project") == corpus["project"]
            and isinstance(questions.get("questions"), list) and questions["questions"],
            "Invalid evaluation set/project")
    rows = []
    seen = set()
    for q in questions["questions"]:
        require(isinstance(q, dict) and isinstance(q.get("id"), str) and q["id"] not in seen
                and isinstance(q.get("query"), str) and isinstance(q.get("relevant"), list)
                and all(isinstance(i, str) and i in nav.nodes for i in q["relevant"]),
                "Invalid evaluation question")
        seen.add(q["id"])
        expected = set(q["relevant"])
        query, intent = q["query"], q.get("intent", "implement")
        anchors = q.get("anchors", [])
        require(isinstance(anchors, list) and all(isinstance(i, str) and i in nav.nodes for i in anchors),
                "Unknown evaluation anchor")
        # Compare same inputs: both baselines may use the explicitly provided anchors.
        lexical = list(dict.fromkeys(anchors + nav.lexical(query, set(nav.nodes))))
        ranked = list(dict.fromkeys(anchors + nav.search(query, intent=intent)))
        active, paths, cut = nav.plan(query, anchors, intent, 2)
        variants = {}
        for name, ids, explanation in (("bm25", lexical, None), ("ranked", ranked, None),
                                       ("active", active, paths)):
            response = nav.render(ids, limit=k, paths=explanation, cut=cut if name == "active" else False)
            actual = [n["id"] for n in response["results"]]
            variants[name] = {"metrics": metrics(actual, expected, k), "retrieved": actual,
                              "response_bytes": len(json.dumps(response, ensure_ascii=False,
                                                                separators=(",", ":")).encode())}
        pack = context_pack(nav, {"schemaVersion":1, "kind":"context-pack-input", "project":corpus["project"],
                                  "steps":[{"query":query, "anchors":anchors, "intent":intent}]})
        actual = list(dict.fromkeys(n["id"] for step in pack["steps"]
                                   for n in step["response"]["results"]))[:k]
        variants["adaptive"] = {"metrics": metrics(actual, expected, k), "retrieved": actual,
                                "response_bytes": len(json.dumps(pack, ensure_ascii=False,
                                                                 separators=(",", ":")).encode()),
                                "calls": pack["calls"]}
        rows.append({"id": q["id"], "variants": variants})
    aggregate = {}
    for variant in ("bm25", "ranked", "active", "adaptive"):
        values = [r["variants"][variant] for r in rows]
        summary = {}
        for name in ("precision_at_k", "recall_at_k", "mrr", "ndcg_at_k", "correct_abstention"):
            numbers = [v["metrics"][name] for v in values if v["metrics"][name] is not None]
            summary[name] = sum(numbers) / len(numbers) if numbers else None
        summary["mean_response_bytes"] = sum(v["response_bytes"] for v in values) / len(values)
        aggregate[variant] = summary
    return {"status": "evaluated", "project": corpus["project"], "k": k,
            "questions": len(rows), "aggregate": aggregate, "rows": rows,
            "warning": "Labeled retrieval fixture only; not task success or model training."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("corpus", type=Path)
    p.add_argument("questions", type=Path)
    p.add_argument("--k", type=int, default=5)
    a = p.parse_args()
    print(json.dumps(evaluate(load_json(a.corpus), load_json(a.questions), a.k),
                     ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
