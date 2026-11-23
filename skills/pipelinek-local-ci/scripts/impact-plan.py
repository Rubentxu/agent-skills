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


def validated_graph(value):
    """Portable graph facts produced by native build adapters, never executable commands."""
    if not isinstance(value, dict) or value.get("schema") != "pipelinek.component-graph/v1":
        raise ValueError("graph must have pipelinek.component-graph/v1 schema")
    components = value.get("components")
    if not isinstance(components, list) or not components:
        raise ValueError("graph requires non-empty components[]")
    entries = {}
    for item in components:
        if not isinstance(item, dict):
            raise ValueError("invalid component graph entry")
        key, roots, deps, checks = (item.get(k) for k in ("id", "roots", "dependsOn", "checks"))
        if not isinstance(key, str) or not key or key in entries or len(key) > 140:
            raise ValueError("component id is empty, duplicated or oversized")
        if not all(isinstance(x, list) and all(isinstance(i, str) for i in x) for x in (roots, deps, checks)):
            raise ValueError("roots, dependsOn and checks must be string arrays")
        if not roots:
            raise ValueError("component must own at least one source root")
        normalized = []
        for root in roots:
            source = Path(root)
            if source.is_absolute() or ".." in source.parts or not root or "\\" in root:
                raise ValueError("source roots must be relative normalized paths")
            normalized.append(source.as_posix().rstrip("/") or ".")
        entries[key] = {"roots": normalized, "dependsOn": deps, "checks": checks}
    for name, data in entries.items():
        if any(d not in entries for d in data["dependsOn"]):
            raise ValueError("component " + name + " refers to unknown dependency")
    return entries


def graph_impact(changed, graph):
    """Reverse dependency closure; never claims proof of test coverage."""
    direct, unknown = set(), []
    for changed_path in changed:
        if changed_path.startswith("docs/") or Path(changed_path).suffix.lower() in DOC_EXTENSIONS:
            continue
        candidates = []
        for name, data in graph.items():
            for root in data["roots"]:
                if root == "." or changed_path == root or changed_path.startswith(root + "/"):
                    candidates.append((len(root), name))
        if not candidates:
            unknown.append(changed_path)
            continue
        best_length = max(length for length, _ in candidates)
        direct.update(name for length, name in candidates if length == best_length)
    dependents = {name: set() for name in graph}
    for component, data in graph.items():
        for dependency in data["dependsOn"]:
            dependents[dependency].add(component)
    affected = set(direct)
    pending = list(direct)
    while pending:
        node = pending.pop()
        for dependent in dependents[node]:
            if dependent not in affected:
                affected.add(dependent)
                pending.append(dependent)
    checks = sorted({name for component in affected for name in graph[component]["checks"]})
    return {"direct": sorted(direct), "affected": sorted(affected),
            "checks": checks, "unmapped": sorted(unknown)}


def classify(root, changed, graph=None):
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
    result = {
        "level": level, "coverage": "PLANNING_ONLY", "changed": changed,
        "modules": sorted(modules), "reasons": sorted(reasons),
        "fullGateStillRequiredByPolicy": True,
        "automaticallySelectedTests": [],
        "reliableTestCoverageProved": False,
    }
    if graph is not None:
        impact = graph_impact(changed, graph)
        result["graph"] = impact
        if impact["unmapped"]:
            result["level"] = "FULL_REQUIRED_AT_INTEGRATION"
            result["reasons"].append("graph does not map every non-document change")
        elif impact["checks"] and not global_impact and not unknown:
            result["level"] = "AFFECTED_CANDIDATE"
            result["candidateCheckIds"] = impact["checks"]
            result["reasons"].append("reverse-dependency closure from provided component graph")
        elif not impact["checks"] and not doc_only:
            result["level"] = "FULL_REQUIRED_AT_INTEGRATION"
            result["reasons"].append("graph selected no checks; no empty green")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--base", required=True, help="explicit local Git commit/ref; no network calls")
    parser.add_argument("--graph", help="optional local JSON component/dependency graph; never executable")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    resolved = Path(os.fsdecode(git(root, "rev-parse", "--show-toplevel").strip())).resolve()
    if root != resolved:
        raise ValueError("--root must be the worktree top level")
    graph = validated_graph(json.loads(Path(args.graph).read_text(encoding="utf-8"))) if args.graph else None
    report = classify(root, changes(root, args.base), graph)
    print(json.dumps({"schema": "pipelinek.impact-plan/v1", **report},
                     ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        sys.exit("impact plan refused: " + str(exc))
