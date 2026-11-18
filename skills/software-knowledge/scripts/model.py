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
        if "content_state" in n:
            require(n["content_state"] in ("captured", "metadata-only", "provided"),
                    f"Invalid content state: {i}")
            require(n["content_state"] != "metadata-only" or not n.get("body"),
                    f"Metadata-only node cannot carry body: {i}")
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
    """Project observed v1 envelopes, connecting only exact native IDs and paths.

    Conflicting snapshots are rejected rather than silently preferring newer-looking data.
    Search results are metadata, not document contents. All coverage remains partial.
    """
    validate(corpus)
    require(snapshot.get("schemaVersion") == 1, "Unsupported Backlog envelope")
    kind = snapshot.get("kind")
    records = []
    types = {"task": "task", "document": "doc", "decision": "decision"}
    if kind in ("task-list", "decision-list"):
        key, typ = ("tasks", "task") if kind == "task-list" else ("decisions", "decision")
        require(isinstance(snapshot.get(key), list), "Expected Backlog records")
        records = [(typ, x) for x in snapshot[key]]
    elif kind in ("task-view", "decision-view"):
        typ = kind.removesuffix("-view")
        records = [(typ, snapshot.get(typ))]
    elif kind == "search":
        require(isinstance(snapshot.get("results"), list), "Expected search results")
        for record in snapshot["results"]:
            require(isinstance(record, dict) and record.get("type") in types, "Unsupported search record")
            records.append((record["type"], record.get("data")))
    else:
        raise ValueError("Unsupported Backlog envelope")

    nodes = {n["id"]: dict(n) for n in corpus["nodes"]}
    edges = {(e["from"], e["predicate"], e["to"]): dict(e) for e in corpus["edges"]}

    def link(a, pred, b):
        if a in nodes and b in nodes:
            edges.setdefault((a, pred, b), {"from": a, "predicate": pred, "to": b})

    for typ, item in records:
        require(isinstance(item, dict) and identifier(item.get("id"))
                and isinstance(item.get("title"), str) and item["title"].strip(), "Malformed Backlog record")
        i = types[typ] + ":" + item["id"]
        keys = ("path", "status", "archived", "description", "finalSummary", "decision", "context",
                "consequences", "content", "implementationNotes", "implementationPlan", "acceptanceCriteria", "definitionOfDone", "documentation",
                "references", "dependencies", "supersededBy", "modifiedFiles", "labels", "tags",
                "type", "priority", "isReady", "parentTaskId", "milestone",
                "acceptanceCriteriaCount", "acceptanceCriteriaCompleted", "updatedAt", "date")
        detail = {k: item[k] for k in keys if k in item and item[k] is not None}
        if i in nodes:
            existing = nodes[i]
            require(any(s["provider"] == "backlog" and s["locator"] == item["id"]
                        for s in existing.get("sources", [])), "Conflicting provider identity")
            require(existing["title"] == item["title"], "Conflicting snapshots: " + i)
            earlier = existing.get("native_fields", {})
            require(all(earlier[k] == detail[k] for k in earlier.keys() & detail.keys()),
                    "Conflicting snapshot fields: " + i)
            detail = {**earlier, **detail}
        else:
            tags = item.get("tags", []) if typ == "document" else []
            require(strings(tags), "Invalid document tags")
            kinds = [x[5:] for x in tags if x.startswith("kind:")]
            nodes[i] = node(i, kinds[0] if typ == "document" and len(kinds) == 1 else typ,
                            item["title"], item["title"], level="L0" if typ == "task" else "L1",
                            tags=tags, contexts=[x[4:] for x in tags if x.startswith("ctx:")],
                            claim_state="observed", sources=[{"provider": "backlog", "locator": item["id"]}])
        n = nodes[i]
        n["native_fields"] = detail
        if "status" in detail:
            n["native_status"] = detail["status"]
        if typ != "document":
            n["body"] = (detail["content"] if typ == "decision" and isinstance(detail.get("content"), str)
                         else json.dumps(detail, ensure_ascii=False, sort_keys=True))
            if isinstance(detail.get("description"), str) and 0 < len(detail["description"].strip()) <= 400:
                n["summary"] = detail["description"]

    # Only exact, unambiguous paths from observed document metadata.
    path_ids = {}
    for i, n in nodes.items():
        path = n.get("native_fields", {}).get("path")
        if i.startswith("doc:") and isinstance(path, str):
            path_ids.setdefault(path, []).append(i)
    refs = {n["id"] for n in nodes.values()}
    for i, n in nodes.items():
        fields = n.get("native_fields", {})
        if i.startswith("task:"):
            for dep in fields.get("dependencies", []) or []:
                if isinstance(dep, str):
                    link(i, "depends_on", "task:" + dep)
            for path in fields.get("documentation", []) or []:
                if isinstance(path, str) and len(path_ids.get(path, [])) == 1:
                    link(i, "about", path_ids[path][0])
            for locator in fields.get("references", []) or []:
                if isinstance(locator, str) and locator in refs:
                    link(i, "related", locator)
        if i.startswith("decision:") and isinstance(fields.get("supersededBy"), str):
            link("decision:" + fields["supersededBy"], "supersedes", i)
    return make_corpus(corpus["project"], list(nodes.values()), list(edges.values()), "partial")
