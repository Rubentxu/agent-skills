#!/usr/bin/env python3
"""Read-only planner of Backlog.md Kanban operations. No CLI or Git access."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

IDENTITY = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
CONFIG = ("autoCommit", "remoteOperations", "bypassGitHooks", "onStatusChange")


def outcome(op, decision, reason, argv=None):
    return {"schemaVersion": 1, "kind": "board-operation-proposal",
            "operation": op, "decision": decision, "status": "NAVIGATION_ONLY",
            "reason": reason, "suggestedArgv": argv,
            "next": "Reread current task/configuration before executing, then verify CLI result"}


def text(value, name, max_length=900):
    if not isinstance(value, str) or not value.strip() or len(value) > max_length or "\0" in value:
        raise ValueError("Invalid " + name)
    return value.strip()


def strings(value, name):
    if not isinstance(value, list) or len(value) > 30:
        raise ValueError("Invalid " + name)
    result = [text(s, name) for s in value]
    if len(set(result)) != len(result):
        raise ValueError("Duplicate " + name)
    return result


def task_observed(task):
    if not isinstance(task, dict):
        raise ValueError("Observed task object required")
    identity = text(task.get("id"), "task ID", 64)
    if not IDENTITY.fullmatch(identity):
        raise ValueError("Unsafe task ID")
    text(task.get("status"), "observed status")
    if type(task.get("archived")) is not bool:
        raise ValueError("Observed archived must be boolean")
    for name in ("isReady", "finalSummaryRecorded"):
        if name in task and type(task[name]) is not bool:
            raise ValueError("Invalid " + name)
    for name in ("acceptanceCriteriaCount", "acceptanceCriteriaCompleted",
                 "definitionOfDoneCount", "definitionOfDoneCompleted"):
        if name in task and (type(task[name]) is not int or task[name] < 0):
            raise ValueError("Invalid " + name)
    return task


def verified(task):
    """Completion reflects observed acceptance and DoD, not an administrative gate."""
    return all(task.get(k + "Count") is not None
               and task.get(k + "Completed") == task.get(k + "Count")
               for k in ("acceptanceCriteria", "definitionOfDone"))




def delivery_guard(data, task):
    """Observe technical acceptance, not just checkbox totals. No CLI execution."""
    if task.get("acceptanceCriteriaCount", 0) <= 0:
        return outcome("transition", "BLOCKED", "Final status requires actual acceptance criteria")
    assessment = data.get("deliveryAssessment")
    if not isinstance(assessment, dict):
        return outcome("transition", "INSPECT_MORE", "Observe technical acceptance at the authorized delivery target")
    if (assessment.get("kind") != "delivery-assessment" or assessment.get("schemaVersion") != 1
            or assessment.get("taskId") != task["id"]
            or assessment.get("acceptanceCriteriaCount") != task["acceptanceCriteriaCount"]
            or assessment.get("definitionOfDoneCount") != task["definitionOfDoneCount"]):
        return outcome("transition", "INSPECT_MORE", "Delivery assessment identity or criteria inventory differs")
    pin = data.get("acceptanceTaskDigest")
    if (not isinstance(pin, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", pin)
            or assessment.get("taskDigest") != pin or data.get("currentContractCompared") is not True):
        return outcome("transition", "INSPECT_MORE", "Compare original authorized contract with current task before closing")
    scope = assessment.get("scope")
    proof = assessment.get("observationDigest")
    if (scope not in ("research", "internal", "integration", "product-capability", "release")
            or not isinstance(assessment.get("targetRef"), str) or not assessment["targetRef"].strip()
            or not isinstance(proof, str) or not re.fullmatch(r"[0-9a-f]{64}", proof)):
        return outcome("transition", "INSPECT_MORE", "Scope, target and observation provenance required")
    if assessment.get("status") in ("FAIL", "BLOCKED"):
        return outcome("transition", "BLOCKED", "Technical acceptance not satisfied")
    if assessment.get("status") != "CANDIDATE_READY":
        return outcome("transition", "INSPECT_MORE", "Technical acceptance not yet evidenced")
    # The caller independently checks the sources. A JSON projection grants no permissions.
    return None


def reconcile_delivery(data):
    """Inspect supplied task/evidence observations without mutating the tracker."""
    if data.get("schemaVersion") != 1 or data.get("kind") != "delivery-reconciliation-input":
        raise ValueError("invalid reconciliation input")
    terminal = text(data.get("terminalStatus"), "terminal status")
    tasks = data.get("tasks")
    observations = data.get("observations")
    if not isinstance(tasks, list) or not isinstance(observations, list) or len(tasks) > 1000:
        raise ValueError("observed inventories required")
    by_id = {}
    for row in observations:
        if not isinstance(row, dict) or row.get("status") not in ("CANDIDATE_READY", "FAIL", "BLOCKED", "NOT_RUN"):
            raise ValueError("invalid technical observation")
        ident = text(row.get("taskId"), "task identity")
        if ident in by_id:
            raise ValueError("duplicate observation")
        if row["status"] != "NOT_RUN" and not strings(row.get("evidenceRefs", []), "evidence references"):
            raise ValueError("positive or negative claim requires evidence")
        by_id[ident] = row
    findings = []
    seen = set()
    for task in tasks:
        task = task_observed(task)
        ident = task["id"]
        if ident in seen:
            raise ValueError("duplicate task")
        seen.add(ident)
        row = by_id.get(ident)
        state = row["status"] if row else "NOT_RUN"
        reasons = []
        for k in ("acceptanceCriteria", "definitionOfDone"):
            count, done = task.get(k + "Count"), task.get(k + "Completed")
            if count is not None and done is not None and count != done:
                reasons.append(k + " incomplete")
        if task["status"] == terminal:
            if reasons or state == "FAIL":
                decision = "RECONCILE_CLOSURE"
            elif not verified(task) or state != "CANDIDATE_READY":
                decision = "INSPECT_EVIDENCE"
            else:
                decision = "KEEP_AS_IS"
        elif state == "CANDIDATE_READY":
            decision = "INSPECT_EXISTING_DELIVERY"
        else:
            decision = "KEEP_OPEN"
        findings.append({"taskId": ident, "decision": decision, "reasons": reasons,
                         "observationStatus": state, "evidenceRefs": row.get("evidenceRefs", []) if row else []})
    if set(by_id) - seen:
        raise ValueError("unknown observed task")
    return {"schemaVersion": 1, "kind": "delivery-reconciliation", "findings": findings,
            "authorized": False, "runtimeVerified": False}


def _owners(value):
    """An empty observed assignees list is a shared, unassigned WIP lane."""
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        return None
    names = [x.strip() for x in value]
    return (names or ["<unassigned>"]) if len(set(names)) == len(names) else None


def wip_guard(data, operation, target, current=None, task_id=None):
    """Apply a strict WIP simulation only when the caller opted into wipPolicy."""
    policy = data.get("wipPolicy")
    if policy is None:
        return None  # WIP is advisory by default and cannot block delivery.
    if not isinstance(policy, dict) or set(policy) != {"activeStatuses", "maxGlobal", "maxPerAssignee"}:
        raise ValueError("WIP policy requires activeStatuses, maxGlobal, maxPerAssignee")
    active = policy["activeStatuses"]
    if (not isinstance(active, list) or not active
            or any(not isinstance(x, str) or x not in data["statuses"] for x in active)
            or len(active) != len(set(active))
            or data["defaultStatus"] in active or data["terminalStatus"] in active):
        raise ValueError("WIP activeStatuses must be distinct, configured, non-default and nonterminal")
    if any(type(policy[key]) is not int or policy[key] < 1 for key in ("maxGlobal", "maxPerAssignee")):
        raise ValueError("WIP limits must be positive integers")
    if target not in active or (operation == "transition" and current in active):
        return None  # Exiting WIP or changing an active column consumes no extra slot.

    board = data.get("boardSnapshot")
    if (not isinstance(board, dict) or board.get("schemaVersion") != 1
            or board.get("kind") != "task-list" or not isinstance(board.get("tasks"), list)
            or data.get("boardComplete") is not True or "total" in board
            or board.get("nextSkip") is not None):
        return outcome(operation, "INSPECT_MORE",
                       "Read unfiltered backlog task list --json; verify complete policy scope and boardComplete=true")
    observed = {}
    for item in board["tasks"]:
        if (not isinstance(item, dict) or not isinstance(item.get("id"), str)
                or not IDENTITY.fullmatch(item["id"]) or item["id"] in observed
                or item.get("status") not in data["statuses"] or type(item.get("archived")) is not bool
                or _owners(item.get("assignees")) is None):
            return outcome(operation, "INSPECT_MORE", "WIP snapshot contains missing, duplicate or inconsistent task data")
        observed[item["id"]] = item
    if operation == "transition":
        candidate = observed.get(task_id)
        if candidate is None or candidate["status"] != current or candidate["archived"]:
            return outcome(operation, "INSPECT_MORE", "Task-view and task-list differ; refresh both before starting")
        owners = _owners(candidate["assignees"])
        if "assignees" in data["task"] and _owners(data["task"]["assignees"]) != owners:
            return outcome(operation, "INSPECT_MORE", "Task assignees changed since board snapshot")
        if data["task"].get("isReady") is not True:
            return outcome(operation, "INSPECT_MORE", "Starting a WIP slot requires isReady=true")
    elif operation == "restore":
        owners = _owners(data["task"].get("assignees"))
        if owners is None or (task_id in observed and not observed[task_id]["archived"]):
            return outcome(operation, "INSPECT_MORE", "Review archived task assignees and board identity")
    else:
        raise ValueError("WIP guard only handles transition and restore")

    running = [x for x in observed.values() if not x["archived"] and x["status"] in active]
    if len(running) >= policy["maxGlobal"]:
        return outcome(operation, "BLOCKED",
                       f"Global WIP full: {len(running)}/{policy['maxGlobal']}; finish or pause work first")
    occupied = {}
    for entry in running:
        for owner in _owners(entry["assignees"]):
            occupied[owner] = occupied.get(owner, 0) + 1
    for owner in owners:
        if occupied.get(owner, 0) >= policy["maxPerAssignee"]:
            return outcome(operation, "BLOCKED",
                           f"Owner WIP full for {owner}: {occupied[owner]}/{policy['maxPerAssignee']}")
    return None


def plan(data):
    if not isinstance(data, dict) or data.get("kind") != "board-operation" or data.get("schemaVersion") != 1:
        raise ValueError("Expected board-operation schemaVersion 1")
    op = data.get("operation")
    if op not in ("create", "transition", "archive", "restore", "delete"):
        raise ValueError("Unknown board operation")
    statuses = data.get("statuses")
    if (not isinstance(statuses, list) or not 2 <= len(statuses) <= 30
            or any(not isinstance(s, str) or not s.strip() or len(s) > 80 for s in statuses)
            or len(set(statuses)) != len(statuses)):
        raise ValueError("Configured statuses required")
    default = data.get("defaultStatus")
    if not isinstance(default, str) or default not in statuses:
        raise ValueError("Observed default status required")
    terminal = data.get("terminalStatus")
    if not isinstance(terminal, str) or terminal not in statuses:
        raise ValueError("Observed terminal status required")
    if op == "delete":
        return outcome(op, "BLOCKED", "Permanent deletion can release IDs and remove dependency links; separate human maintenance action required")
    if op == "create":
        if data.get("duplicateReview") != "clear":
            return outcome(op, "INSPECT_MORE", "Review existing tasks, drafts, archived records and historical identities")
        creation = data.get("newTask")
        if not isinstance(creation, dict):
            raise ValueError("newTask required")
        title = text(creation.get("title"), "title", 200)
        description = text(creation.get("description"), "description")
        ac = strings(creation.get("acceptanceCriteria"), "acceptance criteria")
        if not ac:
            return outcome(op, "BLOCKED", "At least one verifiable acceptance criterion required")
        selected = creation.get("status", default)
        if selected not in statuses or selected == terminal:
            return outcome(op, "BLOCKED", "New task requires configured, nonterminal status")
        refs = strings(creation.get("references", []), "references")
        argv = ["backlog", "task", "create", title, "-d", description]
        if selected != default:
            argv.extend(["-s", selected])
        for criterion in ac:
            argv.extend(["--ac", criterion])
        for ref in refs:
            argv.extend(["--ref", ref])
    else:
        task = task_observed(data.get("task"))
        tid, current = task["id"], task["status"]
        if current not in statuses:
            return outcome(op, "INSPECT_MORE", "Observed status differs from configured columns")
        if op == "transition":
            if task["archived"]:
                return outcome(op, "BLOCKED", "Archived tasks are read-only; restore first")
            target = data.get("targetStatus")
            if target not in statuses:
                return outcome(op, "BLOCKED", "Target must match configured column exactly")
            if target == current:
                return outcome(op, "NO_CHANGE", "Already in target column")
            if target == terminal and not verified(task):
                return outcome(op, "BLOCKED", "Final status requires observed completion of AC/DoD; no administrative gate is required")
            if target == terminal:
                guard = delivery_guard(data, task)
                if guard is not None:
                    return guard
            if current == terminal and target != terminal and not data.get("reopenReason"):
                return outcome(op, "INSPECT_MORE", "Reopening needs an explicit reason")
            if current == default and target != terminal and task.get("isReady") is False:
                return outcome(op, "INSPECT_MORE", "Check readiness and dependencies before starting")
            if target not in (default, terminal):
                verdict = wip_guard(data, op, target, current=current, task_id=tid)
                if verdict is not None:
                    return verdict
            argv = ["backlog", "task", "edit", tid, "-s", target]
        elif op == "archive":
            if task["archived"]:
                return outcome(op, "NO_CHANGE", "Task already archived")
            reason = data.get("archiveReason")
            if reason not in ("completed", "cancelled", "duplicate", "invalid", "obsolete"):
                return outcome(op, "INSPECT_MORE", "Explicit archive reason required")
            if reason == "completed":
                if current != terminal or not verified(task):
                    return outcome(op, "BLOCKED", "Completed archive requires verified AC/DoD and terminal status")
            elif data.get("dependencyImpact") != "reviewed":
                return outcome(op, "INSPECT_MORE", "Inspect genuine dependents before archiving unfinished work")
            argv = ["backlog", "task", "archive", tid]
        else:
            if not task["archived"]:
                return outcome(op, "NO_CHANGE", "Task already on the board")
            if current not in (default, terminal):
                verdict = wip_guard(data, op, current, task_id=tid)
                if verdict is not None:
                    return verdict
            argv = ["backlog", "task", "restore", tid]
    config = data.get("config")
    if (not isinstance(config, dict) or set(config) != set(CONFIG)
            or any(type(config[k]) is not bool for k in CONFIG)):
        return outcome(op, "INSPECT_MORE", "Observe all Git/callback configuration before any write")
    active = [k for k in CONFIG if config[k]]
    if active and data.get("effectsAcknowledged") is not True:
        return outcome(op, "BLOCKED", "Review configuration side effects: " + ", ".join(active))
    if data.get("authorized") is not True:
        return outcome(op, "PROPOSE_ONLY", "Explicit write permission required", argv)
    return outcome(op, "AUTHORIZED_ACTION", "Authorized proposal; this helper never executes CLI", argv)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: board_crud.py <board-operation.json>")
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    result = reconcile_delivery(data) if data.get("kind") == "delivery-reconciliation-input" else plan(data)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
