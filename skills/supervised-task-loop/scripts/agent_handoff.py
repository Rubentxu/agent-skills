#!/usr/bin/env python3
"""agent_handoff.py — el handoff del tablero y el prompt de la sesión.

QUÉ ES

Prepara lo que una iteración del bucle Ralph necesita antes de arrancar:

  1. el documento de handoff del tablero (lo crea la primera vez, con su esqueleto);
  2. la marca de tiempo del documento, para saber después si la sesión lo actualizó;
  3. el estado de la ronda de cada repositorio (¿toca pagar los gates?);
  4. el prompt de la sesión, renderizado desde la plantilla.

EL HANDOFF ES EL ÚNICO ESTADO ENTRE SESIONES

Como cada sesión arranca con el contexto en cero, lo único que sobrevive de una a otra es
lo que queda escrito. El tablero guarda el qué; el handoff guarda el cómo se llegó ahí: la
evidencia de la última tarea, lo que quedó a medias y lo aprendido. Por eso el documento se
escribe con la CLI de Backlog.md y nunca a mano: la CLI es la autoridad sobre lo que sus
propios ficheros significan, y un fichero escrito a mano en `backlog/docs/` es un documento
sin id, que `backlog doctor` marca como averiado.

CÓDIGOS DE SALIDA

  0  el handoff existe y el prompt está renderizado
  1  me negué: el tablero no responde o el handoff no se puede crear
  2  no pude medir
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_config import ErrorDeConfig, Runtime, init_runtime, repos_de_producto  # noqa: E402

TITULO_DOC = "handoff"
SUBDIR_DOC = "agent"


class Negativa(Exception):
    """Me negué: el tablero no responde o el handoff no se puede crear."""


def correr(orden: list[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    """Un comando de la CLI del tablero. Su codigo de salida se propaga: un fallo es un dato."""
    return subprocess.run(
        orden, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
    )


def texto_de(orden: list[str], cwd: Path) -> str:
    """La salida de un comando que tiene que funcionar."""
    resultado = correr(orden, cwd)
    if resultado.returncode != 0:
        raise Negativa(
            f"el tablero no responde a `{' '.join(orden)}`: "
            f"{(resultado.stderr or resultado.stdout).strip()}"
        )
    return resultado.stdout


def resolver_doc(rt: Runtime) -> str:
    """El id del documento de handoff, si ya existe."""
    salida = texto_de(["backlog", "doc", "list", "--plain"], rt.home_repo)
    for linea in salida.splitlines():
        partes = linea.split(" - ")
        if len(partes) >= 2 and partes[1].strip() == TITULO_DOC:
            return partes[0].strip()
    return ""


def crear_doc(rt: Runtime) -> str:
    """Crea el documento con su esqueleto y devuelve su id."""
    resultado = correr(
        ["backlog", "doc", "create", TITULO_DOC, "-p", SUBDIR_DOC, "-t", "other"], rt.home_repo
    )
    salida = resultado.stdout + resultado.stderr
    if resultado.returncode != 0:
        raise Negativa(f"no pude crear el documento: {salida.strip()}")
    encontrado = re.search(r"Created document (doc-\d+)", salida)
    if not encontrado:
        raise Negativa(f"la CLI no devolvio el id del documento creado: {salida.strip()}")
    doc_id = encontrado.group(1)

    esqueleto = (rt.assets / "handoff-template.md").read_text(encoding="utf-8")
    resultado = correr(
        ["backlog", "doc", "update", doc_id, "--content", esqueleto], rt.home_repo
    )
    if resultado.returncode != 0:
        raise Negativa(
            f"no pude escribir el esqueleto en {doc_id}: "
            f"{(resultado.stderr or resultado.stdout).strip()}"
        )
    return doc_id


def ruta_del_doc(rt: Runtime, doc_id: str) -> str:
    """La ruta real del documento: la que dice la CLI, nunca una adivinada.

    `backlog doc list` no da la ruta; hay que buscarla.
    """
    salida = texto_de(["backlog", "search", TITULO_DOC, "--json"], rt.home_repo)
    try:
        datos = json.loads(salida)
    except ValueError:
        return ""
    for resultado in datos.get("results") or []:
        if resultado.get("type") != "document":
            continue
        datos_doc = resultado.get("data") or {}
        if str(datos_doc.get("id")) == doc_id and datos_doc.get("path"):
            return str(datos_doc["path"])
    return ""


def marca_de_actualizacion(rt: Runtime, doc_id: str) -> str:
    """La marca de tiempo, para saber despues si la sesion lo toco."""
    resultado = correr(["backlog", "doc", "view", doc_id, "--plain"], rt.home_repo)
    if resultado.returncode != 0:
        return ""
    encontrado = re.search(
        r"^updated_date: *'?([^'\n]*)'?$", resultado.stdout, re.MULTILINE
    )
    return encontrado.group(1).strip() if encontrado else ""


def slug_de_repo(repo: Path) -> str:
    """El slug del repositorio: su nombre en el remoto, no el de la carpeta.

    El tablero cuenta por etiqueta `repo:<slug>`, y el slug es el nombre del repositorio en
    su remoto. Por eso el slug se saca del remoto: un repositorio cuyo remoto no se puede
    leer no se mide.
    """
    url = ""
    try:
        resultado = subprocess.run(
            ["git", "-C", str(repo), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if resultado.returncode == 0:
            url = resultado.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        url = ""
    if not url:
        return ""
    slug = re.sub(r"^.*[:/]", "", url)
    return re.sub(r"\.git$", "", slug)


def etiquetas_del_tablero(rt: Runtime) -> list[str]:
    """Las etiquetas que declara el tablero."""
    resultado = correr(["backlog", "config", "get", "labels"], rt.home_repo)
    if resultado.returncode != 0:
        return []
    return [e.strip() for e in resultado.stdout.strip().split(",") if e.strip()]


def ronda_para_repo(repo: Path, slug: str, rt: Runtime, etiquetas: list[str]) -> str:
    """¿Toca pagar los gates de este repositorio?

    La linea base la escribe la puerta, no este script: aqui solo se lee.
    """
    if not (repo / "tools/gate-cadence.py").is_file():
        return f"  - {slug}: este repositorio no tiene contador de ronda"
    if f"repo:{slug}" not in etiquetas:
        return f"  - {slug}: el tablero no declara etiqueta para el; su ronda no se mide"

    resultado = subprocess.run(
        [
            "python3",
            "-I",
            "tools/gate-cadence.py",
            "--board",
            str(rt.board_dir),
            "--repository",
            slug,
            "--strict",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if resultado.returncode == 3:
        return f"  - {slug}: TOCA (la ronda de este bloque esta pendiente)"
    if resultado.returncode == 0:
        return f"  - {slug}: no toca todavia"
    detalle = (resultado.stderr or resultado.stdout).strip().splitlines()
    return f"  - {slug}: no pude medir la ronda ({detalle[-1] if detalle else 'sin detalle'})"


def calcular_ronda(rt: Runtime) -> str:
    """La ronda de cada repositorio de producto, una linea por repositorio."""
    etiquetas = etiquetas_del_tablero(rt)
    lineas: list[str] = []
    for repo in repos_de_producto(rt.workspace, rt.home_repo):
        slug = slug_de_repo(repo) or repo.name
        lineas.append(ronda_para_repo(repo, slug, rt, etiquetas))
    if not lineas:
        return "  - no hay repos de producto que medir"
    return "\n".join(lineas)


def texto_de_las_skills(rt: Runtime) -> str:
    """Las skills que la sesion debe leer.

    Si la configuracion dice donde estan, se dice con la ruta exacta: no dependas de que se
    carguen solas. Si no lo dice, se nombran para que la sesion las busque.
    """
    if rt.skills:
        return "\n".join(f"- `{ruta}`" for ruta in rt.skills)
    return (
        "- `backlog-agile-workflow` — busca su `SKILL.md` en los directorios de skills de tu "
        "instalacion\n"
        "- `software-knowledge` — idem\n"
        "- `goldfish-review` — idem\n"
        "- `delivery-first-testing` — idem"
    )


def renderizar_prompt(rt: Runtime, doc_id: str, doc_path: str, ronda: str) -> Path:
    """El prompt de la sesion: la plantilla con sus marcadores sustituidos."""
    plantilla = rt.assets / "agent-prompt.md"
    if not plantilla.is_file():
        raise Negativa(f"no encuentro la plantilla del prompt: {plantilla}")

    texto = plantilla.read_text(encoding="utf-8")
    reemplazos = {
        "{{HANDOFF_ID}}": doc_id,
        "{{HANDOFF_PATH}}": doc_path,
        "{{HOME_DIR}}": str(rt.home_repo),
        "{{BOARD_DIR}}": str(rt.board_dir),
        "{{RONDA}}": ronda,
        "{{WORKSPACE_DIR}}": str(rt.workspace),
        "{{RUNTIME_DIR}}": str(rt.runtime_dir),
        "{{SKILLS}}": texto_de_las_skills(rt),
    }
    for marca, valor in reemplazos.items():
        texto = texto.replace(marca, valor)

    pendientes = [marca for marca in reemplazos if marca in texto]
    if pendientes:
        raise Negativa(f"el prompt conserva marcadores sin sustituir: {pendientes}")

    destino = rt.state / "prompt.md"
    rt.state.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    return destino


def preparar(rt: Runtime) -> dict[str, str]:
    """Deja el handoff listo y el prompt renderizado. Devuelve lo que la iteracion necesita.

    Si el documento no existe, se crea con su esqueleto: siempre hay un handoff valido, aunque
    la sesion falle.
    """
    doc_id = resolver_doc(rt)
    if not doc_id:
        print(
            f"handoff: el documento \"{TITULO_DOC}\" no existe; se crea con su esqueleto.",
            file=sys.stderr,
        )
        doc_id = crear_doc(rt)
        print(f"handoff: documento {doc_id} creado.", file=sys.stderr)

    doc_path = ruta_del_doc(rt, doc_id)
    if not doc_path:
        raise Negativa(
            f"no pude resolver la ruta del documento {doc_id}; la CLI no lo devuelve."
        )

    updated_antes = marca_de_actualizacion(rt, doc_id)
    ronda = calcular_ronda(rt)
    renderizar_prompt(rt, doc_id, doc_path, ronda)
    return {
        "doc_id": doc_id,
        "doc_path": doc_path,
        "updated_before": updated_antes,
        "ronda": ronda,
    }


def main() -> int:
    try:
        rt = init_runtime()
    except ErrorDeConfig as exc:
        print(f"handoff: ERROR — {exc}", file=sys.stderr)
        return 1

    rt.state.mkdir(parents=True, exist_ok=True)

    try:
        datos = preparar(rt)
    except Negativa as exc:
        print(f"handoff: {exc}", file=sys.stderr)
        return 1

    # Lo que la siguiente etapa necesita.
    (rt.state / "handoff.json").write_text(
        json.dumps(
            {
                "doc_id": datos["doc_id"],
                "doc_path": datos["doc_path"],
                "updated_before": datos["updated_before"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"handoff: documento {datos['doc_id']} en {datos['doc_path']}", file=sys.stderr)
    print(f"handoff: prompt renderizado en {rt.state / 'prompt.md'}", file=sys.stderr)
    print(f"handoff: ronda\n{datos['ronda']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
