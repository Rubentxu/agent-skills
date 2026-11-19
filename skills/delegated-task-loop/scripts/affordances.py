#!/usr/bin/env python3
"""Pure navigation over explicitly observed state; never invokes host or providers."""
from __future__ import annotations
import json
import sys
from pathlib import Path

BACKLOG = "backlog-agile-workflow"
KNOWLEDGE = "software-knowledge"
GOLDFISH = "goldfish-review"
TESTING = "delivery-first-testing"
PHASES = {"discover", "ready", "running", "verify", "review", "accept", "learn", "release", "interrupted", "stopped"}
CAPS = {"fresh", "background", "notify", "progress", "steer", "cancel", "resume", "reviewReadOnly"}
SIGNALS = {"normal", "repeated-failure", "stalled", "budget-exhausted", "context-pressure", "scope-drift", "question", "result", "pending", "silence", "resource-drift","relay-assess","relay-checkpoint","relay-deadline"}

def validate(s):
    if not isinstance(s, dict) or type(s.get("schemaVersion")) is not int or s["schemaVersion"] != 1 or s.get("kind") != "delegated-loop-state":
        raise ValueError("expected delegated-loop-state v1")
    required = {"schemaVersion", "kind", "phase", "availableSkills", "capabilities", "budgetRemaining", "taskId", "signal", "ownership", "evidence", "review", "outcome"}
    optional={"preflight","preflightRef","resourceState","relayRequired","relayReady"}
    for k in ("relayRequired","relayReady"):
        if k in s and type(s[k]) is not bool:raise ValueError("invalid relay flag")
    if required-set(s) or set(s)-required-optional:
        raise ValueError("missing or unexpected state fields")
    preflight=s.get("preflight","unknown")
    resources=s.get("resourceState","unknown")
    if preflight not in ("unknown","needs-refinement","prepared") or resources not in ("unknown","clear","live","adoptable"):
        raise ValueError("invalid preparation or resource state")
    if preflight=="prepared" and (not isinstance(s.get("preflightRef"),str) or not s["preflightRef"].strip() or len(s["preflightRef"])>1024):
        raise ValueError("prepared handoff requires reference")
    for name, allowed in (
        ("phase", PHASES), ("signal", SIGNALS),
        ("ownership", {"unknown", "clear", "active", "terminated"}),
        ("evidence", {"unknown", "sufficient", "insufficient"}),
        ("review", {"none", "required", "resolved", "not-run"}),
        ("outcome", {"unknown", "accepted", "blocked"}),
    ):
        if not isinstance(s[name], str) or s[name] not in allowed:
            raise ValueError("invalid " + name)
    if not isinstance(s["availableSkills"], list) or any(not isinstance(x, str) or not x for x in s["availableSkills"]):
        raise ValueError("invalid availableSkills")
    caps = s["capabilities"]
    if not isinstance(caps, dict) or set(caps) - CAPS or any(type(v) is not bool for v in caps.values()):
        raise ValueError("invalid capabilities")
    if type(s["budgetRemaining"]) is not int or s["budgetRemaining"] < 0:
        raise ValueError("invalid budgetRemaining")
    if s["taskId"] is not None and (not isinstance(s["taskId"], str) or not s["taskId"].strip() or len(s["taskId"]) > 128):
        raise ValueError("invalid taskId")
    if s["phase"] in {"running", "verify", "review", "accept", "learn", "interrupted"} and not s["taskId"]:
        raise ValueError("taskId required")

def route(s):
    validate(s)
    skills, caps = set(s["availableSkills"]), s["capabilities"]
    phase, ownership, signal = s["phase"], s["ownership"], s["signal"]
    prepared=s.get("preflight","unknown")
    resources=s.get("resourceState","unknown")
    links, lenses, limits = [], [], []
    decision = "READY"

    def link(rel, **kwargs):
        links.append({"rel": rel, **kwargs})

    def provider(rel, skill, operation):
        if skill in skills:
            link(rel, skill=skill, operation=operation)
        else:
            limits.append(skill + ": unavailable")

    def native(rel, cap):
        if caps.get(cap, False):
            link(rel, capability=cap)

    def reconcile():
        nonlocal decision
        decision = "RECONCILE"
        lenses.append("references/recovery.md")
        link("reconcile-ownership")

    if phase == "stopped":
        decision = "STOP"
    elif phase == "discover":
        lenses.append("references/host-capabilities.md")
        link("discover-host")
        provider("locate-home", KNOWLEDGE, "locate-home")
        provider("discover-board", BACKLOG, "discover")
        if ownership != "clear":
            link("reconcile-ownership")
        if not caps.get("fresh"):
            limits.append("fresh subagent not confirmed")
    elif phase == "ready":
        if ownership != "clear":
            reconcile()
        elif s["budgetRemaining"] == 0:
            decision = "STOP"
        elif not caps.get("fresh"):
            decision = "NOT_RUN"
            limits.append("fresh subagent not confirmed")
        elif BACKLOG not in skills:
            decision = "DEGRADED"
            limits.append("Backlog authority unavailable")
        elif not s["taskId"]:
            provider("select-task", BACKLOG, "ready_candidates")
        elif resources!="clear":
            decision="RECONCILE"
            lenses.append("references/resource-adoption.md")
            link("reconcile-live-resources")
        elif prepared=="prepared":
            lenses.append("references/handoff-engineering.md")
            native("delegate-after-preflight", "fresh")
        else:
            decision="NEEDS_REFINEMENT" if prepared=="needs-refinement" else "PREPARE"
            lenses.extend(["references/handoff-engineering.md", "references/skill-composition.md"])
            provider("verify-task-anchors", BACKLOG, "technical_readiness")
            provider("prepare-handoff", BACKLOG, "context_handoff")
            provider("prepare-verification-plan", TESTING, "verification_plan")
            provider("prepare-context", KNOWLEDGE, "context-pack")
            provider("recover-verified-facts", KNOWLEDGE, "verified_facts")
            link("validate-versioned-handoff")
    elif phase == "running":
        if ownership != "active":
            reconcile()
        else:
            lenses.append("references/supervision.md")
            if signal in ("relay-assess","relay-checkpoint","relay-deadline"):
                decision={"relay-assess":"ASSESS_RELAY","relay-checkpoint":"PREPARE_RELAY","relay-deadline":"RECONCILE_RELAY"}[signal]
                lenses.append("references/endurance-relay.md")
                link("assess-remaining-work")
                if signal!="relay-assess":
                    link("checkpoint")
                    link("reconcile-relay")
                native("steer", "steer")
            elif signal in {"repeated-failure", "stalled"}:
                decision = "INTERVENE"
                provider("recover-flow", BACKLOG, "stalled-work")
                native("steer", "steer")
            elif signal == "scope-drift":
                decision = "INTERVENE"
                link("revalidate-scope")
                native("steer", "steer")
            elif signal == "question":
                decision = "INTERVENE"
                provider("recover-context", KNOWLEDGE, "context-pack")
                link("answer-question")
                native("steer", "steer")
            elif signal == "budget-exhausted":
                decision = "CHECKPOINT"
                link("checkpoint")
                link("stop-or-reconcile")
                native("steer", "steer")
            elif signal == "context-pressure":
                decision = "CHECKPOINT"
                link("checkpoint")
                provider("recover-context", KNOWLEDGE, "context-pack")
                native("steer", "steer")
            elif signal == "pending":
                decision = "WAIT_PENDING"
                link("reconcile-live-resources")
                link("await-existing-operation")
            elif signal in {"silence","resource-drift"}:
                decision = "RECONCILE"
                link("observe-liveness")
                link("reconcile-live-resources")
                native("steer", "steer")
            elif signal == "result":
                link("reconcile-result")
            else:
                if caps.get("progress"):
                    native("observe-events", "progress")
                elif caps.get("background") and caps.get("notify"):
                    native("await-notification", "notify")
                else:
                    link("await-native-result")
                    limits.append("live progress not confirmed")
            native("interrupt-if-authorized", "cancel")
    elif phase == "interrupted":
        lenses.append("references/recovery.md")
        if ownership != "terminated":
            decision = "RECONCILE"
            link("reconcile-ownership")
        elif s["budgetRemaining"] == 0:
            decision = "STOP"
            link("preserve-checkpoint")
        elif resources not in ("clear","adoptable"):
            decision="RECONCILE"
            link("adopt-live-resources-before-resume")
        else:
            link("revalidate-checkpoint")
            link("adopt-live-resources-before-resume")
            if s.get("relayRequired"):
                if not s.get("relayReady") or prepared!="prepared":
                    decision="PREPARE_RELAY"
                    link("compile-baton")
                    link("validate-fresh-successor")
                elif caps.get("fresh"):
                    decision="RELAY_READY"
                    native("delegate-successor", "fresh")
                else:
                    decision="NOT_RUN"
                    limits.append("fresh successor unavailable; preserve checkpoint")
            elif caps.get("resume"):
                native("resume-after-revalidation", "resume")
            elif caps.get("fresh"):
                native("replace-after-revalidation", "fresh")
            else:
                decision = "NOT_RUN"
    elif phase in {"verify", "review", "accept"}:
        if ownership not in {"clear", "terminated"}:
            reconcile()
        elif resources!="clear":
            decision="RECONCILE"
            lenses.append("references/resource-adoption.md")
            link("reconcile-live-resources")
        else:
            lenses.append("references/proportional-verification.md")
            if phase == "verify" or s["evidence"] != "sufficient":
                provider("verify-evidence", BACKLOG, "verify")
                if s["evidence"] != "sufficient":
                    decision = "NEEDS_EVIDENCE"
            if s["review"] in {"required", "not-run"}:
                if GOLDFISH in skills and caps.get("fresh") and caps.get("reviewReadOnly"):
                    provider("request-independent-review", GOLDFISH, "review")
                else:
                    limits.append("independent review not available")
                decision = "REVIEW_PENDING"
            elif phase == "accept" and s["evidence"] == "sufficient":
                if BACKLOG in skills:
                    provider("accept-after-authority-check", BACKLOG, "close")
                else:
                    decision = "DEGRADED"
                    limits.append("Backlog authority unavailable")
            elif phase != "accept" and s["evidence"] == "sufficient":
                link("revalidate-for-acceptance")
    elif phase == "learn":
        if s["outcome"] != "accepted":
            link("reconcile-result")
        else:
            provider("reconcile-learning", KNOWLEDGE, "checkpoint")
            link("checkpoint-supervisor")
    elif phase == "release":
        if ownership not in {"clear", "terminated"}:
            reconcile()
        elif resources!="clear":
            decision="RECONCILE"
            lenses.append("references/resource-adoption.md")
            link("reconcile-live-resources")
        else:
            link("release-owned-resources")
            link("checkpoint-supervisor")
    return {"schemaVersion": 1, "kind": "delegated-loop-affordances", "decision": decision,
            "lenses": lenses[:2], "_links": links, "limitations": limits, "authorized": False}

def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError("usage: affordances.py FILE|-")
        raw = sys.stdin.read(65537) if sys.argv[1] == "-" else Path(sys.argv[1]).read_bytes()
        if len(raw) > 65536:
            raise ValueError("state too large")
        print(json.dumps(route(json.loads(raw)), ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
