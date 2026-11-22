---
name: supervised-task-loop
description: "Conduce un bucle de sesiones de agente donde cada sesión cierra UNA tarea del tablero Backlog.md con el contexto en cero, escribe el handoff entre sesiones, mide lo entregado y libera los recursos. Úsala cuando haya que encadenar trabajo repetitivo sobre un backlog (proyecto único o patrón home repo), supervisar sesiones que se cuelgan o se duplican, o medir el coste real de una sesión de agente."
---

# Bucle supervisado — un agente por encima, una tarea por sesión

Un **supervisor** sin contexto propio: abre una sesión por tarea, comprueba que la sesión
entregó, deja el estado para la siguiente, libera lo que la sesión dejó vivo, y abre la
siguiente con lo que necesita. Nada más.

## La invariante

> **Una sesión, una tarea, contexto en cero.** El supervisor no recuerda: mide.

Todo lo que cruza el límite entre sesiones son **dos** cosas: el **tablero** (qué está
hecho) y el **handoff** (cómo fue la anterior). Todo lo demás —el objetivo, el modo, el
perfil, el estado de la máquina— se vuelve a derivar en cada iteración, y por eso se deriva
en el sitio donde se puede derivar: el fichero de configuración.

## Los tres sitios

Una configuración que no distingue estos tres no funciona en el patrón home repo, que es
donde vive el dolor de cabeza. Se separan, y se dicen en cada arranque:

| Sitio | Qué es | Por qué importa |
|---|---|---|
| **workspace agéntico** | el directorio desde el que el agente ve **sus** repos | puede ser el propio proyecto, o el **padre** de varios repos |
| **home repo** | el repo del proyecto: el que lleva el **tablero** (`backlog/`) | el tablero es la única autoridad sobre lo que está hecho; aquí corre la pipeline |
| **runtime** | donde viven los scripts (`agent_*.py`) | la skill instalada, o el propio proyecto |

Los tres pueden coincidir (proyecto único) o no (patrón home repo: el workspace es el padre,
el home repo es un hijo suyo). El runtime los deduce y el `.env` los puede fijar.

## Las tres piezas

| Pieza | Qué hace | Dónde |
|---|---|---|
| `pipeline.agent.kts` | el ritmo: preflight → handoff → N sesiones → evidencia | `assets/` |
| `scripts/agent_*.py` | el runtime: configura, mide, espera, decide | `scripts/` |
| `assets/agent-prompt.md` | el contrato de la sesión: qué hacer y qué dejar escrito | `assets/` |

## El bucle del supervisor

```
preflight ──▶ handoff ──▶ ┌ sesión 1 ─▶ medir ──▶ liberar ┐
                       │   └ sesión 2 ─▶ medir ─▶ liberar ┘──▶ evidencia
                       └──▶ (N veces, o hasta que se acaben)
```

- **preflight**: comprueba que la máquina puede responder *antes* de gastar una tarea.
- **handoff**: crea el documento del tablero (la primera vez, con su esqueleto) y renderiza
  el prompt con el estado real.
- **sesión**: un proceso nuevo de agente, con el contexto en cero, que cierra **una** tarea.
- **medir**: el informe compara el tablero antes y después y decide `PASS`/`FAIL`/`BLOCKED`/`NOT_RUN`.
- **liberar**: lo que la sesión dejó vivo (worktrees, ramas, pods, daemons) se suelta.

## La evidencia medida

Lo que se midió en la instancia real que motivó esta skill (18-nov), antes y después:

| Métrica | Antes | Después |
|---|---|---|
| compactaciones por sesión | 28 y 76 | 0 |
| contexto por turno | 160 K (p90 246 K) | ~124 K, sin compactar |
| `Read` : shell | 1:23 y 1:42 | 0,143 – 0,462 |
| sondeos (`until`/`while` + espera) | 2.032 (contados en bruto) | 0 |

El sondeo se cuenta **por forma**: un bucle que espera y repite. Una espera suelta no es
sondeo. Sin esa distinción, la guarda de regresión no guarda nada.

## Instalación

Dos formas, y las dos valen. Elige según si quieres que el proyecto lleve el runtime dentro
o lo tomes de la skill instalada.

### A. El runtime en el proyecto (copiado de la skill)

```bash
# 1. los scripts y los assets
cp -r <skill>/scripts <proyecto>/scripts
cp -r <skill>/assets  <proyecto>/assets
cp <skill>/assets/pipeline.agent.kts <proyecto>/pipeline.agent.kts

# 2. la configuracion, rellenada una vez
cp <skill>/assets/agent-loop.env <proyecto>/agent-loop.env
$EDITOR <proyecto>/agent-loop.env

# 3. el run
python3 <proyecto>/scripts/agent_run.py
```

### B. El runtime en la skill instalada (el proyecto solo lleva la configuracion)

```bash
cp <skill>/assets/agent-loop.env <proyecto>/agent-loop.env
$EDITOR <proyecto>/agent-loop.env   # AGENT_RUNTIME=<ruta>/scripts
python3 <skill>/scripts/agent_run.py
```

En la forma B el proyecto no lleva ni scripts ni pipeline: la pipeline es la de la skill, los
scripts se invocan por la ruta que dice `AGENT_RUNTIME`, y los artefactos del run se archivan
en el proyecto (`build/reports/agent-loop/`, gitignored).

El `.env` no tiene secretos: la autenticación va en el perfil del agente y las credenciales
del repositorio en las suyas.

## Referencias

| Referencia | Qué hay dentro |
|---|---|
| [`references/01-supervisor.md`](references/01-supervisor.md) | el bucle en detalle: qué hace cada etapa y por qué en ese orden |
| [`references/02-session-contract.md`](references/02-session-contract.md) | el contrato de la sesión: qué recibe, qué devuelve, qué hereda |
| [`references/03-measurement.md`](references/03-measurement.md) | cómo se mide y cómo se decide el veredicto |
| [`references/04-failure-modes.md`](references/04-failure-modes.md) | las eventualidades y cómo se corrigen |

## Triage entre harnesses (opt-in)

Con `backlog-agile-workflow` confirmado en el inventario del host, abrir [global-supervision](references/global-supervision.md): consultar eventos del Home Repo, solicitar `YIELD` y recuperar solo tras parada/inventario verificados y generación CAS. Esta skill supervisa sus sesiones sin considerarse autoridad global ni instalar otro monitor.

## Los límites

- El bucle es un **driver, no una puerta**: no juzga código, no concede estados, no
  reimplementa gates. La autoridad sigue siendo el tablero y la puerta de cada repo.
- **No se escribe estado operativo en el repo**: el estado del run vive en
  `${XDG_STATE_HOME:-$HOME/.local/state}/pipelinek/<home-repo>`.
- La sesión se abre **sin `--bare`** por defecto: ese flag apaga también el login de
  `claude.ai`, con el que se autentican estos perfiles. El contexto en cero lo garantiza el
  proceso nuevo, no el flag.
- El tope exterior vive en el pipeline; un watchdog independiente limita el grupo de sesión y el prompt lleva soft/hard deadline absoluto. Recursos deliberadamente desprendidos requieren reconciliación.

## Recuperación y pruebas proporcionales

El runtime no mide JSON vacío, incompleto ni error de arranque como sesión terminada. Reutiliza informe válido sin recalcular. Si hay intento incompleto, reconciliar proceso/operaciones y archivar sin borrar. Ver [recuperación](references/04-failure-modes.md). El supervisor prepara pruebas proporcionales mediante delivery-first-testing si disponible y traslada hechos, políticas y recursos; no se presupone rama ni autorización de publicación.

## Endurance Relay externo

Máximo 60 minutos por sesión, soft deadline antes del hard. El relay externo admite un segundo intento explícitamente reconciliado de la misma tarea (ver [fallos](references/04-failure-modes.md)); conserva presupuesto acumulado de 120 min y evidencia. No confundir bloqueo de pipeline con autorización de retry. La versión nativa sigue en delegated-task-loop y no requiere este driver.
