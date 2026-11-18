#!/usr/bin/env python3
"""Local active knowledge navigation. Explicit export only; no external commands."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import sqlite3

from model import load_json, v1_to_v2, include_backlog, validate, require, make_corpus
from providers import markdown_corpus
from retrieval import Navigator, PROFILES, INTENTS
from projection import compare, export_markdown
from reconcile import reconcile, map_candidates
from sections import section_response


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--home", help="Previously initialized private knowledge project")
    src.add_argument("--corpus", type=Path)
    src.add_argument("--markdown", type=Path)
    src.add_argument("--backlog-only", action="store_true", help="Build a partial corpus from explicit snapshots")
    p.add_argument("--cache", action="store_true", help="Use private external SQLite/FTS5 index (requires --project)")
    p.add_argument("--project", help="Explicit ID for Markdown or v1; check identity for v2")
    p.add_argument("--backlog", type=Path, action="append", default=[], help="Observed v1 JSON list/view/search envelope")
    p.add_argument("--profile", choices=PROFILES, default="normal")
    p.add_argument("--limit", type=int)
    p.add_argument("--budget-bytes", type=int)
    p.add_argument("--detail", choices=["identity", "summary", "full", "evidence"], default="summary")
    p.add_argument("--known", action="append", default=[], help="Previously observed node fingerprints in this project")
    sub = p.add_subparsers(dest="command", required=True)
    for command in ("validate", "overview", "tracks", "snapshot", "map-candidates", "index-status"):
        sub.add_parser(command)
    for command in ("architecture-review", "checkpoint", "context-pack"):
        rp = sub.add_parser(command)
        rp.add_argument("input", type=Path)
    cp = sub.add_parser("constitution")
    cp.add_argument("--anchor", action="append", default=[])
    cp.add_argument("--context")
    rec = sub.add_parser("reconcile")
    rec.add_argument("proposal", type=Path)
    e = sub.add_parser("export")
    e.add_argument("output", type=Path)
    d = sub.add_parser("diff")
    d.add_argument("before", type=Path)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--intent", choices=INTENTS, default="implement")
    s.add_argument("--context")
    s.add_argument("--kind")
    s.add_argument("--level", choices=["L0", "L1", "L2", "L3"])
    s = sub.add_parser("sections")
    s.add_argument("id")
    s.add_argument("--query", default="")
    s = sub.add_parser("section")
    s.add_argument("id")
    s.add_argument("section_id")
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
    if args.backlog_only:
        require(bool(args.backlog), "At least one Backlog snapshot required")
        c = make_corpus(args.project, [], [])
    elif args.markdown:
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
    if args.home:
        from knowledge_home import resolve, read_snapshot, snapshot_path
        b = resolve(args.home)
        require(not args.project or args.project == b["project"], "Managed home identity mismatch")
        require(not args.backlog, "Managed home does not accept external Backlog overlays")
        args.project = b["project"]
        if b["provider"] == "markdown":
            args.markdown = Path(b["root"])
        else:
            # Revalidate private binding and snapshot before reading/indexing.
            read_snapshot(args.home)
            args.corpus = snapshot_path(args.home)
    if args.cache:
        from cache_index import indexed
        require(bool(args.project) and not args.backlog and not args.backlog_only,
                "--cache requires --project and explicit corpus or Markdown without overlays")
        require(args.command not in {"validate", "snapshot", "export", "diff", "reconcile", "map-candidates", "architecture-review", "checkpoint"},
                "Use uncached source for maintenance or full snapshots")
        source = args.corpus or args.markdown
        with indexed(source, "snapshot" if args.corpus else "markdown", args.project) as (nav, stats):
            if args.command == "index-status":
                return {"status": "indexed", **stats}
            return navigate(args, nav)
    require(args.command != "index-status", "index-status requires --cache")
    c = load(args)
    if args.home:
        c.pop("home_binding_digest", None)
    if args.command == "architecture-review":
        from architecture import review
        return review(c, load_json(args.input), limit=20 if args.limit is None else args.limit,
                      budget=12000 if args.budget_bytes is None else args.budget_bytes)
    if args.command == "checkpoint":
        from discovery import checkpoint
        return checkpoint(c, load_json(args.input), budget=12000 if args.budget_bytes is None else args.budget_bytes)
    if args.command == "reconcile":
        return reconcile(c, load_json(args.proposal))
    if args.command == "map-candidates":
        return map_candidates(c)
    if args.command == "export":
        if args.home:
            from knowledge_home import outside_git, private_dir
            destination = outside_git(args.output)
            private_dir(destination.parent)
            return export_markdown(c, destination)
        return export_markdown(c, args.output)
    if args.command == "diff":
        return compare(load_json(args.before), c)
    if args.command == "snapshot":
        # Explicit full output bypasses retrieval budgets; do not use in routine retrieval.
        return c
    if args.command == "validate":
        return {"status": "valid-structure", "project": c["project"], "coverage": c["coverage"],
                "nodes": len(c["nodes"]), "edges": len(c["edges"])}
    return navigate(args, Navigator(c))


def navigate(args, nav):
    limit, depth, budget = PROFILES[args.profile]
    limit = args.limit if args.limit is not None else limit
    budget = args.budget_bytes if args.budget_bytes is not None else budget
    paths, cut = None, False
    detail = args.detail
    command = args.command
    if command == "context-pack":
        from adaptive import context_pack
        return context_pack(nav, load_json(args.input), profile=args.profile, budget=budget, max_results=limit)
    if command == "constitution":
        from discovery import constitution
        return constitution(nav, args.anchor, context=args.context, limit=limit, budget=budget)
    if command in {"sections", "section"}:
        return section_response(nav, args.id, query=getattr(args, "query", ""),
                                section_id=getattr(args, "section_id", None), limit=limit, budget=budget)
    if command in {"overview", "tracks"}:
        ids = nav.ids_for_level("L3" if command == "overview" else "L2")
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
    except (ValueError, TypeError, KeyError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"status": "invalid-input", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
