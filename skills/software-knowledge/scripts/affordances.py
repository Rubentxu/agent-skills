#!/usr/bin/env python3
"""HATEOAS-like pure workflow router, using only caller-observed state and local registries."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

from model import identifier, require

ROOT = Path(__file__).resolve().parents[1]
NAV = {"understand", "implement", "refactor", "verify", "debug", "security", "architecture"}
INTENTS = NAV | {"catalog", "discover", "capture", "follow", "index", "architecture-review",
                 "constitution", "checkpoint", "maintain", "context-pack", "federate", "evaluate"}
ACTIONS = {"get", "trace", "expand", "zoom-in", "zoom-out", "sections", "section", "capture-doc"}
STATES = {
    "basis": {"unknown", "observed", "stale"},
    "corpus": {"unknown", "absent", "ready"},
    "source": {"unknown", "snapshot", "markdown", "backlog"},
    "cli": {"unknown", "available", "missing"},
    "backlog_project": {"unknown", "initialized", "absent"},
    "remote_policy": {"unknown", "local-only", "remote-enabled"},
    "mode": {"read", "propose", "apply"},
}


def local(href):
    target = (ROOT / href).resolve()
    require(target.is_relative_to(ROOT.resolve()) and target.is_file(), "Invalid local playbook")
    return href


def registry(name, key):
    data = json.loads((ROOT / "references" / name).read_text(encoding="utf-8"))
    require(data.get("schema_version") == 1 and isinstance(data.get(key), list), "Invalid registry")
    items = data[key]
    require(all(isinstance(x, dict) and identifier(x.get("id")) and isinstance(x.get("intents"), list)
                and all(i in INTENTS for i in x["intents"]) for x in items), "Invalid registry entry")
    require(len({x["id"] for x in items}) == len(items), "Duplicate registry entry")
    return items


def link(rel, why, href=None, **extra):
    return {"rel": rel, "why": why, **({"href": local(href)} if href else {}), **extra}


def strings(value, name, maximum=32):
    require(isinstance(value, list) and len(value) <= maximum and all(identifier(x) for x in value)
            and len(set(value)) == len(value), "Invalid " + name)
    return value


def selected_link(value):
    require(isinstance(value, dict) and value.get("action") in ACTIONS
            and identifier(value.get("id")), "Unknown or malformed navigation action")
    action = value["action"]
    allowed = {"action", "id"}
    if action == "get":
        allowed.add("detail")
        require(value.get("detail", "full") in {"identity", "summary", "full", "evidence"}, "Invalid detail")
    if action == "section":
        allowed.add("section_id")
        require(isinstance(value.get("section_id"), str) and re.fullmatch(r"[0-9a-f]{64}", value["section_id"]),
                "Invalid section identity")
    if action == "capture-doc":
        require(re.fullmatch(r"doc-[0-9]+", value["id"], re.IGNORECASE) is not None, "Invalid native document ID")
    require(set(value) <= allowed, "Unsupported navigation link fields")
    return value


def affordances(state):
    require(isinstance(state, dict), "Session must be object")
    allowed = set(STATES) | {"intent", "project", "query", "anchors", "available_skills",
                            "read_authorized", "input_ready", "selected_link", "reuse_index"}
    require(set(state) <= allowed, "Unknown session fields")
    intent = state.get("intent", "catalog")
    require(intent in INTENTS, "Unknown intent")
    values = {k: state.get(k, "read" if k == "mode" else "unknown") for k in STATES}
    require(all(isinstance(v, str) and v in STATES[k] for k, v in values.items()), "Invalid session state")
    project = state.get("project")
    require(project is None or identifier(project), "Invalid project identity")
    query = state.get("query", "")
    require(isinstance(query, str) and len(query) <= 1200, "Invalid query")
    anchors = strings(state.get("anchors", []), "anchors", 16)
    installed = strings(state.get("available_skills", []), "available skills")
    for k in ("read_authorized", "input_ready", "reuse_index"):
        require(type(state.get(k, False)) is bool, "Invalid " + k)
    follow = selected_link(state["selected_link"]) if "selected_link" in state else None
    require(follow is None or intent == "follow", "Selected link requires follow intent")
    catalog = registry("lens-registry.json", "lenses")
    for entry in catalog:
        require(entry.get("status") in {"ready", "planned"}, "Invalid lens status")
        local(entry["playbook"])
    result = {"intent": intent, "status": "NAVIGATION_ONLY", "decision": None, "project": project,
              "lenses": [], "_links": [], "suggested_reads": [], "warnings": []}
    links = result["_links"]
    def finish(decision, *next_links):
        result["decision"] = decision
        links.extend(next_links)
        return result
    if intent == "catalog":
        result["available"] = [{"id": x["id"], "status": x["status"]} for x in catalog]
        return result
    if project is None:
        return finish("DISCOVER", link("identify-project", "Seleccionar identidad explícita del proyecto."))
    if values["basis"] != "observed":
        return finish("INSPECT_MORE", link("refresh-basis", "Comprobar fuentes y revisión; no asumir vigencia."))
    for entry in [x for x in catalog if x["status"] == "ready" and intent in x["intents"]][:2]:
        result["lenses"].append(entry["id"])
        links.append(link("read-lens", "Guía " + entry["id"], entry["playbook"]))
    def delegate():
        for x in registry("skill-registry.json", "related_skills"):
            if x["id"] in installed and intent in x["intents"]:
                links.append(link("delegate-skill", x["reason"], skill_id=x["id"]))
    def operation(rel, why, href, script, command, **arguments):
        # All scripts and commands come from this router, never from external content.
        return link(rel, why, href, operation={"script": local(script), "command": command,
                                               "arguments": {"project": project, **arguments}})
    def capture(native=None):
        href = "references/backlog-capture.md"
        if values["cli"] != "available":
            return finish("DISCOVER", link("inspect-cli", "Comprobar CLI Backlog; no instalar automáticamente.", href))
        if values["backlog_project"] != "initialized":
            return finish("DISCOVER", link("inspect-project", "Comprobar raíz y configuración; no inicializar.", href))
        if values["remote_policy"] != "local-only" or not state.get("read_authorized", False):
            return finish("INSPECT_MORE", link("inspect-capture-policy",
                "Requiere lectura autorizada y política local-only observada; no alterar la configuración.", href))
        delegate()
        return finish("READY", operation("capture-doc" if native else "capture-backlog",
            "Captura acotada; seleccionar raíz y alcance explícitos.", href, "scripts/capture_backlog.py",
            "capture", **({"doc": native} if native else {"query": query, "anchors": anchors})))
    if intent == "capture" or (follow and follow["action"] == "capture-doc"):
        if intent == "capture" and values["source"] != "backlog":
            return finish("DISCOVER", link("select-source", "Elegir Markdown, snapshot o Backlog autorizado.",
                                           "references/contract.md"))
        return capture(follow["id"] if follow else None)
    if intent == "discover" or values["corpus"] != "ready":
        return finish("DISCOVER", link("inspect-source", "Seleccionar y validar corpus, raíz Markdown o snapshots autorizados.",
                                       "references/contract.md"))
    # A ready snapshot does not require the original provider's installation.
    if intent == "follow":
        if follow is None:
            return finish("INSPECT_MORE", link("select-link", "Elegir una affordance realmente devuelta."))
        return finish("READY", operation(follow["action"], "Navegar en el corpus seleccionado.",
            "references/navigation.md", "scripts/knowledge.py", follow["action"],
            **{k: v for k, v in follow.items() if k != "action"}))
    if intent in NAV:
        if not (query or anchors) and intent != "understand":
            return finish("INSPECT_MORE", link("narrow-scope", "Aportar pregunta o identidades observadas."))
        command = "context" if anchors else "search" if query else "overview"
        delegate()
        return finish("READY", operation(command, "Recuperar el mínimo contexto pertinente.",
            "references/navigation.md", "scripts/knowledge.py", command,
            query=query, anchors=anchors, intent=intent))
    if intent == "index":
        if not state.get("reuse_index", False):
            return finish("READY", link("use-memory", "Modo puro por defecto; usar caché solo si aporta reutilización.",
                                        "references/index-cache.md"))
        return finish("READY", operation("index-status", "Índice opcional privado fuera de Git.",
            "references/index-cache.md", "scripts/knowledge.py", "index-status", cache=True))
    if intent == "maintain":
        delegate()
        return finish("PROPOSE_ONLY", operation("map-candidates", "Localizar átomos sin estructura; no escribir.",
            "references/architecture-discovery.md", "scripts/knowledge.py", "map-candidates"))
    if intent == "constitution":
        if not anchors:
            return finish("INSPECT_MORE", link("narrow-scope", "Seleccionar anclajes o usar ámbito explícito de la guía.",
                                               "references/architecture-discovery.md"))
        return finish("READY", operation("constitution", "Reglas existentes y conflictos; no nueva autoridad.",
            "references/architecture-discovery.md", "scripts/knowledge.py", "constitution", anchors=anchors))
    if not state.get("input_ready", False):
        return finish("INSPECT_MORE", link("prepare-input", "Obtener entrada explícita conforme al contrato de la lente."))
    delegate()
    if intent == "federate":
        return finish("READY", operation("federate", "Referencias calificadas; fuentes externas explícitas.",
            "references/federation.md", "scripts/federation.py", "navigate"))
    if intent == "evaluate":
        return finish("READY", link("choose-evaluation", "Distinguir recuperación, índice y ensayos observados.",
                                    "references/operational-evaluation.md"))
    if intent in {"architecture-review", "checkpoint", "context-pack"}:
        decision = "PROPOSE_ONLY" if intent in {"architecture-review", "checkpoint"} else "READY"
        return finish(decision, operation(intent, "Proyección acotada; no concede autorización ni verifica fuentes vivas.",
            "references/architecture-discovery.md", "scripts/knowledge.py", intent))
    raise ValueError("Unreachable navigation intent")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: affordances.py <session.json|->")
    try:
        if sys.argv[1] == "-":
            raw = sys.stdin.buffer.read(65537)
        else:
            with Path(sys.argv[1]).open("rb") as f:
                raw = f.read(65537)
        require(len(raw) <= 65536, "Oversized session")
        print(json.dumps(affordances(json.loads(raw)), ensure_ascii=False, separators=(",", ":")))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(json.dumps({"status": "INVALID_STATE", "error": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
