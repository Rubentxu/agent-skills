#!/usr/bin/env python3
"""Review architectural knowledge against explicit external evidence references.

No source inspection, provider execution, graph replication, or authority escalation.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import sys

from model import digest, identifier, load_json, require, validate
from retrieval import CRITICAL, INTENTS, SEMANTIC, Navigator

PROVIDERS = {"cognicode", "groma", "git", "backlog", "external"}
PLANES = {"static", "curated", "change", "runtime", "test", "unknown"}
MAX_ITEMS = 250


def text(value, name, maximum=400):
    require(isinstance(value, str) and 0 < len(value.strip()) <= maximum
            and len(value) <= maximum and not any(ord(c) < 32 for c in value), "Invalid " + name)
    return value


def path(value):
    value = text(value, "repository-relative path")
    require(not value.startswith("/") and "\\" not in value and ":" not in value
            and all(x not in {"", ".", ".."} for x in value.split("/")), "Invalid repository-relative path")
    return value


def array(value, name):
    require(isinstance(value, list) and len(value) <= MAX_ITEMS, "Invalid or oversized " + name)
    return value


def revision(value):
    if value is None:
        return None
    return text(value, "declared revision", 160)


def source_ref(provider, locator):
    require(isinstance(provider, str) and provider in PROVIDERS, "Unsupported evidence provider")
    return provider, text(locator, "external evidence locator")


def capsule_reference(capsule, locator, project, paths=()):
    """Read a native M5 handoff *as a reference*, never repeat or certify its graph."""
    require(isinstance(capsule, dict) and capsule.get("generator") == "cognicode-diagrams-capsule-v1"
            and capsule.get("schema_version") == 1 and capsule.get("kind") == "agent-handoff",
            "Expected CogniCode M5 capsule")
    e = capsule["evidence"]
    require(e["authority"] == "cognicode" and e["plane"] == "static"
            and capsule["status"] == "PARTIAL_HANDOFF"
            and e["revision_freshness"] == "UNVERIFIED_WITH_RUNTIME",
            "Unexpected capsule contract")
    pin = e.get("derivation_sha256")
    require(isinstance(pin, str) and re.fullmatch(r"[0-9a-f]{64}", pin), "Malformed capsule derivation")
    basis = e.get("basis") or {}
    require(isinstance(basis, dict), "Invalid capsule basis")
    return {"provider": "cognicode", "locator": text(locator, "capsule locator"),
            "project": project, "revision": revision(basis.get("revision")), "digest": digest(capsule),
            "plane": "static", "coverage": "partial",
            "paths": sorted({path(x) for x in paths}),
            "external_ids": {
                "symbol": text(capsule["target"]["symbol_id"], "symbol"),
                "claims": [text(x, "claim ID") for x in array(e.get("claim_ids"), "claims")],
                "queries": [text(x, "query ID") for x in array(e.get("query_ids"), "queries")]},
            "limitation": "Derived capsule reference; runtime freshness and implementation remain unverified."}


def groma_references(payload, project, reference_scope):
    """Existing groma-task-link-input uses host-confirmed IDs; not native ownership output."""
    require(payload.get("schemaVersion") == 1 and payload.get("kind") == "groma-task-link-input",
            "Expected existing Groma task-link input")
    task = payload["task"]
    task_id = text(task["id"], "task ID")
    # Changed files are NOT ownership mappings. Do not attach them to element refs.
    return [{"provider": "groma", "locator": text(i, "Groma element ID"), "project": project,
             "revision": None, "plane": "curated", "coverage": "unknown", "paths": [],
             "external_ids": {"task": task_id, "scope": text(reference_scope, "scope")},
             "limitation": "Host-confirmed element reference, not proof of ownership or implementation."}
            for i in array(payload.get("confirmedElementIds"), "Groma elements")]


def observations(data, project):
    refs = {}
    for row in array(data.get("observations", []), "observations"):
        require(isinstance(row, dict) and row.get("project") == project, "Cross-project observation")
        k = source_ref(row.get("provider"), row.get("locator"))
        require(k not in refs, "Duplicate evidence identity")
        require(row.get("plane") in PLANES and row.get("coverage") in {"partial", "unknown", "complete"},
                "Invalid observation plane or coverage")
        paths = sorted({path(x) for x in array(row.get("paths", []), "observed paths")})
        pin = row.get("digest")
        require(pin is None or isinstance(pin, str) and re.fullmatch(r"[0-9a-f]{64}", pin), "Invalid evidence digest")
        # Omit raw graph, code, claims or arbitrary provider payloads.
        refs[k] = {"provider": k[0], "locator": k[1], "plane": row["plane"],
                   "coverage": row["coverage"], "revision": revision(row.get("revision")),
                   "paths": paths}
        if pin:
            refs[k]["digest"] = pin
    return refs


def review(corpus, data, *, limit=20, budget=12000):
    validate(corpus)
    require(data.get("schemaVersion") == 1 and data.get("kind") == "architecture-review-input"
            and data.get("project") == corpus["project"], "Invalid review project or contract")
    require(1 <= limit <= 50 and 1024 <= budget <= 64000, "Invalid review budget")
    intent = data.get("intent", "architecture")
    require(intent in INTENTS, "Unknown intent")
    current = revision(data.get("revision"))
    changed = {path(x) for x in array(data.get("changedPaths", []), "changed paths")}
    nav = Navigator(corpus)
    refs = observations(data, corpus["project"])
    bindings = defaultdict(set)
    pin_mismatches = set()
    known_locations = defaultdict(set)
    reasons = defaultdict(list)
    for i,n in nav.nodes.items():
        # A Git locator only matches an exact repository-relative path.
        for s in n.get("sources", []):
            if s["provider"] in PROVIDERS:
                k = (s["provider"], s["locator"])
                if k in refs:
                    bindings[k].add(i)
                    if any(s.get(field) and s.get(field) != refs[k].get(field) for field in ("digest", "revision")):
                        pin_mismatches.add((i, k))
                if s["provider"] == "git" and s["locator"] in changed:
                    known_locations[i].add(s["locator"])
        for f in n.get("native_fields", {}).get("modifiedFiles", []) or []:
            if isinstance(f, str) and f in changed:
                known_locations[i].add(f)
    for row in array(data.get("bindings", []), "review bindings"):
        require(isinstance(row, dict) and row.get("node") in nav.nodes, "Unknown binding node")
        k = source_ref(row.get("provider"), row.get("locator"))
        require(k in refs, "Binding without observed reference")
        bindings[k].add(row["node"])
    for i, paths in known_locations.items():
        reasons[i].append({"reason": "exact-changed-path", "paths": sorted(paths)})
    for k, ref in refs.items():
        if current is None or ref["revision"] is None:
            freshness = "unknown"
        elif ref["revision"] != current:
            freshness = "different-declared-revision"
        else:
            freshness = "same-declared-revision-not-live-verified"
        ref["freshness"] = freshness
        affected = sorted(changed & set(ref["paths"]))
        for i in sorted(bindings[k]):
            if affected or (i, k) in pin_mismatches or freshness != "same-declared-revision-not-live-verified":
                reasons[i].append({"reason": "external-evidence-review", "provider": k[0],
                                   "locator": k[1], "paths": affected, "freshness": freshness,
                                   "plane": ref["plane"], "coverage": ref["coverage"], "revision": ref["revision"],
                                   "digest": ref.get("digest"), "source_pin_mismatch": (i,k) in pin_mismatches})
    for f in array(data.get("findings", []), "findings"):
        require(isinstance(f, dict) and f.get("node") in nav.nodes, "Unknown finding node")
        k = source_ref(f.get("provider"), f.get("locator"))
        require(k in refs and f["node"] in bindings[k], "Unbound finding reference")
        require(f.get("kind") in {"possible-contradiction", "missing-evidence", "possible-drift"},
                "Unsupported finding")
        reason = text(f.get("reason"), "finding reason", 600)
        item = {"reason": f["kind"], "provider": k[0], "locator": k[1], "detail": reason}
        reasons[f["node"]].append(item)
    anchors = array(data.get("anchors", []), "anchors")
    require(all(isinstance(i, str) and i in nav.nodes for i in anchors), "Unknown review anchor")
    for i in anchors:
        reasons[i].append({"reason": "explicit-anchor"})
    seeds = sorted(reasons, key=lambda i: (i not in anchors, nav.nodes[i]["kind"] not in CRITICAL, i))
    selected = seeds[:80]
    reached, cut = nav.walk(selected, 2, SEMANTIC) if selected else ({}, False)
    ordered = sorted(reached, key=lambda i: (i not in anchors, i not in reasons,
                                              nav.nodes[i]["kind"] not in CRITICAL,
                                              nav.nodes[i]["kind"] not in INTENTS[intent],
                                              reached[i][0], i))
    result = {"schemaVersion": 1, "kind": "architecture-review", "status": "candidates",
              "project": corpus["project"], "coverage": corpus["coverage"], "intent": intent,
              "revision": current, "changed_path_count": len(changed), "direct_count": len(seeds),
              "candidate_count": len(ordered), "cut": cut or len(seeds) > len(selected),
              "results": [], "omitted": 0, "edit_authorized": False,
              "warning": "Review candidates only. Absence is not proof of safety; no claim state changed."}
    def size():
        return len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode())
    for i in ordered:
        n = nav.nodes[i]
        item = {"id": i, "kind": n["kind"], "title": n["title"],
                "claim_state": n.get("claim_state", "unknown"), "reasons": reasons.get(i, []),
                "path": reached[i][1], "_links": [{"action": "get", "id": i, "detail": "evidence"}]}
        if len(result["results"]) >= limit:
            result["omitted"] += 1
            continue
        result["results"].append(item)
        if size() > budget - 64:
            result["results"].pop()
            result["omitted"] += 1
    if result["omitted"] or result["cut"]:
        result["status"] = "partial"
    elif not ordered:
        result["status"] = "unknown"
    require(size() <= budget, "Review envelope exceeds budget")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    rp = sub.add_parser("review")
    rp.add_argument("corpus", type=Path)
    rp.add_argument("input", type=Path)
    rp.add_argument("--limit", type=int, default=20)
    rp.add_argument("--budget-bytes", type=int, default=12000)
    cp = sub.add_parser("capsule-ref")
    cp.add_argument("input", type=Path)
    cp.add_argument("--project", required=True)
    cp.add_argument("--locator", required=True)
    cp.add_argument("--path", action="append", default=[])
    gp = sub.add_parser("groma-refs")
    gp.add_argument("input", type=Path)
    gp.add_argument("--project", required=True)
    gp.add_argument("--scope", required=True)
    a = p.parse_args()
    try:
        if a.command == "review":
            result = review(load_json(a.corpus), load_json(a.input), limit=a.limit, budget=a.budget_bytes)
        else:
            require(identifier(a.project), "Explicit valid project required")
            data = load_json(a.input)
            if a.command == "capsule-ref":
                result = capsule_reference(data, a.locator, a.project, a.path)
            else:
                result = {"project": a.project, "observations": groma_references(data, a.project, a.scope)}
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(json.dumps({"status":"invalid-input", "error":str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
