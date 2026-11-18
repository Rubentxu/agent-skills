"""Neutral read-only knowledge contract. No host permissions or writes."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}\Z")
LEVELS = {"L0", "L1", "L2", "L3"}
PROVIDERS = {"backlog", "markdown", "snapshot", "git", "cognicode", "groma", "external"}
STATES = {"unknown", "proposed", "observed", "inferred", "verified", "contradicted", "stale", "superseded"}
RELATIONS = {"about", "supports", "contradicts", "investigates", "threatens", "constrains",
             "motivates", "supersedes", "implements", "affects", "validates", "maps_to",
             "related", "requires", "realizes", "governs", "verified_by", "violates",
             "derived_from", "applies_to", "exemplifies", "contains", "depends_on"}
MAX_BYTES = 16 * 1024 * 1024


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def identifier(value: Any) -> bool:
    return isinstance(value, str) and ID.fullmatch(value) is not None


def strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value)


def load_json(path: Path) -> dict:
    require(path.is_file() and path.stat().st_size <= MAX_BYTES, "Missing or oversized JSON input")
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "Expected JSON object")
    return data


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def validate(corpus: dict) -> dict:
    """Validate structure, not truth, authority, coverage or runtime evidence."""
    require(isinstance(corpus, dict) and corpus.get("schemaVersion") == 2
            and corpus.get("kind") == "knowledge-corpus", "Expected knowledge-corpus v2")
    require(identifier(corpus.get("project")), "Explicit project ID required")
    require(corpus.get("coverage") in ("partial", "declared-complete"), "Explicit coverage required")
    nodes, edges = corpus.get("nodes"), corpus.get("edges")
    require(isinstance(nodes, list) and isinstance(edges, list), "Expected nodes and edges")
    ids = {}
    for n in nodes:
        require(isinstance(n, dict) and identifier(n.get("id")), "Invalid node ID")
        i = n["id"]
        require(i not in ids, f"Duplicate identity: {i}")
        require(n.get("level") in LEVELS and identifier(n.get("kind")), f"Invalid level/kind: {i}")
        for key in ("title", "summary"):
            require(isinstance(n.get(key), str) and n[key].strip(), f"Missing {key}: {i}")
        require(isinstance(n.get("body", ""), str), f"Invalid body: {i}")
        for key in ("contexts", "aliases", "tags"):
            require(strings(n.get(key, [])), f"Invalid {key}: {i}")
        require(n.get("claim_state", "unknown") in STATES, f"Invalid claim state: {i}")
        srcs = n.get("sources", [])
        require(isinstance(srcs, list), f"Invalid sources: {i}")
        for s in srcs:
            require(isinstance(s, dict) and s.get("provider") in PROVIDERS
                    and isinstance(s.get("locator"), str) and s["locator"].strip(),
                    f"Invalid source: {i}")
            require(all(isinstance(s[k], str) and s[k].strip()
                        for k in ("revision", "digest") if k in s), f"Invalid source pin: {i}")
        if n["level"] == "L0" or n.get("claim_state") == "verified":
            require(bool(srcs), f"Evidence or verified claim needs source: {i}")
        ids[i] = n
    seen = set()
    for e in edges:
        require(isinstance(e, dict) and identifier(e.get("from")) and identifier(e.get("to"))
                and isinstance(e.get("predicate"), str) and e["predicate"] in RELATIONS,
                "Invalid relationship")
        a, b, pred = e["from"], e["to"], e["predicate"]
        require(a in ids and b in ids, f"Unresolved relationship: {a} -> {b}")
        require((a, pred, b) not in seen, f"Duplicate relationship: {a} {pred} {b}")
        seen.add((a, pred, b))
        if pred == "contains":
            require(int(ids[a]["level"][1]) > int(ids[b]["level"][1]), "Containment must descend")
        if "reason" in e:
            require(isinstance(e["reason"], str) and e["reason"].strip(), "Invalid relationship reason")
    return corpus


def make_corpus(project: str, nodes: list, edges: list, coverage: str = "partial") -> dict:
    return validate({"schemaVersion": 2, "kind": "knowledge-corpus", "project": project,
                     "coverage": coverage, "nodes": nodes, "edges": edges})


def node(i: str, kind: str, title: str, summary: str, **kw: Any) -> dict:
    return {"id": i, "level": "L1", "kind": kind, "title": title, "summary": summary, **kw}


def v1_to_v2(data: dict, project: str) -> dict:
    """Lossless semantic projection for supported v1 fields; never upgrades authority."""
    require(data.get("schemaVersion") == 1 and data.get("kind") == "knowledge-corpus",
            "Expected knowledge-corpus v1")
    require(isinstance(data.get("terms"), list) and isinstance(data.get("documents"), list),
            "Expected v1 terms/documents")
    nodes, edges, mapping = [], [], {}
    for t in data["terms"]:
        require(isinstance(t, dict) and identifier(t.get("id")), "Invalid term")
        i = "term:" + t["id"]
        require(t["id"] not in mapping, "Ambiguous v1 identity")
        mapping[t["id"]] = i
        nodes.append(node(i, "term", t["label"], t["definition"], contexts=[t["context"]],
                          aliases=t.get("aliases", []), claim_state="proposed",
                          legacy_status=t.get("status", "proposed")))
    for d in data["documents"]:
        require(isinstance(d, dict) and identifier(d.get("id")), "Invalid document")
        i = "doc:" + d["id"]
        require(d["id"] not in mapping, "Ambiguous v1 identity")
        mapping[d["id"]] = i
        tags = d.get("tags", [])
        require(strings(tags), "Invalid v1 tags")
        kinds = [x[5:] for x in tags if x.startswith("kind:")]
        body = d["content"]
        nodes.append(node(i, kinds[0] if len(kinds) == 1 else "document", d["title"],
                          d["title"], body=body, tags=tags,
                          contexts=[x[4:] for x in tags if x.startswith("ctx:")],
                          claim_state="unknown", legacy_status=d.get("status", "draft"),
                          legacy_type=d["type"], legacy_sources=d.get("sources", []),
                          sources=[{"provider": "backlog", "locator": d["id"]}]))
    for d in data["documents"]:
        a = mapping[d["id"]]
        for t in d.get("tags", []):
            if t.startswith("term:"):
                require(t[5:] in mapping, f"Unknown term {t}")
                edges.append({"from": a, "predicate": "about", "to": mapping[t[5:]]})
        for e in d.get("relations", []):
            require(e["target"] in mapping, "Unknown v1 target")
            edges.append({"from": a, "predicate": e["predicate"], "to": mapping[e["target"]],
                          "legacy_terms": e.get("terms", [])})
    return make_corpus(project, nodes, edges)


def include_backlog(corpus: dict, snapshot: dict) -> dict:
    """Only observed JSON envelopes; doc bodies remain in the normalized v1 corpus."""
    validate(corpus)
    kind = snapshot.get("kind")
    require(snapshot.get("schemaVersion") == 1 and kind in ("task-list", "decision-list"),
            "Unsupported Backlog envelope")
    key, prefix = ("tasks", "task:") if kind == "task-list" else ("decisions", "decision:")
    require(isinstance(snapshot.get(key), list), "Expected Backlog records")
    nodes = list(corpus["nodes"])
    edges = list(corpus["edges"])
    for item in snapshot[key]:
        require(isinstance(item, dict) and identifier(item.get("id"))
                and isinstance(item.get("title"), str), "Malformed Backlog record")
        i = prefix + item["id"]
        detail = {k: item[k] for k in ("status", "archived", "description", "finalSummary",
                                      "decision", "context", "consequences", "acceptanceCriteria",
                                      "documentation", "references", "dependencies", "supersededBy")
                  if k in item}
        nodes.append(node(i, "task" if key == "tasks" else "decision", item["title"], item["title"],
                          level="L0" if key == "tasks" else "L1", claim_state="observed",
                          native_status=item.get("status"), native_fields=detail,
                          body=json.dumps(detail, ensure_ascii=False, sort_keys=True),
                          sources=[{"provider": "backlog", "locator": item["id"]}]))
    ids = {n["id"] for n in nodes}
    for item in snapshot[key]:
        i = prefix + item["id"]
        if key == "tasks" and isinstance(item.get("dependencies"), list):
            for dep in item["dependencies"]:
                if isinstance(dep, str) and "task:" + dep in ids:
                    edge = {"from": i, "predicate": "depends_on", "to": "task:" + dep}
                    if edge not in edges:
                        edges.append(edge)
        if key == "decisions" and isinstance(item.get("supersededBy"), str):
            target = "decision:" + item["supersededBy"]
            if target in ids:
                edges.append({"from": target, "predicate": "supersedes", "to": i})
    return make_corpus(corpus["project"], nodes, edges, "partial")
