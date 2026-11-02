#!/usr/bin/env python3
"""Mide el presupuesto de contexto estático de un harness de agente.

Solo lee: no escribe, no modifica configuración y no invoca al harness. Inventaría lo que se
carga en cada petición (always-on) y lo que sólo se carga al invocarse (on-demand), y lo
reporta con una estimación de tokens.

Los tokens se estiman como bytes/4 (esquema JSON, código, prosa técnica) o palabras*1.3
(prosa). Es una estimación declarada, no una medición: para el número real hay que leer el
`input_tokens` de una respuesta del harness.

Uso:
    python3 measure_context.py [--project DIR] [--config DIR] [--json] [--top N]

    --project DIR   raíz del proyecto (por defecto, el directorio actual)
    --config DIR    directorio de configuración del harness
                    (por defecto $CLAUDE_CONFIG_DIR o ~/.claude)
    --json          salida en JSON para consumo programático
    --top N         cuántas entradas detalle listar por sección (por defecto 12)
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

# Ficheros que el harness lee como instrucciones del proyecto.
ENTRY_NAMES = ("AGENTS.md", "CLAUDE.md", ".claude/CLAUDE.md", ".claude/AGENTS.md",
               "CLAUDE.local.md")
# Ficheros de reglas por路径 (scoped) — no se cargan siempre si llevan `paths:`.
RULE_DIRS = (".claude/rules",)
# Nombres de fichero de instrucciones que cuentan como entrada del usuario.
SKILL_FILES = ("SKILL.md",)


def tokens_of(text: str) -> int:
    """Tokens aproximados: palabras*1.3 para prosa, bytes/4 para el resto.

    Se usa la prosa cuando el texto tiene una alta proporción de palabras; para JSON, código
    o tablas la división por bytes es más ajustada.
    """
    words = len(text.split())
    if words and len(text) / max(words, 1) < 9:
        return int(words * 1.3)
    return len(text) // 4


def tokens_of_bytes(data: bytes) -> int:
    return len(data) // 4


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def frontmatter_description(text: str) -> str:
    """Extrae la descripción del front matter de un SKILL.md, si la hay."""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end == -1:
        return ""
    block = text[3:end]
    match = re.search(r"^description:\s*(.+)$", block, re.M)
    if not match:
        return ""
    value = match.group(1).strip().strip("'\"")
    return value


def is_path_scoped(text: str) -> bool:
    """Una regla con `paths:` en el front matter no se carga siempre."""
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    if end == -1:
        return False
    return bool(re.search(r"^paths:", text[3:end], re.M))


class Inventory:
    def __init__(self) -> None:
        self.always_on: list[dict] = []
        self.on_demand: list[dict] = []
        self.servers: list[dict] = []
        self.plugins: list[dict] = []
        self.hook_events: dict[str, int] = {}
        self.warnings: list[str] = []

    def add_always(self, source: str, scope: str, path: Path, tokens: int, note: str = "") -> None:
        self.always_on.append({
            "source": source, "scope": scope, "path": str(path),
            "tokens": tokens, "note": note,
        })

    def add_on_demand(self, source: str, path: Path, tokens: int) -> None:
        self.on_demand.append({
            "source": source, "path": str(path), "tokens": tokens,
        })


def scan_entry_files(project: Path, config_dir: Path, inv: Inventory) -> None:
    """Cadena de ficheros de instrucciones: proyecto y cada directorio padre hasta la raíz."""
    seen: set[Path] = set()
    current = project.resolve()
    while True:
        for name in ENTRY_NAMES:
            candidate = current / name
            if not candidate.is_file():
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            text = read(candidate)
            inv.add_always("instructions", "project", candidate, tokens_of(text))
        if current.parent == current:
            break
        current = current.parent

    user_entry = config_dir / "CLAUDE.md"
    if user_entry.is_file():
        text = read(user_entry)
        inv.add_always("instructions", "user", user_entry, tokens_of(text))


def scan_rules(project: Path, config_dir: Path, inv: Inventory) -> None:
    """Ficheros de reglas: los no acotados por `paths:` cargan siempre."""
    roots = [project / d for d in RULE_DIRS] + [config_dir / "rules"]
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            text = read(path)
            if is_path_scoped(text):
                inv.add_on_demand("rules-scoped", path, tokens_of(text))
            else:
                inv.add_always("rules", "project" if root.is_relative_to(project) else "user",
                               path, tokens_of(text))


def scan_skills(project: Path, config_dir: Path, inv: Inventory) -> None:
    """El catálogo (nombre + descripción) carga siempre; el cuerpo, al invocarse."""
    roots = [config_dir / "skills", project / ".claude" / "skills",
             project / ".agents" / "skills"]
    for root in roots:
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            skill_file = entry / "SKILL.md" if entry.is_dir() else (
                entry if entry.name in SKILL_FILES else None)
            if skill_file is None or not skill_file.is_file():
                continue
            text = read(skill_file)
            description = frontmatter_description(text)
            catalogue = len(description.split()) * 1.3
            inv.add_always("skill-catalogue", "user" if root.is_relative_to(config_dir) else "project",
                           skill_file, int(catalogue), note=description[:120])
            body_tokens = tokens_of(text) - int(catalogue)
            inv.add_on_demand("skill-body", skill_file, max(body_tokens, 0))
            for ref in sorted(entry.rglob("*.md")):
                if ref == skill_file:
                    continue
                inv.add_on_demand("skill-reference", ref, tokens_of(read(ref)))


def scan_agents(project: Path, config_dir: Path, inv: Inventory) -> None:
    """Las descripciones de agentes cargan siempre; su cuerpo, al lanzarse."""
    roots = [config_dir / "agents", project / ".claude" / "agents",
             project / ".agents" / "agents"]
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.md")):
            text = read(path)
            description = frontmatter_description(text)
            catalogue = len(description.split()) * 1.3 if description else len(text.split()) * 1.3
            inv.add_always("agent-catalogue", "user" if root.is_relative_to(config_dir) else "project",
                           path, int(catalogue))
            inv.add_on_demand("agent-body", path, max(tokens_of(text) - int(catalogue), 0))


def scan_mcp(project: Path, config_dir: Path, inv: Inventory) -> None:
    """Los servidores MCP se declaran en tres sitios: global, proyecto y plugin."""
    global_config = load_json(config_dir / ".claude.json") or {}
    candidates: list[tuple[str, Path, dict]] = [
        ("user", config_dir / ".claude.json", global_config.get("mcpServers") or {}),
    ]
    project_mcp = project / ".mcp.json"
    if project_mcp.is_file():
        candidates.append(("project", project_mcp,
                           load_json(project_mcp).get("mcpServers") or {}))
    settings = load_json(config_dir / "settings.json")
    settings_servers = settings.get("mcpServers") or {}
    if settings_servers:
        candidates.append(("user-settings", config_dir / "settings.json", settings_servers))

    for scope, path, servers in candidates:
        for name, spec in servers.items():
            tools = 0
            if isinstance(spec, dict):
                tools = int(spec.get("toolCount") or spec.get("tools") or 0)
            inv.servers.append({
                "name": name, "scope": scope, "path": str(path),
                "tools": tools, "declared_tools": bool(tools),
            })

    # Un servidor declarado en más de un sitio se paga en todos: es el error clásico.
    by_name: dict[str, list[str]] = {}
    for server in inv.servers:
        by_name.setdefault(server["name"], []).append(server["scope"])
    for name, scopes in by_name.items():
        if len(scopes) > 1:
            inv.warnings.append(
                f"el servidor MCP '{name}' está declarado en {len(scopes)} sitios "
                f"({', '.join(sorted(set(scopes)))}): quitar uno no basta")


def scan_plugins(config_dir: Path, inv: Inventory) -> None:
    settings = load_json(config_dir / "settings.json")
    enabled = settings.get("enabledPlugins") or {}
    for name, value in enabled.items():
        inv.plugins.append({"name": name, "enabled": bool(value)})
    installed = load_json(config_dir / "plugins" / "installed_plugins.json")
    for name, scopes in (installed.get("plugins") or {}).items():
        if name in enabled:
            continue
        inv.plugins.append({"name": name, "enabled": False})


def scan_hooks(config_dir: Path, project: Path, inv: Inventory) -> None:
    """Cuenta hooks por evento en cada fuente de configuración."""
    sources = [config_dir / "settings.json", project / ".claude" / "settings.json",
               project / ".claude" / "settings.local.json",
               config_dir / "settings.local.json"]
    for source in sources:
        data = load_json(source)
        hooks = data.get("hooks")
        if not isinstance(hooks, dict):
            continue
        for event, entries in hooks.items():
            if isinstance(entries, list):
                inv.hook_events[event] = inv.hook_events.get(event, 0) + len(entries)


def project_slug(project: Path) -> str:
    """El identificador que el harness usa para nombrar la carpeta del proyecto.

    Claude Code deriva el nombre del directorio de sesión de la ruta absoluta
    sustituyendo cada barra por un guion: `/var/home/u/proyecto` → `-var-home-u-proyecto`.
    """
    return str(project.resolve()).replace("/", "-")


def scan_memory(config_dir: Path, project: Path, inv: Inventory) -> None:
    """El índice de memoria del proyecto activo carga siempre; los temas, al leerlos.

    Sólo cuenta la carpeta que corresponde a este proyecto: la memoria de otro proyecto no se
    adjunta a esta sesión, así que sumarla infla la carga fija medida.
    """
    projects_dir = config_dir / "projects"
    if not projects_dir.is_dir():
        return
    entry = projects_dir / project_slug(project)
    if not entry.is_dir():
        return
    index = entry / "memory" / "MEMORY.md"
    if index.is_file():
        inv.add_always("memory-index", "project", index, tokens_of(read(index)))
    memory_dir = entry / "memory"
    if not memory_dir.is_dir():
        return
    for topic in sorted(memory_dir.glob("*.md")):
        if topic == index:
            continue
        inv.add_on_demand("memory-topic", topic, tokens_of(read(topic)))


def build(project: Path, config_dir: Path) -> Inventory:
    inv = Inventory()
    scan_entry_files(project, config_dir, inv)
    scan_rules(project, config_dir, inv)
    scan_skills(project, config_dir, inv)
    scan_agents(project, config_dir, inv)
    scan_mcp(project, config_dir, inv)
    scan_plugins(config_dir, inv)
    scan_hooks(config_dir, project, inv)
    scan_memory(config_dir, project, inv)
    return inv


def report(inv: Inventory, top: int) -> str:
    always = sum(item["tokens"] for item in inv.always_on)
    on_demand = sum(item["tokens"] for item in inv.on_demand)
    lines: list[str] = []
    lines.append("# Inventario de contexto (estimado, tokens ≈ bytes/4 o palabras×1.3)")
    lines.append("")
    lines.append(f"Always-on (se paga cada turno): ≈{always} tokens")
    lines.append(f"On-demand (sólo al invocarse):  ≈{on_demand} tokens")
    lines.append("")
    lines.append("## Always-on, por fuente")
    by_source: dict[str, int] = {}
    for item in inv.always_on:
        by_source[item["source"]] = by_source.get(item["source"], 0) + item["tokens"]
    for source, tokens in sorted(by_source.items(), key=lambda kv: -kv[1]):
        lines.append(f"  {source:<22} ≈{tokens:>8} tokens")
    lines.append("")
    lines.append("## Detalle (mayores primero)")
    for item in sorted(inv.always_on, key=lambda i: -i["tokens"])[:top]:
        lines.append(f"  ≈{item['tokens']:>7}  [{item['scope']}] {item['source']}: {item['path']}")
    if inv.servers:
        lines.append("")
        lines.append("## Servidores MCP")
        for server in inv.servers:
            declared = (f" ~{server['tools']} tools declarados"
                        if server["declared_tools"] else " (tools no contables en disco)")
            lines.append(f"  {server['name']} [{server['scope']}]{declared}")
    if inv.hook_events:
        lines.append("")
        lines.append("## Hooks por evento")
        for event, count in sorted(inv.hook_events.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {event:<24} {count}")
    if inv.warnings:
        lines.append("")
        lines.append("## Avisos")
        for warning in inv.warnings:
            lines.append(f"  ! {warning}")
    lines.append("")
    lines.append("Los esquemas de herramientas MCP no se cuentan: dependen del harness y de "
                 "si difiere la carga. Mide el `input_tokens` real de una respuesta.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=".", help="raíz del proyecto")
    parser.add_argument("--config", default=None,
                        help="directorio de configuración del harness")
    parser.add_argument("--json", action="store_true", help="salida JSON")
    parser.add_argument("--top", type=int, default=12, help="entradas a detallar")
    args = parser.parse_args(argv)

    project = Path(args.project).resolve()
    config_dir = Path(args.config).resolve() if args.config else Path(
        os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")).resolve()

    if not project.is_dir():
        print(f"ERROR: no existe el directorio de proyecto: {project}")
        return 2

    inv = build(project, config_dir)
    if args.json:
        always = sum(item["tokens"] for item in inv.always_on)
        on_demand = sum(item["tokens"] for item in inv.on_demand)
        print(json.dumps({
            "project": str(project), "config": str(config_dir),
            "always_on_tokens": always, "on_demand_tokens": on_demand,
            "always_on": inv.always_on, "on_demand": inv.on_demand,
            "mcp_servers": inv.servers, "plugins": inv.plugins,
            "hook_events": inv.hook_events, "warnings": inv.warnings,
        }, indent=2, ensure_ascii=False))
    else:
        print(report(inv, args.top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
