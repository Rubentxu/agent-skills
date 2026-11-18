"""Prepare knowledge maintenance candidates without saving them or approving claims."""
from __future__ import annotations

from model import validate, make_corpus, require, digest
from retrieval import Navigator, normalize


def reconcile(corpus: dict, proposal: dict) -> dict:
    """A deterministic advisory operation. Semantic equality requires human/agent review."""
    validate(corpus)
    validate(proposal)
    require(corpus["project"] == proposal["project"], "Proposal project mismatch")
    require(len(proposal["nodes"]) == 1, "Provide exactly one candidate atom")
    candidate = dict(proposal["nodes"][0])
    require(candidate["level"] == "L1", "Propose one L1 atom; maps are maintained separately")
    nav = Navigator(corpus)
    i = candidate["id"]
    # Match identities and exact normalized assertions, not merely word overlap.
    matches = sorted(n["id"] for n in corpus["nodes"]
                     if n["kind"] == candidate["kind"] and
                     normalize(n["summary"]).strip() == normalize(candidate["summary"]).strip() and
                     set(n.get("contexts", [])) == set(candidate.get("contexts", [])))
    query = candidate["title"] + " " + candidate["summary"]
    nearby = nav.search(query, intent="architecture", kind=candidate["kind"])[:5]
    if i in nav.nodes:
        action = "KEEP_AS_IS" if digest(nav.nodes[i]) == digest(candidate) else "REVIEW_EXISTING"
    elif matches:
        action = "REVIEW_DUPLICATE"
    else:
        action = "PROPOSE_STORE"
    return {"status": "proposal-only", "project": corpus["project"], "candidate": i,
            "action": action, "same_assertion_candidates": matches,
            "nearby": nav.render(nearby, detail="identity", limit=5, budget=4000),
            "provenance": "declared-not-verified",
            "warning": "No writes. Similarity is not equivalence; compare scope, sources, authority and contradictions before choosing REFINE, LINK, CONFLICT, SUPERSEDE, STORE or SKIP."}


def map_candidates(corpus: dict) -> dict:
    """Suggest tracks by explicit contexts and unlocated atoms; no generated claims."""
    validate(corpus)
    nav = Navigator(corpus)
    contexts = {}
    for n in corpus["nodes"]:
        if n["level"] != "L1":
            continue
        for ctx in n.get("contexts", []):
            contexts.setdefault(ctx, []).append(n["id"])
    tracks = {n["id"] for n in corpus["nodes"] if n["level"] == "L2"}
    unlocated = [n["id"] for n in corpus["nodes"] if n["level"] == "L1" and
                 not any(e["predicate"] == "contains" and e["from"] in tracks
                         for e in nav.inc[n["id"]])]
    return {"status": "candidates", "project": corpus["project"],
            "contexts": [{"context": ctx, "atoms": sorted(set(ids))}
                         for ctx, ids in sorted(contexts.items())],
            "unlocated_atoms": sorted(unlocated),
            "has_profile": any(n["level"] == "L3" for n in corpus["nodes"]),
            "warning": "These are explicit labels, not invented bounded contexts or approved structure notes."}
