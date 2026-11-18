# 01 — El supervisor: el bucle, etapa por etapa

El supervisor **no tiene contexto propio**. No recuerda la sesión anterior, no decide qué
tarea toca, no sabe qué se hizo. Solo hace cuatro cosas, y las hace siempre en el mismo
orden: comprobar, preparar, lanzar, medir.

## Las etapas

### 1. `preflight` — nada se gasta hasta que la máquina puede responder

Gastar una sesión de agente es un recurso caro. Descubrir que `gh` no está autenticado
después de la primera tarea es descubrirlo tarde. El preflight comprueba, **antes** de abrir
nada:

- los binarios: `backlog`, `gh`, `claude`, `pipelinek`;
- la autenticación de `gh` (sin ella no hay PR, y el PR es parte del ciclo);
- el perfil de Claude Code que se usará;
- que el tablero responde y cuántas tareas ve;
- que el directorio de estado se puede escribir;
- que el workspace agéntico existe y qué repos de producto cuelgan de él.

Falla con `1` (me niego) o `2` (no pude medir). Nunca sigue a medias: un preflight que
responde "más o menos" es un preflight que no ha comprobado.

### 2. `handoff` — el estado que cruza sesiones se escribe antes de empezar

Tres cosas:

1. **El documento de handoff** del tablero. Si no existe, se crea con su esqueleto: siempre
   hay un handoff válido, aunque la sesión falle. Se escribe con la CLI de Backlog.md y
   nunca a mano —un `.md` escrito a mano en `backlog/docs/` es un documento sin id, que
   `backlog doctor` marca como averiado.
2. **La marca de tiempo** del documento: es la línea base para saber después si la sesión lo
   actualizó.
3. **El prompt**, renderizado desde la plantilla con lo que hay que saber: dónde está el
   tablero, dónde está el handoff, dónde está el workspace agéntico, qué skills aplicar y
   qué toca de la ronda.

El prompt se renderiza **en cada iteración**, no una vez por run. Renderizado una sola vez,
la iteración 2 arrancaría con la foto de antes de la iteración 1, y la cadena de lo
aprendido se cortaría justo en el punto que el bucle existe para no cortar.

### 3. `task-N` — una sesión, una tarea, contexto en cero

La etapa abre **un** proceso de agente y espera a que termine. Sin bucles de sondeo, sin
`grep -c` sobre un log, y sin un timeout corto que expire antes de que el trabajo acabe.

El techo de la etapa (90 minutos por defecto) es del pipeline, no del prompt: un objetivo
sin tope más un mecanismo que re-pregunta es un bucle infinito.

### 4. `evidence` — los recibos se quedan con el run

El informe de cada iteración se copia a `build/reports/agent-loop/` (gitignored) y se
archiva como artefacto. Es lo que permite leer el veredicto sin la terminal que lo produjo.

## El ritmo

Las iteraciones son **idempotentes**: si una iteración ya está medida, se reutiliza su
informe y no consume una tarea. Si la sesión terminó pero el informe no llegó a escribirse
(murió por fuera después de que la sesión acabara), se mide la sesión que hay, no se abre
otra. Repetir el trabajo ya hecho para volver a medirlo es el error caro.

## Dónde vive cada tope

| Tope | Dónde | Efecto |
|---|---|---|
| **1 tarea** | el objetivo del prompt | la sesión cierra una tarea y sale |
| **N sesiones** | `AGENT_MAX_TASKS` | el run abre N sesiones y para |
| **90 min/iteración** | `timeout` de la etapa | el run no se cuelgue |
| **contexto** | proceso nuevo por iteración | contexto en cero, sin compactación |
| **tiempo** | `await_verdict.py` con timeout holgado | ninguna espera corta que expire antes del trabajo |

## Lo que el supervisor NO hace

- No elige la tarea: la elige el agente, leyendo el tablero.
- No juzga el código: eso es de la puerta del repo.
- No concede el estado terminal de una tarea: eso es del tablero y de la puerta.
- No reimplementa gates: delega en los scripts de cada repo.
- No limpia lo que no es suyo: la sesión suelta lo suyo, y el supervisor verifica.

Es un **driver**, no una segunda puerta.
