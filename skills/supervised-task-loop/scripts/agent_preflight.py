#!/usr/bin/env python3
"""agent_preflight.py — comprobar que el bucle puede correr antes de gastar una tarea.

QUÉ ES

La puerta previa del bucle Ralph. No hace trabajo: comprueba que todo lo que la iteración
necesita existe y responde, y se niega a seguir si algo no está. Gastar una sesión de agente
es un recurso caro; descubrir que `gh` no está autenticado después de la primera tarea es
descubrirlo tarde.

LO QUE COMPRUEBA

  - los binarios: backlog, gh, claude, pipelinek
  - la autenticación de gh (sin ella no hay PR, y el PR es parte del ciclo)
  - el perfil de Claude Code que se usará
  - el tablero: se lee y se responde
  - el directorio de estado: se puede escribir
  - el workspace agéntico: existe
  - los repos de producto que cuelgan de él (aviso si no hay ninguno)

CÓDIGOS DE SALIDA

  0  todo lo necesario está y responde
  1  me negué: falta algo o algo está mal usado
  2  no pude medir: algo no respondió
"""
from __future__ import annotations

import json
import os
import ipaddress
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from urllib.error import HTTPError, URLError
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_config import ErrorDeConfig, Runtime, init_runtime, repos_de_producto  # noqa: E402

BINARIOS = ("backlog", "gh", "claude", "pipelinek", "timeout")


class Fallo(Exception):
    """Un fallo del preflight: o me niego (1), o no pude medir (2)."""

    def __init__(self, mensaje: str, codigo: int = 1) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


def comprobar_binarios(rt: Runtime) -> None:
    for binario in BINARIOS:
        donde = shutil.which(binario)
        if donde is None:
            raise Fallo(f"falta el binario: {binario}")
        print(f"preflight: ok {binario} -> {donde}")


def comprobar_gh(rt: Runtime) -> None:
    """Sin `gh` autenticado no hay PR, y el PR es parte del ciclo."""
    try:
        resultado = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Fallo(f"gh no responde: {exc}") from exc
    if resultado.returncode != 0:
        detalle = (resultado.stdout + resultado.stderr).strip()
        (rt.state / "gh-auth-preflight.txt").write_text(detalle + "\n", encoding="utf-8")
        raise Fallo(
            f"gh no esta autenticado; el ciclo de tarea necesita abrir PR "
            f"(ver {rt.state / 'gh-auth-preflight.txt'})"
        )
    print("preflight: ok gh autenticado")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def catalogo_modelos(profile: dict, environ: dict | None = None, opener=None) -> str:
    env = os.environ if environ is None else environ
    mode = env.get("AGENT_MODEL_CHECK", "auto").strip()
    if mode == "off":
        return "DISABLED"
    if mode not in ("auto", "required"):
        raise Fallo("AGENT_MODEL_CHECK invalido")
    profile_env = profile.get("env") or {}
    if not isinstance(profile_env, dict):
        raise Fallo("perfil: env invalido")
    def effective(key):
        a,b=profile_env.get(key),env.get(key)
        if a and b and a!=b:
            # Do not pretend to know precedence across hosts/configurations.
            raise Fallo("MODEL_UNRESOLVED: configuracion en conflicto para "+key, codigo=2)
        value=a or b
        if value is not None and not isinstance(value,str): raise Fallo("perfil: valor invalido de "+key)
        return value
    base=effective("ANTHROPIC_BASE_URL")
    model=env.get("AGENT_MODEL_CHECK_MODEL") or effective("ANTHROPIC_MODEL") or profile.get("model")
    def unsupported(reason):
        if mode=="required": raise Fallo(reason,codigo=2)
        return reason
    if not base:
        return unsupported("CHECK_UNSUPPORTED: sin gateway explicito")
    if not isinstance(model,str) or not model.strip() or model.lower() in ("sonnet","opus","haiku","default","opusplan"):
        return unsupported("MODEL_UNRESOLVED: alias o modelo no concreto")
    try:
        u=urlsplit(base)
        if u.username or u.password or u.query or u.fragment or not u.hostname: raise ValueError()
        local=u.hostname=="localhost"
        try: local=local or ipaddress.ip_address(u.hostname).is_loopback
        except ValueError: pass
        if u.scheme!="https" and not (u.scheme=="http" and local): raise ValueError()
    except ValueError:
        raise Fallo("MODEL_CHECK_UNSAFE_URL: use HTTPS o loopback",codigo=2)
    url=base.rstrip("/")
    url += "/models" if url.endswith("/v1") else "/v1/models"
    headers={"Accept":"application/json"}
    token=effective("ANTHROPIC_AUTH_TOKEN")
    key=effective("ANTHROPIC_API_KEY")
    if token and key:
        raise Fallo("MODEL_UNRESOLVED: autenticacion ambigua",codigo=2)
    # Never forward login/OAuth credentials or follow redirects.
    if token: headers["Authorization"]="Bearer "+token
    if key: headers["x-api-key"]=key
    if any("\n" in x or "\r" in x for x in headers.values()): raise Fallo("cabecera de autenticacion invalida")
    client=opener or build_opener(ProxyHandler({}),NoRedirect())
    try:
        with client.open(Request(url,headers=headers,method="GET"),timeout=3) as response:
            raw=response.read(1024*1024+1)
        if len(raw)>1024*1024: raise Fallo("MODEL_CHECK_INVALID_RESPONSE",codigo=2)
        data=json.loads(raw)
    except HTTPError as e:
        if e.code in (404,405):
            return unsupported("CHECK_UNSUPPORTED: catalogo no disponible")
        if e.code in (401,403):
            raise Fallo("AUTH_FAILED: catalogo rechazo autenticacion",codigo=2) from None
        raise Fallo("PROVIDER_UNAVAILABLE: HTTP "+str(e.code),codigo=2) from None
    except (URLError,TimeoutError,OSError,ValueError):
        raise Fallo("PROVIDER_UNAVAILABLE: catalogo no responde o formato invalido",codigo=2) from None
    rows=data.get("data") if isinstance(data,dict) else None
    if not isinstance(rows,list) or any(not isinstance(x,dict) or not isinstance(x.get("id"),str) for x in rows):
        return unsupported("CHECK_UNSUPPORTED: catalogo sin IDs")
    if model in {x["id"] for x in rows}:
        return "READY"
    if data.get("has_more") or data.get("next"):
        return unsupported("MODEL_UNRESOLVED: catalogo paginado")
    raise Fallo("MODEL_UNAVAILABLE: modelo configurado ausente del catalogo",codigo=2)

def comprobar_perfil(rt: Runtime) -> None:
    """El perfil de Claude Code: cada perfil vive en su fichero y trae su autenticacion."""
    perfil = Path.home() / ".config/claude-profiles" / f"{rt.profile}.json"
    if not perfil.is_file():
        raise Fallo(f"el perfil de Claude Code no existe: {perfil}")
    try:
        profile=json.loads(perfil.read_text(encoding="utf-8"))
        if not isinstance(profile,dict): raise ValueError()
    except (OSError,ValueError):
        raise Fallo("perfil JSON invalido") from None
    status=catalogo_modelos(profile)
    print(f"preflight: perfil {perfil}; modelo={status}")


def comprobar_tablero(rt: Runtime) -> None:
    """El tablero tiene que responder, y decir cuantas tareas ve."""
    try:
        resultado = subprocess.run(
            ["backlog", "task", "list", "--json"],
            cwd=rt.home_repo,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Fallo(f"el tablero no responde: {exc}", codigo=2) from exc
    if resultado.returncode != 0:
        (rt.state / "board-preflight.err").write_text(resultado.stderr, encoding="utf-8")
        raise Fallo(
            f"el tablero no responde (ver {rt.state / 'board-preflight.err'})",
            codigo=2,
        )
    (rt.state / "board-preflight.json").write_text(resultado.stdout, encoding="utf-8")
    try:
        datos = json.loads(resultado.stdout)
        tareas = datos.get("tasks") if isinstance(datos, dict) else None
        numero = len(tareas or [])
    except ValueError:
        numero = 0
    print(f"preflight: ok tablero con {numero} tareas")


def comprobar_estado(rt: Runtime) -> None:
    """El estado del run: se puede escribir."""
    try:
        rt.state.mkdir(parents=True, exist_ok=True)
        prueba = rt.state / ".preflight-write"
        prueba.write_text("", encoding="utf-8")
        prueba.unlink()
    except OSError as exc:
        raise Fallo(f"no puedo escribir en el directorio de estado: {rt.state}: {exc}") from exc
    print("preflight: ok estado escribible")


def comprobar_workspace(rt: Runtime) -> None:
    """El workspace agéntico existe. Que sea o no un repositorio Git es cosa del proyecto:
    lo único que se comprueba es que exista y que el estado del run NO se escriba dentro."""
    if not rt.workspace.is_dir():
        raise Fallo(f"el workspace agentico no existe: {rt.workspace}")
    print(f"preflight: ok workspace agentico {rt.workspace}")
    if (rt.workspace / ".git").exists():
        print(
            f"preflight: aviso — el workspace agentico es un repositorio Git: "
            f"el estado del run va a {rt.state}, no dentro"
        )


def comprobar_repos(rt: Runtime) -> None:
    """Los repos de producto: los que cuelgan del workspace agéntico."""
    repos = repos_de_producto(rt.workspace, rt.home_repo)
    if not repos:
        print(
            f"preflight: aviso — no hay repos de producto con .git bajo {rt.workspace} "
            "(el agente trabaja sobre el propio home repo)"
        )
        return
    for repo in repos:
        print(f"preflight: ok repo de producto {repo}")


def self_test() -> int:
    """Un ejecutable que no existe tiene que producir un fallo, no un verde."""
    if shutil.which("este-binario-no-existe-nunca-12345") is not None:
        print(
            "preflight: no-certificado — un binario inexistente no deberia pasar",
            file=sys.stderr,
        )
        return 3
    print(
        "preflight: certificado — comprueba lo que hace falta antes de gastar una tarea."
    )
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        return self_test()

    try:
        rt = init_runtime()
    except ErrorDeConfig as exc:
        print(f"preflight: FALLA — {exc}", file=sys.stderr)
        return 1

    rt.state.mkdir(parents=True, exist_ok=True)

    print(f"preflight: run={rt.run_dir}")
    print(f"preflight: workspace agentico={rt.workspace}")
    print(f"preflight: home repo={rt.home_repo}")
    print(f"preflight: tablero={rt.board_dir}")
    print(f"preflight: estado={rt.state}")
    print(f"preflight: perfil={rt.profile}")

    fallos = 0
    codigo = 0
    for nombre, comprobacion in (
        ("los binarios", comprobar_binarios),
        ("la autenticacion de gh", comprobar_gh),
        ("el perfil de Claude Code", comprobar_perfil),
        ("el tablero", comprobar_tablero),
        ("el estado", comprobar_estado),
        ("el workspace agentico", comprobar_workspace),
        ("los repos de producto", comprobar_repos),
    ):
        try:
            comprobacion(rt)
        except Fallo as exc:
            print(f"preflight: FALLA — {nombre}: {exc}", file=sys.stderr)
            fallos += 1
            codigo = max(codigo, exc.codigo)

    if fallos:
        print(f"preflight: {fallos} fallos", file=sys.stderr)
        return codigo or 1
    print("preflight: 0 fallos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
