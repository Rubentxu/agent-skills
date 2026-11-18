#!/usr/bin/env python3
"""await_verdict.py — esperar a que un trabajo largo deje su veredicto, sin sondear.

POR QUÉ EXISTE

Un trabajo largo (un gate, una suite, una medición) deja su veredicto en un fichero. La
forma natural de esperarlo es un bucle `until [ -f ... ]; do sleep 20; done` dentro de un
`timeout 600`, y ese patrón se rompe por los dos lados:

  - el `timeout` expira antes de que el trabajo termine, así que se relanza y se remide: el
    mismo trabajo medido cinco veces, con el mismo resultado y el doble de tiempo;
  - el sondeo cada 20 segundos quema turnos de agente por minutos, y con ellos tokens.

Este script hace la espera una sola vez, con un timeout holgado por defecto y sin volver a
preguntar. Cuando el fichero aparece, lo imprime y traduce su veredicto al código de salida
de la casa.

CÓDIGOS DE SALIDA (el vocabulario del workspace)

  0  el veredicto apareció y es un PASS
  1  mal uso (faltan argumentos)
  2  no pude medir (el veredicto no apareció a tiempo, dice BLOCKED, o no se puede interpretar)
  3  el veredicto apareció y es un FAIL

USO

  await_verdict.py FICHERO [--timeout SEGUNDOS] [--label NOMBRE]
  await_verdict.py --self-test

EJEMPLO

  setsid ./medicion_fria.sh > /tmp/medicion.log 2>&1 &
  await_verdict.py /tmp/medicion/verdict.json --timeout 3600 --label medicion-fria
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

DEFAULT_TIMEOUT = 1800
INITIAL_SLEEP = 5
MAX_SLEEP = 60

# Los veredictos que el harness y las puertas ya usan, de mas especifico a mas generico.
PATRON_PLANO = re.compile(
    r"(EXECUTED_PASS|EXECUTED_FAIL|EXECUTED_BLOCKED|PASSED|FAILED|BLOCKED|PASS|FAIL)",
    re.IGNORECASE,
)


def verdict_de(fichero: Path) -> str:
    """El veredicto normalizado en bruto (PASS, FAIL, BLOCKED...), o "".

    Busca el campo `outcome` o `verdict` con el valor más reciente. Un fichero que declara
    PASS y también declara FAIL no es un PASS: se queda con el último veredicto que se
    encuentra, que es el que el trabajo escribió al final.
    """
    try:
        texto = fichero.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    # 1) JSON con los campos que el harness y las puertas ya usan.
    try:
        datos = json.loads(texto)
    except ValueError:
        datos = None

    if isinstance(datos, dict):
        for clave in ("outcome", "verdict", "result", "status"):
            valor = datos.get(clave)
            if isinstance(valor, str) and valor.strip():
                return valor.strip().upper()

    # 2) JSON anidado: se busca la clave más profunda que parezca un veredicto.
    if isinstance(datos, (dict, list)):
        encontrados: list[str] = []

        def buscar(nodo: object) -> None:
            if isinstance(nodo, dict):
                for clave, valor in nodo.items():
                    if clave in ("outcome", "verdict") and isinstance(valor, str):
                        encontrados.append(valor.strip().upper())
                    buscar(valor)
            elif isinstance(nodo, list):
                for elemento in nodo:
                    buscar(elemento)

        buscar(datos)
        if encontrados:
            return encontrados[-1]

    # 3) Texto plano: la última coincidencia de un veredicto conocido.
    coincidencias = PATRON_PLANO.findall(texto)
    if coincidencias:
        return coincidencias[-1].upper()
    return ""


def normaliza(bruto: str) -> str:
    """El veredicto de la casa: PASS, FAIL, BLOCKED, o "" si no se reconoce."""
    match = bruto.strip().upper()
    if match in {"EXECUTED_PASS", "PASSED", "PASS", "OK", "SUCCESS"}:
        return "PASS"
    if match in {"EXECUTED_FAIL", "FAILED", "FAIL", "ERROR"}:
        return "FAIL"
    if match in {"EXECUTED_BLOCKED", "BLOCKED"}:
        return "BLOCKED"
    return ""


def esperar(fichero: Path, timeout: int) -> bool:
    """Espera a que el fichero aparezca, con un backoff que crece y un techo.

    Devuelve False si se agota el tiempo: un timeout NUNCA es un verde.
    """
    limite = time.monotonic() + timeout
    dormir = INITIAL_SLEEP
    while not fichero.exists():
        if time.monotonic() >= limite:
            print(
                f"await-verdict: no pude medir — {fichero} no aparecio en {timeout}s.",
                file=sys.stderr,
            )
            print(
                "                El trabajo puede seguir vivo: comprueba el proceso antes de relanzarlo.",
                file=sys.stderr,
            )
            return False
        time.sleep(dormir)
        if dormir < MAX_SLEEP:
            dormir = min(dormir * 2, MAX_SLEEP)
    return True


def self_test() -> int:
    """Se demuestra a si mismo: cada veredicto, a su codigo."""
    import tempfile

    fallos = 0
    with tempfile.TemporaryDirectory() as temporal:
        base = Path(temporal)
        (base / "pase.json").write_text('{"outcome": "EXECUTED_PASS"}\n', encoding="utf-8")
        (base / "fallo.json").write_text('{"outcome": "EXECUTED_FAIL"}\n', encoding="utf-8")
        (base / "bloqueado.json").write_text('{"outcome": "EXECUTED_BLOCKED"}\n', encoding="utf-8")
        (base / "plano.txt").write_text("verdict: PASSED\n", encoding="utf-8")
        (base / "ilegible.txt").write_text("lo que sea\n", encoding="utf-8")

        comprobaciones = [
            ("un veredicto PASS devuelve 0", 0, [str(base / "pase.json"), "--timeout", "5"]),
            ("un veredicto FAIL devuelve 3", 3, [str(base / "fallo.json"), "--timeout", "5"]),
            ("un veredicto BLOCKED devuelve 2", 2, [str(base / "bloqueado.json"), "--timeout", "5"]),
            ("un veredicto en texto plano devuelve 0", 0, [str(base / "plano.txt"), "--timeout", "5"]),
            ("un veredicto ilegible devuelve 2", 2, [str(base / "ilegible.txt"), "--timeout", "5"]),
            ("un fichero que no aparece devuelve 2", 2, [str(base / "nunca.json"), "--timeout", "2"]),
        ]
        for nombre, esperado, argumentos in comprobaciones:
            codigo = main(argumentos)
            if codigo != esperado:
                print(
                    f"await-verdict: no-certificado — {nombre}: esperado {esperado}, obtenido {codigo}",
                    file=sys.stderr,
                )
                fallos += 1

        codigo = main([])
        if codigo != 1:
            print(
                f"await-verdict: no-certificado — una invocacion sin argumentos devuelve 1: "
                f"obtenido {codigo}",
                file=sys.stderr,
            )
            fallos += 1

    if fallos:
        return 3
    print(
        "await-verdict: certificado — espera un veredicto, lo traduce al codigo de la casa "
        "y nunca sondea mas de lo necesario."
    )
    return 0


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=True, description=__doc__.split("\n")[0])
    parser.add_argument("fichero", nargs="?", help="el fichero de veredicto que se espera")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help="segundos maxima de espera (por defecto 1800)")
    parser.add_argument("--label", default="", help="nombre del trabajo, para el log")
    try:
        args = parser.parse_args(argumentos)
    except SystemExit as exc:
        # argparse ya ha impreso el error y el uso. El uso incorrecto es un 1, no un 2.
        return 0 if exc.code in (0, None) else 1

    if not args.fichero:
        print("ERROR: falta el fichero de veredicto.", file=sys.stderr)
        return 1
    if args.timeout < 0:
        print("ERROR: --timeout debe ser un numero de segundos.", file=sys.stderr)
        return 1

    fichero = Path(args.fichero).expanduser()
    if args.label:
        print(
            f"await-verdict: esperando {args.label} ({args.timeout}s maximo) en {fichero}",
            file=sys.stderr,
        )

    if not esperar(fichero, args.timeout):
        return 2

    # El fichero apareció: se lee una vez y se traduce.
    try:
        contenido = fichero.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"await-verdict: no pude leer el veredicto: {exc}", file=sys.stderr)
        return 2
    print(contenido)

    bruto = verdict_de(fichero)
    veredicto = normaliza(bruto)

    if veredicto == "PASS":
        return 0
    if veredicto == "FAIL":
        print("await-verdict: el veredicto es FAIL.", file=sys.stderr)
        return 3
    if veredicto == "BLOCKED":
        print("await-verdict: el veredicto es BLOCKED: no se pudo medir.", file=sys.stderr)
        return 2
    print(
        f"await-verdict: el fichero existe pero no declara un veredicto reconocible "
        f"({bruto or 'sin veredicto'}).",
        file=sys.stderr,
    )
    print("                    El contenido se ha impreso arriba: leelo y decide.", file=sys.stderr)
    # El veredicto esta pero no se entiende: no pude medir. Nunca un verde.
    return 2


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        raise SystemExit(self_test())
    raise SystemExit(main())
