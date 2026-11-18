"""Explicit Markdown input and JSON snapshot adapters, without subprocesses."""
from __future__ import annotations

import json
from pathlib import Path

from model import MAX_BYTES, make_corpus, node, require


def parse_note(path: Path) -> tuple[dict, list]:
    """Read the documented OKF-compatible JSON-flow YAML subset, not arbitrary YAML."""
    require(path.is_file() and path.stat().st_size <= MAX_BYTES, "Missing or oversized note")
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    require(bool(lines) and lines[0] == "---", "Expected note front matter")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise ValueError("Unterminated front matter") from None
    meta = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, sep, val = line.partition(":")
        require(bool(sep) and key not in meta, "Invalid or duplicate metadata key")
        meta[key] = json.loads(val.strip())
    ext = meta.get("x_knowledge")
    require(isinstance(ext, dict), "Missing x_knowledge extension")
    require(isinstance(meta.get("type"), str), "Missing OKF type")
    i = ext["id"]
    n = node(i, meta["type"], meta["title"], ext["summary"], level=ext["level"],
             contexts=ext.get("contexts", []), tags=meta.get("tags", []),
             aliases=ext.get("aliases", []), claim_state=ext.get("claim_state", "unknown"),
             sources=ext.get("sources", []), body="\n".join(lines[end + 1:]).strip())
    relations = ext.get("relations", [])
    require(isinstance(relations, list), "Invalid note relations")
    edges = []
    for edge in relations:
        require(isinstance(edge, dict) and "from" not in edge, "Malformed outgoing relation")
        edges.append({"from": i, **edge})
    return n, edges


def markdown_corpus(root: Path, project: str) -> dict:
    """Root is explicitly selected; skip generated index and never follow symlinks."""
    require(root.is_dir() and not root.is_symlink(), "Expected explicit Markdown root")
    root = root.resolve()
    nodes, edges = [], []
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root)
        if p.name == "index.md" or any(part.startswith(".") for part in rel.parts):
            continue
        require(p.resolve().is_relative_to(root) and not any(
            (root / Path(*rel.parts[:j])).is_symlink() for j in range(1, len(rel.parts) + 1)),
                "Symlink in knowledge root")
        n, outgoing = parse_note(p)
        nodes.append(n)
        edges.extend(outgoing)
    return make_corpus(project, nodes, edges)
