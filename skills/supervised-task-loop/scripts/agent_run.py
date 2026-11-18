#!/usr/bin/env python3
"""agent_run.py — lanza el bucle supervisado.

QUÉ ES

El lanzador. Carga la configuración (el fichero `agent-loop.env`, si lo hay), deduce el
tablero, y arranca la pipeline. Es el único comando que hace falta.

  ./scripts/agent_run.py                 # el bucle de siempre
  ./scripts/agent_run.py --rerun         # repetir el run (la iteracion es idempotente)
  AGENT_MAX_TASKS=1 ./scripts/agent_run.py

Si la máquina vigila los recursos por slices, el lanzamiento es `systemd-run` (la unidad
vive en la slice, desacoplada del shell que la lanzó, con su directorio de trabajo y su
PATH; el `--setenv` hace falta porque las unidades de usuario no heredan el PATH del shell):

  systemd-run --user --unit=<nombre> --slice=dev-jvm.slice \\
      --working-directory=<home repo> --setenv=PATH="$PATH" \\
      bash -c 'python3 <runtime>/agent_run.py'

EL ESTADO

Vive fuera del repo, en `${XDG_STATE_HOME:-$HOME/.local/state}/pipelinek/<home-repo>`: la
base de datos del run, el control root, el prompt renderizado y los informes de cada
iteración. El árbol no lleva estado operativo.

EL SUPERVISOR TAMBIÉN ES TRABAJO LARGO

La pipeline es un proceso Java de larga vida, igual que un build. Si la máquina vigila sus
recursos por slices y el supervisor corre fuera del suyo, el vigilante lo mata a los
minutos como "build fuera de slice" — y la sesión que abrió sobrevive huérfana. Por eso
`agent_run.py` se niega a arrancar si la configuración declara `AGENT_SLICE` y este proceso
no está dentro de esa slice: la manera correcta de lanzarlo es `systemd-run` (ver abajo).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_config import ErrorDeConfig, Runtime, anunciar, init_runtime  # noqa: E402

FICHERO_CGROUP = Path("/proc/self/cgroup")


def esta_en_la_slice(contenido: str, slice_nombre: str) -> bool:
    """¿Alguna línea del cgroup v2 cuelga de esa slice?

    Las líneas son `0::/user.slice/user-1000.slice/.../dev-jvm.slice/<unidad>`. Basta con
    ver la slice como un tramo del camino: un `dev-jvmx.slice` no contiene a `dev-jvm.slice`.
    """
    for linea in contenido.splitlines():
        partes = linea.split(":", 2)
        if len(partes) != 3:
            continue
        ruta = partes[2]
        if f"/{slice_nombre}/" in ruta or ruta.rstrip("/").endswith(f"/{slice_nombre}"):
            return True
    return False


def linea_de_lanzamiento(rt: Runtime) -> str:
    """La orden que lanza el run dentro de su slice, para decirla en el error."""
    return (
        f"systemd-run --user --unit=<nombre> --slice={rt.slice} "
        f'--working-directory={rt.home_repo} --setenv=PATH="$PATH" '
        f"bash -c 'python3 {rt.script_dir}/agent_run.py'"
    )


def main() -> int:
    try:
        rt = init_runtime()
    except ErrorDeConfig as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    anunciar(rt)

    # La slice declarada es un contrato con la máquina: el supervisor es trabajo largo y su
    # vigilante mata lo que corre fuera de su sitio. Si no estamos dentro, me niego ANTES de
    # abrir nada: un run que va a morir a los quince minutos con una sesión huérfana detrás
    # es peor que no arrancar. Sin AGENT_SLICE no hay contrato que comprobar.
    if rt.slice:
        try:
            contenido = FICHERO_CGROUP.read_text(encoding="utf-8")
        except OSError:
            contenido = ""
        if contenido and not esta_en_la_slice(contenido, rt.slice):
            print(
                f"ERROR: la configuracion declara AGENT_SLICE={rt.slice} pero el supervisor "
                "corre fuera de ella; el vigilante de la maquina lo mataria en cuanto lo viera "
                "como un build sin sitio. Lanzalo dentro de su slice:\n"
                f"  {linea_de_lanzamiento(rt)}",
                file=sys.stderr,
            )
            return 1

    rt.state.mkdir(parents=True, exist_ok=True)

    # `--resume` no reintenta un step fallido: lo reporta. Para re-ejecutar hay que usar
    # `--rerun`, y `--rerun` es seguro porque la iteracion es idempotente: la iteracion ya
    # medida reutiliza su informe y no consume una tarea.
    extra: list[str] = []
    for argumento in sys.argv[1:]:
        if argumento in ("--resume", "--rerun"):
            extra.append(argumento)
        else:
            print("uso: agent_run.py [--resume|--rerun]", file=sys.stderr)
            return 1

    # El workspace de la pipeline es el PROYECTO (el home repo): ahi es donde se archivan los
    # artefactos y donde vive el tablero. El runtime puede estar en otro sitio —la skill
    # instalada— y entonces los scripts se invocan por la ruta que dice `AGENT_RUNTIME`.
    orden = [
        "pipelinek",
        "run",
        *extra,
        "--workspace",
        str(rt.home_repo),
        "--db",
        str(rt.state / "run.sqlite"),
        "--control-root",
        str(rt.state / "control"),
        str(rt.pipeline_file),
    ]
    try:
        return subprocess.run(orden, check=False).returncode
    except FileNotFoundError:
        print("ERROR: no encuentro el binario pipelinek.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
