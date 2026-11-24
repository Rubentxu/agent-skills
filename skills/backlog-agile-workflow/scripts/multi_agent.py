#!/usr/bin/env python3
"""Pure Backlog.md coordination reducer and conservative multi-agent planning.

No network, git, subprocess, clocks or files are read here. Backlog.md task-view
comments are the authoritative, append-only source for coordination events.
Every writer must use the same confirmed CAS authority; this module does not
provide distributed atomicity on its own.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import hashlib
import re
from typing import Any

PREFIX = "COORDINATION_EVENT_V1 "
MAX_EVENTS = 1000
MAX_EVENT_BYTES = 8192
COORD_LABELS = frozenset({
    "coord:claimed", "coord:stalled", "coord:yield-requested",
    "coord:handoff-ready", "coord:needs-recovery", "coord:quarantined", "coord:awaiting-integration",
})
TASK_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
RESOURCE = re.compile(r"^(repo|api|k8s|test|service)://[A-Za-z0-9._/@:+*=-]+$")
ID = re.compile(r"^[A-Za-z0-9_.:@/-]{1,160}$")
EVENTS = frozenset({"CLAIM", "HEARTBEAT", "PROGRESS", "YIELD_REQUESTED",
                    "YIELD_ACK", "YIELD_DEFERRED", "CHECKPOINT_READY",
                    "RELEASE", "QUARANTINE", "RECOVER", "DELIVER", "ADOPT", "COMPLETE"})


class Conflict(ValueError):
    """An event violates the observed coordination state (fail closed)."""


def utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("UTC timestamp with trailing Z required")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Malformed timestamp") from exc
    if result.utcoffset() != timezone.utc.utcoffset(result):
        raise ValueError("Timestamp must be UTC")
    return result


def _id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("Invalid " + name)
    return value


def _resources(items: Any) -> list[str]:
    if not isinstance(items, list) or len(items) > 64 or any(
        not isinstance(i, str) or not RESOURCE.fullmatch(i) or ".." in i.split("/")
        for i in items
    ):
        raise ValueError("Invalid resource scopes")
    if len(set(items)) != len(items):
        raise ValueError("Duplicate resource")
    return sorted(items)


def contract_digest(task):
    """Pin semantic task contract, not mutable status, checkboxes or comments."""
    def criteria(name):
        values = task.get(name)
        if not isinstance(values, list):
            raise ValueError("Full criterion text required: " + name)
        result = []
        for entry in values:
            if isinstance(entry, str) and entry.strip():
                result.append(entry)
            elif isinstance(entry, dict):
                item = {k: v for k, v in entry.items() if k not in {"checked", "completed", "isCompleted"}}
                if not item or not any(isinstance(v, str) and v.strip() for v in item.values()):
                    raise ValueError("Missing criterion text")
                result.append(item)
            else:
                raise ValueError("Missing criterion text")
        return result
    ac, dod = criteria("acceptanceCriteria"), criteria("definitionOfDone")
    if not ac or not isinstance(task.get("description"), str) or not isinstance(task.get("title"), str):
        raise ValueError("Full task contract required")
    value = {k: task.get(k) for k in ("id", "title", "description", "dependencies", "references", "documentation")}
    value.update(acceptanceCriteria=ac, definitionOfDone=dod)
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def delivery_intent(value):
    if not isinstance(value, dict) or set(value) != {"repository", "targetRef", "targetRemote", "scope", "authorityRef"}:
        raise ValueError("Explicit authorized delivery intent required")
    _id(value["repository"], "canonical repository")
    if not isinstance(value["targetRef"], str) or not re.fullmatch(r"refs/heads/[A-Za-z0-9][A-Za-z0-9._/-]{0,240}", value["targetRef"]) or ".." in value["targetRef"] or "//" in value["targetRef"]:
        raise ValueError("Explicit target branch required")
    if not isinstance(value["targetRemote"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,120}", value["targetRemote"]):
        raise ValueError("Explicit configured target remote required")
    if value["scope"] not in ("integration", "product-capability", "release"):
        raise ValueError("Integration intent requires integrated delivery scope")
    if not isinstance(value["authorityRef"], str) or not value["authorityRef"].strip() or len(value["authorityRef"]) > 512:
        raise ValueError("Observed policy reference required")
    return value


def candidate_payload(value):
    if not isinstance(value, dict) or set(value) != {"repository", "baseCommit", "candidateCommit",
            "candidateRef", "targetRef", "contractDigest", "scope"}:
        raise ValueError("Invalid integration candidate")
    _id(value["repository"], "canonical repository")
    for key in ("baseCommit", "candidateCommit"):
        if not isinstance(value[key], str) or not re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", value[key]):
            raise ValueError("Full commit required: " + key)
    for key in ("candidateRef", "targetRef"):
        if not isinstance(value[key], str) or not re.fullmatch(r"refs/(heads|tags)/[A-Za-z0-9][A-Za-z0-9._/-]{0,240}", value[key]) or ".." in value[key] or "//" in value[key]:
            raise ValueError("Durable Git ref required: " + key)
    if not value["targetRef"].startswith("refs/heads/"):
        raise ValueError("Integration target must be a branch")
    if not isinstance(value["contractDigest"], str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", value["contractDigest"]):
        raise ValueError("Semantic contract digest required")
    if value["scope"] not in ("integration", "product-capability", "release"):
        raise ValueError("Candidate flow is for integrated deliveries")
    return value


def _event(obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict) or obj.get("v") != 1 or obj.get("type") not in EVENTS:
        raise ValueError("Unknown coordination event")
    if not isinstance(obj.get("generation"), int) or isinstance(obj["generation"], bool) or obj["generation"] < 0:
        raise ValueError("Invalid generation")
    for key in ("id", "actor"):
        _id(obj.get(key), key)
    utc(obj.get("at"))
    t = obj["type"]
    if t in {"CLAIM", "HEARTBEAT", "PROGRESS", "YIELD_ACK", "YIELD_DEFERRED", "CHECKPOINT_READY", "RELEASE", "DELIVER", "ADOPT", "COMPLETE"}:
        _id(obj.get("claimId"), "claimId")
    if t in {"CLAIM", "ADOPT"}:
        _resources(obj.get("resources"))
        _id(obj.get("harness"), "harness")
        utc(obj.get("leaseUntil"))
        if "deliveryIntent" in obj:
            if t != "CLAIM":
                raise ValueError("Intent cannot change on adoption")
            delivery_intent(obj["deliveryIntent"])
        if "contractDigest" in obj and not re.fullmatch(r"sha256:[a-f0-9]{64}", str(obj["contractDigest"])):
            raise ValueError("Invalid contract digest")
        if "originalStatus" in obj or "workingStatus" in obj:
            for field in ("originalStatus", "workingStatus"):
                if not isinstance(obj.get(field), str) or not obj[field].strip() or len(obj[field]) > 120:
                    raise ValueError("Invalid claim status: " + field)
    elif t == "HEARTBEAT":
        utc(obj.get("leaseUntil"))
    elif t in {"RELEASE", "RECOVER", "DELIVER", "COMPLETE"}:
        if obj.get("resourcesClear") is not True or not isinstance(obj.get("evidenceRef"), str) or not obj["evidenceRef"].strip():
            raise ValueError("Release/recovery requires confirmed clear inventory evidence")
        if t == "DELIVER":
            candidate_payload(obj.get("candidate"))
        if t == "COMPLETE":
            if not re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", str(obj.get("targetCommit", ""))):
                raise ValueError("Observed integrated revision required")
            if not isinstance(obj.get("terminalStatus"), str) or not obj["terminalStatus"].strip():
                raise ValueError("Configured terminal status required")
            if not re.fullmatch(r"[a-f0-9]{64}", str(obj.get("assessmentDigest", ""))):
                raise ValueError("Acceptance assessment digest required")
    elif t == "QUARANTINE":
        if not isinstance(obj.get("reason"), str) or not obj["reason"].strip():
            raise ValueError("Quarantine must state its reason")
    elif t in {"PROGRESS", "CHECKPOINT_READY"}:
        if not isinstance(obj.get("evidenceRef"), str) or not obj["evidenceRef"].strip():
            raise ValueError("Material progress requires evidenceRef")
    elif t == "YIELD_REQUESTED":
        if not isinstance(obj.get("reason"), str) or not obj["reason"].strip():
            raise ValueError("Yield needs a reason")
    elif t in {"YIELD_ACK", "YIELD_DEFERRED"}:
        _id(obj.get("inReplyTo"), "inReplyTo")
    return obj


def parse_comments(comments: Any) -> list[dict[str, Any]]:
    if not isinstance(comments, list):
        raise ValueError("Task comments missing")
    events: list[dict[str, Any]] = []
    seen = set()
    for c in comments:
        if not isinstance(c, dict) or not isinstance(c.get("body"), str):
            raise ValueError("Malformed comment")
        body = c["body"]
        if not body.startswith(PREFIX):
            continue
        if len(body.encode("utf-8")) > MAX_EVENT_BYTES:
            raise ValueError("Oversized coordination event")
        obj = _event(json.loads(body[len(PREFIX):]))
        if obj["id"] in seen:
            raise Conflict("Duplicate coordination event id")
        seen.add(obj["id"])
        events.append(obj)
        if len(events) > MAX_EVENTS:
            raise ValueError("Too many coordination events: compact with an authorized protocol upgrade")
    return events


def replay(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Replay events in persisted comment order. No derived status grants permission."""
    state: dict[str, Any] = {"generation": 0, "owner": None, "claimId": None,
                             "leaseUntil": None, "resources": [], "phase": "AVAILABLE",
                             "lastHeartbeatAt": None, "lastProgressAt": None,
                             "checkpointRef": None, "requestId": None, "claimAt": None, "lastReason": None, "requestStatus": None,
                             "originalStatus": None, "workingStatus": None, "candidate": None, "contractDigest": None, "deliveryIntent": None, "integrationOwner": False, "completion": None}
    for obj in events:
        ev = _event(obj)
        t, gen, actor = ev["type"], ev["generation"], ev["actor"]
        prev = state["generation"]
        if t in {"CLAIM", "ADOPT"}:
            required_phase = "AVAILABLE" if t == "CLAIM" else "AWAITING_INTEGRATION"
            if state["phase"] != required_phase or gen != prev + 1:
                raise Conflict("Conflicting claim or stale generation")
            state.update(owner=actor, claimId=ev["claimId"], generation=gen,
                         resources=_resources(ev["resources"]), leaseUntil=ev["leaseUntil"],
                         lastHeartbeatAt=ev["at"], claimAt=ev["at"], lastProgressAt=None,
                         requestId=None, lastReason=None, requestStatus=None, phase="ACTIVE",
                         originalStatus=ev.get("originalStatus"), workingStatus=ev.get("workingStatus"),
                         contractDigest=ev.get("contractDigest") if t == "CLAIM" else state["contractDigest"],
                         integrationOwner=(t == "ADOPT"))
            if t == "CLAIM":
                state.update(candidate=None, completion=None, deliveryIntent=ev.get("deliveryIntent"))
            continue
        if gen != prev:
            raise Conflict("Stale event generation")
        if t == "YIELD_REQUESTED":
            if state["phase"] != "ACTIVE":
                raise Conflict("Yield already pending or task not active")
            state.update(phase="YIELD_REQUESTED", requestId=ev["id"], requestStatus="PENDING", lastReason=ev["reason"])
            continue
        if t == "QUARANTINE":
            if state["phase"] not in {"ACTIVE", "YIELD_REQUESTED"}:
                raise Conflict("Cannot quarantine unowned task")
            state.update(phase="QUARANTINED", generation=gen + 1, requestId=ev["id"], lastReason=ev["reason"])
            continue
        if t == "RECOVER":
            if state["phase"] != "QUARANTINED":
                raise Conflict("Recovery requires quarantine")
            state.update(phase="AWAITING_INTEGRATION" if state["candidate"] else "AVAILABLE", owner=None, claimId=None,
                         leaseUntil=None, resources=[], requestId=None,
                         originalStatus=None, workingStatus=None)
            continue
        if state["phase"] not in {"ACTIVE", "YIELD_REQUESTED"} or actor != state["owner"] or ev.get("claimId") != state["claimId"]:
            raise Conflict("Not current claim owner")
        if t == "HEARTBEAT":
            if utc(ev["leaseUntil"]) <= utc(ev["at"]):
                raise Conflict("Heartbeat must extend future lease")
            state.update(lastHeartbeatAt=ev["at"], leaseUntil=ev["leaseUntil"])
        elif t == "PROGRESS":
            state["lastProgressAt"] = ev["at"]
        elif t == "CHECKPOINT_READY":
            state.update(lastProgressAt=ev["at"], checkpointRef=ev["evidenceRef"])
        elif t == "YIELD_ACK":
            if state["phase"] != "YIELD_REQUESTED" or ev["inReplyTo"] != state["requestId"]:
                raise Conflict("Stale or missing yield request to acknowledge")
            state["requestStatus"] = "ACKNOWLEDGED"
        elif t == "YIELD_DEFERRED":
            if state["phase"] != "YIELD_REQUESTED" or ev["inReplyTo"] != state["requestId"]:
                raise Conflict("Stale or missing yield request to defer")
            state["requestStatus"] = "DEFERRED"
        elif t == "DELIVER":
            if state["phase"] != "ACTIVE" or not state["contractDigest"] or ev["candidate"]["contractDigest"] != state["contractDigest"]:
                raise Conflict("Candidate requires unchanged claimed contract")
            intent = state["deliveryIntent"]
            if not intent or any(ev["candidate"][k] != intent[k] for k in ("repository","targetRef","scope")):
                raise Conflict("Candidate differs from authorized intent at claim")
            if state["candidate"] is not None:
                raise Conflict("Existing candidate must be reconciled, not overwritten")
            state.update(phase="AWAITING_INTEGRATION", candidate=ev["candidate"], owner=None,
                         claimId=None, resources=[], leaseUntil=None, checkpointRef=ev["evidenceRef"])
        elif t == "COMPLETE":
            if state["phase"] != "ACTIVE" or not state["integrationOwner"] or state["candidate"] is None:
                raise Conflict("Completion requires adopted candidate")
            state.update(phase="COMPLETED", completion=ev, owner=None, claimId=None,
                         resources=[], leaseUntil=None)
        elif t == "RELEASE":
            state.update(phase="AWAITING_INTEGRATION" if state["candidate"] else "AVAILABLE", owner=None, claimId=None, resources=[],
                         leaseUntil=None, requestId=None, requestStatus=None,
                         originalStatus=None, workingStatus=None)
    return state


def task_state(task: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(task, dict) or not TASK_ID.fullmatch(str(task.get("id", ""))):
        raise ValueError("Invalid task")
    return replay(parse_comments(task.get("comments")))


def _scope_parts(scope: str) -> tuple[str, list[str]]:
    scheme, rest = scope.split("://", 1)
    return scheme, rest.split("/")


def scope_conflict(left: str, right: str) -> bool:
    """Conservative hierarchical scope conflicts; '*' is an entire subtree."""
    if not RESOURCE.fullmatch(left) or not RESOURCE.fullmatch(right):
        raise ValueError("Unknown scope")
    a, sa = _scope_parts(left)
    b, sb = _scope_parts(right)
    if a != b:
        return False  # Caller must declare cross-domain effects explicitly.
    for x, y in zip(sa, sb):
        if x == "*" or y == "*":
            return True
        if x != y:
            return False
    return True  # ancestor and descendant paths collide


def conflict_with_active(resources: list[str], tasks: list[dict[str, Any]], target: str) -> list[str]:
    _resources(resources)
    conflicts = []
    for task in tasks:
        if task["id"] == target:
            continue
        state = task_state(task)
        if state["phase"] not in {"ACTIVE", "YIELD_REQUESTED", "QUARANTINED"}:
            continue
        if any(scope_conflict(a, b) for a in resources for b in state["resources"]):
            conflicts.append(task["id"])
    return sorted(conflicts)


def task_candidate(task: dict[str, Any], state: dict[str, Any], statuses: list[str] | None = None) -> str:
    """Fail closed: isReady is only DAG-readiness, not a free claim."""
    if state["phase"] == "AWAITING_INTEGRATION":
        return "INTEGRATION_PENDING"
    if task.get("archived") is not False or task.get("isReady") is not True:
        return "NOT_READY"
    if state["phase"] != "AVAILABLE":
        return "OWNED_OR_QUARANTINED"
    # Configured columns are explicit: no guessing from arbitrary In Progress,
    # Done or archived statuses. Default is a conservative compatibility set.
    if statuses is not None:
        if (not isinstance(statuses, list) or not 1 <= len(statuses) <= 16
                or any(not isinstance(x, str) or not x.strip() or len(x) > 120 for x in statuses)
                or len(set(x.casefold().strip() for x in statuses)) != len(statuses)):
            raise ValueError("Invalid configured claimable status names")
    claimable = statuses if statuses is not None else ["To Do", "Todo", "Open", "Ready", "Not Started", "Pending"]
    status = str(task.get("status", "")).casefold().strip().replace("_", " ").replace("-", " ")
    if status not in {x.casefold().strip().replace("_", " ").replace("-", " ") for x in claimable}:
        return "UNMANAGED_ACTIVE_OR_TERMINAL"
    # In the absence of a configured terminal status, be conservative about other assignees.
    if task.get("assignees"):
        return "ASSIGNED_WITHOUT_COORDINATION"
    return "CANDIDATE"


def triage(tasks: list[dict[str, Any]], now: str, no_progress_minutes: int = 30) -> dict[str, Any]:
    current = utc(now)
    if type(no_progress_minutes) is not int or not 1 <= no_progress_minutes <= 10080:
        raise ValueError("Invalid progress interval")
    rows = []
    for task in tasks:
        state = task_state(task)
        phase = state["phase"]
        expired = bool(state["leaseUntil"] and current > utc(state["leaseUntil"]))
        reference = state["lastProgressAt"] or state["claimAt"]
        stalled = bool(reference and (current - utc(reference)).total_seconds() >= no_progress_minutes * 60)
        # Liveness and useful progress are separate dimensions.
        health = ("QUARANTINED" if phase == "QUARANTINED" else
                  "YIELD_REQUESTED" if phase == "YIELD_REQUESTED" else
                  "SUSPECT" if phase == "ACTIVE" and expired else
                  "STALLED" if phase == "ACTIVE" and stalled else
                  "ACTIVE" if phase == "ACTIVE" else
                  task_candidate(task, state))
        rows.append({"taskId": task["id"], "health": health, "owner": state["owner"],
                     "generation": state["generation"], "leaseExpired": expired,
                     "lastProgressAt": state["lastProgressAt"], "checkpointRef": state["checkpointRef"],
                     "reason": state["lastReason"], "requestStatus": state["requestStatus"],
                     "candidate": state["candidate"], "completion": state["completion"]})
    return {"kind": "coordination-triage-v1", "total": len(rows), "tasks": rows,
            "notice": "Advisory: lack of heartbeat/progress does not prove the old worker stopped."}


def make_event(kind: str, *, actor: str, id: str, at: str, generation: int, **fields: Any) -> str:
    obj = {"v": 1, "type": kind, "id": id, "actor": actor,
           "at": at, "generation": generation, **fields}
    _event(obj)
    return PREFIX + json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def labels_for_phase(phase: str) -> set[str]:
    return {
        "ACTIVE": {"coord:claimed"},
        "YIELD_REQUESTED": {"coord:claimed", "coord:yield-requested"},
        "QUARANTINED": {"coord:quarantined", "coord:needs-recovery"},
        "AVAILABLE": set(),
        "AWAITING_INTEGRATION": {"coord:awaiting-integration"},
        "COMPLETED": set(),
    }[phase]
