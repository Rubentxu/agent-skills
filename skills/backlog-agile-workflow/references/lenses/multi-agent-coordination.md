# Coordinación de varios agentes — frontera, claims y ámbitos

**Intents:** `coordinate-work`, `schedule-work`, `claim-task`. [Volver al navegador](../navigation.md).

## Autoridad y capacidades

- Backlog.md sigue siendo la **única autoridad** de tareas, estados, dependencias, decisiones y eventos de coordinación. No crear otro tracker ni copiar el Backlog al checkout de código. Resolver primero el Home Repo mediante `software-knowledge` si está disponible.
- `isReady` demuestra **solo dependencias**; no que la tarea esté libre. Consultar `task view --json` y comentarios de todas las tareas antes del claim. Los `coord:*` son **índices visuales**, nunca locks.
- El protocolo v1 codifica eventos `COORDINATION_EVENT_V1 {...}` en **comentarios nativos** de la tarea; `--add-label` y `--remove-label` solo proyectan el estado. Un evento confirmado en la autoridad Git compartida reemplaza la hipótesis local.
- Un **scope** es `repo://...`, `api://...`, `k8s://...`, `test://...` o `service://...`; reservar el conjunto de efectos realmente compartidos, no solo los archivos obvios. `*` cubre subárboles. Sin evidencia de los ámbitos, no conceder escritura paralela.
- Sin un **único** Git remoto/rama compartida (o coordinador equivalente), no declarar exclusividad entre clones. El adaptador Git usa push de avance rápido sin `--force`, con los cambios de la tarea escritos mediante la CLI de Backlog. Es cooperación, no un mecanismo de autenticación: proteger la rama autoritativa y las rutas de publicación.

## Navegación mínima

1. `backlog instructions overview`, `backlog task list --json` sin paginar, y `task view --json` para candidatos y ámbitos activos. Si el Home Repo no está identificado, navegar a discovery; no inicializar automáticamente.
2. Con observaciones completas, `scripts/multi_agent_scheduler.py snapshot.json` propone lotes por prioridad de producto, desbloqueos inmediatos, profundidad y compatibilidad de skills/recursos. **No** inicia workers ni guarda estado.
3. Leer `_links` del planificador, comprobar recursos y utilizar `scripts/multi_agent_cli.py claim --remote ... --task ... --actor ... --claim-id ... --harness ... --lease-until ... --resource repo://...`. Sin `CONFIRMED`, no modificar recursos compartidos.
4. Volver a validar claim/generación antes de publicar, desplegar o cerrar; la integración debe imponer la misma regla en una frontera que el worker no pueda omitir. Un agente externo que no cumple el protocolo invalida la garantía.
5. Antes de publicar, el trabajador cooperativo invoca `multi_agent_cli.py verify --remote ... --task ... --actor ... --claim-id ... --generation ...`; si pierde la generación, detiene escrituras. Es una comprobación puntual; el destino de publicación necesita validar de nuevo para cerrar la ventana TOCTOU. Para columnas personalizadas indicar `--claimable-status` y `--working-status` al adquirir; `release/recover` restaura el estado original registrado en el claim, salvo cambios externos que exigen conciliación. `--resource` es obligatorio; `--event-id` estable permite reintentos idempotentes tras un push de resultado incierto.
6. En cada checkpoint, renovar lease **sin** falsear progreso; registrar progreso `PROGRESS` solo con evidencia; cesión con el flujo de [yield-negotiation](yield-negotiation.md); recuperación tras bloqueo con [stalled-work-recovery](stalled-work-recovery.md).

**Atención:** el adaptador Git v1 usa un clon efímero de la autoridad por operación, por lo que prioriza corrección sobre rendimiento y no reemplaza un backend de claims transaccionales de Backlog.md. Los timestamps locales no prueban parada; el remote de Git tampoco ofrece aislamiento para efectos externos. No publicar tokens, paths privados o credenciales en comentarios.

## HATEOAS: seguir solo enlaces relevantes

- `select-ready` → [dependency-management](dependency-management.md) y [technical-readiness](technical-readiness.md).
- `claim` → esta lente + `scripts/multi_agent_cli.py`.
- `yield` → [yield-negotiation](yield-negotiation.md).
- `recover` → [stalled-work-recovery](stalled-work-recovery.md).
- `delegate` → `delegated-task-loop` **solo si** figura en `available_skills`; el router ajeno sigue siendo dueño de su journal y relay.
- `supervise` → `supervised-task-loop` **solo si** está instalada y dispone de una señal/host observados.
- `observe-harness` → [bridge de eventos](../harness-interop.md), sin lectura de transcripciones ni liberación automática.
- `protect-publication` → [gate del destino](../harness-interop.md); `verify` es solo preflight.
- `verify` → [verification](verification.md) y `delivery-first-testing` si disponible.

**Nunca** confundir el claim de Git con un permiso del host ni suprimir gates de seguridad funcional del proyecto.

## Entrega recuperable e integración coordinada
El mismo protocolo de comentarios v1 añade DELIVER, ADOPT, COMPLETE. Actualizar todas las instancias cooperativas antes de usar estos eventos; versiones antiguas los rechazan. Al claim se fija el digest semántico del task-view completo cuando está disponible. DELIVER requiere candidato Git preservado (repository, baseCommit, candidateCommit, candidateRef, targetRef, scope, contractDigest), inventario clear y evidencia; pasa a AWAITING_INTEGRATION sin liberar el código ni marcar Done. ADOPT reserva ámbitos de integración con nueva generación; release/recover conserva el candidato. COMPLETE usa una observación independiente, el target remoto efectivo, ancestro candidato y AC/DoD completos para cambiar la columna y liquidar claim en el mismo CAS Home. Los comandos exigen --generation. Preparar --candidate-file y --assessment-file mediante observaciones existentes; no asumir que una proyección autentica al revisor. Ver [integration workflow](integration-workflow.md). Los candidatos no ocupan un slot de escritura; no borrar la última ref. La publicación sigue siendo responsabilidad autorizada de Git y su gate de destino.
