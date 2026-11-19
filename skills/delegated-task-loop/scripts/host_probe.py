#!/usr/bin/env python3
"""Project observed native-host canaries into conservative router capabilities."""
from __future__ import annotations
import json
import sys

CAPABILITIES = {
    "fresh": "fresh-context",
    "background": "nonblocking-launch",
    "notify": "native-notification",
    "progress": "live-progress",
    "steer": "live-steering",
    "cancel": "confirmed-stop",
    "resume": "native-resume",
}
EXTRA = {"read-only-review", "isolated-writer", "supervisor-compaction"}
CASES = set(CAPABILITIES.values()) | EXTRA

def evaluate(report):
    if not isinstance(report, dict) or set(report) != {"schemaVersion", "kind", "host", "version", "sessionRef", "cases"}:
        raise ValueError("invalid host report")
    if type(report["schemaVersion"]) is not int or report["schemaVersion"] != 1 or report["kind"] != "delegation-host-observations":
        raise ValueError("unsupported report")
    for k in ("host", "version", "sessionRef"):
        if not isinstance(report[k], str) or not report[k].strip() or len(report[k].encode()) > 512:
            raise ValueError("invalid " + k)
    if not isinstance(report["cases"], list) or len(report["cases"]) > len(CASES):
        raise ValueError("invalid case list")
    observations = {}
    for c in report["cases"]:
        if not isinstance(c, dict) or set(c) != {"id", "status", "evidenceRefs"}:
            raise ValueError("invalid case")
        cid, status, refs = c["id"], c["status"], c["evidenceRefs"]
        if not isinstance(cid, str) or cid not in CASES or cid in observations:
            raise ValueError("unknown or duplicate case")
        if status not in ("PASS", "FAIL", "NOT_RUN"):
            raise ValueError("invalid case status")
        if not isinstance(refs, list) or len(refs) > 8 or any(not isinstance(x, str) or not x.strip() or len(x.encode()) > 512 for x in refs):
            raise ValueError("invalid evidence references")
        if status in ("PASS", "FAIL") and not refs:
            raise ValueError("observed outcome requires evidence")
        observations[cid] = status
    capabilities = {cap: observations.get(case) == "PASS" for cap, case in CAPABILITIES.items()}
    limitations = [case for case in sorted(CASES) if observations.get(case) != "PASS"]
    if not capabilities["fresh"]:
        level = "NOT_RUN"
    elif capabilities["progress"] and capabilities["steer"] and capabilities["background"] and capabilities["notify"]:
        level = "REACTIVE"
    elif capabilities["background"] and capabilities["notify"]:
        level = "ASYNC"
    else:
        level = "RESULT_ONLY"
    # A failed fresh-context canary prevents all worker launch affordances via the router.
    return {"kind": "delegation-host-capabilities", "schemaVersion": 1,
            "host": report["host"], "version": report["version"], "sessionRef": report["sessionRef"],
            "capabilities": capabilities, "level": level,
            "reviewReadOnlyObserved": observations.get("read-only-review") == "PASS",
            "writerIsolationObserved": observations.get("isolated-writer") == "PASS",
            "compactionObserved": observations.get("supervisor-compaction") == "PASS",
            "limitations": limitations, "runtimeVerified": False, "authorized": False}

def main():
    try:
        raw = sys.stdin.buffer.read(65537)
        if len(raw) > 65536:
            raise ValueError("report too large")
        print(json.dumps(evaluate(json.loads(raw)), sort_keys=True))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
