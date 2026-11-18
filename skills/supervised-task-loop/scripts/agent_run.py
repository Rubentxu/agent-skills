#!/usr/bin/env python3
"""agent_run.py — lanza el bucle supervisado.

QUÉ ES

El lanzador. Carga la configuración (el fichero `agent-loop.env`, si lo hay), deduce el
tablero, y arranca la pipeline. Es el único comando que hace falta.

  ./scripts/agent_run.py                 # el bucle de siempre
  ./scripts/agent_run.py --rerun         # repetir el run (la iteracion es idempotente)
  AGENT_MAX_TASKS=1 ./scripts/agent_run.py

EL ESTADO

Vive fuera del repo, en `${XDG_STATE_HOME:-$HOME/.local/state}/pipelinek/<home-repo>`: la
base de datos del run, el control root, el prompt renderizado y los informes de cada
iteración. El árbol no lleva estado operativo.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_config import ErrorDeConfig, anunciar, init_runtime  # noqa: E402


def main() -> int:
    try:
        rt = init_runtime()
    except ErrorDeConfig as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    anunciar(rt)

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

    # El workspace de la pipeline es el directorio del run: ahi es donde estan los scripts que
    # invoca cada etapa (`./scripts/...`), y donde se archivan los artefactos. El workspace
    # agéntico —donde corre la sesion— es otro sitio, y lo dice la configuracion.
    orden = [
        "pipelinek",
        "run",
        *extra,
        "--workspace",
        str(rt.run_dir),
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
