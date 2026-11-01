#!/usr/bin/env python3
"""Selective decision recall and advisory votes, without storing conversations.

Backlog.md owns decisions; authority_context owns consistency checking. Agents
can rate usefulness, but their ratings never change approval or decision state.
"""
from __future__ import annotations

import argparse
import json
from typing import Any
from authority_context import envelope, read, require, validate


def recall(assessment: dict, decisions: dict, *,
           scope: list[str], ids: list[str] | None = None, limit: int = 5) -> dict:
    rows = envelope(assessment, "authority-assessment", "records")
    native = envelope(decisions, "decision-list", "decisions")
    require(0 < limit <= 20, "limit must be 1..20")
    require(all(isinstance(x, str) for x in scope), "invalid scope query")
    titles = {d["id"]: d.get("title", "") for d in native if isinstance(d.get("id"), str)}
    selected = []
    for row in rows:
        if row.get("verdict") != "VERIFIED":
            continue
        did = row.get("backlogDecisionId")
        tags = row.get("scope", [])
        explicit = did in (ids or [])
        overlap = len(set(tags) & set(scope))
        if not explicit and not overlap:
            continue
        selected.append((2 if explicit else 0, overlap, did, {
            "id": did, "title": titles.get(did, ""),
            "scope": tags, "sourcePin": row["sourcePin"],
            "verdict": "VERIFIED", "use": "CONTEXT_ONLY"}))
    selected.sort(key=lambda x: (-x[0], -x[1], x[2]))
    return {"schemaVersion": 1, "kind": "owner-memory-projection",
            "status": "REVIEW_ONLY", "items": [r[3] for r in selected[:limit]],
            "omitted": max(0, len(selected) - limit),
            "warning": "No decision or recalled memory grants tool permissions."}


def feedback(assessment: dict, votes: dict) -> dict:
    rows = envelope(assessment, "authority-assessment", "records")
    items = envelope(votes, "agent-feedback", "votes")
    valid = {r["id"] for r in rows}
    results = []
    for vote in items:
        require(vote.get("recordId") in valid, "unknown authority record")
        require(vote.get("value") in {"useful", "misleading", "stale"},
                "invalid feedback value")
        require(isinstance(vote.get("agentId"), str)
                and 0 < len(vote["agentId"]) <= 128, "missing agent ID")
        results.append({"recordId": vote["recordId"], "agentId": vote["agentId"],
                        "value": vote["value"], "effect": "REVIEW_SUGGESTION_ONLY"})
    return {"schemaVersion": 1, "kind": "memory-feedback-projection", "votes": results,
            "changesToApprovals": 0, "changesToBacklog": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    remember = sub.add_parser("recall")
    remember.add_argument("claims")
    remember.add_argument("messages")
    remember.add_argument("decisions")
    remember.add_argument("--scope", action="append", default=[])
    remember.add_argument("--decision-id", action="append", default=[])
    remember.add_argument("--limit", type=int, default=5)
    review = sub.add_parser("feedback")
    review.add_argument("assessment")
    review.add_argument("votes")
    args = parser.parse_args()
    try:
        if args.command == "recall":
            decisions = read(args.decisions)
            observed = validate(read(args.claims), read(args.messages), decisions)
            result = recall(observed, decisions, scope=args.scope, ids=args.decision_id,
                            limit=args.limit)
        else:
            result = feedback(read(args.assessment), read(args.votes))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, "BLOCKED: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
