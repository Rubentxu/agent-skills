#!/usr/bin/env python3
"""Offline, read-only candidate test-impact planner for arbitrary Git projects.

This tool never runs tests and never grants a PASS. It identifies candidates
for proportional verification; the project's build and policy remain authority.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

MANIFESTS = ("build.gradle.kts", "build.gradle", "pom.xml", "Cargo.toml",
             "go.mod", "pyproject.toml", "package.json", "Makefile", "justfile")
GLOBAL = ("gradle.properties", "settings.gradle.kts", "settings.gradle",
          "Cargo.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
          "poetry.lock", "uv.lock", "go.sum", "Dockerfile", ".tool-versions",
          "mise.toml", ".mise.toml", "AGENTS.md")
DOC_EXTENSIONS = (".md", ".rst", ".adoc")
SOURCE_EXTENSIONS = (".kt", ".kts", ".java", ".rs", ".go", ".py", ".js", ".jsx",
                     ".ts", ".tsx", ".c", ".cc", ".cpp", ".h", ".hpp", ".sh", ".sql")


def git(root, *arguments):
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode:
        raise ValueError("Git inspection refused for " + " ".join(arguments[:2]))
    return completed.stdout


def changed_pairs(raw):
    """Parse --name-status -z including rename/copy with two path tokens."""
    items = raw.split(b"\0")
    paths = []
    i = 0
    while i < len(items) and items[i]:
        status = items[i].decode("utf-8", "surrogateescape")
        i += 1
        if status[:1] in ("R", "C"):
            if i + 1 >= len(items):
                raise ValueError("incomplete Git rename/copy status")
            paths.extend((items[i], items[i+1]))
            i += 2
        else:
            if i >= len(items):
                raise ValueError("incomplete Git change status")
            paths.append(items[i])
            i += 1
    return [p.decode("utf-8", "surrogateescape") for p in paths]


def changes(root, base):
    if not base or base.startswith("-"):
        raise ValueError("base reference must be explicit")
    git(root, "rev-parse", "--verify", base + "^{commit}")
    tracked = []
    tracked += changed_pairs(git(root, "diff", "-z", "--name-status", base, "HEAD", "--"))
    tracked += changed_pairs(git(root, "diff", "-z", "--name-status", "--cached", "--"))
    tracked += changed_pairs(git(root, "diff", "-z", "--name-status", "--"))
    untracked = git(root, "ls-files", "-z", "--others", "--exclude-standard").split(b"\0")
    tracked += [name.decode("utf-8", "surrogateescape") for name in untracked if name]
    return sorted(set(tracked))


def nearest_manifest(root, rel):
    candidate = (root / rel).parent
    for ancestor in (candidate, *candidate.parents):
        if ancestor == root or root in ancestor.parents:
            for item in MANIFESTS:
                if (ancestor / item).is_file():
                    return str(ancestor.relative_to(root)) or "."
        if ancestor == root:
            break
    return None


def classify(root, changed):
    if not changed:
        return {"level": "NO_CHANGES", "coverage": "NOT_MEASURED",
                "modules": [], "changed": [], "reasons": ["no changes were observed"]}
    modules = set()
    reasons = set()
    code = False
    global_impact = False
    doc_only = True
    unknown = False
    for name in changed:
        path = Path(name)
        basename = path.name
        if basename in GLOBAL or ".pipelinek" in path.parts or path.parts[:1] == (".github",):
            global_impact = True
            reasons.add("build, toolchain, CI or shared configuration changed")
        if name.startswith("pipelines/") or basename.endswith(".pipeline.kts") or basename == "pipeline.kts":
            global_impact = True
            reasons.add("pipeline definition changed")
        if name.startswith("docs/") or path.suffix.lower() in DOC_EXTENSIONS:
            continue
        doc_only = False
        if basename in MANIFESTS:
            global_impact = True
            reasons.add("module manifest changed; dependents may change")
        elif path.suffix.lower() in SOURCE_EXTENSIONS:
            code = True
        else:
            unknown = True
            reasons.add("unrecognized file; cannot prove affected-only scope")
        owner = nearest_manifest(root, name)
        if owner is None:
            unknown = True
        else:
            modules.add(owner)
    if global_impact or unknown:
        level = "FULL_REQUIRED_AT_INTEGRATION"
    elif doc_only:
        level = "DOC_GATE_CANDIDATE"
    elif code:
        level = "AFFECTED_CANDIDATE"
    else:
        level = "FULL_REQUIRED_AT_INTEGRATION"
    if code:
        reasons.add("reverse dependencies and contract consumers need project-specific inspection")
    if doc_only:
        reasons.add("run project's documentation/contract gate; do not imply no verification")
    if unknown:
        reasons.add("missing module ownership or unrecognized file requires conservative coverage")
    return {
        "level": level, "coverage": "PLANNING_ONLY", "changed": changed,
        "modules": sorted(modules), "reasons": sorted(reasons),
        "fullGateStillRequiredByPolicy": True,
        "automaticallySelectedTests": [],
        "reliableTestCoverageProved": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--base", required=True, help="explicit local Git commit/ref; no network calls")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    resolved = Path(os.fsdecode(git(root, "rev-parse", "--show-toplevel").strip())).resolve()
    if root != resolved:
        raise ValueError("--root must be the worktree top level")
    report = classify(root, changes(root, args.base))
    print(json.dumps({"schema": "pipelinek.impact-plan/v1", **report},
                     ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        sys.exit("impact plan refused: " + str(exc))
