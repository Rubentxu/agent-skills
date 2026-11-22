#!/usr/bin/env python3
"""Classify structured harness observations without scraping private transcripts.

No network, side effects or provider-specific secrets. A classification is a
recommendation; it does not claim, release, stop a worker or authenticate a host.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

QUOTA = frozenset({"insufficient_quota", "quota_exhausted", "credits_exhausted", "usage_limit_reached"})
RATE = frozenset({"rate_limit_exceeded", "too_many_requests", "rate_limited"})
AUTH = frozenset({"unauthorized", "authentication_failed", "token_expired", "forbidden"})


def classify(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("kind") != "harness-observation-v1":
        raise ValueError("Expected harness-observation-v1")
    allowed = {"kind", "taskId", "agentId", "claimId", "harness", "signal", "code", "httpStatus",
               "retryAfterSeconds", "observedAt", "processStopped", "operationsClear", "evidenceRef"}
    if set(payload) - allowed:
        raise ValueError("Unknown observation keys")
    for key in ("taskId", "agentId", "claimId", "harness", "observedAt", "evidenceRef"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise ValueError("Missing or invalid " + key)
    signal = payload.get("signal")
    if signal not in {"provider_error", "process_stopped", "no_progress", "external_wait", "heartbeat_lost"}:
        raise ValueError("Unknown signal")
    code = payload.get("code")
    if code is not None and (not isinstance(code, str) or len(code) > 100):
        raise ValueError("Invalid structured provider code")
    status = payload.get("httpStatus")
    if status is not None and (type(status) is not int or status not in range(100, 600)):
        raise ValueError("Invalid HTTP status")
    retry = payload.get("retryAfterSeconds")
    if retry is not None and (type(retry) is not int or not 0 <= retry <= 604800):
        raise ValueError("Invalid Retry-After")
    for key in ("processStopped", "operationsClear"):
        if key in payload and type(payload[key]) is not bool:
            raise ValueError("Invalid observation flag")
    if signal == "provider_error":
        if code in QUOTA:
            health, action = "CAPACITY_BLOCKED", "REQUEST_YIELD"
        elif code in AUTH or status in {401, 403}:
            health, action = "AUTH_BLOCKED", "REQUEST_YIELD"
        elif code in RATE or status == 429:
            health, action = "RATE_LIMITED", "RETRY_OR_YIELD"
        else:
            health, action = "UNKNOWN_PROVIDER_FAILURE", "INSPECT_HOST"
    elif signal == "process_stopped":
        if payload.get("processStopped") is not True:
            health, action = "UNVERIFIED_STOP", "INSPECT_HOST"
        elif payload.get("operationsClear") is True:
            health, action = "STOPPED_RESOURCES_CLEAR", "RECONCILE_AND_YIELD"
        else:
            health, action = "STOPPED_OPERATIONS_UNKNOWN", "QUARANTINE_AND_RECONCILE"
    elif signal == "no_progress":
        health, action = "STALLED", "REQUEST_DIAGNOSIS_OR_YIELD"
    elif signal == "external_wait":
        health, action = "WAITING_EXTERNAL", "CHECK_AND_POSSIBLY_YIELD"
    else:
        health, action = "SUSPECT", "TRIAGE_NO_AUTO_RELEASE"
    return {"kind": "harness-advice-v1", "taskId": payload["taskId"],
            "claimId": payload["claimId"], "observedAt": payload["observedAt"],
            "classification": health, "recommendation": action,
            "retryAfterSeconds": retry, "evidenceRef": payload["evidenceRef"],
            "_links": [{"rel": "yield", "href": "references/lenses/yield-negotiation.md"},
                       {"rel": "recover", "href": "references/lenses/stalled-work-recovery.md"}],
            "notice": "Structured observed signals are claims, not authenticated stop or quota proof. Do not release on classification alone."}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: harness_signal.py <observed-harness-event.json>")
    p = Path(sys.argv[1])
    if not p.is_file() or p.is_symlink() or p.stat().st_size > 32768:
        raise ValueError("Unsafe or missing observation")
    print(json.dumps(classify(json.loads(p.read_text(encoding="utf-8"))), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
