# Claims compartidos antes de delegación fresca

La reserva local de `run_state.py` solo evita colisiones entre instancias cooperativas del mismo estado POSIX; **nunca** garantiza exclusión con otro host/harness. Cuando `backlog-agile-workflow` anuncia `multi-agent-coordination` en el catálogo de skills disponibles, consultar la lente y adquirir un claim global confirmado **antes de** iniciar un worker escritor. Transferir en el brief `taskId`, `claimId`, `generation`, recursos normalizados y `leaseUntil`, además de requisitos de autorización nativos.

Una llamada a `multi_agent_scheduler.py` es solo propuesta; nunca equivale a `claim`. El supervisor conserva su journal para handles, pacing y relay, pero no intenta adquirir el mismo scope otra vez sin verificar la propiedad de Backlog. El worker revalida antes de la publicación y no escribe tras recibir `RESUME_REJECTED` o perder generación. Las operaciones externas requieren sus controles reales de permisos/fencing y el protocolo de `resource-adoption.md`.

Cuando falla quota/autenticación, el host puede registrar petición de cesión aunque el LLM no pueda contestar. Handoff seguro: checkpoint → parada observada → conciliación de inventario → release confirmado → nuevo claim. Sin proveedor global disponible, ejecutar serial en un único dominio de autoridad, no afirmar multi-host seguro.

Navegar a [run-state](run-state.md), [resource-adoption](resource-adoption.md) y [endurance-relay](endurance-relay.md) solo cuando el host observe el caso. No duplicar esos contratos aquí.
