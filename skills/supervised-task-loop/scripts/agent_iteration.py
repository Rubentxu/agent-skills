#!/usr/bin/env python3
"""agent_iteration.py — una iteración del bucle: una sesión, una tarea.

QUÉ ES

Ejecuta UNA sesión de agente con el contexto en cero y mide lo que entrega. La sesión es un
proceso nuevo: no hereda el contexto de la anterior, así que no hay compactaciones ni el olvido
de lo que se hizo hace tres horas. Lo que sobrevive entre sesiones es el handoff del tablero
y el propio tablero.

POR QUÉ NO SE SONDEA

La sesión se lanza y se espera a que termine. No hay bucles `until ... sleep`, no hay
`grep -c` sobre un log, y no hay un timeout corto que expire antes de que el trabajo acabe:
ese patrón era lo que hacía que una medición de diez minutos se relanzara cinco veces.

LO QUE MIDE

El informe (`agent_loop_report.py`) compara el tablero antes y después, lee el transcript de
la sesión y pregunta a GitHub por los PR. Su veredicto es el de la casa: PASS, FAIL, BLOCKED
o NOT_RUN.

USO

  agent_iteration.py NUMERO

CÓDIGOS DE SALIDA

  0  la iteración entregó (PASS)
  1  me negué (uso incorrecto)
  2  no pude medir (BLOCKED, o no hubo trabajo listo)
  3  la iteración falló (FAIL)
"""
from __future__ import annotations

import errno
import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_handoff  # noqa: E402
from agent_config import ErrorDeConfig, Runtime, init_runtime  # noqa: E402

ESPERA_SESION_MIN_POR_DEFECTO = 60


class Negativa(Exception):
    """Me negué: el uso es incorrecto o falta algo."""


def vivo(pid: int) -> bool:
    """¿El proceso sigue vivo? Un pid que no es nuestro da EPERM, y tambien es vivo."""
    try:
        os.kill(pid, 0)
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False
        if exc.errno == errno.EPERM:
            return True
        raise
    return True


def esperar_a(pid: int, segundos: int) -> None:
    """Espera a que el proceso muera, sin sondear.

    Con `pidfd` el kernel avisa: se espera a un evento, no a un reloj. Sin `pidfd` (o sin
    permiso para abrirlo), se usa `tail --pid`, que tampoco sondea.
    """
    try:
        descriptor = os.pidfd_open(pid)
    except (AttributeError, OSError):
        subprocess.run(
            ["timeout", str(segundos), "tail", f"--pid={pid}", "-f", "/dev/null"],
            check=False,
            capture_output=True,
        )
        return
    try:
        poller = select.poll()
        poller.register(descriptor, select.POLLIN)
        poller.poll(max(segundos, 1) * 1000)
    finally:
        os.close(descriptor)


def lanzar_sesion(rt: Runtime, prompt: Path, destino_sesion: Path, destino_error: Path) -> int:
    """La sesión: un proceso nuevo, con su propio grupo de procesos, y su PID guardado.

    `start_new_session` (setsid) pone la sesion en su PROPIA sesion de procesos. Sin esto, la
    sesion comparte grupo con la pipeline y con el shell de la herramienta que lo lanzo:
    cualquier senal que llegue a ese grupo se lleva por delante la pipeline entera. Se ha
    visto pasar dos veces (SIGTERM desde fuera, con el paso muriendo de SIGPIPE). Aislar la
    sesion hace que eso no pueda tocar la pipeline, y de paso los daemons que el agente deja
    tirados (Gradle, watchers) no se quedan pegados al grupo de la pipeline.
    """
    perfil = Path.home() / ".config/claude-profiles" / f"{rt.profile}.json"
    if not perfil.is_file():
        raise Negativa(f"el perfil no existe: {perfil}")

    orden = ["claude"]
    if rt.bare:
        # `--bare` apaga los hooks de plugin, pero tambien apaga el login de claude.ai, y los
        # perfiles de esta maquina se autentican con `CLAUDE_CODE_OAUTH_TOKEN`: con `--bare`
        # la sesion responde "Not logged in". El contexto en cero lo garantiza el proceso
        # nuevo, no el flag.
        orden.append("--bare")
    orden += [
        "--settings",
        str(perfil),
        "-p",
        prompt.read_text(encoding="utf-8"),
        "--output-format",
        "json",
    ]

    with destino_sesion.open("w", encoding="utf-8") as salida, destino_error.open(
        "w", encoding="utf-8"
    ) as error:
        proceso = subprocess.Popen(
            orden,
            cwd=rt.workspace,
            stdout=salida,
            stderr=error,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        # El PID de la sesion se guarda: si la pipeline muere por fuera, la sesion puede
        # seguir viva, y un reintento tiene que reconocerla en vez de abrir otra encima.
        (destino_sesion.parent / "sesion.pid").write_text(str(proceso.pid), encoding="utf-8")
        return proceso.wait()


def construir_informe(rt: Runtime, dir_iter: Path, handoff: dict[str, str], inicio: str) -> Path:
    """El informe: una funcion de los artefactos en disco, de modo que siempre se puede rehacer."""
    informe = dir_iter / "report.json"
    # El directorio del transcript: el cwd codificado como lo nombra el agente. El cwd de la
    # sesion es el WORKSPACE AGENTICO, que no tiene por que ser el home repo.
    dir_transcripto = Path.home() / ".claude/projects" / str(rt.workspace).replace("/", "-")

    orden = [
        "python3",
        "-I",
        str(rt.script_dir / "agent_loop_report.py"),
        "--before",
        str(dir_iter / "board-before.json"),
        "--after",
        str(dir_iter / "board-after.json"),
        "--session",
        str(dir_iter / "session.json"),
        "--project-dir",
        str(dir_transcripto),
        "--workspace",
        str(rt.workspace),
        "--handoff-id",
        handoff["doc_id"],
        "--handoff-path",
        handoff["doc_path"],
        "--handoff-before",
        handoff["updated_before"],
        "--handoff-after",
        handoff["updated_after"],
        "--terminal-status",
        "Done",
        "--since",
        inicio,
        "--iteration",
        handoff["iteracion"],
        "--out",
        str(informe),
    ]
    with (dir_iter / "report.txt").open("w", encoding="utf-8") as salida, (
        dir_iter / "report.err"
    ).open("w", encoding="utf-8") as error:
        subprocess.run(orden, stdout=salida, stderr=error, check=False, cwd=rt.workspace)
    if not informe.is_file():
        raise Negativa(f"no pude construir el informe (ver {dir_iter / 'report.err'})")
    return informe


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("ERROR: hace falta el numero de iteracion.", file=sys.stderr)
        return 1
    iteracion = sys.argv[1].strip()

    try:
        rt = init_runtime()
    except ErrorDeConfig as exc:
        print(f"iteracion {iteracion}: ERROR — {exc}", file=sys.stderr)
        return 1

    try:
        return ejecutar(rt, iteracion)
    except Negativa as exc:
        print(f"iteracion {iteracion}: {exc}", file=sys.stderr)
        return 1


def ejecutar(rt: Runtime, iteracion: str) -> int:
    rt.state.mkdir(parents=True, exist_ok=True)
    dir_iter = rt.state / f"iter-{iteracion}"
    dir_iter.mkdir(parents=True, exist_ok=True)
    informe = dir_iter / "report.json"

    # --- la iteracion es idempotente -------------------------------------------------------------
    # Una iteracion puede morir por fuera (una senal, un corte) DESPUES de que la sesion acabara.
    # En ese caso el trabajo ya esta hecho y lo unico que falta es la medida: repetir la sesion
    # gastaria una tarea del tablero para volver a hacer lo mismo. Asi que:
    #
    #   - si ya hay informe, esta iteracion esta medida: se sale con el veredicto guardado;
    #   - si hay sesion pero no informe, la sesion se termino: se mide la que hay, no otra.
    reanuda = False
    if informe.is_file():
        reanuda = True
        print(f"iteracion {iteracion}: ya medida; se reutiliza el informe.", file=sys.stderr)
    elif (dir_iter / "session.json").is_file() and (dir_iter / "session.json").stat().st_size > 0:
        reanuda = True
        print(
            f"iteracion {iteracion}: la sesion ya termino; se mide la que hay en vez de abrir otra.",
            file=sys.stderr,
        )

    # --- una tarea, una sesion: dos sesiones a la vez sobre la misma tarea NO ----------------------
    # Si la pipeline muere por fuera (una senal), la sesion que abrio puede **seguir viva**: el
    # SIGTERM no la alcanza. Entonces un reintento abriria una SEGUNDA sesion sobre la misma tarea
    # y en el mismo worktree: dos agentes peleandose por el mismo codigo, y el segundo acaba
    # sin cerrar nada. Se ha visto exactamente eso.
    #
    # Asi que antes de abrir nada, si la sesion anterior de esta iteracion sigue viva, se espera a
    # que termine (sin sondear) y se mide la suya.
    fichero_pid = dir_iter / "sesion.pid"
    if not reanuda and fichero_pid.is_file():
        try:
            pid_previo = int(fichero_pid.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            pid_previo = 0
        if pid_previo and vivo(pid_previo):
            print(
                f"iteracion {iteracion}: la sesion anterior (pid {pid_previo}) sigue viva; "
                "se espera a que termine.",
                file=sys.stderr,
            )
            espera_min = int(os.environ.get("AGENT_ESPERA_SESION_MIN", ESPERA_SESION_MIN_POR_DEFECTO))
            esperar_a(pid_previo, espera_min * 60)
            if vivo(pid_previo):
                print(
                    f"iteracion {iteracion}: la sesion anterior sigue viva tras la espera; "
                    "no se abre otra.",
                    file=sys.stderr,
                )
                return 2
            print(
                f"iteracion {iteracion}: la sesion anterior termino; se mide la suya.",
                file=sys.stderr,
            )
            reanuda = True

    # --- el prompt se renderiza en CADA iteracion, no una vez por run ------------------------------
    # El prompt lleva dentro el estado del handoff: que se cerro, que queda a medias, que se
    # aprendio. Si se renderizara una sola vez al principio del run, la iteracion 2 y la 3
    # arrancarian con la foto de antes de la iteracion 1, y la cadena de lo aprendido se
    # cortaria justo en el punto que el bucle existe para no cortar.
    #
    # En una iteracion que se reanuda NO se vuelve a renderizar: no hay sesion que abrir, y
    # ademas el renderizado volveria a capturar la marca del handoff DESPUES de que la sesion
    # la cambiara, y la guarda diria que el handoff no se toco cuando si se toco.
    if not reanuda:
        try:
            agent_handoff.preparar(rt)
        except agent_handoff.Negativa as exc:
            print(
                f"iteracion {iteracion}: no pude renderizar el prompt ({exc}).", file=sys.stderr
            )
            return 2

    fichero_handoff = rt.state / "handoff.json"
    if not fichero_handoff.is_file():
        raise Negativa("no hay handoff.json; ejecuta antes agent_handoff.py")
    handoff = json.loads(fichero_handoff.read_text(encoding="utf-8"))

    # La marca del handoff ANTES de la sesion se guarda la primera vez y no se vuelve a tocar:
    # es la linea base de la guarda, y si se recalculara al reanudar ya valdria "despues".
    fichero_antes = dir_iter / "handoff-antes.txt"
    if fichero_antes.is_file():
        handoff["updated_before"] = fichero_antes.read_text(encoding="utf-8")
    else:
        fichero_antes.write_text(handoff.get("updated_before", ""), encoding="utf-8")

    prompt = rt.state / "prompt.md"
    if not prompt.is_file():
        raise Negativa(f"no hay prompt renderizado en {prompt}")

    # El instante de arranque de la sesion se guarda: si la iteracion se reanuda, la ventana de
    # medida tiene que ser la de la sesion real, no la del momento en que se retoma.
    fichero_inicio = dir_iter / "inicio.txt"
    if fichero_inicio.is_file():
        inicio = fichero_inicio.read_text(encoding="utf-8")
    else:
        inicio = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        fichero_inicio.write_text(inicio, encoding="utf-8")

    # El tablero antes: es la linea base contra la que se mide el avance.
    antes = dir_iter / "board-before.json"
    if not antes.is_file():
        resultado = subprocess.run(
            ["backlog", "task", "list", "--json"],
            cwd=rt.home_repo,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        antes.write_text(resultado.stdout, encoding="utf-8")

    if not reanuda:
        print(f"iteracion {iteracion}: launching session in {rt.workspace}", file=sys.stderr)
        codigo = lanzar_sesion(
            rt, prompt, dir_iter / "session.json", dir_iter / "session.err"
        )
        print(
            f"iteracion {iteracion}: la sesion termino con codigo {codigo}", file=sys.stderr
        )

    # El tablero despues.
    resultado = subprocess.run(
        ["backlog", "task", "list", "--json"],
        cwd=rt.home_repo,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    (dir_iter / "board-after.json").write_text(resultado.stdout, encoding="utf-8")

    # La marca del handoff despues: si no cambio, la sesion no dejo estado.
    resultado = subprocess.run(
        ["backlog", "doc", "view", handoff["doc_id"], "--plain"],
        cwd=rt.home_repo,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    handoff["updated_after"] = agent_handoff.marca_de_actualizacion(rt, handoff["doc_id"])
    handoff["iteracion"] = iteracion

    informe = construir_informe(rt, dir_iter, handoff, inicio)

    # Una copia donde la pipeline la archiva como artefacto del run (build/ es gitignored). La
    # pipeline archiva desde su workspace, que es el proyecto (el home repo).
    destino = rt.home_repo / "build/reports/agent-loop"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"iter-{iteracion}.json").write_text(
        informe.read_text(encoding="utf-8"), encoding="utf-8"
    )

    try:
        datos = json.loads(informe.read_text(encoding="utf-8"))
    except ValueError:
        datos = {}
    veredicto = str(datos.get("verdict", ""))
    razon = str(datos.get("reason", ""))

    print(f"iteracion {iteracion}: veredicto {veredicto} — {razon}", file=sys.stderr)
    print((dir_iter / "report.txt").read_text(encoding="utf-8"), end="")

    if veredicto == "PASS":
        return 0
    if veredicto == "FAIL":
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
