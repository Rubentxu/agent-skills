#!/usr/bin/env python3
"""agent_config.py — la configuracion del bucle: donde se lee, que se deduce y que se dice.

QUÉ ES

Un módulo. Deja en el entorno lo que el runtime necesita saber y **dice de dónde lo ha
sacado**: una configuración que se deduce en silencio es una configuración que nadie puede
corregir.

LOS TRES SITIOS (y por qué son tres)

  RUN_DIR    el directorio del RUN: donde vive el runtime (los scripts y pipeline.agent.kts).
             Es el cwd de las etapas de la pipeline, y el estado del run se escribe en el.
  WORKSPACE  el WORKSPACE AGENTICO: el directorio desde el que el agente ve SUS repos.
             Puede ser el propio proyecto, o el DIRECTORIO PADRE de varios repos (el
             patrón home repo). Aquí es donde corre la sesión.
  HOME_REPO  el REPO DEL PROYECTO: el repositorio que lleva el tablero (`backlog/`). El
             tablero manda sobre lo que está hecho; el home repo es donde vive.

Los tres pueden coincidir o no, y por eso se separan y se dicen:

  un solo proyecto:    RUN_DIR = WORKSPACE = HOME_REPO = el proyecto.
  patrón home repo:   WORKSPACE = el directorio padre (donde están los repos de producto),
                       HOME_REPO = el hijo que lleva el tablero,
                       RUN_DIR = donde vive el runtime (el home repo, o la skill instalada).

LO QUE RESUELVE

  1. El fichero de configuracion (`agent-loop.env`). Se busca en varios sitios y se anuncia
     el que se ha usado. Las variables del entorno GANAN al fichero: el fichero es el valor
     del proyecto, el entorno es el override de una vez.
  2. El tablero. Si no se dice, se busca: en el directorio del run, en el de donde se lanzó,
     o en un único subdirectorio que lo tenga. Si hay varios, se dicen y se para: adivinar
     el tablero es abrir sesiones contra la autoridad equivocada.
  3. Los assets (la plantilla del prompt y el esqueleto del handoff).
  4. El directorio de estado del run: fuera del repo, en la convención de la máquina.

El módulo NO ejecuta el fichero de configuracion: lo lee línea a línea. Un `.env` que se
evalúa es un `.env` que puede hacer cualquier cosa.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS_DEL_SKILL = SCRIPT_DIR.parent / "assets"

# Los valores por defecto del runtime. Se pueden cambiar con el fichero de configuracion
# o con el entorno.
DEFECTOS = {
    "AGENT_PROFILE": "cuenta-6",
    "AGENT_BARE": "0",
    "AGENT_MAX_TASKS": "3",
    "AGENT_TASK_TIMEOUT_MIN": "60",
    "AGENT_SLICE": "dev-jvm.slice",
}


class ErrorDeConfig(Exception):
    """Un problema de configuración: no se puede seguir sin adivinar."""


@dataclass(frozen=True)
class Runtime:
    """Todo lo que el runtime necesita saber, ya resuelto."""

    script_dir: Path
    cwd: Path
    run_dir: Path
    workspace: Path
    home_repo: Path
    board_dir: Path
    runtime_dir: Path
    assets: Path
    pipeline_file: Path
    state: Path
    config_file: Path | None
    profile: str
    bare: bool
    max_tasks: int
    task_timeout_min: int
    slice: str
    skills: tuple[str, ...]

    def valor(self, nombre: str, defecto: str = "") -> str:
        return os.environ.get(nombre, defecto)


# --- el fichero de configuracion ------------------------------------------------------------------
def leer_config(ruta: Path) -> dict[str, str]:
    """Lee el fichero de configuracion linea a linea. No lo ejecuta.

    El entorno gana al fichero: si la variable ya viene de fuera, el fichero no la pisa.
    """
    valores: dict[str, str] = {}
    try:
        texto = ruta.read_text(encoding="utf-8")
    except OSError as exc:
        raise ErrorDeConfig(f"no puedo leer la configuracion {ruta}: {exc}") from exc

    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip()
        valor = valor.strip()
        # Se ignoran las comillas que envuelven el valor.
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        # Solo claves de entorno: mayusculas y guion bajo.
        if not clave or not all(c.isupper() or c == "_" for c in clave):
            continue
        if not clave[0].isalpha() and clave[0] != "_":
            continue
        if clave in os.environ:
            continue
        valores[clave] = valor
        os.environ[clave] = valor
    return valores


def buscar_config(run_dir: Path, cwd: Path) -> Path | None:
    """El fichero de configuracion: el que dice el entorno, o el primero que exista."""
    indicado = os.environ.get("AGENT_LOOP_ENV", "").strip()
    if indicado:
        return Path(indicado).expanduser()
    for candidato in (
        run_dir / "agent-loop.env",
        cwd / "agent-loop.env",
        SCRIPT_DIR.parent / "agent-loop.env",
        Path.home() / ".config/agent-skills/supervised-task-loop.env",
    ):
        if candidato.is_file():
            return candidato
    return None


# --- los tres sitios -----------------------------------------------------------------------------
def deducir_run_dir(cwd: Path) -> Path:
    """El directorio del run: donde vive el runtime.

    Primero junto a los scripts que se están ejecutando (el runtime de verdad), y luego en el
    directorio desde el que se lanzó.
    """
    junto = SCRIPT_DIR.parent
    if (junto / "pipeline.agent.kts").is_file() or (junto / "assets/pipeline.agent.kts").is_file():
        return junto
    if (cwd / "pipeline.agent.kts").is_file() or (cwd / "assets/pipeline.agent.kts").is_file():
        return cwd
    raise ErrorDeConfig(
        "no encuentro el runtime: no hay pipeline.agent.kts junto a los scripts "
        f"({SCRIPT_DIR.parent}) ni en el directorio desde el que se lanzó ({cwd})"
    )


def _absolutizar(ruta: str | Path, base: Path) -> Path:
    """Una ruta relativa se resuelve contra el directorio de donde se lanzó."""
    ruta = Path(ruta).expanduser()
    if ruta.is_absolute():
        return ruta
    return (base / ruta).resolve()


def deducir_tablero(run_dir: Path, cwd: Path, workspace: Path) -> Path:
    """El tablero: la unica autoridad.

    Prioridad: lo que se dice; el directorio del run (el home repo de costumbre); el
    directorio desde el que se lanzó; y un único subdirectorio que lo tenga (el patrón home
    repo). Con varios, se dicen y se para.
    """
    indicado = os.environ.get("AGENT_BOARD", "").strip()
    if indicado:
        return _absolutizar(indicado, cwd)

    for raiz in (run_dir, cwd, workspace):
        if (raiz / "backlog/config.yml").is_file():
            return raiz / "backlog"

    encontrados: list[Path] = []
    for raiz in (run_dir, cwd, workspace):
        for candidato in sorted(raiz.glob("*/backlog/config.yml")):
            tablero = candidato.parent.resolve()
            if tablero not in encontrados:
                encontrados.append(tablero)

    if not encontrados:
        raise ErrorDeConfig(
            "no encuentro el tablero (ningun backlog/config.yml en "
            f"{run_dir}, en {cwd} ni en sus subdirectorios).\n"
            "       Ponlo en agent-loop.env: AGENT_BOARD=/ruta/al/tablero"
        )
    if len(encontrados) > 1:
        lista = "\n".join(f"       - {p}" for p in encontrados)
        raise ErrorDeConfig(
            f"hay mas de un tablero y no se cual es:\n{lista}\n"
            "       Ponlo en agent-loop.env: AGENT_BOARD=/ruta/al/tablero"
        )
    return encontrados[0]


def resolver_assets(run_dir: Path) -> Path:
    """Los assets: la plantilla del prompt y el esqueleto del handoff.

    Los del proyecto mandan sobre los de la skill: el prompt se puede customizing.
    """
    indicado = os.environ.get("AGENT_ASSETS", "").strip()
    if indicado:
        return _absolutizar(indicado, Path.cwd())
    for candidato in (run_dir / "assets", ASSETS_DEL_SKILL, SCRIPT_DIR):
        if (candidato / "agent-prompt.md").is_file():
            return candidato
    raise ErrorDeConfig(
        f"no encuentro la plantilla del prompt (ni en {run_dir}/assets ni en "
        f"{ASSETS_DEL_SKILL} ni en {SCRIPT_DIR})"
    )


def resolver_pipeline(run_dir: Path, home_repo: Path) -> Path:
    """La pipeline: la del proyecto si la tiene, y si no la del runtime.

    El proyecto manda: su pipeline es la suya (puede estar ajustada a su tablero). La del
    runtime es el plan por defecto.
    """
    for candidato in (home_repo / "pipeline.agent.kts", run_dir / "pipeline.agent.kts",
                      run_dir / "assets/pipeline.agent.kts",
                      ASSETS_DEL_SKILL / "pipeline.agent.kts"):
        if candidato.is_file():
            return candidato
    raise ErrorDeConfig(
        f"no encuentro pipeline.agent.kts (ni en {home_repo} ni en {run_dir} "
        f"ni en {ASSETS_DEL_SKILL})"
    )


def repos_de_producto(workspace: Path, home_repo: Path) -> list[Path]:
    """Los repos de producto: los repos Git que cuelgan del workspace agéntico.

    El home repo NO es producto: lleva el tablero y el runtime.
    """
    repos: list[Path] = []
    if not workspace.is_dir():
        return repos
    for entrada in sorted(workspace.iterdir()):
        if not entrada.is_dir():
            continue
        if not (entrada / ".git").exists():
            continue
        if entrada.resolve() == home_repo.resolve():
            continue
        repos.append(entrada)
    return repos


# --- el runtime: donde vive, y donde se configura -------------------------------------------------
def init_runtime() -> Runtime:
    """Resuelve todo y lo deja listo. Lanza ErrorDeConfig si algo no se puede saber."""
    cwd = Path.cwd().resolve()
    run_dir = deducir_run_dir(cwd)

    fichero = buscar_config(run_dir, cwd)
    if fichero is not None:
        leer_config(fichero)

    # El workspace agéntico: por defecto, el directorio desde el que se lanzó. Si el fichero
    # lo dice, se usa el que dice: ese es el caso del patrón home repo, donde el agente
    # trabaja desde el padre.
    workspace = _absolutizar(os.environ.get("AGENT_WORKSPACE", "").strip() or str(cwd), cwd)

    tablero = deducir_tablero(run_dir, cwd, workspace)
    home_repo = tablero.parent

    # El estado del run: fuera del repo, en la convención de la máquina. Se nombra por el home
    # repo, que es el proyecto: el estado es del proyecto, no del script.
    estado = os.environ.get("AGENT_STATE", "").strip()
    if estado:
        estado = _absolutizar(estado, cwd)
    else:
        base = os.environ.get("XDG_STATE_HOME", "").strip() or str(Path.home() / ".local/state")
        estado = Path(base) / "pipelinek" / home_repo.name

    # Los scripts: en el directorio del run, o en el del propio runtime.
    runtime_dir = run_dir / "scripts" if (run_dir / "scripts").is_dir() else SCRIPT_DIR

    def entero(nombre: str, defecto: int) -> int:
        bruto = os.environ.get(nombre, str(defecto)).strip()
        try:
            return int(bruto)
        except ValueError:
            return defecto

    # Las skills que la sesion debe leer: rutas absolutas, separadas por dos puntos.
    skills = tuple(
        parte.strip()
        for parte in os.environ.get("AGENT_SKILLS", "").split(":")
        if parte.strip()
    )

    return Runtime(
        script_dir=SCRIPT_DIR,
        cwd=cwd,
        run_dir=run_dir,
        workspace=workspace,
        home_repo=home_repo,
        board_dir=tablero,
        runtime_dir=runtime_dir,
        assets=resolver_assets(run_dir),
        pipeline_file=resolver_pipeline(run_dir, home_repo),
        state=estado,
        config_file=fichero,
        profile=os.environ.get("AGENT_PROFILE", DEFECTOS["AGENT_PROFILE"]).strip(),
        bare=os.environ.get("AGENT_BARE", DEFECTOS["AGENT_BARE"]).strip() == "1",
        max_tasks=entero("AGENT_MAX_TASKS", int(DEFECTOS["AGENT_MAX_TASKS"])),
        task_timeout_min=entero("AGENT_TASK_TIMEOUT_MIN", int(DEFECTOS["AGENT_TASK_TIMEOUT_MIN"])),
        slice=os.environ.get("AGENT_SLICE", DEFECTOS["AGENT_SLICE"]).strip(),
        skills=skills,
    )


def anunciar(rt: Runtime) -> None:
    """Que se use esto es un dato: se dice una vez, en una linea, y con que fichero."""
    print(f"config: {rt.config_file or 'sin fichero (todo deducido)'}")
    print(f"config: pipeline={rt.pipeline_file}")
    print(f"config: run={rt.run_dir}")
    print(f"config: workspace agentico={rt.workspace}")
    print(f"config: home repo={rt.home_repo}")
    print(f"config: tablero={rt.board_dir}")
    print(f"config: estado={rt.state}")
    print(
        f"config: perfil={rt.profile} | tareas={rt.max_tasks} | "
        f"techo={rt.task_timeout_min} min | slice={rt.slice}"
    )


def main() -> int:
    try:
        anunciar(init_runtime())
    except ErrorDeConfig as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
