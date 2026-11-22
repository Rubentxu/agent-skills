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
import re
from typing import Any

PREFIX = "COORDINATION_EVENT_V1 "
MAX_EVENTS = 1000
MAX_EVENT_BYTES = 8192
COORD_LABELS = frozenset({
    "coord:claimed", "coord:stalled", "coord:yield-requested",
    "coord:handoff-ready", "coord:needs-recovery", "coord:quarantined",
})
TASK_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
RESOURCE = re.compile(r"^(repo|api|k8s|test|service)://[A-Za-z0-9._/@:+*=-]+$")
ID = re.compile(r"^[A-Za-z0-9_.:@/-]{1,160}$")
EVENTS = frozenset({"CLAIM", "HEARTBEAT", "PROGRESS", "YIELD_REQUESTED",
                    "YIELD_ACK", "YIELD_DEFERRED", "CHECKPOINT_READY",
                    "RELEASE", "QUARANTINE", "RECOVER"})


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


def _event(obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict) or obj.get("v") != 1 or obj.get("type") not in EVENTS:
        raise ValueError("Unknown coordination event")
    if not isinstance(obj.get("generation"), int) or isinstance(obj["generation"], bool) or obj["generation"] < 0:
        raise ValueError("Invalid generation")
    for key in ("id", "actor"):
        _id(obj.get(key), key)
    utc(obj.get("at"))
    t = obj["type"]
    if t in {"CLAIM", "HEARTBEAT", "PROGRESS", "YIELD_ACK", "YIELD_DEFERRED", "CHECKPOINT_READY", "RELEASE"}:
        _id(obj.get("claimId"), "claimId")
    if t == "CLAIM":
        _resources(obj.get("resources"))
        _id(obj.get("harness"), "harness")
        utc(obj.get("leaseUntil"))
    elif t == "HEARTBEAT":
        utc(obj.get("leaseUntil"))
    elif t in {"RELEASE", "RECOVER"}:
        if obj.get("resourcesClear") is not True or not isinstance(obj.get("evidenceRef"), str) or not obj["evidenceRef"].strip():
            raise ValueError("Release/recovery requires confirmed clear inventory evidence")
    elif t == "QUARANTINE":
        if not isinstance(obj.get("reason"), str) or not obj["reason"].strip():
            raise ValueError("Quarantine must state its reason")
    elif t in {"PROGRESS", "CHECKPOINT_READY"}:
        if not isinstance(obj.get("evidenceRef"), str) or not obj["evidenceRef"].strip():
            raise ValueError("Material progress requires evidenceRef")
    elif t == "YIELD_REQUESTED":
        if not isinstance(obj.get("reason"), str) or not obj["reason"].strip():
            raise ValueError("Yield needs a reason")
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
                             "checkpointRef": None, "requestId": None, "claimAt": None}
    for obj in events:
        ev = _event(obj)
        t, gen, actor = ev["type"], ev["generation"], ev["actor"]
        prev = state["generation"]
        if t == "CLAIM":
            if state["phase"] != "AVAILABLE" or gen != prev + 1:
                raise Conflict("Conflicting claim or stale generation")
            state.update(owner=actor, claimId=ev["claimId"], generation=gen,
                         resources=_resources(ev["resources"]), leaseUntil=ev["leaseUntil"],
                         lastHeartbeatAt=ev["at"], claimAt=ev["at"], lastProgressAt=None,
                         checkpointRef=None, requestId=None, phase="ACTIVE")
            continue
        if gen != prev:
            raise Conflict("Stale event generation")
        if t == "YIELD_REQUESTED":
            if state["phase"] not in {"ACTIVE", "YIELD_REQUESTED"}:
                raise Conflict("No active owner for yield request")
            state.update(phase="YIELD_REQUESTED", requestId=ev["id"])
            continue
        if t == "QUARANTINE":
            if state["phase"] not in {"ACTIVE", "YIELD_REQUESTED"}:
                raise Conflict("Cannot quarantine unowned task")
            state.update(phase="QUARANTINED", generation=gen + 1, requestId=ev["id"])
            continue
        if t == "RECOVER":
            if state["phase"] != "QUARANTINED":
                raise Conflict("Recovery requires quarantine")
            state.update(phase="AVAILABLE", owner=None, claimId=None,
                         leaseUntil=None, resources=[], requestId=None)
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
            if state["phase"] != "YIELD_REQUESTED":
                raise Conflict("No yield request to acknowledge")
        elif t == "YIELD_DEFERRED":
            if state["phase"] != "YIELD_REQUESTED":
                raise Conflict("No yield request to defer")
        elif t == "RELEASE":
            state.update(phase="AVAILABLE", owner=None, claimId=None, resources=[],
                         leaseUntil=None, requestId=None)
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
    if task.get("archived") is not False or task.get("isReady") is not True:
        return "NOT_READY"
    if state["phase"] != "AVAILABLE":
        return "OWNED_OR_QUARANTINED"
    status = str(task.get("status", "")).casefold().replace("_", " ").replace("-", " ")
    if status in {"in progress", "inprogress", "doing", "review", "done", "complete", "completed", "blocked"}:
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
                     "lastProgressAt": state["lastProgressAt"], "checkpointRef": state["checkpointRef"]})
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
    }[phase]
