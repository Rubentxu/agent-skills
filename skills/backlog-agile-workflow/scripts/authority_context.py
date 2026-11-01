#!/usr/bin/env python3
"""Pure, fail-closed decision provenance projections. No Backlog/Git/network access.

Inputs are snapshots curated by a trusted host. This module checks internal
consistency; JSON files alone cannot authenticate an actor or grant permissions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
STATES = {"proposed", "approved", "rejected", "superseded"}
VERDICTS = {"VERIFIED", "UNVERIFIED", "STALE", "CONFLICTED"}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def envelope(value: Any, kind: str, field: str) -> list[dict]:
    require(isinstance(value, dict) and value.get("schemaVersion") == 1
            and value.get("kind") == kind, "unsupported " + kind + " envelope")
    rows = value.get(field)
    require(isinstance(rows, list) and len(rows) <= 10000
            and all(isinstance(row, dict) for row in rows), "invalid " + field)
    return rows


def sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def timestamp(value: Any) -> datetime:
    require(isinstance(value, str) and len(value) <= 40, "invalid timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    require(dt.tzinfo is not None, "timestamp must include timezone")
    return dt.astimezone(timezone.utc)


def identity(source: dict) -> tuple[str, str, str]:
    parts = (source.get("provider"), source.get("sessionId"), source.get("messageId"))
    require(all(isinstance(x, str) and ID.fullmatch(x) for x in parts),
            "missing or unsafe source identity")
    return tuple(parts)


def validate(claims: dict, messages: dict, decisions: dict, *,
             now: datetime | None = None) -> dict:
    """Verify consistency against distinct snapshots; never issue write authority.

    message-evidence MUST be obtained independently by a trusted adapter.
    The validator cannot attest that an arbitrary JSON file is genuine.
    """
    records = envelope(claims, "authority-records", "records")
    observed = envelope(messages, "message-evidence", "messages")
    native = envelope(decisions, "decision-list", "decisions")
    require(decisions.get("nextSkip") is None and decisions.get("total") in (None, len(native)),
            "decision-list is paginated; collect every page")
    by_decision: dict[str, dict] = {}
    for row in native:
        did = row.get("id")
        require(isinstance(did, str) and ID.fullmatch(did) and did not in by_decision,
                "duplicate or malformed Backlog decision ID")
        by_decision[did] = row
    by_message: dict[tuple[str, str, str], list[dict]] = {}
    for msg in observed:
        key = identity(msg)
        by_message.setdefault(key, []).append(msg)

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    result = []
    seen = set()
    for record in records:
        rid = record.get("id")
        require(isinstance(rid, str) and ID.fullmatch(rid) and rid not in seen,
                "duplicate or malformed authority record")
        seen.add(rid)
        did = record.get("backlogDecisionId")
        require(isinstance(did, str) and ID.fullmatch(did), "invalid backlogDecisionId")
        state = record.get("state")
        require(state in STATES, "invalid authority state")
        scope = record.get("scope")
        require(isinstance(scope, list) and 0 < len(scope) <= 32
                and all(isinstance(s, str) and ID.fullmatch(s) for s in scope),
                "invalid authority scope")
        src = record.get("source")
        require(isinstance(src, dict), "missing source pin")
        key = identity(src)
        digest = src.get("digest")
        require(isinstance(digest, str) and DIGEST.fullmatch(digest), "invalid source digest")
        source_date = src.get("timestamp")
        timestamp(source_date)
        quote = record.get("exactQuote")
        require(isinstance(quote, str) and 0 < len(quote) <= 4096,
                "missing exact human quote")
        expires = record.get("expiresAt")
        if expires is not None:
            expires = timestamp(expires)
        reasons = []
        verdict = "VERIFIED"
        if did not in by_decision:
            verdict, reasons = "UNVERIFIED", ["BACKLOG_DECISION_NOT_OBSERVED"]
        elif by_decision[did].get("status") not in {"accepted", "approved"} and state == "approved":
            verdict, reasons = "CONFLICTED", ["BACKLOG_DECISION_NOT_ACCEPTED"]
        matches = by_message.get(key, [])
        if len(matches) > 1:
            verdict, reasons = "CONFLICTED", ["AMBIGUOUS_MESSAGE_ID"]
        elif not matches:
            if verdict == "VERIFIED":
                verdict = "UNVERIFIED"
            reasons.append("ORIGINAL_MESSAGE_NOT_OBSERVED")
        else:
            msg = matches[0]
            body = msg.get("text")
            if (not isinstance(body, str) or sha256(body) != digest\n                    or msg.get("timestamp") != source_date
                    or quote not in body or msg.get("authorKind") != "human"):
                verdict, reasons = "CONFLICTED", ["SOURCE_MISMATCH_OR_NOT_HUMAN"]
            elif state == "approved" and msg.get("explicitApproval") is not True:
                verdict, reasons = "UNVERIFIED", ["APPROVAL_NOT_ESTABLISHED"]
        if record.get("supersededBy") is not None or state in {"superseded", "rejected"}:
            verdict = "STALE" if verdict != "CONFLICTED" else verdict
            reasons.append("SUPERSEDED_OR_REJECTED")
        if expires is not None and expires <= current:
            verdict = "STALE" if verdict != "CONFLICTED" else verdict
            reasons.append("EXPIRED")
        result.append({"id": rid, "backlogDecisionId": did, "scope": scope,
                       "sourcePin": {"provider": key[0], "sessionId": key[1],
                                     "messageId": key[2], "digest": digest,\n                                     "timestamp": source_date},
                       "verdict": verdict, "reasons": reasons,
                       "canAuthorizeExecution": False})
    return {"schemaVersion": 1, "kind": "authority-assessment",
            "status": "REVIEW_ONLY", "records": result,
            "warning": "Evidence JSON is not authenticated by this validator; enforce permissions in the host."}


def read(path: str) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    require(isinstance(value, dict), "expected JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claims")
    parser.add_argument("messages")
    parser.add_argument("decisions")
    args = parser.parse_args()
    try:
        print(json.dumps(validate(read(args.claims), read(args.messages), read(args.decisions)),
                         ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, "BLOCKED: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
