# 03 — La medición

El supervisor no se fía del agente: mide. El informe (`scripts/agent_loop_report.py`) compara
el tablero antes y después, lee el transcript de la sesión, pregunta a GitHub por los PR, y
decide. El agente puede decir lo que quiera; lo que cuenta es lo que está en el tablero y en
git.

## De dónde sale cada campo

| Campo | De dónde |
|---|---|
| `task_closed`, `task_started` | diff de `backlog task list --json` antes/después |
| `duration_s`, `agent_exit`, `is_error`, `session_id`, tokens | `session.json` (`claude -p --output-format json`) |
| `files_changed`, `lines_changed`, `by_ext`, `code_changed` | el PR de la tarea (`gh pr view --json files`) y, si no hay, `git diff --stat` |
| `pr_url`, `pr_state`, `pr_merged` | `gh pr list --state merged`, casando por el id de la tarea |
| `branches_cleaned` | ¿existen todavía las ramas de la tarea, en local o en remoto? |
| `handoff_updated` | ¿cambió `updated_date` del documento de handoff? |
| `read_calls`, `bash_read_calls`, `read_ratio` | el transcript de la sesión |
| `poll_calls` | comandos de shell que son **sondeos** |
| `verdict` | `PASS` / `FAIL` / `BLOCKED` / `NOT_RUN` |

## Tres decisiones que hubo que tomar

### El PR de la tarea, no el primero que sale

En la ventana de tiempo puede haber otros PR fusionados —otra sesión trabajando en paralelo
en el mismo repo—. Si el PR que se reporta y el PR que se miden son distintos, el informe
miente. Por eso el PR se elige **por el id de la tarea** (la rama lo lleva) y, sin id, no se
reporta ningún PR.

Y el PR manda sobre el clon local: el agente fusiona por la API, así que el `main` local puede
estar viejo. Un "0 ficheros" con un PR de 12 ficheros detrás es un falso negativo.

### El sondeo se cuenta por forma, no por palabra

Un sondeo es **un bucle que espera y repite**:

- `until [ -f x ]; do sleep 20; done` → sondeo
- `while ! gh pr view $n; do sleep 5; done` → sondeo
- `sleep 30` → **no** es sondeo: es una espera
- `for f in *.kt; do ...; done` → **no** es sondeo: es un recorrido

La diferencia pareceacademic, pero no lo es: contadas en bruto, las esperas sueltas dan 2.032
"sondeos" frente a los 131 reales. Sin esa distinción, la guarda de regresión no guarda
nada y el número deja de significar nada.

### La guarda del handoff

Una tarea cerrada **sin** handoff actualizado es un `FAIL`, aunque el código de la sesión sea
perfecto y el PR esté fusionado. El motivo es simple: la siguiente sesión arranca con
contexto en cero y sin el handoff no puede continuar. Es una entrega que se pierde.

## El veredicto

| Veredicto | Cuándo |
|---|---|
| `PASS` | sesión correcta, un cierre atribuible y observación técnica externa completa |
| `FAIL` | la sesión cerró la tarea pero no dejó handoff, o no cerró nada, o terminó en error |
| `BLOCKED` | el agente declaró que no puede avanzar (y no cerró nada) |
| `NOT_RUN` | la sesión ni siquiera arrancó, o no se pudo determinar |

`sessionVerdict` mide continuidad operativa; `verdict` exige entrega. Un cierre con handoff pero sin observación técnica queda `NOT_RUN` y detiene el bucle. Los PASS de esquema 1 no se reutilizan como entrega. El veredicto es el **código de salida** de la etapa: `PASS` → 0, `FAIL` → 3, y cualquier
otra cosa → 2 (no pude medir). Nunca un verde por defecto.

## La línea base

Las guardas de regresión no tienen sentido sin la línea base contra la que comparar. La del
18-nov, sobre las sesiones que motivaron esta skill:

| Métrica | Línea base | Depois |
|---|---|---|
| compactaciones | 28 y 76 por sesión | 0 |
| contexto por turno | 160 K (p90 246 K) | ~124 K |
| `Read` : shell | 1:23 y 1:42 | 0,143 – 0,462 |
| sondeos | 131 / 32 / 3 (por forma) | 0 |

**Si el bucle no los mejora, hay que decirlo, no maquillarlo.** Un informe que solo dice
"funcionó" no mide nada.

## El informe es reproducible

El informe es una **función de los artefactos en disco**: tablero antes y después, el JSON de
la sesión, el transcript, la salida de `gh`. Se puede volver a hacer con los mismos
artefactos y tiene que dar lo mismo. Por eso la iteración es idempotente: si el informe ya
está, se reutiliza, y si la sesión terminó sin informe, se mide la que hay en vez de abrir
otra.
