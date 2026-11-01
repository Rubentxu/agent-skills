#!/usr/bin/env python3
"""Small, deterministic inter-agent handoff; not an authorization token.

The sender must supply already observed task-view and authority-assessment
snapshots. Receiver must recheck revisions, sources and runtime permissions.
"""
from __future__ import annotations

import argparse
import json
from authority_context import envelope, read, require, ID


def prepare(task_view: dict, assessment: dict, *, revision: str,
            agent: str, questions: list[str] | None = None) -> dict:
    require(isinstance(task_view, dict) and task_view.get("schemaVersion") == 1
            and task_view.get("kind") == "task-view"
            and isinstance(task_view.get("task"), dict), "expected Backlog task-view")
    task = task_view["task"]
    require(isinstance(task.get("id"), str) and ID.fullmatch(task["id"]),
            "invalid task identity")
    require(isinstance(revision, str) and len(revision) == 40
            and all(c in "0123456789abcdef" for c in revision),
            "expected actual 40-char commit SHA")
    require(isinstance(agent, str) and ID.fullmatch(agent), "invalid agent")
    rows = envelope(assessment, "authority-assessment", "records")
    refs = task.get("references") or []
    require(isinstance(refs, list), "invalid task references")
    require(all(isinstance(v, str) for v in refs), "invalid reference entry")
    questions = questions or []
    require(len(questions) <= 10 and all(isinstance(v, str) and len(v) <= 240
            for v in questions), "invalid unanswered questions")
    decisions = [{"id": r["backlogDecisionId"], "verdict": r["verdict"],
                  "sourcePin": r["sourcePin"]} for r in rows
                 if r["backlogDecisionId"] in refs]
    return {"schemaVersion": 1, "kind": "authority-handoff",
            "taskId": task["id"], "sourceRevision": revision, "agent": agent,
            "decisionRefs": decisions, "references": refs[:64],
            "questions": questions, "editAuthorized": False,
            "verification": "RUNTIME_UNVERIFIED",
            "status": "PREPARED"}


def receive(handoff: dict, assessment: dict, *, revision: str,
            task_id: str) -> dict:
    require(handoff.get("schemaVersion") == 1 and handoff.get("kind") == "authority-handoff",
            "invalid handoff envelope")
    require(isinstance(task_id, str) and ID.fullmatch(task_id),
            "invalid receiving task")
    rows = envelope(assessment, "authority-assessment", "records")
    by_id = {r["backlogDecisionId"]: r for r in rows}
    reasons = []
    if handoff.get("taskId") != task_id:
        reasons.append("TASK_MISMATCH")
    if handoff.get("sourceRevision") != revision:
        reasons.append("REVISION_STALE")
    for pin in handoff.get("decisionRefs", []):
        if not isinstance(pin, dict):
            reasons.append("INVALID_PIN")
            continue
        known = by_id.get(pin.get("id"))
        if not known or known.get("sourcePin") != pin.get("sourcePin"):
            reasons.append("AUTHORITY_CHANGED_OR_MISSING")
        elif known.get("verdict") != "VERIFIED":
            reasons.append("AUTHORITY_" + str(known["verdict"]))
    return {"schemaVersion": 1, "kind": "handoff-receipt",
            "status": "PAUSED" if reasons else "CONTEXT_MATCHES_RUNTIME_UNVERIFIED",
            "reasons": sorted(set(reasons)), "editAuthorized": False,
            "next": "Recheck Backlog task, code revision, source attestations and host permissions."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    send = sub.add_parser("prepare")
    send.add_argument("task_view")
    send.add_argument("assessment")
    send.add_argument("--revision", required=True)
    send.add_argument("--agent", required=True)
    send.add_argument("--question", action="append", default=[])
    recv = sub.add_parser("receive")
    recv.add_argument("handoff")
    recv.add_argument("assessment")
    recv.add_argument("--revision", required=True)
    recv.add_argument("--task", required=True)
    args = parser.parse_args()
    try:
        result = (prepare(read(args.task_view), read(args.assessment),
                          revision=args.revision, agent=args.agent,
                          questions=args.question) if args.command == "prepare"
                  else receive(read(args.handoff), read(args.assessment),
                               revision=args.revision, task_id=args.task))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, "BLOCKED: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
