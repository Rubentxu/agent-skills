#!/usr/bin/env python3 -I
"""agent-loop-report.py — lo que una iteracion del bucle entrega, medido en numeros.

QUE ES

El informe de una iteracion del bucle Ralph. No juzga el codigo: mide. Su trabajo es que
el avance se vea como un numero almacenado y no como una sensacion, y sobre todo que el
regreso de la sesion se pueda comparar con la linea base.

LA GUARDA DE REGRESION

Dos metricas existen para que el problema medido no vuelva:

    read_ratio   Read frente a Bash-que-lee. La linea base es 1:23 (pipelinek) y 1:42
                 (forgejo): el agente exploraba el codigo con `sed`/`grep` en vez de con
                 `Read`, y por eso el contexto crecia hasta compactar.
    poll_calls   Bash que sondea. La linea base son 2032 llamadas en una sesion de 20 h,
                 con 5,2 h de las 8,5 h de shell gastadas esperando.

Un informe que no los improve no es un informe neutro: es la prueba de que el bucle no
ha arreglado lo que decia arreglar.

CÓDIGOS DE SALIDA

    0  se produjo el informe
    1  mal uso
    2  no pude medir
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import re
import subprocess
import sys

# Codigo de salida del veredicto (el vocabulario del workspace).
PASS, FAIL, BLOCKED, NOT_RUN = "PASS", "FAIL", "BLOCKED", "NOT_RUN"

# Extensiones que cuentan como codigo. Un cambio que solo toca .md no es una entrega.
CODIGO = {".kt", ".kts", ".java", ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs",
          ".sh", ".sql", ".yaml", ".yml", ".gradle", ".tf", ".rb", ".cs"}

# Un Bash que lee CODIGO en vez de usar la herramienta Read.
#
# No se cuenta leer el log de la propia prueba: eso es lo que hay que hacer, y contarlo como
# falta de disciplina seria medir la cosa equivocada. Lo que se cuenta es explorar codigo
# con la shell —un `sed -n`, un `grep` sobre un fuente— donde la herramienta Read daria lo
# mismo con la estructura del fichero y sin llenar el contexto de texto plano.
CODIGO_FICHERO = re.compile(
    r"\S+\.(kt|kts|java|ts|tsx|js|jsx|py|go|rs|sh|gradle|toml|ya?ml|json|xml|sql|tf|properties)\b",
    re.IGNORECASE,
)
LECTURA_BASH = re.compile(
    r"(^|\s|\||;|&&)(sed\s+-|cat\s+|head\s|tail\s|less\s|more\s|awk\s|grep\s+)",
    re.IGNORECASE,
)
# Un log o un veredicto no es codigo: leerlos es correcto.
NO_ES_CODIGO = re.compile(r"(/tmp/|\.log\b|\.verdict\b|\.out\b|\.err\b|/proc/|/sys/)", re.IGNORECASE)


def bash_que_lee_codigo(comando: str) -> bool:
    """True si el comando explora codigo con la shell en vez de con la herramienta Read."""
    if not LECTURA_BASH.search(comando):
        return False
    if not CODIGO_FICHERO.search(comando):
        return False
    return not NO_ES_CODIGO.search(comando)

# QUE ES UN SONDEO
#
# Lo que quema el contexto no es esperar: es **esperar y volver a comprobar**. Un bucle que
# repite la comprobacion veinte veces llena la sesion de salidas de shell que no aportan nada,
# y es exactamente el patron que las sesiones del 18-nov tenian (2.032 sondeos en una sesion
# de 20 h) y que el prompt de este bucle prohibe.
#
# Por eso el sondeo se define por su FORMA, no por una palabra suelta:
#
#   - un bucle (`until`, `while`, `for ... in`) que ademas espera (`sleep N`) -> sondeo;
#   - `watch` o `tail -f` -> sondeo (esperan y vuelven a mirar);
#   - un `sleep N` suelto -> NO es sondeo: es una pausa, y no repite nada;
#   - un `while read` de un pipe -> NO es sondeo: consume la entrada una vez;
#   - un `grep -c` sobre un log -> NO es sondeo: cuenta una vez.
#
# Las pausas sueltas se cuentan aparte (`sleep_calls`), para que una regresion visible —volver a
# lanzar cinco veces la misma medicion— siga viéndose sin ensuciar la guarda.
SONDEO_ESPERA = re.compile(r"(\bsleep\s+\d+)|(\btail\s+-f\b)|(\bwatch\b)", re.IGNORECASE)
SONDEO_BUCLE = re.compile(r"(^\s*|\|\s*|;\s*|&&?\s*|\(\s*)(until|while)\b", re.IGNORECASE)
SONDEO_FOR = re.compile(r"\bfor\b[^\n|;]*\bin\b", re.IGNORECASE)
# Una espera suelta: pausa de una vez, sin bucle.
PAUSA = re.compile(r"\bsleep\s+\d+", re.IGNORECASE)


def es_sondeo(comando: str) -> bool:
    """True si el comando espera y vuelve a comprobar, que es lo que quema el contexto."""
    if re.search(r"(\btail\s+-f\b)|(^\s*watch\s)", comando, re.IGNORECASE):
        return True
    if SONDEO_ESPERA.search(comando) and (SONDEO_BUCLE.search(comando) or SONDEO_FOR.search(comando)):
        return True
    return False


# --------------------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------------------

def ahora_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parsear_hora(texto: str | None) -> dt.datetime | None:
    if not texto:
        return None
    try:
        return dt.datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None


def ejecutar(argv: list[str], cwd: str | None = None) -> tuple[int, str]:
    """Ejecuta un comando y devuelve (codigo, salida). Nunca lanza excepcion."""
    try:
        hecho = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=120, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return hecho.returncode, hecho.stdout


def leer_json(ruta: str) -> dict:
    try:
        with open(ruta, encoding="utf-8", errors="replace") as flujo:
            datos = json.load(flujo)
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


# --------------------------------------------------------------------------------------
# El tablero: la unica autoridad. El progreso se ve en su diff.
# --------------------------------------------------------------------------------------

def estados_del_tabulario(documento: dict) -> dict[str, dict]:
    tareas = documento.get("tasks")
    if not isinstance(tareas, list):
        return {}
    estados: dict[str, dict] = {}
    for tarea in tareas:
        if not isinstance(tarea, dict):
            continue
        identificador = str(tarea.get("id", ""))
        if not identificador:
            continue
        estados[identificador] = {
            "id": identificador,
            "title": str(tarea.get("title", "")),
            "status": str(tarea.get("status", "")),
            "ac_completados": tarea.get("acceptanceCriteriaCompleted"),
            "ac_total": tarea.get("acceptanceCriteriaCount"),
            "labels": tarea.get("labels") or [],
        }
    return estados


def diff_del_tabulario(antes: dict[str, dict], despues: dict[str, dict],
                       terminal: set[str]) -> dict:
    """Que cambio en el tablero: que tarea se abrio, que tarea se cerro, que avanzo."""
    abiertas: list[dict] = []
    cerradas: list[dict] = []
    movidas: list[dict] = []

    for identificador, ahora in despues.items():
        antes_del = antes.get(identificador)
        if antes_del is None:
            continue
        if antes_del["status"] == ahora["status"]:
            # La tarea no cambio de estado, pero puede haber avanzado en sus AC.
            if (antes_del.get("ac_completados") != ahora.get("ac_completados")
                    and ahora.get("ac_completados") is not None):
                movidas.append({
                    "id": identificador,
                    "title": ahora["title"],
                    "ac_antes": antes_del.get("ac_completados"),
                    "ac_despues": ahora.get("ac_completados"),
                    "ac_total": ahora.get("ac_total"),
                })
            continue
        movimiento = {
            "id": identificador,
            "title": ahora["title"],
            "de": antes_del["status"],
            "a": ahora["status"],
            "ac_completados": ahora.get("ac_completados"),
            "ac_total": ahora.get("ac_total"),
        }
        if ahora["status"] in terminal:
            cerradas.append(movimiento)
        else:
            abiertas.append(movimiento)

    return {
        "task_closed": cerradas[0] if cerradas else None,
        "task_started": abiertas[0] if abiertas else None,
        "tasks_closed": cerradas,
        "tasks_started": abiertas,
        "tasks_advanced": movidas,
    }


# --------------------------------------------------------------------------------------
# La sesion: lo que el agente hizo de verdad
# --------------------------------------------------------------------------------------

def transcript_de(proyecto: str, session_id: str) -> str:
    """Ruta del transcript de la sesion, o cadena vacia si no se encuentra."""
    if not session_id or not proyecto:
        return ""
    base = os.path.join(proyecto, session_id)
    if os.path.isfile(base + ".jsonl"):
        return base + ".jsonl"
    if os.path.isdir(base):
        principal = os.path.join(base, "main.jsonl")
        if os.path.isfile(principal):
            return principal
    return ""


def medir_transcript(ruta: str) -> dict:
    """Cuenta lo que la sesion leyo y sondeo. Devuelve {} si no hay transcript."""
    if not ruta or not os.path.isfile(ruta):
        return {}

    herramientas = collections.Counter()
    bash_lectura = 0
    sondeos = 0
    pausas = 0
    subagentes = 0
    goldfish = False
    contexto_maximo = 0
    turnos = 0

    try:
        with open(ruta, encoding="utf-8", errors="replace") as flujo:
            for linea in flujo:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    registro = json.loads(linea)
                except ValueError:
                    continue
                if not isinstance(registro, dict):
                    continue
                if registro.get("type") != "assistant":
                    continue
                turnos += 1
                mensaje = registro.get("message") or {}
                uso = mensaje.get("usage") or {}
                leidos = uso.get("cache_read_input_tokens") or 0
                contexto_maximo = max(contexto_maximo, leidos)
                contenido = mensaje.get("content")
                if not isinstance(contenido, list):
                    continue
                for bloque in contenido:
                    if not isinstance(bloque, dict) or bloque.get("type") != "tool_use":
                        continue
                    nombre = str(bloque.get("name", ""))
                    herramientas[nombre] += 1
                    entrada = bloque.get("input") or {}
                    if nombre == "Bash":
                        comando = str(entrada.get("command", ""))
                        if bash_que_lee_codigo(comando):
                            bash_lectura += 1
                        if es_sondeo(comando):
                            sondeos += 1
                        if PAUSA.search(comando):
                            pausas += 1
                    elif nombre in ("Agent", "Task"):
                        subagentes += 1
                        if "goldfish" in json.dumps(entrada).lower():
                            goldfish = True
    except OSError:
        return {}

    lecturas = herramientas.get("Read", 0)
    bash_total = herramientas.get("Bash", 0)
    ratio = None
    if lecturas or bash_total:
        # Se mide el cociente de lecturas de verdad (Read) frente a lecturas hechas con
        # la shell. Un numero alto significa que el agente se lee el codigo por la shell.
        divisor = lecturas + bash_lectura
        ratio = round(lecturas / divisor, 3) if divisor else None

    return {
        "transcript": ruta,
        "assistant_turns": turnos,
        "read_calls": lecturas,
        "bash_calls": bash_total,
        "bash_read_calls": bash_lectura,
        "read_ratio": ratio,
        "poll_calls": sondeos,
        "sleep_calls": pausas,
        "subagent_count": subagentes,
        "goldfish_review_done": goldfish,
        "context_tokens_max": contexto_maximo,
        "tools": dict(herramientas.most_common(12)),
    }


# --------------------------------------------------------------------------------------
# Git y GitHub: que toco la tarea y como se integro
# --------------------------------------------------------------------------------------

def repos_del_workspace(raiz: str) -> list[str]:
    """Los repos del workspace. Un worktree tiene .git como fichero, no como carpeta."""
    repos = []
    try:
        entradas = sorted(os.listdir(raiz))
    except OSError:
        return repos
    for entrada in entradas:
        ruta = os.path.join(raiz, entrada)
        if os.path.exists(os.path.join(ruta, ".git")):
            repos.append(ruta)
    return repos


def commits_de_la_sesion(repo: str, desde: dt.datetime | None) -> list[dict]:
    """Los commits que el agente creo durante la sesion."""
    if desde is None:
        return []
    marca = desde.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    codigo, salida = ejecutar(
        ["git", "-C", repo, "log", f"--since={marca}", "--pretty=format:%H\t%s", "--name-only"]
    )
    if codigo != 0:
        return []
    commits: list[dict] = []
    actual: dict | None = None
    for linea in salida.splitlines():
        if "\t" in linea and re.match(r"^[0-9a-f]{40}", linea):
            sha, _, asunto = linea.partition("\t")
            actual = {"sha": sha, "subject": asunto, "files": []}
            commits.append(actual)
        elif linea.strip() and actual is not None:
            actual["files"].append(linea.strip())
    return commits


def cambios_desde_ficheros(ficheros: list[str], commits: int, sha: str | None,
                           asuntos: list[str]) -> dict:
    """La forma de un cambio, sea venga de git o de GitHub."""
    cuenta: collections.Counter = collections.Counter(ficheros)
    total = len(ficheros)
    extensiones = collections.Counter(
        os.path.splitext(nombre)[1].lower() for nombre in cuenta
    )
    return {
        "commits": commits,
        "files_changed": len(cuenta),
        "files_touched": total,
        "by_ext": dict(extensiones.most_common(10)),
        "code_changed": any(extension in CODIGO for extension in extensiones),
        "only_docs": bool(extensiones) and not any(
            extension in CODIGO for extension in extensiones
        ),
        "sha": sha,
        "commit_subjects": asuntos[:5],
    }


def cambios_de_la_sesion(repo: str, desde: dt.datetime | None) -> dict:
    commits = commits_de_la_sesion(repo, desde)
    ficheros = [nombre for commit in commits for nombre in commit["files"]]
    return cambios_desde_ficheros(
        ficheros,
        len(commits),
        commits[0]["sha"] if commits else None,
        [c["subject"] for c in commits],
    )


def cambios_del_pr(repo: str, numero: int) -> dict:
    """Lo que toco un PR, segun GitHub.

    **Por que no basta con el clone local.** El agente fusiona por la API y el `main` local no
    se mueve: `git log --since` entonces no ve el merge y el informe dice "0 ficheros" de una
    entrega que existe. Y la rama puede estar ya borrada, que es justo lo que el prompt pide.
    El PR es el registro que sobrevive a las dos cosas.
    """
    codigo, salida = ejecutar(
        ["gh", "pr", "view", str(numero), "--json", "files,commits,mergeCommit"],
        cwd=repo,
    )
    if codigo != 0:
        return {}
    try:
        datos = json.loads(salida or "{}")
    except ValueError:
        return {}
    ficheros = [str(f.get("path", "")) for f in datos.get("files", []) if f.get("path")]
    if not ficheros:
        return {}
    commits = datos.get("commits") or []
    asunto = ""
    if commits and isinstance(commits[0], dict):
        asunto = str(commits[0].get("messageHeadline", ""))
    sha = (datos.get("mergeCommit") or {}).get("oid")
    return cambios_desde_ficheros(ficheros, len(commits), sha, [asunto] if asunto else [])


def prs_merged_desde(repo: str, desde: dt.datetime | None) -> list[dict]:
    """Los PR que se fusionaron en la ventana de la sesion.

    `gh` deduce el repositorio del cwd, asi que se ejecuta dentro del repo: asking por un
    repositorio que no es el suyo devuelve la lista de otro.
    """
    if desde is None:
        return []
    codigo, salida = ejecutar(
        ["gh", "pr", "list", "--state", "merged", "--limit", "30",
         "--json", "number,url,title,headRefName,mergedAt"],
        cwd=repo,
    )
    if codigo != 0:
        return []
    try:
        prs = json.loads(salida or "[]")
    except ValueError:
        return []
    dentro = []
    for pr in prs if isinstance(prs, list) else []:
        momento = parsear_hora(str(pr.get("mergedAt", "")))
        if momento is None:
            continue
        if momento >= desde.astimezone(dt.timezone.utc):
            dentro.append(pr)
    return dentro


def rama_limpia(repo: str, rama: str) -> bool:
    """La rama ya no existe ni en local ni en remoto."""
    if not rama:
        return False
    codigo, salida = ejecutar(["git", "-C", repo, "branch", "--list", rama])
    if codigo == 0 and salida.strip():
        return False
    codigo, salida = ejecutar(["git", "-C", repo, "ls-remote", "--heads", "origin", rama])
    if codigo == 0 and salida.strip():
        return False
    return True


def id_de_tarea_de_la_rama(rama: str) -> str | None:
    coincidencia = re.search(r"(pkh[-_]?\d{2,4})", rama, re.IGNORECASE)
    if not coincidencia:
        return None
    digitos = re.sub(r"\D", "", coincidencia.group(1))
    return f"PKH-{digitos.zfill(3)}"


# --------------------------------------------------------------------------------------
# Veredicto
# --------------------------------------------------------------------------------------

def estado_sesion(session: dict) -> str:
    if not isinstance(session, dict) or not session:
        return "MISSING_OR_INVALID"
    turns = session.get("num_turns")
    if type(turns) is int and turns == 0:
        return "STARTUP_FAILED" if session.get("is_error") is True else "NO_TURNS"
    if type(turns) is int and turns > 0 and isinstance(session.get("session_id"), str) and session["session_id"].strip() and type(session.get("is_error")) is bool:
        return "COMPLETED"
    return "INCOMPLETE"

def extracto_resultado(session: dict) -> str:
    result = session.get("result")
    if not isinstance(result, str):
        return ""
    # Best effort, not a general secret scanner. Never include stderr or tool arguments.
    result = re.sub(r"(?i)\b(bearer|basic)\s+\S+", r"\1 [REDACTED]", result)
    result = re.sub(r"(?i)\b(token|password|api[_-]?key|secret|authorization|credential)s?\s*[:=]\s*\S+", r"\1=[REDACTED]", result)
    result = re.sub(r"(?i)\b(?:sk-[A-Za-z0-9_-]+|gh[pousr]_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+)", "[REDACTED]", result)
    result = re.sub(r"(?i)(https?://)[^/\s@]+@", r"\1[REDACTED]@", result)
    lines = [re.sub(r"[\x00-\x1f\x7f]", " ", x).strip() for x in result.splitlines() if x.strip()]
    # Do not copy the whole response to archived reports.
    return lines[-1][:240] if lines else ""

def diagnostico(session: dict, tablero: dict, handoff: dict, verdict: str, exit_code=None) -> dict:
    result = str(session.get("result") or "")
    low = result.lower()
    if exit_code in (124, 137):
        category, action = "DEADLINE_OR_SIGNAL", "RECONCILE_OPERATIONS"
    elif re.search(r"unrecognized_model|model_not_found|unknown model", low):
        category, action = "MODEL_UNAVAILABLE", "RECHECK_PROVIDER"
    elif re.search(r"not logged in|authentication_error|unauthorized|invalid.api.key", low):
        category, action = "AUTH_FAILED", "RECHECK_AUTH"
    elif estado_sesion(session) != "COMPLETED":
        category, action = "STARTUP_OR_INCOMPLETE", "RECONCILE_OPERATIONS"
    elif verdict == PASS:
        category, action = "DELIVERED", "CONTINUE"
    elif tablero.get("task_closed") and not handoff.get("updated"):
        category, action = "HANDOFF_MISSING", "RECOVER_HANDOFF"
    elif verdict == BLOCKED:
        category, action = "REPORTED_BLOCKER", "INVESTIGATE"
    else:
        category, action = "UNCLASSIFIED", "INSPECT_RESULT"
    return {"category": category, "nextAction": action, "lastResultLine": extracto_resultado(session),
            "confidence": "suspected" if category != "DELIVERED" else "observed",
            "sessionState": estado_sesion(session), "exitCode": exit_code,
            "retryAuthorized": False}

def decidir_veredicto(session: dict, tablero: dict, handoff: dict,
                       sesion_arrancada: bool) -> tuple[str, str]:
    """(veredicto, razon). El veredicto usa el vocabulario cerrado del workspace."""
    if not sesion_arrancada:
        return NOT_RUN, "la sesion no llego a arrancar"

    error = bool(session.get("is_error"))
    resultado = str(session.get("result", "")) or ""
    hay_cierre = tablero.get("task_closed") is not None
    handoff_ok = bool(handoff.get("updated"))

    if not hay_cierre and re.search(r"\b(blocked|bloquead|no puedo|blocked)\b", resultado, re.I):
        return BLOCKED, "el agente declaro que no puede avanzar"
    if error:
        return FAIL, f"la sesion termino en error: {extracto_resultado(session)}"
    if hay_cierre and not handoff_ok:
        # La guarda: una tarea cerrada sin handoff es una entrega que la siguiente sesion
        # no puede continuar. Falla aunque el codigo este perfecto.
        return FAIL, "la tarea se cerro pero el handoff no se actualizo"
    if hay_cierre and handoff_ok:
        return PASS, "tarea cerrada y handoff actualizado"
    if not hay_cierre:
        return FAIL, "la sesion termino sin cerrar ninguna tarea" + (": " + extracto_resultado(session) if extracto_resultado(session) else "")
    return NOT_RUN, "no se pudo determinar el veredicto"


# --------------------------------------------------------------------------------------
# Informe
# --------------------------------------------------------------------------------------

def elegir_pr_de_la_tarea(prs: list[dict], id_tarea: str | None) -> dict | None:
    """El PR de la iteracion: el de la tarea que el tablero dice que se cerro.

    En la ventana puede haber otros PR fusionados —otra sesion trabajando en paralelo en el
    mismo repo—, y el que se reporta y el que se miden tienen que ser el mismo.
    """
    if not id_tarea:
        return None
    candidatos = [p for p in prs if p.get("task_id") == id_tarea]
    if not candidatos:
        return None
    return max(candidatos, key=lambda p: str(p.get("mergedAt") or ""))


def construir(args) -> dict:
    antes = estados_del_tabulario(leer_json(args.before))
    despues = estados_del_tabulario(leer_json(args.after))
    terminal = set(args.terminal_status or ["Done"])
    tablero = diff_del_tabulario(antes, despues, terminal)

    session = leer_json(args.session)
    sesion_arrancada = estado_sesion(session) == "COMPLETED"

    desde = parsear_hora(session.get("startedAt")) or parsear_hora(args.since)

    # Handoff: se compara la marca de tiempo del documento antes y despues de la sesion.
    handoff = {"id": args.handoff_id, "path": args.handoff_path,
               "updated": bool(args.handoff_after and args.handoff_after != args.handoff_before)}

    # Git y GitHub.
    repos = [args.repo] if args.repo else repos_del_workspace(args.workspace)
    cambios_por_repo: dict[str, dict] = {}
    prs: list[dict] = []
    for repo in repos:
        if not os.path.exists(os.path.join(repo, ".git")):
            continue
        cambio = cambios_de_la_sesion(repo, desde)
        if cambio["files_changed"] or cambio["commits"]:
            cambios_por_repo[os.path.basename(repo)] = cambio
        for pr in prs_merged_desde(repo, desde):
            enriched = dict(pr)
            enriched["repo"] = os.path.basename(repo)
            enriched["ruta"] = repo
            enriched["task_id"] = id_de_tarea_de_la_rama(str(pr.get("headRefName", "")))
            enriched["branch_cleaned"] = rama_limpia(repo, str(pr.get("headRefName", "")))
            prs.append(enriched)

    # El PR de la iteracion lo fija la TAREA que el tablero dice que se cerro: su rama lleva
    # su id. En la ventana puede haber otros PR fusionados —de otra sesion que trabaja en
    # paralelo en el mismo repo—, y esos no son de esta iteracion.
    id_tarea = (tablero.get("task_closed") or {}).get("id")
    pr_de_la_tarea = elegir_pr_de_la_tarea(prs, id_tarea)
    pr_principal = pr_de_la_tarea or (prs[0] if prs else None)

    # El PR manda sobre el clone local: el agente fusiona por la API y el `main` local no se
    # mueve, asi que el diff del arbol puede decir "0 ficheros" de una entrega que existe.
    # Y manda el PR de la tarea: el de otro, contaria ficheros que no son de esta entrega.
    if pr_principal is not None:
        cambio_pr = cambios_del_pr(str(pr_principal.get("ruta", "")),
                                   int(pr_principal.get("number") or 0))
        if cambio_pr.get("files_changed"):
            cambios_por_repo[str(pr_principal.get("repo"))] = cambio_pr

    todos_los_cambios = list(cambios_por_repo.values())
    cambios = {
        "repos": cambios_por_repo,
        "files_changed": sum(c["files_changed"] for c in todos_los_cambios),
        "commits": sum(c["commits"] for c in todos_los_cambios),
        "code_changed": any(c["code_changed"] for c in todos_los_cambios),
        "only_docs": bool(todos_los_cambios) and all(c["only_docs"] for c in todos_los_cambios),
    }

    if pr_principal is not None:
        pr = {
            "url": pr_principal.get("url"),
            "number": pr_principal.get("number"),
            "title": pr_principal.get("title"),
            "repo": pr_principal.get("repo"),
            "task_id": pr_principal.get("task_id"),
            "merged": True,
            "branch_cleaned": pr_principal.get("branch_cleaned"),
            # `count` son los PR fusionados en la ventana, que pueden incluir los de otra
            # sesion trabajando en paralelo en el mismo repo: por eso va separado del PR de
            # la tarea, que es el que manda.
            "count": len(prs),
            "prs_en_la_ventana": [
                {"number": p.get("number"), "task_id": p.get("task_id"),
                 "merged_at": p.get("mergedAt")}
                for p in prs
            ],
            "es_el_de_la_tarea": pr_de_la_tarea is not None,
        }
    else:
        pr = {"url": None, "merged": False, "branch_cleaned": None, "count": 0,
              "prs_en_la_ventana": [], "es_el_de_la_tarea": False}

    uso = session.get("usage") or {}
    subagentes = session.get("subagent_stats") or {}
    sesion = {
        "session_id": session.get("session_id"),
        "is_error": bool(session.get("is_error")),
        "result": extracto_resultado(session),
        "state": estado_sesion(session),
        "duration_s": session.get("duration_ms", 0) / 1000 if session.get("duration_ms") else None,
        "duration_api_s": session.get("duration_api_ms", 0) / 1000
        if session.get("duration_api_ms") else None,
        "num_turns": session.get("num_turns"),
        "total_cost_usd": session.get("total_cost_usd"),
        "tokens_in": uso.get("input_tokens"),
        "tokens_out": uso.get("output_tokens"),
        "tokens_cache_read": uso.get("cache_read_input_tokens"),
        "tokens_cache_create": uso.get("cache_creation_input_tokens"),
        "subagents_spawned": subagentes.get("spawned"),
        "subagents_completed": subagentes.get("completed"),
        "subagents_failed": subagentes.get("failed"),
        "modelos": sorted((session.get("modelUsage") or {}).keys()),
    }

    transcript = medir_transcript(transcript_de(args.project_dir, str(session.get("session_id") or "")))

    veredicto, razon = decidir_veredicto(session, tablero, handoff, sesion_arrancada)

    informe = {
        "kind": "agent-loop-report",
        "schema_version": 1,
        "generated_at": ahora_iso(),
        "iteration": args.iteration,
        "verdict": veredicto,
        "reason": razon,
        "diagnostic": diagnostico(session, tablero, handoff, veredicto, getattr(args, "exit_code", None)),
        "board": tablero,
        "session": sesion,
        "transcript": transcript,
        "changes": cambios,
        "pr": pr,
        "handoff": handoff,
        "regression_guard": {
            "read_ratio": transcript.get("read_ratio"),
            "read_ratio_linea_base": 0.038,
            "poll_calls": transcript.get("poll_calls"),
            "poll_calls_linea_base": 131,
            "sleep_calls": transcript.get("sleep_calls"),
            "nota": "read_ratio es Read/(Read+Bash-que-lee): mas alto es mejor. Un sondeo es un "
                    "bucle que espera y vuelve a comprobar; un `sleep` suelto no lo es. La linea "
                    "base son las tres sesiones largas del 18-nov medidas con esta misma metrica: "
                    "pipelinek 948beb8c (20,2 h) read_ratio 0,138 y 131 sondeos; forgejo 6add7c05 "
                    "(27,8 h) 0,038 y 32; hodei 4b5179b7 (5,6 h) 0,373 y 3. Aqui se pone la peor de "
                    "las tres. La cifra de 2.032 que circulaba era de una metrica ingenua que "
                    "contaba cada `sleep`; los bucles reales eran 131, 32 y 3.",
        },
    }
    return informe


def self_test() -> int:
    import tempfile

    fallos = 0

    def comprobar(nombre: str, condicion: bool) -> None:
        nonlocal fallos
        if not condicion:
            print(f"agent-loop-report: no-certificado — {nombre}", file=sys.stderr)
            fallos += 1

    with tempfile.TemporaryDirectory() as directorio:
        antes = os.path.join(directorio, "antes.json")
        despues = os.path.join(directorio, "despues.json")
        session = os.path.join(directorio, "session.json")

        with open(antes, "w", encoding="utf-8") as flujo:
            json.dump({"schemaVersion": 1, "kind": "task-list", "tasks": [
                {"id": "PKH-100", "title": "T", "status": "To Do",
                 "acceptanceCriteriaCompleted": 0, "acceptanceCriteriaCount": 3},
            ]}, flujo)
        with open(despues, "w", encoding="utf-8") as flujo:
            json.dump({"schemaVersion": 1, "kind": "task-list", "tasks": [
                {"id": "PKH-100", "title": "T", "status": "Done",
                 "acceptanceCriteriaCompleted": 3, "acceptanceCriteriaCount": 3},
            ]}, flujo)
        with open(session, "w", encoding="utf-8") as flujo:
            json.dump({"session_id": "abc", "is_error": False, "result": "hecho",
                       "duration_ms": 1000, "num_turns": 5,
                       "usage": {"input_tokens": 10, "output_tokens": 20}}, flujo)

        # 1. Una tarea que pasa a terminal se ve como cerrada.
        estados_antes = estados_del_tabulario(leer_json(antes))
        estados_despues = estados_del_tabulario(leer_json(despues))
        diff = diff_del_tabulario(estados_antes, estados_despues, {"Done"})
        comprobar("una tarea que llega a Done se ve cerrada",
                  diff["task_closed"] is not None and diff["task_closed"]["id"] == "PKH-100")
        comprobar("una tarea que llega a Done no se ve como abierta",
                  diff["task_started"] is None)

        # 2. Sin handoff, una tarea cerrada FALLA. Es la guarda de la prueba negativa.
        veredicto, _ = decidir_veredicto(leer_json(session), diff, {"updated": False}, True)
        comprobar("tarea cerrada sin handoff da FAIL", veredicto == FAIL)

        # 3. Con handoff, la misma tarea PASA.
        veredicto, _ = decidir_veredicto(leer_json(session), diff, {"updated": True}, True)
        comprobar("tarea cerrada con handoff da PASS", veredicto == PASS)

        # 4. Una sesion que no arranco es NOT_RUN, no un verde.
        veredicto, _ = decidir_veredicto({}, diff, {"updated": True}, False)
        comprobar("una sesion que no arranco da NOT_RUN", veredicto == NOT_RUN)

        # 5. El id de la tarea se saca de la rama.
        comprobar("pkh-123-en-la-rama da PKH-123",
                  id_de_tarea_de_la_rama("feat/pkh-123-algo") == "PKH-123")
        comprobar("una rama sin id no inventa una tarea",
                  id_de_tarea_de_la_rama("feat/algo") is None)

        # 6. La metrica de lectura distingue explorar codigo de leer un log propio.
        comprobar("explorar un fuente con sed es leer codigo por la shell",
                  bash_que_lee_codigo("sed -n 1,60p Foo.kt"))
        comprobar("leer el log de la propia prueba no es falta de disciplina",
                  not bash_que_lee_codigo("cat /tmp/pkh060-scoped.log"))
        comprobar("leer el veredicto no es falta de disciplina",
                  not bash_que_lee_codigo("cat /tmp/pkh060.verdict"))
        comprobar("un comando que no lee nada no es lectura",
                  not bash_que_lee_codigo("git status --short"))

        # 7. El sondeo se distingue de la pausa: solo el bucle que vuelve a comprobar quema
        #    el contexto, y la guarda tiene que verlo sin dejar que el ruido la tape.
        comprobar("un bucle que espera y vuelve a comprobar es sondeo",
                  es_sondeo("until [ -f /tmp/v ]; do sleep 5; done"))
        comprobar("un bucle until con espera dentro es sondeo",
                  es_sondeo("until grep -q FIN log; do sleep 10; done"))
        comprobar("un bucle for que espera es sondeo",
                  es_sondeo("for i in $(seq 1 10); do sleep 2; done"))
        comprobar("watch es sondeo",
                  es_sondeo("watch -n 5 kubectl get pods"))
        comprobar("tail -f es sondeo",
                  es_sondeo("tail -f /tmp/build.log"))
        comprobar("un sleep suelto NO es sondeo",
                  not es_sondeo("sleep 1; echo lanzado"))
        comprobar("un sleep tras lanzar en background NO es sondeo",
                  not es_sondeo("setsid bash -c 'go' >/dev/null 2>&1 & disown; sleep 1; echo lanzado"))
        comprobar("un while read de un pipe NO es sondeo",
                  not es_sondeo("git status --short | while read f; do echo \"$f\"; done"))
        comprobar("un grep -c cuenta una vez y NO es sondeo",
                  not es_sondeo("grep -c FAIL /tmp/log"))
        comprobar("una pausa suelta se cuenta aparte",
                  PAUSA.search("sleep 1") is not None and not es_sondeo("sleep 1"))

        # 8. El PR que se reporta es el de la tarea cerrada, no otro de la ventana.
        ventana = [
            {"number": 524, "task_id": "PKH-125", "mergedAt": "2026-11-18T16:32:36Z"},
            {"number": 527, "task_id": "PKH-061", "mergedAt": "2026-11-18T17:41:14Z"},
            {"number": 528, "task_id": "PKH-061", "mergedAt": "2026-11-18T17:50:00Z"},
        ]
        elegido = elegir_pr_de_la_tarea(ventana, "PKH-061")
        comprobar("el PR reportado es el de la tarea cerrada",
                  elegido is not None and elegido["number"] == 528)
        comprobar("sin id de tarea no se inventa un PR de la tarea",
                  elegir_pr_de_la_tarea(ventana, None) is None)
        comprobar("una tarea sin PR propio no roba el de otra",
                  elegir_pr_de_la_tarea(ventana, "PKH-999") is None)

    if fallos:
        exit(3)
    print("agent-loop-report: certificado — mide el diff del tablero, el transcript y el PR, "
          "y falla una entrega que no deja handoff.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Informe de una iteracion del bucle Ralph.",
    )
    parser.add_argument("--before", required=False, help="task list --json antes de la sesion")
    parser.add_argument("--after", required=False, help="task list --json despues de la sesion")
    parser.add_argument("--session", required=False, help="session.json de claude -p")
    parser.add_argument("--project-dir", default="", help="~/.claude/projects/<proyecto>")
    parser.add_argument("--workspace", default="", help="raiz del workspace, para buscar repos")
    parser.add_argument("--repo", default="", help="un solo repo, en vez de buscarlos")
    parser.add_argument("--handoff-id", default="")
    parser.add_argument("--handoff-path", default="")
    parser.add_argument("--handoff-before", default="")
    parser.add_argument("--handoff-after", default="")
    parser.add_argument("--terminal-status", action="append", default=[],
                        help="estado terminal del tablero (repetible)")
    parser.add_argument("--since", default="", help="ISO8601: inicio de la sesion")
    parser.add_argument("--iteration", default="", help="numero de iteracion")
    parser.add_argument("--exit-code", type=int, default=None)
    parser.add_argument("--out", default="", help="fichero de salida JSON")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    if not args.before or not args.after:
        print("ERROR: hacen falta --before y --after.", file=sys.stderr)
        return 1

    informe = construir(args)
    texto = json.dumps(informe, indent=2, ensure_ascii=False)

    if args.out:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as flujo:
                flujo.write(texto + "\n")
        except OSError as error:
            print(f"ERROR: no pude escribir el informe: {error}", file=sys.stderr)
            return 2

    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
