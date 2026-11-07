#!/usr/bin/env python3
"""Pure Goldfish review JSON validator, aggregator and fingerprint drift projector."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import PurePosixPath, Path
from typing import Any

SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")
TASK = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}")
REVIEWERS = frozenset({"comprehension", "architecture", "codebase", "failure"})
SEVERITIES = {"Nit": 1, "Major": 2, "Blocker": 3}


def _record(v: Any, label: str) -> dict[str, Any]:
    if not isinstance(v, dict):
        raise ValueError(f"{label} must be an object")
    return v


def _keys(v: dict, required: set[str], optional: set[str] = frozenset()) -> None:
    if required - v.keys() or v.keys() - required - optional:
        raise ValueError(f"invalid fields: required={sorted(required)} actual={sorted(v)}")


def _sha(v: Any, pattern: re.Pattern, label: str) -> str:
    if not isinstance(v, str) or not pattern.fullmatch(v):
        raise ValueError(f"invalid {label}")
    return v


def _path(v: Any, directory: bool = False) -> str:
    if not isinstance(v, str) or not v or len(v) > 1024 or "\\" in v or "\x00" in v:
        raise ValueError("invalid source path")
    if v.startswith("/") or "://" in v or any(p in (".", "..", "") for p in v.rstrip("/").split("/")):
        raise ValueError("source path escapes repository")
    if not directory and v.endswith("/"):
        raise ValueError("target must be a file")
    if str(PurePosixPath(v.rstrip("/"))) != v.rstrip("/"):
        raise ValueError("noncanonical source path")
    return v


def _sources(v: Any) -> list[str]:
    if not isinstance(v, list) or not (1 <= len(v) <= 64):
        raise ValueError("allowedSources must contain 1..64 paths")
    paths = [_path(p, directory=True) for p in v]
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate sources")
    return paths


def _allowed(path: str, sources: list[str]) -> bool:
    return any(path == s or (s.endswith("/") and path.startswith(s)) for s in sources)


def request(data: Any) -> dict:
    r = _record(data, "request")
    _keys(r, {"schemaVersion", "kind", "target", "scope", "reviewers", "limits"}, {"taskId"})
    if (r["schemaVersion"], r["kind"]) != (1, "goldfish-review-request"):
        raise ValueError("unknown request schema")
    target = _record(r["target"], "target")
    _keys(target, {"path", "gitRevision", "sha256"})
    _path(target["path"])
    _sha(target["gitRevision"], SHA, "git revision")
    _sha(target["sha256"], DIGEST, "target digest")
    scope = _record(r["scope"], "scope")
    _keys(scope, {"question", "allowedSources", "mode"})
    if not isinstance(scope["question"], str) or not scope["question"].strip() or len(scope["question"]) > 2000:
        raise ValueError("invalid review question")
    if scope["mode"] not in ("lite", "focused", "deep"):
        raise ValueError("invalid review mode")
    sources = _sources(scope["allowedSources"])
    if not _allowed(target["path"], sources):
        raise ValueError("target is outside allowed sources")
    reviewers = r["reviewers"]
    if not isinstance(reviewers, list) or not reviewers or len(reviewers) > 4 or len(set(map(str, reviewers))) != len(reviewers) or any(x not in REVIEWERS for x in reviewers):
        raise ValueError("invalid reviewer set")
    limits = _record(r["limits"], "limits")
    _keys(limits, {"maxRounds"})
    if type(limits["maxRounds"]) is not int or not (1 <= limits["maxRounds"] <= 5):
        raise ValueError("invalid round cap")
    if (scope["mode"] == "lite" and (len(reviewers) != 1 or limits["maxRounds"] != 1)) or (
        scope["mode"] == "focused" and (not 2 <= len(reviewers) <= 3 or limits["maxRounds"] > 2)):
        raise ValueError("profile budget exceeded")
    if "taskId" in r and (not isinstance(r["taskId"], str) or not TASK.fullmatch(r["taskId"])):
        raise ValueError("invalid task ID")
    return r


def report(data: Any, req: dict) -> dict:
    v = _record(data, "report")
    _keys(v, {"schemaVersion", "kind", "reviewer", "target", "execution", "findings"})
    if (v["schemaVersion"], v["kind"]) != (1, "goldfish-review-report"):
        raise ValueError("unknown report schema")
    if v["reviewer"] not in req["reviewers"]:
        raise ValueError("unexpected reviewer")
    target = _record(v["target"], "report target")
    _keys(target, {"gitRevision", "sha256"})
    if target != {k: req["target"][k] for k in ("gitRevision", "sha256")}:
        raise ValueError("stale or foreign report")
    execution = _record(v["execution"], "execution")
    _keys(execution, {"status", "conversationFresh", "toolsReadOnly", "sourcesRestricted", "hostReported"})
    if execution["status"] not in ("completed", "not_run") or any(type(execution[k]) is not bool for k in
         ("conversationFresh", "toolsReadOnly", "sourcesRestricted", "hostReported")):
        raise ValueError("invalid execution status")
    findings = v["findings"]
    if not isinstance(findings, list) or len(findings) > 100 or (execution["status"] == "not_run" and findings):
        raise ValueError("invalid findings collection")
    for f in findings:
        f = _record(f, "finding")
        _keys(f, {"scope", "claim", "severity", "evidence", "verification"})
        if f["severity"] not in SEVERITIES or any(not isinstance(f[k], str) or not f[k].strip() or len(f[k]) > 3000 for k in ("scope", "claim", "verification")):
            raise ValueError("invalid finding")
        if not isinstance(f["evidence"], list) or not f["evidence"] or len(f["evidence"]) > 16:
            raise ValueError("missing evidence")
        if any(not _allowed(_path(p), req["scope"]["allowedSources"]) for p in f["evidence"]):
            raise ValueError("evidence outside allowed sources")
    return v


def _normalize(v: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", v).casefold().split())


def aggregate(req_data: Any, reports_data: Any) -> dict:
    req = request(req_data)
    if not isinstance(reports_data, list) or len(reports_data) > len(req["reviewers"]):
        raise ValueError("invalid reports collection")
    reports = [report(v, req) for v in reports_data]
    if len({v["reviewer"] for v in reports}) != len(reports):
        raise ValueError("duplicate reviewer reports")
    by_reviewer = {r["reviewer"]: r for r in reports}
    findings = {}
    for r in reports:
        if r["execution"]["status"] != "completed":
            continue
        for f in r["findings"]:
            key = _normalize(f["scope"]) + "\x00" + _normalize(f["claim"])
            fid = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
            if fid not in findings:
                findings[fid] = {**f, "findingId": fid, "reviewers": [], "disposition": "UNVERIFIED"}
            entry = findings[fid]
            entry["reviewers"].append(r["reviewer"])
            entry["evidence"] = sorted(set(entry["evidence"]) | set(f["evidence"]))
            if SEVERITIES[f["severity"]] > SEVERITIES[entry["severity"]]:
                entry["severity"] = f["severity"]
    incomplete = [id for id in req["reviewers"] if id not in by_reviewer or
                  by_reviewer[id]["execution"]["status"] != "completed" or
                  not all(by_reviewer[id]["execution"][k] for k in
                  ("conversationFresh", "toolsReadOnly", "sourcesRestricted", "hostReported"))]
    state = "INCONCLUSIVE" if incomplete else ("REVIEWED_WITH_FINDINGS" if findings else "REVIEWED")
    return {"schemaVersion": 1, "kind": "goldfish-review-summary", "status": state,
            "assurance": "HOST_REPORTED_ONLY", "target": req["target"],
            "reviewers": {i: ("not_run" if i not in by_reviewer else by_reviewer[i]["execution"]["status"]) for i in req["reviewers"]},
            "incompleteReviewers": incomplete,
            "findings": sorted(findings.values(), key=lambda x: (-SEVERITIES[x["severity"]], x["findingId"]))}


def _snapshot(data: Any) -> dict:
    v = _record(data, "source snapshot")
    _keys(v, {"schemaVersion", "kind", "gitRevision", "sources"})
    if (v["schemaVersion"], v["kind"]) != (1, "goldfish-source-snapshot"):
        raise ValueError("unknown snapshot")
    _sha(v["gitRevision"], SHA, "snapshot revision")
    sources = _record(v["sources"], "sources")
    if len(sources) > 256:
        raise ValueError("too many sources")
    for path, digest in sources.items():
        _path(path)
        _sha(digest, DIGEST, "source digest")
    return v


def drift(before: Any, after: Any) -> dict:
    a, b = _snapshot(before), _snapshot(after)
    old, new = a["sources"], b["sources"]
    return {"schemaVersion": 1, "kind": "goldfish-fingerprint-diff",
            "status": "CHANGED" if a["gitRevision"] != b["gitRevision"] or old != new else "NO_HASH_CHANGE",
            "revisionChanged": a["gitRevision"] != b["gitRevision"],
            "changed": sorted(p for p in old.keys() & new.keys() if old[p] != new[p]),
            "added": sorted(new.keys() - old.keys()), "missing": sorted(old.keys() - new.keys()),
            "note": "Fingerprint changes are candidates, not proven semantic drift."}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("validate-request", "aggregate", "drift"))
    p.add_argument("first", type=Path)
    p.add_argument("second", type=Path, nargs="?")
    args = p.parse_args(argv)
    try:
        first = json.loads(args.first.read_text(encoding="utf-8"))
        if args.mode == "validate-request":
            if args.second is not None:
                raise ValueError("unexpected second file")
            out = {"status": "VALID_REQUEST", "reviewers": request(first)["reviewers"]}
        else:
            if args.second is None:
                raise ValueError("second file required")
            second = json.loads(args.second.read_text(encoding="utf-8"))
            out = aggregate(first, second) if args.mode == "aggregate" else drift(first, second)
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (ValueError, OSError, TypeError) as ex:
        print(json.dumps({"status": "INVALID", "reason": str(ex)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
