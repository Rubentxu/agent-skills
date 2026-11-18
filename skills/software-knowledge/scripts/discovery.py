"""Progressive discovery: propose durable notes and contextual constitutions, never mutate."""
from __future__ import annotations

import json

from architecture import array, source_ref, text
from model import make_corpus, require, validate
from reconcile import reconcile, map_candidates
from retrieval import Navigator, CRITICAL, SEMANTIC

KINDS = {"invariant", "contract", "convention", "pattern", "decision", "term", "capability",
         "use-case", "finding", "risk", "hypothesis", "lesson", "failed-experiment", "anti-pattern"}
NEGATIVE = {"failed-experiment", "anti-pattern", "lesson"}


def checkpoint(corpus, request, *, budget=12000):
    validate(corpus)
    require(request.get("schemaVersion") == 1 and request.get("kind") == "knowledge-checkpoint"
            and request.get("project") == corpus["project"], "Checkpoint project mismatch")
    require(1024 <= budget <= 64000, "Invalid checkpoint budget")
    nav = Navigator(corpus)
    candidates = array(request.get("candidates", []), "candidate atoms")
    require(len(candidates) <= 20, "Checkpoint has too many candidates")
    items = []
    seen = set()
    # Reconcile sequentially against transient proposals to detect same-checkpoint duplicates.
    working = corpus
    for candidate in candidates:
        require(isinstance(candidate, dict) and candidate.get("level") == "L1"
                and candidate.get("kind") in KINDS, "Expected durable L1 knowledge candidate")
        i = candidate.get("id")
        require(isinstance(i, str) and i not in seen, "Duplicate checkpoint candidate")
        seen.add(i)
        require(candidate.get("claim_state", "proposed") in {"proposed", "unknown", "inferred", "observed"},
                "Checkpoint may not create verified or adjudicated claims")
        require(bool(candidate.get("contexts")) and bool(candidate.get("sources")),
                "Candidate requires explicit scope and evidence reference")
        if candidate["kind"] in NEGATIVE:
            # Negative knowledge is a bounded learning claim, not a universal ban.
            for key in ("attempted", "outcome", "applicability"):
                text(candidate.get("learning", {}).get(key), "negative knowledge " + key, 600)
        proposed = make_corpus(corpus["project"], [candidate], [])
        plan = reconcile(working, proposed)
        action = plan["action"]
        items.append({"id": i, "kind": candidate["kind"], "action": action,
                      "same_assertion_candidates": plan["same_assertion_candidates"],
                      "nearby_ids": [n["id"] for n in plan["nearby"]["results"]],
                      "existing_in_authority": i in nav.nodes,
                      "write_authorized": False})
        if action == "PROPOSE_STORE":
            working = make_corpus(corpus["project"], [*working["nodes"], candidate], working["edges"])
    maps = map_candidates(corpus)
    result = {"status": "proposal-only", "project": corpus["project"], "results": [],
              "omitted": 0, "existing_unlocated_count": len(maps["unlocated_atoms"]),
              "has_profile": maps["has_profile"], "write_authorized": False,
              "warning": "Inspect source and scope before STORE/REFINE/LINK/SKIP. Proposals are not written."}
    for item in items:
        result["results"].append(item)
        if len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()) > budget - 64:
            result["results"].pop()
            result["omitted"] += 1
    require(len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()) <= budget,
            "Checkpoint envelope exceeds budget")
    return result


def constitution(nav, anchors, *, context=None, limit=10, budget=12000):
    """A scoped view of existing rules and conflicts, not a new rule book."""
    require(isinstance(anchors, list) and all(isinstance(i, str) and i in nav.nodes for i in anchors),
            "Unknown constitution anchor")
    require(bool(anchors) or isinstance(context, str) and context.strip(),
            "Select explicit scope or anchors")
    paths, cut = nav.walk(anchors, 2, SEMANTIC) if anchors else ({}, False)
    scoped = {i for i in paths if nav.nodes[i]["kind"] in CRITICAL}
    if context:
        scoped.update(i for i in nav.nodes if nav.nodes[i]["kind"] in CRITICAL
                      and context in nav.nodes[i].get("contexts", []))
    # Direct conflict endpoints remain visible even when not a normative kind.
    conflicts = {i for i in scoped for e in nav.out[i] + nav.inc[i]
                 if e["predicate"] in {"contradicts", "violates", "supersedes"}
                 for i in (e["from"], e["to"])}
    selected = sorted(scoped | conflicts, key=lambda i: (i not in conflicts, i not in anchors, i))
    return nav.render(selected, detail="evidence", limit=limit, budget=budget, cut=cut)
