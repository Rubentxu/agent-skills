"""Read-only comparison and explicitly requested new Markdown projections."""
from __future__ import annotations

from collections import defaultdict, deque
import json
from pathlib import Path
import tempfile
from urllib.parse import quote

from model import validate, digest, require


def compare(before: dict, after: dict) -> dict:
    validate(before)
    validate(after)
    require(before["project"] == after["project"], "Different project identities")
    b = {n["id"]: digest(n) for n in before["nodes"]}
    a = {n["id"]: digest(n) for n in after["nodes"]}
    added = set(a) - set(b)
    missing = set(b) - set(a)
    changed = {i for i in a.keys() & b.keys() if a[i] != b[i]}
    be = {(e["from"], e["predicate"], e["to"]): digest(e) for e in before["edges"]}
    ae = {(e["from"], e["predicate"], e["to"]): digest(e) for e in after["edges"]}
    edge_changes = {e for e in be.keys() | ae.keys() if be.get(e) != ae.get(e)}
    seeds = added | changed | missing | {i for e in edge_changes for i in (e[0], e[2])}
    # Propagate only to containing maps; no automatic STALE or deletion.
    parents = defaultdict(set)
    for x, pred, y in be.keys() | ae.keys():
        if pred == "contains":
            parents[y].add(x)
    seen = set(seeds)
    queue = deque(sorted(seeds))
    while queue:
        for i in sorted(parents[queue.popleft()]):
            if i not in seen:
                seen.add(i)
                queue.append(i)
    return {"status": "candidates", "project": after["project"],
            "added": sorted(added), "changed": sorted(changed),
            "missing_from_after": sorted(missing),
            "edge_changes": [list(e) for e in sorted(edge_changes)],
            "review_maps": sorted((seen - seeds) & set(a)),
            "coverage": {"before": before["coverage"], "after": after["coverage"]},
            "warning": "Missing or changed is not proof of deletion, contradiction or stale knowledge."}


def _meta(data: dict) -> str:
    return "---\n" + "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in data.items()) + "---\n\n"


def _label(s: str) -> str:
    # Avoid injecting links or headings into the generated navigation.
    return s.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]").replace("\n", " ").replace("\r", " ")


def export_markdown(corpus: dict, target: Path) -> dict:
    """Explicit non-overwriting snapshot; links relative and both directions visible."""
    validate(corpus)
    require(not target.exists() and not target.is_symlink(), "Output already exists")
    require(target.parent.is_dir(), "Output parent must exist")
    nodes = {n["id"]: n for n in corpus["nodes"]}
    paths = {i: f"{digest(i)[:32]}.md" for i in nodes}
    require(len(set(paths.values())) == len(paths), "Filename collision")
    outgoing, incoming = defaultdict(list), defaultdict(list)
    for e in sorted(corpus["edges"], key=lambda x: (x["from"], x["predicate"], x["to"])):
        outgoing[e["from"]].append(e)
        incoming[e["to"]].append(e)
    with tempfile.TemporaryDirectory(prefix=".knowledge-", dir=target.parent) as temp:
        root = Path(temp) / "bundle"
        root.mkdir(mode=0o700)
        (root / "notes").mkdir(mode=0o700)
        index = ["# Knowledge snapshot", "", "Read-only derived view. Coverage: " + corpus["coverage"],
                 "", "Canonical snapshot: [corpus.json](corpus.json)", ""]
        for level in ("L3", "L2", "L1", "L0"):
            index.extend(["## " + level, ""])
            for i in sorted(nodes):
                n = nodes[i]
                if n["level"] != level:
                    continue
                index.append(f"- [{_label(n['title'])}](notes/{paths[i]}) — {i}")
                meta = {"type": n["kind"], "title": n["title"], "tags": n.get("tags", []),
                        "status": "draft",
                        "x_knowledge": {"id": i, "level": n["level"], "summary": n["summary"],
                                        "contexts": n.get("contexts", []), "aliases": n.get("aliases", []),
                                        "claim_state": n.get("claim_state", "unknown"),
                                        "sources": n.get("sources", []),
                                        "relations": [{k: v for k, v in e.items() if k != "from"}
                                                      for e in outgoing[i]]}}
                lines = [_meta(meta), "# " + _label(n["title"]), "", n["summary"], "",
                         n.get("body", ""), "", "## Navigate", "", "- [Index](../index.md)"]
                for e in outgoing[i]:
                    other = e["to"]
                    lines.append(f"- {e['predicate']}: [{_label(nodes[other]['title'])}]({paths[other]})")
                for e in incoming[i]:
                    other = e["from"]
                    lines.append(f"- backlink ({e['predicate']}): [{_label(nodes[other]['title'])}]({paths[other]})")
                (root / "notes" / paths[i]).write_text("\n".join(lines) + "\n", encoding="utf-8")
            index.append("")
        (root / "index.md").write_text("\n".join(index), encoding="utf-8")
        (root / "corpus.json").write_text(json.dumps(corpus, ensure_ascii=False, sort_keys=True,
                                                    indent=2) + "\n", encoding="utf-8")
        # No replacement of an existing directory, even if created since initial check.
        require(not target.exists() and not target.is_symlink(), "Output appeared")
        root.rename(target)
    return {"status": "exported", "project": corpus["project"], "notes": len(nodes),
            "coverage": corpus["coverage"], "path": str(target)}
