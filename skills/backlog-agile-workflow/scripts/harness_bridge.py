#!/usr/bin/env python3
"""Privacy-preserving hook bridge for Claude Code, Qwen Code, Codex and ACP hosts.

Normalizes *structured* lifecycle events to harness-observation-v1, without
reading transcripts, prompts, assistant text or credentials. Codex legacy notify
only reports turn completion: it cannot certify a quota failure or process stop.
This bridge never releases a claim. Optional --request-yield publishes an
idempotent request via the authoritative Backlog.md coordination CLI.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from harness_signal import classify

MAX_BYTES = 65_536
CLAUDE_ERRORS = {
    "rate_limit": "rate_limited", "overloaded": "rate_limited",
    "authentication_failed": "authentication_failed",
    "oauth_org_not_allowed": "authentication_failed",
    "cloud_credential_error": "authentication_failed",
    "account_on_hold": "authentication_failed",
    "billing_error": "billing_error",
}


def _bounded_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 200:
        raise ValueError("Invalid " + label)
    return value


def normalize(provider: str, payload: dict, *, task_id: str, agent_id: str,
              claim_id: str, observed_at: str, evidence_ref: str) -> dict:
    """Return one filtered, typed observation; unknown events fail closed."""
    if not isinstance(payload, dict):
        raise ValueError("Provider hook payload must be an object")
    for key, value in (("taskId", task_id), ("agentId", agent_id),
                       ("claimId", claim_id), ("evidenceRef", evidence_ref),
                       ("observedAt", observed_at)):
        _bounded_string(value, key)
    base = {"kind": "harness-observation-v1", "taskId": task_id,
            "agentId": agent_id, "claimId": claim_id,
            "harness": provider, "observedAt": observed_at,
            "evidenceRef": evidence_ref}
    if provider == "claude-code":
        event = payload.get("hook_event_name")
        if event == "StopFailure":
            # error is a hook enum, never parse free-text details.
            raw = payload.get("error")
            if not isinstance(raw, str):
                raise ValueError("Missing Claude StopFailure error type")
            base.update(signal="provider_error", code=CLAUDE_ERRORS.get(raw, "unknown"))
        elif event == "SessionEnd":
            base.update(signal="session_ending")
        else:
            raise ValueError("Unsupported Claude Code hook event")
    elif provider == "qwen-code":
        event = payload.get("hook_event_name")
        if event == "SessionEnd":
            base.update(signal="session_ending")
        elif event == "PostToolUseFailure":
            # Tool errors are not necessarily provider quota failures.
            base.update(signal="tool_failure")
        else:
            raise ValueError("Unsupported Qwen Code hook event")
    elif provider == "codex":
        # Legacy notify is only turn completion, not process termination.
        if payload.get("type") != "agent-turn-complete":
            raise ValueError("Unsupported Codex legacy notify event")
        base.update(signal="turn_completed")
    elif provider == "acp":
        # Host wrapper contract; ACP implementations vary.
        event = payload.get("event")
        if event == "provider_error":
            err = payload.get("error")
            if not isinstance(err, dict) or not isinstance(err.get("code"), str):
                raise ValueError("ACP host must supply structured error code")
            base.update(signal="provider_error", code=err["code"])
            status = err.get("httpStatus")
            if status is not None:
                base["httpStatus"] = status
            retry = err.get("retryAfterSeconds")
            if retry is not None:
                base["retryAfterSeconds"] = retry
        elif event == "turn_complete":
            base.update(signal="turn_completed")
        elif event == "session_ending":
            base.update(signal="session_ending")
        else:
            raise ValueError("Unsupported ACP host event")
    else:
        raise ValueError("Unknown harness provider")
    classify(base)
    return base


def _load_payload(argument: str | None) -> dict:
    # Codex passes notification JSON as argv, other hooks via stdin.
    raw = argument if argument is not None else sys.stdin.read(MAX_BYTES + 1)
    if len(raw.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Hook payload too large")
    return json.loads(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["claude-code", "qwen-code", "codex", "acp"], required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--claim-id", required=True)
    parser.add_argument("--evidence-ref", required=True, help="Non-secret reference to the hook observation")
    parser.add_argument("--json-argument", help="Codex legacy notify argv, otherwise stdin")
    parser.add_argument("--request-yield", action="store_true", help="Opt-in CAS YIELD_REQUESTED on explicit quota/auth failure only")
    parser.add_argument("--remote", help="Authoritative Home Repo remote; required for --request-yield")
    parser.add_argument("--ref", default="main")
    parser.add_argument("--generation", type=int)
    parser.add_argument("--backlog", default="backlog")
    opts = parser.parse_args()
    try:
        payload = _load_payload(opts.json_argument)
        observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        obj = normalize(opts.provider, payload, task_id=opts.task, agent_id=opts.agent,
                        claim_id=opts.claim_id, observed_at=observed_at,
                        evidence_ref=opts.evidence_ref)
        advice = classify(obj)
        out = {"observation": obj, "advice": advice, "publication": "NOT_REQUESTED"}
        if opts.request_yield:
            if not opts.remote or opts.generation is None:
                raise ValueError("--request-yield needs --remote and --generation")
            if advice["recommendation"] != "REQUEST_YIELD":
                out["publication"] = "NOT_APPLICABLE"
            else:
                # Stable ID for retry. Raw provider JSON never enters Git.
                stable = "|".join([opts.task, opts.agent, opts.claim_id,
                                   str(opts.generation), obj.get("code", ""), opts.evidence_ref])
                event_id = "evt-bridge-" + sha256(stable.encode()).hexdigest()[:24]
                client = Path(__file__).with_name("multi_agent_cli.py")
                argv = [sys.executable, str(client), "yield-request", "--remote", opts.remote,
                        "--ref", opts.ref, "--backlog", opts.backlog,
                        "--task", opts.task, "--actor", opts.agent, "--generation", str(opts.generation),
                        "--event-id", event_id, "--reason", obj.get("code", "provider_error")]
                result = subprocess.run(argv, capture_output=True, text=True, timeout=120)
                if result.returncode:
                    out["publication"] = "UNCONFIRMED_OR_REFUSED"
                    out["nextAction"] = "Supervisor must inspect the authoritative task state"
                else:
                    out["publication"] = json.loads(result.stdout).get("result", "UNCONFIRMED")
        print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    except (ValueError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        # Do not log provider content or potentially secret-bearing exceptions.
        print(json.dumps({"result": "REFUSED", "reason": "Invalid or unavailable observation"}), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
