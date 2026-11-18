"""Bounded adaptive context packs, no model calls or autonomous provider actions."""
from __future__ import annotations

import json

from model import digest, require
from retrieval import INTENTS, PROFILES
from sections import section_response

CALL_LIMITS = {"quick": 2, "normal": 4, "deep": 8}
DETAILS = {"identity", "summary", "evidence", "full"}


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())


def context_pack(nav, request, *, profile="normal", budget=None):
    require(request.get("schemaVersion") == 1 and request.get("kind") == "context-pack-input"
            and request.get("project") == nav.corpus["project"], "Context pack project mismatch")
    require(profile in PROFILES, "Unknown pack profile")
    limit, depth, default_budget = PROFILES[profile]
    budget = default_budget if budget is None else budget
    require(1024 <= budget <= 64000, "Invalid context pack byte budget")
    steps = request.get("steps")
    require(isinstance(steps, list) and 0 < len(steps) <= 32, "Expected bounded context questions")
    max_calls = request.get("maxCalls", CALL_LIMITS[profile])
    require(type(max_calls) is int and 1 <= max_calls <= CALL_LIMITS[profile], "Invalid pack call budget")
    # Dedup only identical returned representations, not the whole node identity.
    known = set()
    result = {"schemaVersion": 1, "kind": "context-pack", "status": "partial",
              "project": nav.corpus["project"], "coverage": nav.corpus["coverage"],
              "profile": profile, "budget_bytes": budget, "max_calls": max_calls,
              "calls": 0, "steps": [], "omitted_steps": 0,
              "warning": "Derived context only; no provider/tool calls, no external authority."}
    for step in steps:
        require(isinstance(step, dict), "Invalid pack step")
        query = step.get("query", "")
        anchors = step.get("anchors", [])
        intent = step.get("intent", "implement")
        require(isinstance(query,str) and len(query)<=1200 and isinstance(anchors,list)
                and len(anchors)<=16 and all(isinstance(i,str) and i in nav.nodes for i in anchors)
                and intent in INTENTS, "Invalid pack query, scope or intent")
        mode = step.get("mode", "auto")
        require(mode in {"auto", "context", "sections"}, "Unknown pack strategy")
        detail = step.get("detail", "summary")
        require(detail in DETAILS, "Unsupported pack detail")
        remaining = budget - size(result) - 160
        if result["calls"] >= max_calls or remaining < 512:
            result["omitted_steps"] += 1
            continue
        # Orientation prefers the profile and tracks; implementation follows explicit anchors.
        strategy = ("orientation" if mode == "auto" and intent == "understand" and not anchors and not query
                    else "sections" if mode == "sections" else "active")
        result["calls"] += 1
        path_map = None
        if strategy == "sections":
            require(len(anchors)==1, "Section navigation requires one node anchor")
            require(remaining >= 512, "Section budget exhausted")
            response = section_response(nav, anchors[0], query=query, limit=limit, budget=remaining)
        else:
            if strategy == "orientation":
                ids = nav.ids_for_level("L3") + nav.ids_for_level("L2")
                cut = False
                nav.search_cut = False
            else:
                ids, path_map, cut = nav.plan(query, anchors, intent, depth)
                if intent in {"verify", "security"} and detail == "summary":
                    detail = "evidence"
            # Candidate dedup is representation-sensitive, including path and detail.
            response = nav.render(ids, paths=path_map, cut=cut, detail=detail,
                                  limit=limit, budget=remaining)
            fresh = []
            for n in response["results"]:
                key = digest([detail, n])
                if key not in known:
                    known.add(key)
                    fresh.append(n)
                else:
                    response["unchanged"] += 1
            response["results"] = fresh
        entry = {"strategy": strategy, "intent": intent, "detail": detail, "response": response}
        result["steps"].append(entry)
        if size(result) > budget - 32:
            result["steps"].pop()
            result["omitted_steps"] += 1
    if result["omitted_steps"] == 0 and all(s["response"]["status"]=="returned" for s in result["steps"]):
        result["status"] = "returned"
    require(size(result)<=budget, "Pack exceeds aggregate byte budget")
    return result
