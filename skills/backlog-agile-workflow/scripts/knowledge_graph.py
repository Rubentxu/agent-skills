#!/usr/bin/env python3
"""Pure validation and opt-in OKF v0.2 projection of a Backlog knowledge snapshot.

Does not invoke Backlog.md, write its records, infer approvals, or access the network.
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path
from typing import Any

TERM = re.compile(r"[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+")
ID = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}")
PREDICATES = frozenset({"supports", "contradicts", "investigates", "threatens", "constrains",
                        "motivates", "supersedes", "implements", "affects", "validates", "maps_to", "related"})
STATUSES = frozenset({"proposed", "validated", "deprecated"})


def validate(corpus: dict[str, Any]) -> list[dict[str, str]]:
    """Check only declared facts; never derive domain terms from keyword similarity."""
    problems: list[dict[str, str]] = []

    def issue(code: str, location: str, detail: str) -> None:
        problems.append({"code": code, "at": location, "detail": detail})

    if not isinstance(corpus, dict) or corpus.get("schemaVersion") != 1 or corpus.get("kind") != "knowledge-corpus":
        return [{"code": "CORPUS", "at": "root", "detail": "Expected knowledge-corpus schemaVersion 1"}]
    terms, docs = corpus.get("terms"), corpus.get("documents")
    if not isinstance(terms, list) or not isinstance(docs, list):
        return [{"code": "CORPUS", "at": "root", "detail": "terms and documents must be arrays"}]
    term_ids: set[str] = set()
    labels: set[tuple[str, str]] = set()
    for i, t in enumerate(terms):
        at = f"terms[{i}]"
        if not isinstance(t, dict):
            issue("TERM", at, "Expected object")
            continue
        tid, ctx, label = t.get("id"), t.get("context"), t.get("label")
        if not isinstance(tid, str) or not TERM.fullmatch(tid) or not isinstance(ctx, str) or not tid.startswith(ctx + "."):
            issue("TERM_ID", at, "Use a canonical context.concept identifier")
            continue
        if tid in term_ids:
            issue("DUPLICATE_TERM", at, tid)
        term_ids.add(tid)
        if not isinstance(label, str) or not label.strip() or not isinstance(t.get("definition"), str) or not t["definition"].strip():
            issue("TERM_DEFINITION", at, "Label and definition are required")
        elif (ctx, label.casefold()) in labels:
            issue("AMBIGUOUS_LABEL", at, f"Duplicate label in {ctx}: {label}")
        else:
            labels.add((ctx, label.casefold()))
        if t.get("status", "proposed") not in STATUSES:
            issue("TERM_STATUS", at, "Invalid glossary status")
        aliases = t.get("aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(a, str) or not a.strip() for a in aliases):
            issue("ALIASES", at, "Aliases must be nonempty strings")
    doc_ids: set[str] = set()
    all_document_ids = {d.get("id") for d in docs if isinstance(d, dict) and isinstance(d.get("id"), str)}
    for i, d in enumerate(docs):
        at = f"documents[{i}]"
        if not isinstance(d, dict):
            issue("DOCUMENT", at, "Expected object")
            continue
        did = d.get("id")
        if not isinstance(did, str) or not ID.fullmatch(did):
            issue("DOCUMENT_ID", at, "Unsafe or absent document id")
            continue
        if did in doc_ids:
            issue("DUPLICATE_DOCUMENT", at, did)
        doc_ids.add(did)
        if not isinstance(d.get("title"), str) or not d["title"].strip() or not isinstance(d.get("content"), str):
            issue("DOCUMENT_BODY", at, "Title and content required")
        if not isinstance(d.get("type"), str) or not d["type"].strip():
            issue("DOCUMENT_TYPE", at, "OKF type required")
        if d.get("status", "draft") not in {"draft", "stable", "deprecated"}:
            issue("DOCUMENT_STATUS", at, "Unknown OKF status")
        tags = d.get("tags")
        if not isinstance(tags, list) or any(not isinstance(t, str) or not t.strip() for t in tags):
            issue("TAGS", at, "tags must be strings")
            tags = []
        attached = [tag[5:] for tag in tags if tag.startswith("term:")]
        if not attached:
            issue("UNTAGGED", at, "At least one canonical term tag required")
        for term in attached:
            if term not in term_ids:
                issue("UNKNOWN_TERM", at, term)
            if "ctx:" + term.split(".")[0] not in tags:
                issue("CONTEXT_TAG", at, term)
        if len(set(attached)) != len(attached):
            issue("DUPLICATE_TAG", at, "Repeated term tag")
        relations = d.get("relations", [])
        if not isinstance(relations, list):
            issue("RELATIONS", at, "relations must be an array")
            continue
        for j, edge in enumerate(relations):
            loc = f"{at}.relations[{j}]"
            if not isinstance(edge, dict) or edge.get("predicate") not in PREDICATES:
                issue("PREDICATE", loc, "Unrecognized relationship")
                continue
            target = edge.get("target")
            if not isinstance(target, str) or target not in term_ids and target not in all_document_ids:
                issue("UNRESOLVED", loc, str(target))
            edge_terms = edge.get("terms")
            if not isinstance(edge_terms, list) or not edge_terms:
                issue("RELATION_TERMS", loc, "Tag each semantic relationship")
            elif any(t not in attached for t in edge_terms):
                issue("RELATION_TERMS", loc, "Relationship terms must also tag its source document")
    return problems


def graph(corpus: dict[str, Any]) -> dict[str, Any]:
    """Deterministic derived graph; no extra persisted authority."""
    nodes = ([{"id": t["id"], "kind": "term", "context": t["context"]} for t in corpus["terms"]]
             + [{"id": d["id"], "kind": "document", "type": d["type"]} for d in corpus["documents"]])
    edges = []
    for doc in corpus["documents"]:
        for tag in doc["tags"]:
            if tag.startswith("term:"):
                edges.append({"from": doc["id"], "predicate": "about", "to": tag[5:]})
        for rel in doc.get("relations", []):
            edges.append({"from": doc["id"], "predicate": rel["predicate"], "to": rel["target"], "terms": rel["terms"]})
    return {"nodes": sorted(nodes, key=lambda n: n["id"]),
            "edges": sorted(edges, key=lambda e: (e["from"], e["predicate"], e["to"]))}


def _yaml(meta: dict[str, Any]) -> str:
    """JSON flow values are YAML 1.2 values; no PyYAML dependency or unsafe escaping."""
    return "---\n" + "".join(f"{key}: {json.dumps(value, ensure_ascii=False)}\n" for key, value in meta.items()) + "---\n\n"


def _path(identifier: str, is_term: bool) -> str:
    return ("glossary/" if is_term else "concepts/") + identifier + ".md"


def export_okf(corpus: dict[str, Any], target: Path) -> list[str]:
    """Create a new OKF bundle only, never overwrite an existing directory."""
    if target.exists():
        raise ValueError("Output already exists; refusing to overwrite")
    target.parent.mkdir(parents=True, exist_ok=True)
    docs = {d["id"]: d for d in corpus["documents"]}
    terms = {t["id"]: t for t in corpus["terms"]}
    with tempfile.TemporaryDirectory(prefix="okf-", dir=target.parent) as tmp:
        root = Path(tmp)
        files = []
        for t in sorted(terms.values(), key=lambda x: x["id"]):
            path = _path(t["id"], True)
            content = _yaml({"type": "Domain Term", "title": t["label"], "tags": ["ctx:" + t["context"], "term:" + t["id"]],
                             "status": "deprecated" if t.get("status") == "deprecated" else "draft",
                             "x_domain": {"id": t["id"], "context": t["context"], "aliases": t.get("aliases", []), "state": t.get("status", "proposed")}})
            content += "# " + t["label"] + "\n\n" + t["definition"] + "\n"
            dest = root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            files.append(path)
        for d in sorted(docs.values(), key=lambda x: x["id"]):
            path = _path(d["id"], False)
            refs = [{"predicate": rel["predicate"], "target": rel["target"], "terms": rel["terms"]} for rel in d.get("relations", [])]
            meta = {"type": d["type"], "title": d["title"], "tags": d["tags"], "status": d.get("status", "draft"),
                    "x_domain": {"terms": [tag[5:] for tag in d["tags"] if tag.startswith("term:")], "relations": refs},
                    "x_backlog": {"document_id": d["id"]}}
            if d.get("sources"):
                meta["sources"] = d["sources"]
            content = _yaml(meta) + d["content"].rstrip() + "\n"
            if refs:
                content += "\n## Semantic links\n\n"
                for ref in refs:
                    link = _path(ref["target"], ref["target"] in terms)
                    content += f"- {ref['predicate']}: [{ref['target']}](/" + link + ")\n"
            dest = root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            files.append(path)
        index = "# Knowledge index\n\n" + "".join(f"- [{p}](/" + p + ")\n" for p in sorted(files))
        (root / "index.md").write_text(index, encoding="utf-8")
        root.rename(target)
    return sorted(files + ["index.md"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path, help="normalized ephemeral Backlog CLI snapshot JSON")
    parser.add_argument("--mode", choices=("validate", "graph", "export"), default="validate")
    parser.add_argument("--output", type=Path, help="new output directory for opt-in OKF export")
    args = parser.parse_args()
    corpus = json.loads(args.snapshot.read_text(encoding="utf-8"))
    errors = validate(corpus)
    if errors:
        print(json.dumps({"status": "INVALID", "issues": errors}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    if args.mode == "export":
        if args.output is None:
            parser.error("--output required for export")
        result = {"status": "EXPORTED", "files": export_okf(corpus, args.output)}
    elif args.mode == "graph":
        result = {"status": "VALID", **graph(corpus)}
    else:
        result = {"status": "VALID", "terms": len(corpus["terms"]), "documents": len(corpus["documents"])}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
