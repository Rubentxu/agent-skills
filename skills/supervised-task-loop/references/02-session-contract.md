# 02 — El contrato de la sesión

Una sesión es un **proceso nuevo** de agente. No hereda el contexto de la anterior: no hay
compactaciones, no hay olvido de lo que se hizo hace tres horas. A cambio, no sabe nada, y
eso es exactamente lo que se quiere.

## Qué recibe

El prompt renderizado. Y nada más. En concreto:

| En el prompt | Qué es |
|---|---|
| `{{WORKSPACE_DIR}}` | el workspace agéntico: el cwd de la sesión, donde ve sus repos |
| `{{HOME_DIR}}` | el home repo: el repo del proyecto, el que lleva el tablero |
| `{{BOARD_DIR}}` | el tablero (la única autoridad) |
| `{{HANDOFF_PATH}}` | el documento de handoff que dejó la sesión anterior |
| `{{SKILLS}}` | las skills que el objetivo tiene que aplicar |
| `{{RUNTIME_DIR}}` | dónde está el runtime, para las esperas honestas |
| `{{RONDA}}` | si toca pagar los gates de algún repo, y de cuál |

No recibe: la conversación anterior, el transcript, el contexto de otras tareas, ni el
"estado" del supervisor. Todo eso se relee del tablero, que es donde está.

## Qué devuelve

Tres cosas, todas medibles:

1. **El tablero movido**: una tarea cerrada (o ninguna, y hay que decirlo).
2. **El handoff actualizado**: el documento de handoff con lo que se hizo, lo que quedó a
   medias y lo aprendido.
3. **El código y los recursos**: la rama, el PR, los worktrees liberados.

Y un código de salida, que es parte del contrato:

| Código | Significado |
|---|---|
| `0` | corrió y pasó |
| `1` | me negué |
| `2` | no pude medir |
| `3` | corrió y falló |

## Qué hereda

Dos cosas, y solo dos:

- **El tablero**: qué está hecho.
- **El handoff**: cómo se llegó ahí.

El handoff es un documento del tablero, escrito con su CLI, con esta estructura:

```markdown
# Handoff

## Ahora
- Tarea: PKH-XXX — <titulo>   (o "Ninguna: sin trabajo listo")

## Ultima tarea cerrada
- PKH-XXX: <que se entrego>
- Evidencia: <puerta que paso, veredicto, sha, PR>

## Que queda a medias
- PKH-YYY: <estado y por que>

## Aprendido
- <sintoma> -> <causa> -> <arreglo>

## Candidatos siguientes
- PKH-AAA (lista, valor X)
```

**Un solo escritor**: el agente. El supervisor **verifica** que cambió (`handoff_updated`) y
lo registra; no lo reescribe. Un handoff reescrito por el supervisor es un handoff que ya no
es verdad de lo que pasó.

## El clear

En el bucle, el "clear" es el fin del proceso: cada iteración es un proceso nuevo, así que el
contexto en cero está garantizado por construcción. En una sesión interactiva, el clear es
del humano: el agente escribe el handoff y el humano pulsa `/clear`.

## Las reglas que el prompt lleva dentro

Están en la plantilla (`assets/agent-prompt.md`) y son la parte que más efecto tiene sobre el
coste de la sesión:

- **Una sola tarea.** Al cerrarla, sale. No elige otra, no amplía el alcance.
- **Contexto en cero**: no busca sesiones anteriores ni lee transcripts.
- **Lectura**: fichero > 30 KB → `ctx outline|symbol|usages|section`; ≤ 30 KB → `Read`. Nunca
  `sed -n` ni `grep` para leer código: eso llena el contexto y lo empeora.
- **Trabajo largo** (> 2 min): en background, **dentro de su slice**, y se espera a su
  **fichero de veredicto** con timeout holgado (`await_verdict.py`). Nunca un timeout corto
  que expire antes del trabajo; nunca bucles `until ... sleep` para sondear.
- **PRs**: push, PR y merge requieren autorización efectiva; el título y el cuerpo en el
  estilo del repo y **sin mencionar herramientas ni agentes** (la política del repo lo
  bloquea).
- **Al terminar**: actualizar el handoff, **liberar lo que la tarea creó** (worktrees, ramas,
  pods, contenedores, kind clusters, procesos auxiliares) y salir.

## Lo que NO cruza

La sesión no hereda el contexto, pero tampoco hereda los recursos: lo que la sesión anterior
dejó vivo (un daemon, un clúster, un worktree) es ruido para la siguiente y un riesgo para la
máquina. Por eso "lo que se usa, se libera" es parte del contrato y no una buena intención.
