#!/usr/bin/env python3
"""Explicit opt-in capture of native Backlog records into a portable v2 corpus."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

from model import MAX_BYTES, RELATIONS, identifier, include_backlog, make_corpus, require, validate

DOC_ID = re.compile(r"doc-[0-9]+\Z", re.IGNORECASE)
NATIVE_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,95}\Z")
LIST_ROW = re.compile(r"(doc-[0-9]+) - (.+)\Z", re.IGNORECASE)
HEADER_ID = re.compile(r"""id:\s*(['"]?)(doc-[0-9]+)\1\s*\Z""", re.IGNORECASE)
OPEN = "<!-- knowledge-links:v1 -->"
CLOSE = "<!-- /knowledge-links:v1 -->"


def native_id(value, *, doc=False):
    require(isinstance(value, str) and (DOC_ID if doc else NATIVE_ID).fullmatch(value),
            "Invalid native record ID")
    return value


def project_root(root: Path) -> Path:
    """Reject accidental parent-project discovery; do not parse configuration."""
    root = root.resolve()
    require(root.is_dir(), "Explicit project root must exist")
    markers = [root / "backlog.config.yml", root / "backlog.json"]
    markers.extend(root / folder / name for folder in ("backlog", ".backlog")
                   for name in ("config.yml", "config.yaml"))
    require(any(m.is_file() for m in markers), "Expected Backlog configuration at selected root")
    return root


class Cli:
    def __init__(self, executable: str, root: Path, *, timeout: int, max_commands: int):
        resolved = shutil.which(executable)
        require(resolved is not None, "Backlog CLI missing; do not install automatically")
        self.executable = str(Path(resolved).resolve())
        self.root = project_root(root)
        self.deadline = time.monotonic() + timeout
        self.max_commands = max_commands
        self.calls = 0

    def __call__(self, *args: str) -> str:
        self.calls += 1
        remaining = self.deadline - time.monotonic()
        require(self.calls <= self.max_commands and remaining > 0, "Capture budget exhausted")
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                result = subprocess.run([self.executable, *args], cwd=self.root, stdin=subprocess.DEVNULL,
                                        stdout=out, stderr=err, timeout=min(30, remaining), check=False)
            except subprocess.TimeoutExpired:
                raise ValueError("Backlog CLI read timed out") from None
            command = " ".join(args[:2])
            require(result.returncode == 0, f"Backlog CLI read failed ({command}, exit {result.returncode})")
            require(err.tell() == 0, f"Backlog CLI emitted diagnostics ({command}); inspect separately")
            require(out.tell() <= MAX_BYTES, f"Backlog CLI output too large ({command})")
            out.seek(0)
            return out.read().decode("utf-8")


def envelope(raw: str, kind: str, collection: str | None = None) -> dict:
    data = json.loads(raw)
    require(isinstance(data, dict) and data.get("schemaVersion") == 1 and data.get("kind") == kind,
            f"Unexpected {kind} JSON envelope")
    if collection:
        require(isinstance(data.get(collection), list), f"Missing {collection}")
        require("nextSkip" not in data and "total" not in data, f"Unexpected paginated {kind}")
    return data


def doc_list(raw: str) -> dict[str, str]:
    lines = [line for line in raw.splitlines() if line.strip()]
    if lines == ["No docs found."]:
        return {}
    result = {}
    for line in lines:
        match = LIST_ROW.fullmatch(line)
        require(match is not None, "Unsupported doc list output")
        i, title = match.groups()
        require(i not in result, "Duplicate document ID in native list")
        result[i] = title
    require(bool(result), "Empty document inventory without native empty marker")
    return result


def document_body(raw: str, expected: str) -> tuple[str, str]:
    """Read native front-matter boundary and ID only; metadata comes from JSON."""
    lines = raw.splitlines(keepends=True)
    require(bool(lines) and lines[0].strip() == "---", "Expected native document front matter")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise ValueError("Unterminated native document front matter") from None
    header = "".join(lines[1:end])
    ids = [m.group(2) for line in lines[1:end] if (m := HEADER_ID.fullmatch(line.strip()))]
    require(ids == [expected], "Native document ID mismatch or unsupported front matter")
    return header, "".join(lines[end + 1:])


def excerpt(text: str, fallback: str) -> str:
    """Exact short paragraph, not a synthesized claim."""
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        value = paragraph.strip()
        if not value or value.startswith(("#", "<!--", "\x60\x60\x60", "~~~", "|")):
            continue
        return value if len(value) <= 400 else fallback
    return fallback


def declared_links(body: str) -> list[dict]:
    """An opt-in JSON block in native content. Ignore fenced examples."""
    fences = None
    collecting = False
    found = False
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        fence = re.match(r"^(\x60{3,}|~{3,})", stripped)
        if not collecting and fence:
            marker = fence.group(1)
            if fences is None:
                fences = marker
            elif marker[0] == fences[0] and len(marker) >= len(fences):
                fences = None
            continue
        if fences:
            continue
        if stripped == OPEN:
            require(not found and not collecting, "Duplicate knowledge-link block")
            collecting = True
            found = True
        elif stripped == CLOSE:
            require(collecting, "Unexpected knowledge-link terminator")
            collecting = False
        elif collecting:
            lines.append(line)
    require(not collecting, "Unterminated knowledge-link block")
    if not found:
        return []
    data = json.loads("\n".join(lines))
    require(isinstance(data, list), "Knowledge links must be a JSON array")
    for link in data:
        require(isinstance(link, dict) and set(link) <= {"predicate", "to", "reason"}
                and isinstance(link.get("predicate"), str) and link["predicate"] in RELATIONS
                and link["predicate"] != "depends_on" and identifier(link.get("to")),
                "Invalid declared semantic relationship")
        if "reason" in link:
            require(isinstance(link["reason"], str) and link["reason"].strip(), "Invalid link reason")
    return data


def capture(read, *, project: str, all_docs: bool = False, documents: tuple = (),
            tasks: tuple = (), decisions: tuple = (), query: str | None = None,
            include_board: bool = False, max_docs: int = 32) -> dict:
    require(identifier(project), "Explicit project identity required")
    require(1 <= max_docs <= 256, "Invalid document budget")
    require(all_docs or documents or tasks or decisions or query or include_board,
            "Select documents, tasks, decisions, query or board explicitly")
    for i in documents:
        native_id(i, doc=True)
    for i in (*tasks, *decisions):
        native_id(i)
    require(query is None or (isinstance(query, str) and 0 < len(query.strip()) <= 200
                              and not query.strip().startswith("-")), "Invalid query")
    remote = read("config", "get", "remoteOperations").strip()
    if remote != "false":
        require(read("config", "get", "filesystemOnly").strip() == "true",
                "Local capture requires remoteOperations=false or filesystemOnly=true")
    version = read("--version").strip()
    require(bool(version) and len(version) <= 200, "Unexpected Backlog version output")
    catalog = doc_list(read("doc", "list", "--plain"))
    search = envelope(read("search", "--type", "document", "--json"), "search", "results")
    metadata = {}
    for record in search["results"]:
        require(isinstance(record, dict) and record.get("type") == "document"
                and isinstance(record.get("data"), dict), "Unexpected document inventory result")
        d = record["data"]
        native_id(d.get("id"), doc=True)
        require(d["id"] not in metadata, "Duplicate metadata ID")
        metadata[d["id"]] = d
    require(set(catalog) == set(metadata), "Document list/search disagree; refresh native inventory")
    require(all(catalog[i] == metadata[i].get("title") for i in catalog),
            "Document titles changed during capture")

    corpus = include_backlog(make_corpus(project, [], []), search)
    corpus = include_backlog(corpus, envelope(read("decision", "list", "--json"), "decision-list", "decisions"))
    if include_board:
        corpus = include_backlog(corpus, envelope(read("task", "list", "--json"), "task-list", "tasks"))
    mandatory = list(dict.fromkeys(documents))
    unresolved_paths = []
    by_path = {}
    for i, d in metadata.items():
        if isinstance(d.get("path"), str):
            by_path.setdefault(d["path"], []).append(i)
    for i in dict.fromkeys(tasks):
        view = envelope(read("task", "view", i, "--json"), "task-view")
        require(isinstance(view.get("task"), dict) and view["task"].get("id") == i,
                "Task view identity mismatch")
        corpus = include_backlog(corpus, view)
        for path in view["task"].get("documentation", []) or []:
            if isinstance(path, str) and len(by_path.get(path, [])) == 1:
                mandatory.append(by_path[path][0])
            elif isinstance(path, str):
                unresolved_paths.append(path)
    mandatory = list(dict.fromkeys(mandatory))
    require(all(i in metadata for i in mandatory), "Requested document absent from active inventory")
    require(len(mandatory) <= max_docs, "Explicit or task-linked documents exceed document budget")
    for i in dict.fromkeys(decisions):
        view = envelope(read("decision", "view", i, "--json"), "decision-view")
        require(isinstance(view.get("decision"), dict) and view["decision"].get("id") == i,
                "Decision view identity mismatch")
        corpus = include_backlog(corpus, view)
    ranked = []
    if query:
        matches = envelope(read("search", query.strip(), "--type", "document", "--json"), "search", "results")
        for record in matches["results"]:
            require(isinstance(record, dict) and record.get("type") == "document"
                    and isinstance(record.get("data"), dict), "Unexpected query result")
            d = record["data"]
            i = d.get("id")
            require(isinstance(i, str) and i in metadata and metadata[i] == d,
                    "Document metadata changed during capture")
            ranked.append(i)
    if all_docs:
        ranked.extend(sorted(metadata))
    planned = list(dict.fromkeys(mandatory + ranked))
    selected = planned[:max_docs]
    nodes = {n["id"]: n for n in corpus["nodes"]}
    edges = {(e["from"], e["predicate"], e["to"]): e for e in corpus["edges"]}
    term_owners = {}
    for i in metadata:
        n = nodes["doc:" + i]
        if n["kind"] in {"profile", "track"}:
            n["level"] = "L3" if n["kind"] == "profile" else "L2"
        terms = [t[5:] for t in n["tags"] if t.startswith("term:") and identifier(t[5:])]
        if n["kind"] == "term" and len(terms) == 1:
            term_owners.setdefault(terms[0], []).append(n["id"])
            n["aliases"] = [terms[0]]
        n["content_state"] = "metadata-only"
        n["claim_state"] = "unknown"
    unresolved_links = []
    for i in selected:
        raw = read("doc", "view", i, "--plain")
        front, body = document_body(raw, i)
        n = nodes["doc:" + i]
        n["body"] = body
        n["summary"] = excerpt(body, n["title"])
        n["native_frontmatter"] = front
        n["content_state"] = "captured"
        n["sources"] = [{"provider": "backlog", "locator": i,
                         "digest": hashlib.sha256(raw.encode("utf-8")).hexdigest()}]
        for edge in declared_links(body):
            a, pred, b = n["id"], edge["predicate"], edge["to"]
            if b not in nodes:
                unresolved_links.append({"from": a, **edge})
                continue
            key = (a, pred, b)
            require(key not in edges or edges[key] == {"from": a, **edge}, "Conflicting declared link")
            edges[key] = {"from": a, **edge}
    for n in nodes.values():
        if not n["id"].startswith("doc:"):
            continue
        for tag in n["tags"]:
            if tag.startswith("term:"):
                owners = term_owners.get(tag[5:], [])
                if len(owners) == 1 and owners[0] != n["id"]:
                    key = (n["id"], "about", owners[0])
                    edges.setdefault(key, {"from": key[0], "predicate": key[1], "to": key[2]})
                elif len(owners) != 1:
                    unresolved_links.append({"from": n["id"], "predicate": "about", "term": tag[5:]})
    if selected:
        after = envelope(read("search", "--type", "document", "--json"), "search", "results")
        require(after == search, "Native inventory changed during capture; retry")
    result = make_corpus(project, list(nodes.values()), list(edges.values()))
    result["capture"] = {"provider": "backlog", "cli_version": version, "document_inventory": len(metadata),
                         "captured_documents": selected, "omitted_documents": planned[max_docs:],
                         "metadata_only_documents": sorted(set(metadata) - set(selected)),
                         "unresolved_task_paths": sorted(set(unresolved_paths)),
                         "unresolved_links": unresolved_links,
                         "atomic": False, "archived_documents_enumerated": False}
    return validate(result)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--backlog-bin", default="backlog")
    p.add_argument("--confirm-cli-read", action="store_true", required=True)
    p.add_argument("--all-docs", action="store_true")
    p.add_argument("--doc", action="append", default=[])
    p.add_argument("--task", action="append", default=[])
    p.add_argument("--decision", action="append", default=[])
    p.add_argument("--query")
    p.add_argument("--include-board", action="store_true")
    p.add_argument("--max-docs", type=int, default=32)
    p.add_argument("--max-commands", type=int, default=80)
    p.add_argument("--timeout", type=int, default=120)
    args = p.parse_args()
    try:
        require(1 <= args.max_commands <= 1024 and 1 <= args.timeout <= 600, "Invalid CLI budget")
        cli = Cli(args.backlog_bin, args.root, timeout=args.timeout, max_commands=args.max_commands)
        result = capture(cli, project=args.project, all_docs=args.all_docs, documents=tuple(args.doc),
                         tasks=tuple(args.task), decisions=tuple(args.decision), query=args.query,
                         include_board=args.include_board, max_docs=args.max_docs)
        result["capture"]["cli_calls"] = cli.calls
        payload = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        require(len(payload) <= MAX_BYTES, "Corpus exceeds reader size limit; narrow capture")
        sys.stdout.buffer.write(payload)
        return 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(json.dumps({"status": "capture-failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
