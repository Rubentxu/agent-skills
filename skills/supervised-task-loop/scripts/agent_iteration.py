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
import fcntl
import datetime as dt
import shutil
import uuid
import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_handoff  # noqa: E402
import agent_preflight  # noqa: E402
import agent_loop_report as report  # noqa: E402
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


def process_identity(pid):
    raw=Path(f"/proc/{pid}/stat").read_text()
    tail=raw[raw.rfind(")")+1:].split()
    return {"pid":pid,"bootId":Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "startTicks":int(tail[19]),"state":tail[0]}

def previous_process(d):
    pin=d/"sesion-identity.json"
    if pin.is_file():
        try:
            p=json.loads(pin.read_text())
            if type(p["pid"]) is not int or p["pid"]<1: return "unknown",None
            if p["bootId"]!=Path("/proc/sys/kernel/random/boot_id").read_text().strip(): return "stopped",p["pid"]
            try: actual=process_identity(p["pid"])
            except FileNotFoundError: return "stopped",p["pid"]
            if (p["bootId"],p["startTicks"])!=(actual["bootId"],actual["startTicks"]) or actual["state"] in ("Z","X"):
                return "stopped",p["pid"]
            return "running",p["pid"]
        except (OSError,ValueError,KeyError,IndexError,TypeError): return "unknown",None
    legacy=d/"sesion.pid"
    if legacy.is_file():
        try:
            pid=int(legacy.read_text().strip())
            if pid<1:return "unknown",None
            return ("unknown" if vivo(pid) else "stopped"),pid
        except (ValueError,OSError):return "unknown",None
    if (d/"launch-error.json").is_file():return "never-launched",None
    if any((d/n).exists() for n in ("launch-intent.json","session.json","report.json")):return "unknown",None
    return "never-launched",None

def write_json(p,v):
    tmp=p.with_name(p.name+".tmp-"+uuid.uuid4().hex)
    try:
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(v,f,ensure_ascii=False)
            f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        tmp.unlink(missing_ok=True)

def deadline_prompt(prompt, seconds):
    now=dt.datetime.now(dt.timezone.utc)
    hard=now+dt.timedelta(seconds=seconds)
    soft=hard-dt.timedelta(seconds=min(300,max(10,seconds//5)))
    return (prompt+"\n\n## Limite operativo de esta sesion\n"
            f"Soft deadline (UTC): {soft.isoformat()}. Deja de iniciar trabajo, guarda checkpoint/handoff y termina.\n"
            f"Hard deadline (UTC): {hard.isoformat()}. No inicies operaciones que no puedas finalizar o transferir de forma segura.\n"),soft.isoformat(),hard.isoformat()

def lanzar_sesion(rt: Runtime, prompt: Path, destino_sesion: Path, destino_error: Path, seconds: int) -> int:
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

    if seconds<20:
        raise Negativa("presupuesto insuficiente para lanzar sesion")
    rendered,soft,hard=deadline_prompt(prompt.read_text(encoding="utf-8"),seconds)
    d=destino_sesion.parent
    (d/"prompt-launch.md").write_text(rendered,encoding="utf-8")
    write_json(d/"deadline.json",{"soft":soft,"hard":hard,"seconds":seconds})
    # A separate timeout process survives death of the PipelineK/Python wrapper.
    orden = ["timeout","--signal=TERM","--kill-after=15s",str(seconds)+"s","claude"]
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
        rendered,
        "--output-format",
        "json",
    ]

    write_json(d/"launch-intent.json",{"deadline":hard})
    with destino_sesion.open("w", encoding="utf-8") as salida, destino_error.open(
        "w", encoding="utf-8"
    ) as error:
        try:
            proceso = subprocess.Popen(
                orden, cwd=rt.workspace, stdout=salida, stderr=error,
                stdin=subprocess.DEVNULL, start_new_session=True,
            )
        except OSError:
            write_json(d/"launch-error.json",{"state":"never-launched"})
            return 127
        try:
            write_json(d/"sesion-identity.json",process_identity(proceso.pid))
        except (OSError,ValueError,IndexError):
            pass # cannot recover identity automatically; launch intent survives
        # El PID de la sesion se guarda: si la pipeline muere por fuera, la sesion puede
        # seguir viva, y un reintento tiene que reconocerla en vez de abrir otra encima.
        (destino_sesion.parent / "sesion.pid").write_text(str(proceso.pid), encoding="utf-8")
        code=proceso.wait()
        write_json(d/"completion.json",{"exitCode":code,"finishedAt":dt.datetime.now(dt.timezone.utc).isoformat()})
        return code


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
    completion=report.leer_json(str(dir_iter/"completion.json"))
    if type(completion.get("exitCode")) is int:
        orden.extend(["--exit-code",str(completion["exitCode"])])
    with (dir_iter / "report.txt").open("w", encoding="utf-8") as salida, (
        dir_iter / "report.err"
    ).open("w", encoding="utf-8") as error:
        result=subprocess.run(orden, stdout=salida, stderr=error, check=False, cwd=rt.workspace)
    if result.returncode!=0:
        raise Negativa("no pude construir el informe; revisar report.err")
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


def snapshot(rt, path):
    result=subprocess.run(["backlog","task","list","--json"],cwd=rt.home_repo,capture_output=True,text=True,timeout=120,check=False)
    try:
        value=json.loads(result.stdout)
        if result.returncode or not isinstance(value,dict) or not isinstance(value.get("tasks"),list):
            raise ValueError()
    except ValueError:
        raise Negativa("snapshot del tablero invalido; no medir")
    write_json(path,value)

def valid_report(d,iteration):
    value=report.leer_json(str(d/"report.json"))
    session=report.leer_json(str(d/"session.json"))
    return (value.get("kind")=="agent-loop-report" and str(value.get("iteration"))==iteration
            and value.get("verdict") in ("PASS","FAIL","BLOCKED")
            and report.estado_sesion(session)=="COMPLETED"
            and isinstance(value.get("session"),dict) and value["session"].get("session_id")==session.get("session_id"))

def finish_report(rt,d,iteration):
    value=report.leer_json(str(d/"report.json"))
    if not value:
        raise Negativa("informe invalido")
    dest=rt.home_repo/"build/reports/agent-loop"
    dest.mkdir(parents=True,exist_ok=True)
    # Existing report is immutable; copy rather than remeasure.
    shutil.copyfile(d/"report.json",dest/f"iter-{iteration}.json")
    print(f"iteracion {iteration}: veredicto {value.get('verdict')} — {value.get('reason')}",file=sys.stderr)
    print(json.dumps(value,ensure_ascii=False,indent=2))
    return {"PASS":0,"FAIL":3}.get(value.get("verdict"),2)

def archive_attempt(d, observation):
    archive=d/"attempts"/uuid.uuid4().hex
    archive.mkdir(parents=True,mode=0o700)
    for p in d.iterdir():
        if p.name!="attempts" and p.is_file():
            p.rename(archive/p.name)
    write_json(archive/"recovery.json",{"observationRef":observation})
    return archive

def recovery_ref(iteration):
    # Explicit per-iteration attestation after confirming old host/process and
    # all dependent operations. Not a force flag; never bypass a live process.
    if os.environ.get("AGENT_RECOVERY_ITERATION")!=iteration:return None
    ref=os.environ.get("AGENT_RECOVERY_REF","").strip()
    return ref if ref and len(ref)<=1024 else None

def ejecutar(rt: Runtime, iteracion: str) -> int:
    if not iteracion.isascii() or not iteracion.isdigit() or len(iteracion)>8:
        raise Negativa("numero de iteracion invalido")
    rt.state.mkdir(parents=True,exist_ok=True)
    fd=os.open(rt.state/"iteration.lock",os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return 2
        return ejecutar_bajo_lock(rt,iteracion)
    finally: os.close(fd)

def ejecutar_bajo_lock(rt: Runtime, iteracion: str) -> int:
    begin=time.monotonic()
    d=rt.state/f"iter-{iteracion}"
    d.mkdir(parents=True,exist_ok=True)
    process,pid=previous_process(d)
    if process=="running":
        print(f"iteracion {iteracion}: esperando sesion atribuida existente",file=sys.stderr)
        wait=min(int(os.environ.get("AGENT_ESPERA_SESION_MIN",ESPERA_SESION_MIN_POR_DEFECTO))*60,max(1,rt.task_timeout_min*60-45))
        esperar_a(pid,wait)
        process,pid=previous_process(d)
        if process=="running":
            return 2
    # A PID without its start identity must not authorize a second writer.
    if process=="unknown" and pid and vivo(pid):
        print("sesion previa sin identidad comprobable; reconciliar antes de repetir",file=sys.stderr)
        return 2
    if valid_report(d,iteracion) and process!="running":
        return finish_report(rt,d,iteracion)
    session=report.leer_json(str(d/"session.json"))
    status=report.estado_sesion(session)
    recovered=recovery_ref(iteracion)
    attempted=any((d/n).exists() for n in ("session.json","launch-intent.json","report.json","sesion.pid"))
    reanuda=status=="COMPLETED"
    if reanuda and process=="unknown" and not recovered:
        print("resultado existente sin identidad de proceso; reconciliar",file=sys.stderr)
        return 2
    if reanuda and not (d/"board-after.json").is_file() and not recovered and not (d/"completion.json").is_file():
        print("sesion finalizada sin snapshot final atribuible; reconciliar",file=sys.stderr)
        return 2
    if attempted and not reanuda:
        if process!="never-launched" and not recovered:
            print(f"sesion NO medida ({status}); confirmar proceso y recursos y suministrar AGENT_RECOVERY_ITERATION/REF; no se abre otra",file=sys.stderr)
            return 2
        archive_attempt(d,recovered or "launch:never-launched")
    # Do not start a different iteration over an unresolved earlier/later one.
    if not reanuda:
        for other in rt.state.glob("iter-*"):
            if other==d or not other.is_dir():continue
            if any((other/n).exists() for n in ("launch-intent.json","session.json","sesion.pid")) and not valid_report(other,other.name[5:]):
                print("otra iteracion no reconciliada: "+other.name,file=sys.stderr)
                return 2
        try:
            agent_preflight.comprobar_perfil(rt)
            handoff=agent_handoff.preparar(rt)
        except (agent_preflight.Fallo,agent_handoff.Negativa) as e:
            print("no se inicia la sesion: "+str(e),file=sys.stderr)
            return 2
        write_json(d/"handoff.json",handoff)
        prompt=d/"prompt.md"
        shutil.copyfile(rt.state/"prompt.md",prompt)
        snapshot(rt,d/"board-before.json")
        inicio=dt.datetime.now(dt.timezone.utc).isoformat()
        (d/"inicio.txt").write_text(inicio,encoding="utf-8")
        remaining=int(rt.task_timeout_min*60-(time.monotonic()-begin))-45
        if remaining<20:
            print("presupuesto agotado antes de lanzar",file=sys.stderr)
            return 2
        code=lanzar_sesion(rt,prompt,d/"session.json",d/"session.err",remaining)
        print(f"iteracion {iteracion}: fin de sesion rc={code}",file=sys.stderr)
        snapshot(rt,d/"board-after.json")
        handoff["updated_after"]=agent_handoff.marca_de_actualizacion(rt,handoff["doc_id"])
        write_json(d/"handoff.json",handoff)
    else:
        # Legacy recovery needs the original task baseline; never replace it
        # using the current global handoff.
        handoff=report.leer_json(str(d/"handoff.json"))
        if not handoff:
            if not recovered:
                print("handoff original no disponible; reconciliar",file=sys.stderr)
                return 2
            handoff=report.leer_json(str(rt.state/"handoff.json"))
            if (d/"handoff-antes.txt").is_file():
                handoff["updated_before"]=(d/"handoff-antes.txt").read_text()
        if not (d/"board-before.json").is_file() or not (d/"inicio.txt").is_file() or not handoff:
            raise Negativa("baseline original incompleto")
        inicio=(d/"inicio.txt").read_text()
        if not (d/"board-after.json").is_file():
            snapshot(rt,d/"board-after.json")
        if "updated_after" not in handoff:
            handoff["updated_after"]=agent_handoff.marca_de_actualizacion(rt,handoff["doc_id"])
        write_json(d/"handoff.json",handoff)
    handoff["iteracion"]=iteracion
    construir_informe(rt,d,handoff,inicio)
    return finish_report(rt,d,iteracion)

if __name__ == "__main__":
    raise SystemExit(main())
