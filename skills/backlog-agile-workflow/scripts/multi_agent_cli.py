#!/usr/bin/env python3
"""Portable Git-CAS Backlog.md coordination client.

Writes are made exclusively via the official `backlog task edit` command in an
isolated clone, then confirmed by a non-force fast-forward push to ONE authority
branch. Not a daemon, workflow engine, secondary tracker or generic Git wrapper.
Only cooperative writers that use the same branch/protocol are coordinated.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

from multi_agent import (COORD_LABELS, Conflict, conflict_with_active,
                         labels_for_phase, make_event, parse_comments,
                         replay, task_candidate, task_state, triage, utc)


def cmd(argv: list[str], cwd: str | Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=120,
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if check and proc.returncode:
        raise RuntimeError(f"Command failed ({argv[0]}): {proc.stderr[:600]}")
    return proc


def read_backlog(root: Path, binary: str) -> tuple[list[dict], dict[str, dict]]:
    payload = json.loads(cmd([binary, "task", "list", "--json"], root).stdout)
    if (not isinstance(payload, dict) or payload.get("kind") != "task-list"
            or payload.get("schemaVersion") != 1 or not isinstance(payload.get("tasks"), list)
            or payload.get("nextSkip") is not None or len(payload["tasks"]) > 20000):
        raise ValueError("Incomplete or unexpected task-list snapshot; fail closed")
    rows = payload["tasks"]
    if len({row.get("id") for row in rows}) != len(rows):
        raise ValueError("Duplicate task identities")
    details: dict[str, dict] = {}
    # Correctness first: task-list does not expose comment metadata. Never infer
    # another owner's absence from list labels alone.
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("Malformed task row")
        detail = json.loads(cmd([binary, "task", "view", row["id"], "--json"], root).stdout)
        if detail.get("kind") != "task-view" or detail.get("schemaVersion") != 1:
            raise ValueError("Invalid task-view")
        task = detail.get("task")
        if not isinstance(task, dict) or task.get("id") != row["id"]:
            raise ValueError("Task identity mismatch")
        for key in ("archived", "isReady", "status", "assignees"):
            if task.get(key) != row.get(key):
                raise ValueError("Inconsistent board/task snapshot: " + key)
        details[row["id"]] = task
    return rows, details


def _event_for(action: str, opts: argparse.Namespace, state: dict, now: str) -> str:
    kind = {"claim": "CLAIM", "renew": "HEARTBEAT", "progress": "PROGRESS",
            "yield-request": "YIELD_REQUESTED", "yield-ack": "YIELD_ACK",
            "yield-defer": "YIELD_DEFERRED", "checkpoint": "CHECKPOINT_READY",
            "release": "RELEASE", "quarantine": "QUARANTINE", "recover": "RECOVER"}[action]
    fields: dict = {}
    generation = state["generation"]
    if action == "claim":
        generation += 1
        if not opts.claim_id or not opts.harness or not opts.resource:
            raise ValueError("claim requires --claim-id, --harness and at least one --resource")
        if utc(opts.lease_until) <= utc(now):
            raise ValueError("Claim lease must extend past observation time")
        fields = {"claimId": opts.claim_id, "harness": opts.harness,
                  "resources": opts.resource, "leaseUntil": opts.lease_until}
    elif action in {"renew", "progress", "yield-ack", "yield-defer", "checkpoint", "release"}:
        if not opts.claim_id or opts.claim_id != state["claimId"]:
            raise Conflict("Owner must provide the observed claimId")
        fields = {"claimId": opts.claim_id}
        if action == "renew":
            fields["leaseUntil"] = opts.lease_until
        if action in {"progress", "checkpoint"}:
            fields["evidenceRef"] = opts.evidence_ref
        if action == "release":
            fields.update(resourcesClear=opts.resources_clear, evidenceRef=opts.evidence_ref)
    elif action == "yield-request":
        fields["reason"] = opts.reason
    elif action == "quarantine":
        fields["reason"] = opts.reason
        if not opts.evidence_ref or not opts.reason:
            raise ValueError("Quarantine needs observation evidence and reason")
        # A liveness timeout authorizes SUSPECT, not a verified stop. This
        # transition revokes the coordination claim, but reserves resources.
        if not state["leaseUntil"] or utc(now) <= utc(state["leaseUntil"]) + timedelta(minutes=opts.grace_minutes):
            raise Conflict("Lease not expired beyond observation grace")
        fields["evidenceRef"] = opts.evidence_ref
    elif action == "recover":
        fields.update(resourcesClear=opts.resources_clear, evidenceRef=opts.evidence_ref)
    return make_event(kind, actor=opts.actor, id=opts.event_id, at=now,
                      generation=generation, **fields)


def _apply(opts: argparse.Namespace, root: Path) -> dict:
    binary = opts.backlog
    _, details = read_backlog(root, binary)
    if opts.task not in details:
        raise ValueError("Task not found in authoritative Backlog.md")
    task = details[opts.task]
    state = task_state(task)
    # A failed push may have succeeded remotely. Retried event IDs must not
    # append a second command or take a second claim. The current generation
    # remains authoritative; a historical event is not a renewed permission.
    existing = next((event for event in parse_comments(task.get("comments"))
                     if event["id"] == opts.event_id), None)
    if existing is not None:
        kind = {"claim":"CLAIM", "renew":"HEARTBEAT", "progress":"PROGRESS",
                "yield-request":"YIELD_REQUESTED", "yield-ack":"YIELD_ACK",
                "yield-defer":"YIELD_DEFERRED", "checkpoint":"CHECKPOINT_READY",
                "release":"RELEASE", "quarantine":"QUARANTINE", "recover":"RECOVER"}[opts.action]
        if (existing["type"] != kind or existing["actor"] != opts.actor
                or (opts.claim_id and existing.get("claimId") != opts.claim_id)
                or (opts.evidence_ref and existing.get("evidenceRef") != opts.evidence_ref)
                or (opts.reason and existing.get("reason") != opts.reason)
                or (opts.resource and existing.get("resources") != sorted(opts.resource))):
            raise Conflict("Event ID reuse with incompatible payload")
        return {"result":"ALREADY_CONFIRMED", "taskId":opts.task,
                "generation":state["generation"], "phase":state["phase"],
                "eventId":opts.event_id, "notice":"Revalidate current claim before effects"}
    if opts.generation is not None and opts.generation != state["generation"]:
        raise Conflict("Expected generation differs from authoritative task")
    if opts.action == "claim":
        if task_candidate(task, state) != "CANDIDATE":
            raise Conflict("Task is not available for exclusive claim")
        colliding = conflict_with_active(opts.resource, list(details.values()), opts.task)
        if colliding:
            raise Conflict("Resource scopes conflict with tasks: " + ", ".join(colliding))
    if opts.action == "renew" and utc(opts.lease_until) <= utc(opts.at):
        raise ValueError("Lease renewal must extend past observation time")
    event = _event_for(opts.action, opts, state, opts.at)
    next_state = replay(parse_comments(task.get("comments") + [{"body": event}]))
    if opts.dry_run:
        return {"result": "PROPOSED_ONLY", "taskId": opts.task,
                "current": state, "next": next_state, "event": event}
    old_labels = COORD_LABELS.intersection(task.get("labels") or [])
    new_labels = labels_for_phase(next_state["phase"])
    argv = [binary, "task", "edit", opts.task, "--comment", event,
            "--comment-author", opts.actor]
    for label in sorted(new_labels - old_labels):
        argv.extend(["--add-label", label])
    for label in sorted(old_labels - new_labels):
        argv.extend(["--remove-label", label])
    if opts.action == "claim" and opts.working_status:
        argv.extend(["--status", opts.working_status])
    if opts.action in {"release", "recover"} and opts.ready_status:
        argv.extend(["--status", opts.ready_status])
    before = cmd(["git", "rev-parse", "HEAD"], root).stdout.strip()
    cmd(argv, root)
    # The CLI may auto-commit. Reject any unexpected side effect in either
    # committed or uncommitted files (hooks included), before publication.
    target = task.get("path")
    if not isinstance(target, str) or Path(target).is_absolute() or not (root / target).resolve().is_relative_to(root.resolve()) or not target.endswith(".md") and not target.endswith(".json"):
        raise ValueError("Task view lacks safe backlog-relative path")
    changed = set(cmd(["git", "diff", "--name-only", before], root).stdout.splitlines())
    changed.update(cmd(["git", "diff", "--name-only"], root).stdout.splitlines())
    changed.update(cmd(["git", "ls-files", "--others", "--exclude-standard"], root).stdout.splitlines())
    if changed != {target}:
        raise RuntimeError("Unexpected task changes; abort publication: " + repr(sorted(changed)))
    cmd(["git", "add", "--", target], root)
    if cmd(["git", "diff", "--cached", "--quiet"], root, check=False).returncode != 0:
        cmd(["git", "-c", "user.name=Backlog Coordination", "-c", "user.email=coordination@localhost",
             "commit", "-m", f"coord({opts.task}): {opts.action}"], root)
    pushed = cmd(["git", "push", "origin", f"HEAD:refs/heads/{opts.ref}"], root, check=False)
    if pushed.returncode:
        # Unknown outcome is not a success or a safe retry. In particular a
        # transient network failure may occur after a successful remote push.
        return {"result": "UNCONFIRMED_OR_CONFLICT", "taskId": opts.task,
                "eventId": opts.event_id, "detail": pushed.stderr[:500],
                "nextAction": "Refresh remote authority; check eventId before attempting anything"}
    return {"result": "CONFIRMED", "taskId": opts.task,
            "generation": next_state["generation"], "phase": next_state["phase"],
            "claimId": next_state["claimId"], "eventId": opts.event_id}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["claim", "renew", "progress", "yield-request",
                                           "yield-ack", "yield-defer", "checkpoint", "release",
                                           "quarantine", "recover", "triage"])
    parser.add_argument("--remote", required=True, help="Canonical remote for authoritative Home Repo")
    parser.add_argument("--ref", default="main", help="Shared authority branch; NOT a per-worker branch")
    parser.add_argument("--backlog", default="backlog", help="Backlog.md CLI executable")
    parser.add_argument("--task")
    parser.add_argument("--actor")
    parser.add_argument("--harness")
    parser.add_argument("--working-status", help="Configured In Progress column for claim")
    parser.add_argument("--ready-status", help="Configured To Do column for release/recover")
    parser.add_argument("--claim-id")
    parser.add_argument("--event-id")
    parser.add_argument("--generation", type=int)
    parser.add_argument("--resource", action="append", default=[])
    parser.add_argument("--lease-until")
    parser.add_argument("--reason")
    parser.add_argument("--evidence-ref")
    parser.add_argument("--resources-clear", action="store_true")
    parser.add_argument("--grace-minutes", type=int, default=20)
    parser.add_argument("--at", help="UTC observation time; host must ensure trustworthy clock")
    parser.add_argument("--dry-run", action="store_true")
    opts = parser.parse_args()
    if not revalidate_ref(opts.ref):
        parser.error("Invalid authority ref")
    opts.at = opts.at or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    utc(opts.at)
    opts.event_id = opts.event_id or "evt-" + uuid.uuid4().hex
    if opts.action != "triage" and (not opts.task or not opts.actor):
        parser.error("Mutations need --task and --actor")
    if opts.action in {"claim", "renew"} and not opts.lease_until:
        parser.error("Lease operations need --lease-until")
    if opts.grace_minutes < 0:
        parser.error("Invalid grace")
    try:
        with tempfile.TemporaryDirectory(prefix="backlog-coordination-") as tmp:
            root = Path(tmp) / "home"
            cmd(["git", "clone", "--quiet", "--single-branch", "--branch", opts.ref, "--", opts.remote, str(root)], tmp)
            if opts.action == "triage":
                _, details = read_backlog(root, opts.backlog)
                out = triage(list(details.values()), opts.at)
            else:
                out = _apply(opts, root)
            print(json.dumps(out, ensure_ascii=False, indent=2))
            if out.get("result") == "UNCONFIRMED_OR_CONFLICT":
                sys.exit(3)
    except (ValueError, Conflict, RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        print(json.dumps({"result": "REFUSED", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


def revalidate_ref(ref: str) -> bool:
    import re
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,120}", ref)
                and ".." not in ref and "//" not in ref and not ref.endswith((".", "/", ".lock")))


if __name__ == "__main__":
    main()
