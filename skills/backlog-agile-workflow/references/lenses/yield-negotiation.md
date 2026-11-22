# Cesión cooperativa entre agentes y harnesses

**Intent:** `yield-task`. [Volver al navegador](../navigation.md) · [Coordinación](multi-agent-coordination.md).

**Protocolo:** `YIELD_REQUESTED` (supervisor) → `YIELD_ACK` o `YIELD_DEFERRED` (propietario vigente) → `CHECKPOINT_READY` (propietario, referencia recuperable) → **parada comprobada del escritor y conciliación de efectos** → `RELEASE` con inventario `resourcesClear` y evidencia. El sucesor adquiere un nuevo `CLAIM` con generación superior; no reutiliza el intento previo.

- Solicitar `YIELD_REQUESTED` por cuota agotada, autenticación, falta de progreso, conflicto de recursos, deadline o espera humana. La petición no autoriza quitar el claim. El receptor la lee al iniciar y en checkpoints naturales, sin comunicación entre harnesses.
- `YIELD_DEFERRED` es válido si el propietario tiene un proceso remoto vivo o una sección crítica; indicar evidencia y momento observable de re-evaluación. No renovar indefinidamente si no hay avance útil.
- Con cuota agotada y adaptador fuera del LLM, permitir que el harness emita la petición y publique último checkpoint recuperable aunque el modelo no pueda responder.
- No guardar secretos, transcripciones ni ficheros fuente en comentarios: solo referencias y digests de contenido privado con acceso autorizado. No publicar automáticamente ramas privadas en repos públicos.
- `RELEASE` exige verificar escritor parado, operaciones adoptadas o finalizadas, y ningún recurso incompatible desconocido. La evidencia declarada por el solicitante **no** es verificada por el script; la autoridad real es el host/proveedor.
- Si no responde el propietario, seguir [stalled-work-recovery](stalled-work-recovery.md), nunca marcar Done ni liberar solo por tiempo.

**Enlaces relacionales:** `inbox` → buscar comentarios de coordinación por ID; `checkpoint` → `delegated-task-loop/references/handoff-engineering.md` si disponible; `adopt-resources` → `delegated-task-loop/references/resource-adoption.md` si disponible; `release` → [multi-agent-coordination](multi-agent-coordination.md).
