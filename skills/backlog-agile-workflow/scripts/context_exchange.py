#!/usr/bin/env python3
"""Export/import portable, sanitized references (NOT conversation vacuuming).

No cryptographic signature or encryption is provided. The digest is only an
accidental-corruption check. Use an authenticated, private transport separately.
"""
from __future__ import annotations

import argparse
import json
from authority_context import envelope, read, require, sha256

def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def export(memory: dict, handoff: dict) -> dict:
    entries = envelope(memory, "owner-memory-projection", "items")
    require(handoff.get("schemaVersion") == 1 and handoff.get("kind") == "authority-handoff",
            "invalid handoff")
    # Explicit allowlist: never copy prompts, quotes, task notes, source or file contents.
    minimal = [{"id": x["id"], "sourcePin": x["sourcePin"], "scope": x["scope"]}
               for x in entries if x.get("verdict") == "VERIFIED"]
    body = {"schemaVersion": 1, "kind": "private-reference-bundle",
            "decisions": minimal,
            "taskId": handoff.get("taskId"),
            "revision": handoff.get("sourceRevision"),
            "editAuthorized": False}
    return {**body, "contentDigest": sha256(canonical(body))}

def inspect(bundle: dict) -> dict:
    require(bundle.get("kind") == "private-reference-bundle"
            and bundle.get("schemaVersion") == 1, "invalid bundle")
    allowed = {"schemaVersion", "kind", "decisions", "taskId",
               "revision", "editAuthorized", "contentDigest"}
    require(set(bundle) == allowed, "bundle carries unexpected or sensitive fields")
    require(bundle["editAuthorized"] is False, "bundle cannot grant execution")
    require(isinstance(bundle["decisions"], list), "invalid decisions")
    for row in bundle["decisions"]:
        require(isinstance(row, dict) and set(row) == {"id", "sourcePin", "scope"},
                "unsafe exported decision")
        require(isinstance(row["sourcePin"], dict)
                and set(row["sourcePin"]) == {"provider", "sessionId", "messageId", "digest", "timestamp"},
                "unsafe source pin")
    body = {key: val for key, val in bundle.items() if key != "contentDigest"}
    require(sha256(canonical(body)) == bundle["contentDigest"], "bundle digest mismatch")
    return {"schemaVersion": 1, "kind": "reference-bundle-inspection",
            "status": "REFERENCES_ONLY_RUNTIME_UNVERIFIED",
            "decisionCount": len(bundle["decisions"]),
            "editAuthorized": False,
            "warning": "Digest does not authenticate the sender; private authenticated transport required."}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    exp = sub.add_parser("export")
    exp.add_argument("memory")
    exp.add_argument("handoff")
    check = sub.add_parser("inspect")
    check.add_argument("bundle")
    args = parser.parse_args()
    try:
        result = (export(read(args.memory), read(args.handoff)) if args.command == "export"
                  else inspect(read(args.bundle)))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, "BLOCKED: " + str(exc) + "\n")

if __name__ == "__main__":
    raise SystemExit(main())
