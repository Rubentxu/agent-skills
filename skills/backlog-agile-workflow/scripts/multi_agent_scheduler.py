#!/usr/bin/env python3
"""Pure, HATEOAS-style multi-harness Backlog.md assignment projection.

Reads an explicit complete task-list + task-view snapshot with scope observations;
never accesses the CLI, mutates tasks, reserves work or launches workers.
"""
from __future__ import annotations

from collections import deque
import json
from pathlib import Path
import sys
from typing import Any

from multi_agent import _resources, conflict_with_active, scope_conflict, task_candidate, task_state


class InvalidPlan(ValueError):
    pass


def _graph(tasks: list[dict[str, Any]]) -> tuple[dict[str, list[str]], dict[str, int], list[list[str]]]:
    ids = {task["id"] for task in tasks}
    next_tasks = {task["id"]: [] for task in tasks}
    indegree = {task["id"]: 0 for task in tasks}
    dependencies = {task["id"]: task.get("dependencies") or [] for task in tasks}
    for task in tasks:
        tid = task["id"]
        if not isinstance(dependencies[tid], list) or any(not isinstance(d, str) for d in dependencies[tid]):
            raise InvalidPlan("Malformed dependency list")
        for dep in dependencies[tid]:
            if dep in ids:
                if tid not in next_tasks[dep]:
                    next_tasks[dep].append(tid)
                    indegree[tid] += 1
            # External/archived IDs: isReady authoritative; do not assume missing
            # from visible list means unresolved or completed.
    queue = deque(i for i, n in indegree.items() if n == 0)
    topo = []
    while queue:
        item = queue.popleft()
        topo.append(item)
        for nxt in next_tasks[item]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if len(topo) != len(tasks):
        # Iterative Kosaraju SCC on residual nodes: O(V+E), no Python recursion.
        residual = {i for i, value in indegree.items() if value > 0}
        reverse = {i: [] for i in residual}
        for i in residual:
            for nxt in next_tasks[i]:
                if nxt in residual:
                    reverse[nxt].append(i)
        visited = set()
        finished = []
        for start in residual:
            if start in visited:
                continue
            visited.add(start)
            stack = [(start, iter(next_tasks[start]))]
            while stack:
                vertex, edges = stack[-1]
                try:
                    nxt = next(edges)
                except StopIteration:
                    finished.append(vertex)
                    stack.pop()
                    continue
                if nxt in residual and nxt not in visited:
                    visited.add(nxt)
                    stack.append((nxt, iter(next_tasks[nxt])))
        visited.clear()
        components = []
        for start in reversed(finished):
            if start in visited:
                continue
            component = []
            todo = [start]
            visited.add(start)
            while todo:
                item = todo.pop()
                component.append(item)
                for prv in reverse[item]:
                    if prv not in visited:
                        visited.add(prv)
                        todo.append(prv)
            if len(component) > 1 or start in next_tasks[start]:
                components.append(sorted(component))
        return next_tasks, {}, sorted(components)

    depth = {i: 0 for i in topo}
    for i in reversed(topo):
        depth[i] = 1 + max((depth[n] for n in next_tasks[i]), default=0)
    return next_tasks, depth, []


def schedule(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("kind") != "multi-agent-plan-v1":
        raise InvalidPlan("Expected multi-agent-plan-v1")
    source = payload.get("taskList")
    if not isinstance(source, dict) or source.get("kind") != "task-list" or source.get("schemaVersion") != 1:
        raise InvalidPlan("Unsupported Backlog task-list envelope")
    if source.get("nextSkip") is not None:
        raise InvalidPlan("A paginated board cannot be used for global scheduling")
    tasks = source.get("tasks")
    details = payload.get("details")
    resources = payload.get("resources")
    agents = payload.get("agents")
    claimable_statuses = payload.get("claimableStatuses")
    if claimable_statuses is not None:
        # Validate even if no tasks are currently ready.
        task_candidate({"archived": False, "isReady": True, "status": "__validation__",
                        "assignees": []}, {"phase": "AVAILABLE"}, claimable_statuses)
    if (not isinstance(tasks, list) or not isinstance(details, dict) or not isinstance(resources, dict)
            or not isinstance(agents, list) or len(tasks) > 20000 or len(agents) > 100):
        raise InvalidPlan("Malformed or oversized snapshot")
    ids = [t.get("id") for t in tasks if isinstance(t, dict)]
    if len(ids) != len(tasks) or len(set(ids)) != len(ids) or any(not isinstance(i, str) for i in ids):
        raise InvalidPlan("Invalid or duplicate task IDs")
    if set(details) != set(ids):
        raise InvalidPlan("All task views are required to check coordination ownership")
    for t in tasks:
        detail = details[t["id"]]
        if not isinstance(detail, dict) or detail.get("id") != t["id"]:
            raise InvalidPlan("Task view mismatch")
        for field in ("status", "isReady", "archived", "assignees"):
            if t.get(field) != detail.get(field):
                raise InvalidPlan("Task snapshot changed: " + field)
    next_tasks, depth, cycles = _graph(tasks)
    if cycles:
        return {"kind": "multi-agent-proposal-v1", "status": "INVALID_DEPENDENCY_GRAPH",
                "cycles": cycles, "assignments": [], "_links": [
                {"rel": "inspect-dependencies", "href": "references/lenses/dependency-management.md"}]}
    for a in agents:
        if (not isinstance(a, dict) or not isinstance(a.get("id"), str) or
                not isinstance(a.get("skills"), list) or
                not all(isinstance(x, str) for x in a["skills"]) or
                type(a.get("capacity")) is not int or not 0 <= a["capacity"] <= 8):
            raise InvalidPlan("Invalid worker capacity/capabilities")
    candidates = []
    skipped = []
    integration = []
    states = {tid: task_state(details[tid]) for tid in ids}
    for task in tasks:
        state = states[task["id"]]
        if state["phase"] == "AWAITING_INTEGRATION":
            integration.append({"taskId": task["id"], "candidate": state["candidate"],
                                "generation": state["generation"], "action": "ADOPT_OR_RECONCILE"})
    pending = len(integration)
    max_pending = payload.get("maxPendingIntegrations")
    if max_pending is not None and (type(max_pending) is not int or max_pending < 1):
        raise InvalidPlan("Invalid integration WIP limit")
    busy_repositories = {row["candidate"]["repository"] for row in integration}
    # Repository hints are explicit; never infer effect scopes from names.
    repositories = payload.get("repositories", {})
    if not isinstance(repositories, dict):
        raise InvalidPlan("Invalid repository hints")
    for rank, task in enumerate(tasks):
        tid = task["id"]
        state = states[tid]
        eligible = task_candidate(task, state, claimable_statuses)
        if eligible != "CANDIDATE":
            skipped.append({"taskId": tid, "reason": eligible})
            continue
        blocked_deps = [dep for dep in task.get("dependencies", [])
                        if dep not in states or (states[dep]["candidate"] and states[dep]["phase"] != "COMPLETED")]
        if blocked_deps:
            skipped.append({"taskId": tid, "reason": "DEPENDENCY_DELIVERY_PENDING", "dependencies": blocked_deps})
            continue
        if max_pending is not None and pending >= max_pending and repositories.get(tid) in busy_repositories:
            skipped.append({"taskId": tid, "reason": "PRIORITIZE_INTEGRATION"})
            continue
        if tid not in resources or resources[tid] is None:
            skipped.append({"taskId": tid, "reason": "EFFECT_SCOPES_UNKNOWN"})
            continue
        scopes = _resources(resources[tid])
        if not scopes:
            skipped.append({"taskId": tid, "reason": "EXCLUSIVE_SCOPE_REQUIRED"})
            continue
        conflicts = conflict_with_active(scopes, list(details.values()), tid)
        if conflicts:
            skipped.append({"taskId": tid, "reason": "RESOURCE_BUSY", "conflictsWith": conflicts})
            continue
        needs = task.get("requiredSkills", [])
        if not isinstance(needs, list) or not all(isinstance(x, str) for x in needs):
            raise InvalidPlan("Invalid skill requirement")
        priority = task.get("priority")
        # Existing product priority dominates optimization; when absent use CLI order.
        priority_index = {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(str(priority).lower(), 2)
        candidates.append((priority_index, -len(next_tasks[tid]), -depth[tid], rank, tid, scopes, set(needs)))
    candidates.sort()
    occupied = []
    assignments = []
    remaining = {a["id"]: a["capacity"] for a in agents}
    for _, _, _, _, tid, scopes, needs in candidates:
        if any(scope_conflict(a, b) for a in scopes for b in occupied):
            skipped.append({"taskId": tid, "reason": "BATCH_CONFLICT"})
            continue
        matches = [a for a in agents if remaining[a["id"]] and needs.issubset(a["skills"])]
        if not matches:
            skipped.append({"taskId": tid, "reason": "NO_ELIGIBLE_AGENT"})
            continue
        # Stable best-fit: prefer most free capacity, then agent ID.
        chosen = min(matches, key=lambda a: (-remaining[a["id"]], a["id"]))
        remaining[chosen["id"]] -= 1
        occupied.extend(scopes)
        assignments.append({"taskId": tid, "agentId": chosen["id"], "resources": scopes,
                            "authority": "PROPOSAL_ONLY"})
    return {"kind": "multi-agent-proposal-v1", "status": "PROPOSAL_ONLY",
            "assignments": assignments, "skipped": skipped, "integrationCandidates": integration, "pendingIntegrations": pending, "_links": [
                {"rel": "claim", "href": "references/lenses/multi-agent-coordination.md"},
                {"rel": "recover", "href": "references/lenses/stalled-work-recovery.md"}],
            "notice": "Recheck all claims and scopes atomically on authority branch before execution."}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: multi_agent_scheduler.py <complete-snapshot.json>")
    p = Path(sys.argv[1])
    if not p.is_file() or p.is_symlink() or p.stat().st_size > 8_388_608:
        raise ValueError("Missing or unsafe snapshot")
    print(json.dumps(schedule(json.loads(p.read_text())), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
