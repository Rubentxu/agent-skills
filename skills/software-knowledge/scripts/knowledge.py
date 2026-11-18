#!/usr/bin/env python3
"""Local active knowledge navigation. stdout JSON; no writes or external commands."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from model import load_json, v1_to_v2, include_backlog, validate, require
from providers import markdown_corpus
from retrieval import Navigator, PROFILES, INTENTS


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--corpus", type=Path)
    src.add_argument("--markdown", type=Path)
    p.add_argument("--project", help="Explicit ID for Markdown or v1; check identity for v2")
    p.add_argument("--backlog", type=Path, action="append", default=[], help="Observed JSON list envelope")
    p.add_argument("--profile", choices=PROFILES, default="normal")
    p.add_argument("--limit", type=int)
    p.add_argument("--budget-bytes", type=int)
    p.add_argument("--detail", choices=["identity", "summary", "full", "evidence"], default="summary")
    p.add_argument("--known", action="append", default=[], help="Previously observed node fingerprints in this project")
    sub = p.add_subparsers(dest="command", required=True)
    for command in ("validate", "overview", "tracks", "snapshot"):
        sub.add_parser(command)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--intent", choices=INTENTS, default="implement")
    s.add_argument("--context")
    s.add_argument("--kind")
    s.add_argument("--level", choices=["L0", "L1", "L2", "L3"])
    g = sub.add_parser("get")
    g.add_argument("ids", nargs="+")
    for command in ("expand", "trace", "zoom-in", "zoom-out", "impact"):
        s = sub.add_parser(command)
        s.add_argument("id")
        s.add_argument("--depth", type=int)
        s.add_argument("--relation", action="append")
    s = sub.add_parser("context")
    s.add_argument("query", nargs="?", default="")
    s.add_argument("--anchor", action="append", default=[])
    s.add_argument("--intent", choices=INTENTS, default="implement")
    return p


def load(args):
    if args.markdown:
        c = markdown_corpus(args.markdown, args.project)
    else:
        c = load_json(args.corpus)
        if c.get("schemaVersion") == 1:
            c = v1_to_v2(c, args.project)
        else:
            validate(c)
            require(not args.project or args.project == c["project"], "Project mismatch")
    for path in args.backlog:
        c = include_backlog(c, load_json(path))
    return c


def run(args):
    c = load(args)
    if args.command == "snapshot":
        # Explicit full output bypasses retrieval budgets; do not use in routine retrieval.
        return c
    if args.command == "validate":
        return {"status": "valid-structure", "project": c["project"], "coverage": c["coverage"],
                "nodes": len(c["nodes"]), "edges": len(c["edges"])}
    nav = Navigator(c)
    limit, depth, budget = PROFILES[args.profile]
    limit = args.limit if args.limit is not None else limit
    budget = args.budget_bytes if args.budget_bytes is not None else budget
    paths, cut = None, False
    detail = args.detail
    command = args.command
    if command in {"overview", "tracks"}:
        ids = sorted(i for i, n in nav.nodes.items() if n["level"] == ("L3" if command == "overview" else "L2"))
    elif command == "search":
        ids = nav.search(args.query, intent=args.intent, context=args.context, kind=args.kind, level=args.level)
    elif command == "get":
        ids = list(dict.fromkeys(args.ids))
    elif command == "context":
        ids, paths, cut = nav.plan(args.query, args.anchor, args.intent, depth)
    else:
        d = args.depth if args.depth is not None else depth
        relations = set(args.relation) if args.relation else None
        direction = "both"
        if command in {"zoom-in", "zoom-out"}:
            relations = {"contains"}
            direction = "out" if command == "zoom-in" else "in"
        elif command == "trace":
            relations = {"contains", "derived_from", "verified_by", "validates", "supports"}
            detail = "evidence"
        elif command == "impact":
            direction = "in"
        paths, cut = nav.walk([args.id], d, relations, direction)
        ids = sorted(paths, key=lambda i: (paths[i][0], i))
        if command not in {"trace", "impact"}:
            ids.remove(args.id)
    return nav.render(ids, detail=detail, limit=limit, budget=budget, paths=paths,
                      cut=cut, known=set(args.known))


def main():
    try:
        result = run(parser().parse_args())
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")), end="")
        return 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(json.dumps({"status": "invalid-input", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
