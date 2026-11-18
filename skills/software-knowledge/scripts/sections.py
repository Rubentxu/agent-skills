"""Exact Markdown excerpts with offsets, not synthesized claims."""
from __future__ import annotations

import json
import re

from model import digest, require
from retrieval import tokens

TARGET = 1800
HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^ {0,3}(\x60{3,}|~{3,})(.*)$")


def split_sections(body: str) -> list[dict]:
    """Keep complete paragraphs and fenced code blocks; offsets are Unicode code points.

    Oversized indivisible blocks remain whole and may not fit a response budget.
    """
    if not body:
        return []
    blocks = []
    start = pos = 0
    fence = None
    heading = ""
    for line in body.splitlines(keepends=True):
        clean = line.rstrip("\r\n")
        marker = FENCE.match(clean)
        h = HEADING.match(clean) if fence is None and not marker else None
        if h:
            if pos > start:
                blocks.append((start, pos, heading))
            start = pos
            heading = h.group(1)
        if marker:
            mark, tail = marker.groups()
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence) and not tail.strip():
                fence = None
        pos += len(line)
        if not clean.strip() and fence is None:
            if pos > start:
                blocks.append((start, pos, heading))
            start = pos
    if pos > start:
        blocks.append((start, pos, heading))
    merged = []
    for a, b, h in blocks:
        if merged and merged[-1][2] == h and b - merged[-1][0] <= TARGET:
            merged[-1] = (merged[-1][0], b, h)
        else:
            merged.append((a, b, h))
    result = []
    for a, b, h in merged:
        value = body[a:b]
        result.append({"id": digest([a, b, value]), "heading": h,
                       "start": a, "end": b, "text": value})
    return result


def section_response(nav, identity: str, *, query: str = "", section_id: str | None = None,
                     limit: int = 5, budget: int = 12000) -> dict:
    require(identity in nav.nodes, "Unknown node")
    require(1 <= limit <= 50 and 512 <= budget <= 64000, "Invalid output budget")
    n = nav.nodes[identity]
    parts = nav.sections(identity)
    if section_id is not None:
        parts = [s for s in parts if s["id"] == section_id]
        require(bool(parts), "Unknown or stale section ID")
    elif query:
        wanted = set(tokens(query))
        scored = []
        for s in parts:
            title = len(wanted & set(tokens(s["heading"])))
            body = len(wanted & set(tokens(s["text"])))
            if title or body:
                scored.append((-(title * 3 + body), s["start"], s))
        parts = [s for _, _, s in sorted(scored, key=lambda x: x[:2])]
    result = {"status": "partial", "project": nav.corpus["project"], "node": identity,
              "claim_state": n.get("claim_state", "unknown"), "coverage": nav.corpus["coverage"],
              "content_state": n.get("content_state", "provided"),
              "offset_unit": "unicode-code-point", "results": [], "omitted": 0}
    def size():
        return len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    if n.get("content_state") == "metadata-only":
        result["_links"] = [{"action": "capture-doc", "id": s["locator"]}
                            for s in n.get("sources", []) if s["provider"] == "backlog"
                            and identity == "doc:" + s["locator"]]
    for s in parts:
        if len(result["results"]) >= limit:
            result["omitted"] += 1
            continue
        item = {k: v for k, v in s.items() if k != "text"}
        if section_id is not None:
            item["text"] = s["text"]
            item["sources"] = n.get("sources", [])
        else:
            item["_links"] = [{"action": "section", "id": identity, "section_id": s["id"]}]
        result["results"].append(item)
        if size() > budget - 40:
            result["results"].pop()
            result["omitted"] += 1
    result["status"] = ("unknown" if not parts else "partial" if result["omitted"] or
                        nav.corpus["coverage"] == "partial" else "returned")
    require(size() <= budget, "Section envelope exceeds budget")
    return result
