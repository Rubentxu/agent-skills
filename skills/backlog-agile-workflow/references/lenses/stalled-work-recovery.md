# Revisión de tareas estancadas y recuperación segura

**Intents:** `inspect-stalled`, `recover-task`. [Volver al navegador](../navigation.md) · [Cesión](yield-negotiation.md).

## No confundir tres señales

- **Liveness:** `HEARTBEAT` actualiza `leaseUntil` y `lastHeartbeatAt`; no demuestra entrega.
- **Progress:** `PROGRESS` y `CHECKPOINT_READY` llevan `evidenceRef` de un resultado material; commits o llamadas vacíos no son avance.
- **Ownership:** un `CLAIM` confirmado y no revocado indica escritor cooperativo. La expiración del lease es solo motivo de investigación.

## Triage por demanda

`multi_agent_cli.py triage --remote <home-repo-remoto> --ref main --at <UTC>` lee el backlog de una rama autoritativa. Categorías: `ACTIVE`, `STALLED` (sin avance útil), `SUSPECT` (lease expirado), `YIELD_REQUESTED`, `QUARANTINED`, `CANDIDATE` o las causas de indisponibilidad. No requiere daemon ni LLM para el cálculo. Un supervisor puede ejecutarlo a demanda o desde un job externo opcional; no prometer detección continua cuando nadie lo ejecuta.

1. Clasificar fallos concretos: `quota_exhausted`, `rate_limited` (+ `retryAfter` observado), `auth_expired`, `worker_unreachable`, `repeated_failure`, `external_operation_pending`, `awaiting_human`, `unknown_resources`.
2. Con respuesta del propietario: solicitar `YIELD_REQUESTED` y seguir la [negociación](yield-negotiation.md).
3. Sin respuesta y vencidos lease + gracia: `QUARANTINE` con razón y evidencia observada. Incrementa la generación y **conserva** reserva de recursos; no permite un segundo escritor. Si el propietario reaparece, su vieja generación queda invalidada en la frontera de publicación.
4. Observar handle nativo, operaciones con `operationKey`, Kubernetes UID, contenedor, jobs remotos, worktree y checkpoint. No inferir parada por PID genérico, silencio, mtime ni falta de crédito.
5. Solo con evidencia verificable de cese/adopción y recursos libres: `RECOVER --resources-clear --evidence-ref ...`; únicamente entonces la tarea vuelve a ser candidata. Si hay UNKNOWN, mantener QUARANTINED y permitir trabajo ajeno sin conflicto.
6. Antes de integraciones de código, comprobar `claimId`/generación actual mediante `multi_agent_cli.py verify`. La comprobación local no sustituye un gate autoritativo de servidor para recursos externos.
7. Tras sucesión, `Fresh Eyes` verifica AC/DoD, pruebas, base SHA y recursos; no repetir operaciones no idempotentes ni reiniciar presupuesto acumulado de tarea. Aplicar [flow-recovery](flow-recovery.md) ante dos hipótesis estériles.

**Límites recomendados:** intervalo 5–10 min de heartbeat, 30 min de lease, revisión 20–30 min sin progreso, relevo ordinario ≤60 min. Son parámetros, no SLA ni permisos de reclamación. La hora de la máquina es un indicio; con reloj sesgado, partición o remoto inaccesible, fallar de forma conservadora.

**HATEOAS:** `triage` → esta lente; `yield` → [yield-negotiation](yield-negotiation.md); `quarantine` → ver inventario con `delegated-task-loop` si está disponible; `recover` → [multi-agent-coordination](multi-agent-coordination.md); `verify` → [verification](verification.md).
