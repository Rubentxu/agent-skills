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
import hashlib
import re
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

from multi_agent import (COORD_LABELS, Conflict, conflict_with_active, contract_digest, candidate_payload, delivery_intent,
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


def read_task(root: Path, binary: str, task_id: str) -> dict:
    """Single-task path for non-claim transitions. Claim still scans all owners."""
    doc = json.loads(cmd([binary, "task", "view", task_id, "--json"], root).stdout)
    task = doc.get("task")
    if (doc.get("kind") != "task-view" or doc.get("schemaVersion") != 1
            or not isinstance(task, dict) or task.get("id") != task_id):
        raise ValueError("Invalid authoritative task view")
    return task


def read_object(path):
    if not path:
        raise ValueError("Observed input file required")
    with open(path, "rb") as handle:
        data = handle.read(262145)
    if len(data) > 262144:
        raise ValueError("Input exceeds budget")
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("Expected object")
    return value


def observe_candidate(candidate, product_repo, target_remote=None):
    """Read Git only. Local preservation is not publication or authorization."""
    candidate_payload(candidate)
    if not product_repo:
        raise ValueError("Product checkout required")
    root = Path(product_repo).resolve()
    def ancestor(left, right):
        if cmd(["git", "merge-base", "--is-ancestor", left, right], root, check=False).returncode:
            raise Conflict("Candidate or base not reachable from observed revision")
    if target_remote is None:
        ref = cmd(["git", "rev-parse", "--verify", candidate["candidateRef"] + "^{commit}"], root).stdout.strip()
        ancestor(candidate["baseCommit"], candidate["candidateCommit"])
        ancestor(candidate["candidateCommit"], ref)
        return ref
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,120}", target_remote):
        raise ValueError("Explicit configured remote name required")
    # The caller must select the authorized checkout/remote. A local tracking ref may be stale.
    rows = cmd(["git", "ls-remote", "--exit-code", target_remote, candidate["targetRef"]], root).stdout.splitlines()
    matches = [line.split()[0] for line in rows if len(line.split()) == 2 and line.split()[1] == candidate["targetRef"]]
    if len(matches) != 1 or not re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", matches[0]):
        raise Conflict("Target revision unknown")
    ancestor(candidate["candidateCommit"], matches[0])
    return matches[0]


def observe_completion(opts, task, state):
    candidate = state["candidate"]
    if not candidate or not state["integrationOwner"] or contract_digest(task) != candidate["contractDigest"]:
        raise Conflict("Candidate contract changed or integration not adopted")
    if not opts.target_remote or not state["deliveryIntent"] or opts.target_remote != state["deliveryIntent"]["targetRemote"]:
        raise ValueError("Completion needs the originally authorized remote target")
    target = observe_candidate(candidate, opts.product_repo, opts.target_remote)
    a = read_object(opts.assessment_file)
    required = {"taskId": task["id"], "contractDigest": candidate["contractDigest"],
                "candidateCommit": candidate["candidateCommit"], "targetCommit": target,
                "targetRef": candidate["targetRef"], "scope": candidate["scope"],
                "generation": state["generation"]}
    if a.get("kind") != "delivery-assessment" or a.get("schemaVersion") != 1 or a.get("status") != "CANDIDATE_READY" or any(a.get(k) != v for k,v in required.items()):
        raise Conflict("Independent acceptance does not match exact candidate, generation and target")
    if not isinstance(a.get("observationDigest"), str) or not re.fullmatch(r"[a-f0-9]{64}", a["observationDigest"]):
        raise ValueError("Acceptance provenance required")
    for name in ("acceptanceCriteria", "definitionOfDone"):
        count, done = task.get(name + "Count"), task.get(name + "Completed")
        if (type(count) is not int or type(done) is not int or count != done
                or count != len(task[name]) or a.get(name + "Count") != count):
            raise Conflict("Acceptance/DoD inventory not fully checked")
    if not opts.terminal_status or not opts.resources_clear or not opts.evidence_ref:
        raise ValueError("Completion requires configured terminal status and clear inventory evidence")
    return target, hashlib.sha256(json.dumps(a,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()


def _retry_matches(existing: dict, action: str, opts: argparse.Namespace) -> bool:
    """Retry only the *same* event semantics; never accept merely the same ID."""
    kinds = {"claim": "CLAIM", "renew": "HEARTBEAT", "progress": "PROGRESS",
             "yield-request": "YIELD_REQUESTED", "yield-ack": "YIELD_ACK",
             "yield-defer": "YIELD_DEFERRED", "checkpoint": "CHECKPOINT_READY",
             "release": "RELEASE", "quarantine": "QUARANTINE", "recover": "RECOVER", "deliver": "DELIVER", "adopt": "ADOPT", "complete": "COMPLETE"}
    if existing["type"] != kinds[action] or existing["actor"] != opts.actor:
        return False
    required = {
        "claim": {"claimId": opts.claim_id, "harness": opts.harness,
                  "leaseUntil": opts.lease_until, "resources": sorted(opts.resource)},
        "renew": {"claimId": opts.claim_id, "leaseUntil": opts.lease_until},
        "progress": {"claimId": opts.claim_id, "evidenceRef": opts.evidence_ref},
        "yield-request": {"reason": opts.reason},
        "yield-ack": {"claimId": opts.claim_id, "inReplyTo": opts.request_id},
        "yield-defer": {"claimId": opts.claim_id, "inReplyTo": opts.request_id},
        "checkpoint": {"claimId": opts.claim_id, "evidenceRef": opts.evidence_ref},
        "release": {"claimId": opts.claim_id, "evidenceRef": opts.evidence_ref,
                    "resourcesClear": opts.resources_clear},
        "quarantine": {"reason": opts.reason, "evidenceRef": opts.evidence_ref},
        "recover": {"evidenceRef": opts.evidence_ref, "resourcesClear": opts.resources_clear},
        "deliver": {"claimId": opts.claim_id, "evidenceRef": opts.evidence_ref,
                    "resourcesClear": opts.resources_clear, "candidate": read_object(opts.candidate_file) if action == "deliver" else None},
        "adopt": {"claimId": opts.claim_id, "harness": opts.harness,
                  "leaseUntil": opts.lease_until, "resources": sorted(opts.resource)},
        "complete": {"claimId": opts.claim_id, "evidenceRef": opts.evidence_ref,
                     "resourcesClear": opts.resources_clear, "terminalStatus": opts.terminal_status,
                     "assessmentDigest": hashlib.sha256(json.dumps(read_object(opts.assessment_file),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest() if action == "complete" else None},
    }[action]
    if (any(v is None or v is False or (isinstance(v, list) and not v)
            for v in required.values()) or
            any(existing.get(k) != v for k, v in required.items())):
        return False
    expected_generation = opts.generation
    if (expected_generation is not None and
            expected_generation != existing["generation"] - (1 if action in {"claim", "adopt"} else 0)):
        return False
    if action == "claim" and opts.working_status and existing.get("workingStatus") != opts.working_status:
        return False
    if action == "claim" and existing.get("deliveryIntent") != (read_object(opts.delivery_intent_file) if opts.delivery_intent_file else None):
        return False
    return True


def _event_for(action: str, opts: argparse.Namespace, state: dict, now: str,
               task: dict) -> str:
    kind = {"claim": "CLAIM", "renew": "HEARTBEAT", "progress": "PROGRESS",
            "yield-request": "YIELD_REQUESTED", "yield-ack": "YIELD_ACK",
            "yield-defer": "YIELD_DEFERRED", "checkpoint": "CHECKPOINT_READY",
            "release": "RELEASE", "quarantine": "QUARANTINE", "recover": "RECOVER", "deliver": "DELIVER", "adopt": "ADOPT", "complete": "COMPLETE"}[action]
    fields: dict = {}
    generation = state["generation"]
    if action in {"claim", "adopt"}:
        generation += 1
        if not opts.claim_id or not opts.harness or not opts.resource:
            raise ValueError("claim requires --claim-id, --harness and at least one --resource")
        if utc(opts.lease_until) <= utc(now):
            raise ValueError("Claim lease must extend past observation time")
        fields = {"claimId": opts.claim_id, "harness": opts.harness,
                  "resources": opts.resource, "leaseUntil": opts.lease_until,
                  "originalStatus": task["status"],
                  "workingStatus": opts.working_status or task["status"]}
        if action == "claim":
            try:
                fields["contractDigest"] = contract_digest(task)
            except ValueError:
                pass  # Legacy task views can still claim, but not submit integrated candidates.
            if opts.delivery_intent_file:
                fields["deliveryIntent"] = delivery_intent(read_object(opts.delivery_intent_file))
                if not fields.get("contractDigest"):
                    raise ValueError("Integrated delivery needs full task contract")
        else:
            if state["candidate"] is None or contract_digest(task) != state["candidate"]["contractDigest"]:
                raise Conflict("Candidate contract changed; reconcile first")
            # If a previous merge succeeded before a crash, allow adopting from the integrated target.
            if opts.target_remote:
                if opts.target_remote != state["deliveryIntent"]["targetRemote"]:
                    raise Conflict("Remote differs from original intent")
                observe_candidate(state["candidate"], opts.product_repo, opts.target_remote)
            else:
                observe_candidate(state["candidate"], opts.product_repo)
    elif action in {"renew", "progress", "yield-ack", "yield-defer", "checkpoint", "release", "deliver", "complete"}:
        if not opts.claim_id or opts.claim_id != state["claimId"]:
            raise Conflict("Owner must provide the observed claimId")
        fields = {"claimId": opts.claim_id}
        if action in {"yield-ack", "yield-defer"}:
            fields["inReplyTo"] = opts.request_id
        if action == "renew":
            fields["leaseUntil"] = opts.lease_until
        if action in {"progress", "checkpoint"}:
            fields["evidenceRef"] = opts.evidence_ref
        if action in {"release", "deliver", "complete"}:
            fields.update(resourcesClear=opts.resources_clear, evidenceRef=opts.evidence_ref)
        if action in {"deliver", "complete"}:
            if not state["leaseUntil"] or utc(now) >= utc(state["leaseUntil"]):
                raise Conflict("Current lease required")
        if action == "deliver":
            candidate = candidate_payload(read_object(opts.candidate_file))
            if contract_digest(task) != candidate["contractDigest"]:
                raise Conflict("Task contract changed")
            observe_candidate(candidate, opts.product_repo)
            fields["candidate"] = candidate
        if action == "complete":
            target, assessment_digest = observe_completion(opts, task, state)
            fields.update(targetCommit=target, assessmentDigest=assessment_digest, terminalStatus=opts.terminal_status)
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
    # Only a new claim must examine every other task's resources. Renew,
    # checkpoint, release and takeover transitions are task-local.
    if opts.action in {"claim", "adopt"}:
        _, details = read_backlog(root, binary)
        if opts.task not in details:
            raise ValueError("Task not found in authoritative Backlog.md")
        task = details[opts.task]
    else:
        details = None
        task = read_task(root, binary, opts.task)
    state = task_state(task)
    # A failed push may have succeeded remotely. Retried event IDs must not
    # append a second command or take a second claim. The current generation
    # remains authoritative; a historical event is not a renewed permission.
    existing = next((event for event in parse_comments(task.get("comments"))
                     if event["id"] == opts.event_id), None)
    if existing is not None:
        if not _retry_matches(existing, opts.action, opts):
            raise Conflict("Event ID reuse with incompatible payload")
        return {"result":"ALREADY_CONFIRMED", "taskId":opts.task,
                "generation":state["generation"], "phase":state["phase"],
                "eventId":opts.event_id, "notice":"Revalidate current claim before effects"}
    if opts.generation is not None and opts.generation != state["generation"]:
        raise Conflict("Expected generation differs from authoritative task")
    if opts.action in {"claim", "adopt"}:
        if opts.action == "claim" and task_candidate(task, state, opts.claimable_status or None) != "CANDIDATE":
            raise Conflict("Task is not available for exclusive claim")
        if opts.action == "adopt" and (state["phase"] != "AWAITING_INTEGRATION" or task.get("archived") is not False):
            raise Conflict("No candidate available for adoption")
        if opts.action == "claim":
            # New writers must not build on a managed dependency still awaiting integration.
            for dep in task.get("dependencies") or []:
                parent = details.get(dep)
                if parent is None or task_state(parent)["candidate"] and task_state(parent)["phase"] != "COMPLETED":
                    raise Conflict("Dependency delivery not integrated: " + dep)
        colliding = conflict_with_active(opts.resource, list(details.values()), opts.task)
        if colliding:
            raise Conflict("Resource scopes conflict with tasks: " + ", ".join(colliding))
    if opts.action == "renew" and utc(opts.lease_until) <= utc(opts.at):
        raise ValueError("Lease renewal must extend past observation time")
    # Captures original column in CLAIM and restores it automatically on
    # RELEASE/RECOVER, even for localized or customized boards.
    restore_status = opts.ready_status
    if opts.action in {"release", "recover"} and state["originalStatus"] and not state["candidate"]:
        expected = {state["originalStatus"], state["workingStatus"]}
        if task.get("status") not in expected:
            raise Conflict("Status changed outside coordination; investigate before release")
        if restore_status and restore_status != state["originalStatus"]:
            raise Conflict("Requested ready status differs from claim baseline")
        restore_status = state["originalStatus"]
    if opts.action in {"claim", "adopt", "renew"}:
        if utc(opts.lease_until) > utc(opts.at) + timedelta(minutes=opts.max_lease_minutes):
            raise ValueError("Requested lease exceeds configured maximum duration")
    event = _event_for(opts.action, opts, state, opts.at, task)
    next_state = replay(parse_comments(task.get("comments") + [{"body": event}]))
    if opts.dry_run:
        return {"result": "PROPOSED_ONLY", "taskId": opts.task,
                "current": state, "next": next_state, "event": event}
    original_labels = task.get("labels")
    if not isinstance(original_labels, list) or not all(isinstance(x, str) for x in original_labels):
        raise ValueError("Malformed task labels")
    desired_labels = (set(original_labels) - COORD_LABELS) | labels_for_phase(next_state["phase"])
    argv = [binary, "task", "edit", opts.task, "--comment", event,
            "--comment-author", opts.actor]
    if desired_labels != set(original_labels):
        # --label is supported in older Backlog.md releases too; avoid assuming
        # incremental --add-label/--remove-label options exist on every host.
        argv.extend(["--label", ",".join(sorted(desired_labels))])
    if opts.action in {"claim", "adopt"} and opts.working_status:
        argv.extend(["--status", opts.working_status])
    if opts.action == "complete":
        argv.extend(["--status", opts.terminal_status])
    if opts.action in {"release", "recover"} and not state["candidate"] and restore_status and restore_status != task.get("status"):
        argv.extend(["--status", restore_status])
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
                                           "quarantine", "recover", "triage", "verify", "deliver", "adopt", "complete"])
    parser.add_argument("--remote", required=True, help="Canonical remote for authoritative Home Repo")
    parser.add_argument("--ref", default="main", help="Shared authority branch; NOT a per-worker branch")
    parser.add_argument("--backlog", default="backlog", help="Backlog.md CLI executable")
    parser.add_argument("--task")
    parser.add_argument("--actor")
    parser.add_argument("--harness")
    parser.add_argument("--working-status", help="Configured In Progress column for claim")
    parser.add_argument("--claimable-status", action="append", default=[],
                        help="Explicit Backlog.md claimable column; repeat for each allowed status")
    parser.add_argument("--max-lease-minutes", type=int, default=120)
    parser.add_argument("--ready-status", help="Configured To Do column for release/recover")
    parser.add_argument("--claim-id")
    parser.add_argument("--event-id")
    parser.add_argument("--request-id", help="Target YIELD_REQUESTED event for ACK/DEFER")
    parser.add_argument("--generation", type=int)
    parser.add_argument("--resource", action="append", default=[])
    parser.add_argument("--lease-until")
    parser.add_argument("--reason")
    parser.add_argument("--evidence-ref")
    parser.add_argument("--resources-clear", action="store_true")
    parser.add_argument("--grace-minutes", type=int, default=20)
    parser.add_argument("--at", help="UTC observation time; host must ensure trustworthy clock")
    parser.add_argument("--delivery-intent-file", help="Authorized scope and target before delegation")
    parser.add_argument("--candidate-file")
    parser.add_argument("--assessment-file")
    parser.add_argument("--product-repo")
    parser.add_argument("--target-remote")
    parser.add_argument("--terminal-status")
    parser.add_argument("--dry-run", action="store_true")
    opts = parser.parse_args()
    if not revalidate_ref(opts.ref):
        parser.error("Invalid authority ref")
    opts.at = opts.at or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    utc(opts.at)
    opts.event_id = opts.event_id or "evt-" + uuid.uuid4().hex
    if opts.action != "triage" and (not opts.task or not opts.actor):
        parser.error("Mutations need --task and --actor")
    if opts.action in {"claim", "adopt", "renew"} and not opts.lease_until:
        parser.error("Lease operations need --lease-until")
    if opts.action in {"deliver", "adopt", "complete"} and opts.generation is None:
        parser.error("Delivery transitions require expected generation")
    if opts.grace_minutes < 0 or not 1 <= opts.max_lease_minutes <= 1440:
        parser.error("Invalid grace or max lease duration")
    try:
        with tempfile.TemporaryDirectory(prefix="backlog-coordination-") as tmp:
            root = Path(tmp) / "home"
            cmd(["git", "clone", "--quiet", "--single-branch", "--branch", opts.ref, "--", opts.remote, str(root)], tmp)
            if opts.action == "triage":
                _, details = read_backlog(root, opts.backlog)
                out = triage(list(details.values()), opts.at)
            elif opts.action == "verify":
                if opts.generation is None or not opts.claim_id:
                    raise ValueError("verify requires claim ID and expected generation")
                task = read_task(root, opts.backlog, opts.task)
                state = task_state(task)
                if (state["phase"] != "ACTIVE" or state["owner"] != opts.actor
                        or state["claimId"] != opts.claim_id
                        or state["generation"] != opts.generation
                        or not state["leaseUntil"] or utc(opts.at) >= utc(state["leaseUntil"])
                        or (opts.resource and any(x not in state["resources"] for x in opts.resource))):
                    raise Conflict("No currently valid confirmed claim for this writer")
                out = {"result": "VALID_FOR_COOPERATIVE_WRITER", "taskId": opts.task,
                       "generation": state["generation"], "claimId": state["claimId"],
                       "notice": "Point-in-time check only; target-side publication must fence again"}
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
